import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Avatar,
  Chip,
  Divider,
  CircularProgress,
  Stepper,
  Step,
  StepLabel,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Paper,
  Skeleton,
  Alert,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Send as SendIcon,
  SmartToy as SmartToyIcon,
  Person as PersonIcon,
  Schedule as ScheduleIcon,
  Healing as HealingIcon,
  AssignmentTurnedIn as AssignmentTurnedInIcon,
  Science as ScienceIcon,
} from '@mui/icons-material';
import { getCaseDetail, addComment, sendPlanInstruction, createDoctorCarePlan } from '../../api/doctor';
import type { CaseDetail } from '../../api/doctor';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
} from '@mui/material';
import { flexRowGap05Mb05, flexRowGap1, flexRowGap15, flexRowGap1Mb1 } from '../../styles/sxUtils';


interface PatientInfo {
  age: number;
  gender: string;
  allergies: string[];
  height?: string;
  weight?: string;
  bloodType?: string;
}

interface TimelineEvent {
  label: string;
  date: string;
  description?: string;
}

interface StructuredReport {
  primary_diagnosis: string;
  confidence: string;
  differential_diagnoses: Array<{ name: string; probability: string }>;
  suggested_exams: string[];
  key_findings: string[];
}

/** 演示数据 */
const MOCK_CASE: CaseDetail & {
  patient_info: PatientInfo;
  timeline: TimelineEvent[];
  structured_report: StructuredReport;
} = {
  id: 'case-001',
  patient_id: 'p-101',
  patient_name: '张伟',
  title: '持续性胸痛伴呼吸困难',
  description: '患者近3天出现持续性胸痛，活动后加重，伴呼吸困难、心悸。既往有高血压病史5年。',
  diagnosis: '冠心病 不稳定型心绞痛',
  agent_summary: 'AI分析提示急性冠脉综合征可能性较高，建议尽快完善心肌酶谱及冠脉CTA检查。',
  structured_report: {
    primary_diagnosis: '急性冠脉综合征（不稳定型心绞痛）',
    confidence: '82%',
    differential_diagnoses: [
      { name: '急性心肌梗死', probability: '65%' },
      { name: '主动脉夹层', probability: '15%' },
      { name: '肺栓塞', probability: '12%' },
      { name: '气胸', probability: '8%' },
    ],
    suggested_exams: [
      '心肌酶谱（肌钙蛋白I/T、CK-MB）',
      '12导联心电图',
      '胸部CTA或冠脉CTA',
      'D-二聚体',
      '血气分析',
    ],
    key_findings: [
      '胸痛呈压榨性，持续>20分钟',
      '活动后加重，休息后稍缓解',
      '伴出汗、恶心',
      '血压160/95mmHg，心率102次/分',
    ],
  },
  comments: [
    {
      id: 'c1',
      author: '李主任',
      content: '患者症状典型，建议立即收入CCU，完善相关检查，排除STEMI。',
      created_at: '2025-04-28T09:30:00Z',
    },
    {
      id: 'c2',
      author: '王医生',
      content: '同意李主任意见。已开立心肌酶谱和心电图，结果待回报。',
      created_at: '2025-04-28T10:15:00Z',
    },
    {
      id: 'c3',
      author: 'AI助手',
      content: '已生成初步诊疗计划，建议30分钟内复查心电图，监测肌钙蛋白动态变化。',
      created_at: '2025-04-28T10:20:00Z',
    },
  ],
  created_at: '2025-04-28T08:00:00Z',
  updated_at: '2025-04-28T10:20:00Z',
  patient_info: {
    age: 58,
    gender: '男',
    allergies: ['青霉素', '磺胺类药物'],
    height: '172cm',
    weight: '78kg',
    bloodType: 'A型',
  },
  timeline: [
    { label: '接诊', date: '2025-04-28 08:00', description: '急诊接诊，记录主诉' },
    { label: '初检', date: '2025-04-28 08:20', description: '生命体征采集，心电图检查' },
    { label: 'AI评估', date: '2025-04-28 08:45', description: 'Agent生成结构化摘要' },
    { label: '会诊', date: '2025-04-28 09:30', description: '心内科会诊，制定诊疗计划' },
    { label: '处置', date: '2025-04-28 10:15', description: '开立检查，药物治疗' },
  ],
};

const EXAMPLE_INSTRUCTIONS = ['安排复查', '调整用药', '生成趋势报告'];

function formatDate(iso: string) {
  const d = new Date(iso);
  return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [caseData, setCaseData] = useState<typeof MOCK_CASE | null>(null);
  const [error, setError] = useState('');
  const [comments, setComments] = useState<typeof MOCK_CASE.comments>([]);
  const [commentInput, setCommentInput] = useState('');
  const [sendingComment, setSendingComment] = useState(false);

  // Plan instruction
  const [instructionInput, setInstructionInput] = useState('');
  const [sendingInstruction, setSendingInstruction] = useState(false);
  const [instructionError, setInstructionError] = useState<string | null>(null);
  const [instructionResult, setInstructionResult] = useState<{
    tasks_created: Array<{ description: string; due_date?: string }>;
    message: string;
  } | null>(null);

  // Create care plan dialog
  const [planDialogOpen, setPlanDialogOpen] = useState(false);
  const [planTitle, setPlanTitle] = useState('');
  const [planGoals, setPlanGoals] = useState('');
  const [planTasks, setPlanTasks] = useState('');
  const [creatingPlan, setCreatingPlan] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const data = await getCaseDetail(caseId || '');
        if (!cancelled) {
          // Map backend timeline format to frontend format
          const mappedTimeline = (data.timeline || []).map((t: any) => ({
            label: t.type || t.intent || '事件',
            date: t.time ? new Date(t.time).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '',
            description: t.summary || t.intent || '',
          }));

          // Build structured report from backend data if available
          const structuredReport = data.structured_report || {
            primary_diagnosis: data.diagnosis || '待诊断',
            confidence: 'N/A',
            differential_diagnoses: [],
            suggested_exams: [],
            key_findings: [],
          };

          setCaseData({
            ...MOCK_CASE,
            ...data,
            timeline: mappedTimeline.length ? mappedTimeline : [],
            structured_report: structuredReport.primary_diagnosis ? structuredReport : { primary_diagnosis: data.diagnosis || '待诊断', confidence: 'N/A', differential_diagnoses: [], suggested_exams: [], key_findings: [] },
            patient_info: data.patient_info || { age: 0, gender: '暂无', allergies: [], height: '暂无', weight: '暂无', bloodType: '暂无' },
          });
          if (data.comments) setComments(data.comments);
        }
      } catch (err) {
        if (!cancelled) {
          setError('加载病例详情失败，请稍后重试');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [caseId]);

  const handleAddComment = async () => {
    if (!commentInput.trim() || !caseId) return;
    setSendingComment(true);
    try {
      await addComment(caseId, commentInput.trim());
      const newComment = {
        id: `c-${Date.now()}`,
        author: '当前医生',
        content: commentInput.trim(),
        created_at: new Date().toISOString(),
      };
      setComments((prev) => [...prev, newComment]);
      setCommentInput('');
    } catch {
      // 演示模式：直接添加到本地
      const newComment = {
        id: `c-${Date.now()}`,
        author: '当前医生',
        content: commentInput.trim(),
        created_at: new Date().toISOString(),
      };
      setComments((prev) => [...prev, newComment]);
      setCommentInput('');
    } finally {
      setSendingComment(false);
    }
  };

  const handleSendInstruction = async () => {
    if (!instructionInput.trim() || !caseId) return;
    setSendingInstruction(true);
    setInstructionResult(null);
    setInstructionError(null);
    try {
      const res = await sendPlanInstruction(caseId, instructionInput.trim());
      setInstructionResult(res);
      setInstructionInput('');
    } catch (err) {
      setInstructionError(err instanceof Error ? err.message : '指令处理失败，请重试');
    } finally {
      setSendingInstruction(false);
    }
  };

  const handleCreatePlan = async () => {
    if (!planTitle.trim() || !caseData?.patient_id) return;
    setCreatingPlan(true);
    try {
      const goals = planGoals.split('\n').filter(Boolean);
      const tasks = planTasks.split('\n').filter(Boolean).map(d => ({ description: d }));
      await createDoctorCarePlan(caseData.patient_id, {
        title: planTitle.trim(),
        goals: goals.length ? goals : undefined,
        tasks: tasks.length ? tasks : undefined,
      });
      setPlanDialogOpen(false);
      setPlanTitle('');
      setPlanGoals('');
      setPlanTasks('');
    } catch {
      // 静默处理，演示模式下保持体验
    }
    setCreatingPlan(false);
  };

  const activeStep = caseData ? caseData.timeline.length - 1 : 0;

  return (
    <Box sx={{ bgcolor: '#F5F7FA', minHeight: '100vh', pb: 4 }}>
      {/* 顶部导航 */}
      <Paper
        elevation={0}
        sx={{
          px: { xs: 2, md: 3 },
          py: 2,
          borderRadius: 0,
          borderBottom: '1px solid #E0E6ED',
          bgcolor: '#fff',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <Box sx={flexRowGap15}>
          <IconButton onClick={() => navigate('/doctor/cases')} sx={{ color: 'text.secondary' }}>
            <ArrowBackIcon />
          </IconButton>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" sx={{ color: 'text.primary', fontWeight: 600, lineHeight: 1.3 }}>
              {loading ? <Skeleton width={220} /> : caseData?.title}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.25 }}>
              <PersonIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                {loading ? <Skeleton width={120} /> : `患者：${caseData?.patient_name}`}
              </Typography>
              {!loading && caseData && (
                <Chip
                  label={caseData.diagnosis || '待诊断'}
                  size="small"
                  color="primary"
                  sx={{ height: 22, fontSize: '0.75rem', fontWeight: 500 }}
                />
              )}
            </Box>
          </Box>
        </Box>
      </Paper>

      <Box sx={{ maxWidth: 1280, mx: 'auto', px: { xs: 2, md: 3 }, pt: 3 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>
            {error}
          </Alert>
        )}

 <Grid container spacing={3}>
          {/* 左侧主区 */}
 <Grid size={{ xs: 12, md: 8 }}>
            {/* Agent 摘要卡片 */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <SmartToyIcon color="primary" />
                  <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>
                    Agent 结构化摘要
                  </Typography>
                </Box>

                {loading ? (
                  <Skeleton variant="rectangular" height={180} sx={{ borderRadius: 2 }} />
                ) : caseData?.structured_report ? (
 <Grid container spacing={2}>
 <Grid>
                      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'primary.light' }}>
                        <Typography variant="caption" sx={{ color: '#1976D2', fontWeight: 600 }}>
                          首选诊断
                        </Typography>
                        <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'text.primary', mt: 0.5 }}>
                          {caseData.structured_report.primary_diagnosis}
                        </Typography>
                        <Box sx={{ mt: 1 }}>
                          <Chip
                            label={`置信度 ${caseData.structured_report.confidence}`}
                            size="small"
                            sx={{ bgcolor: '#1976D2', color: '#fff', fontWeight: 500 }}
                          />
                        </Box>
                      </Paper>
                    </Grid>

 <Grid>
                      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: '#FFF3E0' }}>
                        <Typography variant="caption" sx={{ color: '#E65100', fontWeight: 600 }}>
                          鉴别诊断（可能性）
                        </Typography>
                        <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                          {caseData.structured_report.differential_diagnoses.map((d) => (
                            <Chip
                              key={d.name}
                              label={`${d.name} ${d.probability}`}
                              size="small"
                              variant="outlined"
                              sx={{ borderColor: '#FB8C00', color: '#E65100', fontWeight: 500 }}
                            />
                          ))}
                        </Box>
                      </Paper>
                    </Grid>

 <Grid>
                      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                        <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                          关键发现
                        </Typography>
                        <Box component="ul" sx={{ m: 0, pl: 2, mt: 0.5 }}>
                          {caseData.structured_report.key_findings.map((f, idx) => (
                            <Typography component="li" variant="body2" key={idx} sx={{ color: 'text.primary', py: 0.25 }}>
                              {f}
                            </Typography>
                          ))}
                        </Box>
                      </Paper>
                    </Grid>

 <Grid>
                      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: '#E8F5E9' }}>
                        <Box sx={flexRowGap05Mb05}>
                          <ScienceIcon sx={{ fontSize: 16, color: '#43A047' }} />
                          <Typography variant="caption" sx={{ color: '#2E7D32', fontWeight: 600 }}>
                            建议检查
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 0.5 }}>
                          {caseData.structured_report.suggested_exams.map((exam) => (
                            <Chip
                              key={exam}
                              label={exam}
                              size="small"
                              sx={{ bgcolor: '#C8E6C9', color: '#2E7D32', fontWeight: 500 }}
                            />
                          ))}
                        </Box>
                      </Paper>
                    </Grid>
                  </Grid>
                ) : null}
              </CardContent>
            </Card>

            {/* 病历时间线 */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary', mb: 2 }}>
                  病历时间线
                </Typography>
                {loading ? (
                  <Skeleton variant="rectangular" height={80} sx={{ borderRadius: 2 }} />
                ) : (
                  <Stepper activeStep={activeStep} orientation="vertical">
                    {caseData?.timeline.map((event, index) => (
                      <Step key={index}>
                        <StepLabel>
                          <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                            {event.label}
                            <Typography component="span" variant="caption" sx={{ color: 'text.secondary', ml: 1 }}>
                              {event.date}
                            </Typography>
                          </Typography>
                          {event.description && (
                            <Typography variant="caption" sx={{ color: 'text.secondary', mt: 0.5 }}>
                              {event.description}
                            </Typography>
                          )}
                        </StepLabel>
                      </Step>
                    ))}
                  </Stepper>
                )}
              </CardContent>
            </Card>

            {/* 医生评论区 */}
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary', mb: 2 }}>
                  医生评论
                </Typography>

                <List sx={{ py: 0 }}>
                  {comments.map((c) => (
                    <ListItem
                      key={c.id}
                      alignItems="flex-start"
                      sx={{ px: 0, py: 1.5, borderBottom: '1px solid #F0F3F7' }}
                    >
                      <ListItemAvatar>
                        <Avatar
                          sx={{
                            bgcolor: c.author === 'AI助手' ? 'primary.light' : '#EDE7F6',
                            color: c.author === 'AI助手' ? '#1976D2' : '#5E35B1',
                            width: 36,
                            height: 36,
                            fontSize: '0.875rem',
                          }}
                        >
                          {c.author === 'AI助手' ? <SmartToyIcon sx={{ fontSize: 18 }} /> : c.author[0]}
                        </Avatar>
                      </ListItemAvatar>
                      <ListItemText
                        primary={
                          <Box sx={flexRowGap1}>
                            <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                              {c.author}
                            </Typography>
                            <Typography variant="caption" sx={{ color: 'secondary.light' }}>
                              {formatDate(c.created_at)}
                            </Typography>
                          </Box>
                        }
                        secondary={
                          <Typography variant="body2" sx={{ color: '#455A64', mt: 0.25, whiteSpace: 'pre-wrap' }}>
                            {c.content}
                          </Typography>
                        }
                      />
                    </ListItem>
                  ))}
                </List>

                <Box sx={{ display: 'flex', gap: 1.5, mt: 2 }}>
                  <TextField
                    fullWidth
                    size="small"
                    placeholder="输入评论..."
                    value={commentInput}
                    onChange={(e) => setCommentInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleAddComment();
                      }
                    }}
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        bgcolor: '#F5F7FA',
                      },
                    }}
                  />
                  <Button
                    variant="contained"
                    disabled={!commentInput.trim() || sendingComment}
                    onClick={handleAddComment}
                    endIcon={sendingComment ? <CircularProgress size={16} color="inherit" /> : <SendIcon />}
                    sx={{ minWidth: 100, whiteSpace: 'nowrap' }}
                  >
                    发送
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* 右侧边栏 */}
 <Grid>
            {/* 患者基本信息 */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary', mb: 2 }}>
                  患者信息
                </Typography>
                {loading ? (
                  <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 2 }} />
                ) : (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    <Box sx={flexRowGap15}>
                      <Avatar sx={{ bgcolor: 'primary.main', width: 48, height: 48 }}>
                        {caseData?.patient_name?.[0]}
                      </Avatar>
                      <Box>
                        <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'text.primary' }}>
                          {caseData?.patient_name}
                        </Typography>
                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                          ID: {caseData?.patient_id}
                        </Typography>
                      </Box>
                    </Box>

                    <Divider sx={{ my: 0.5 }} />

                    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
                      <Box>
                        <Typography variant="caption" sx={{ color: 'secondary.light' }}>
                          年龄
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.primary' }}>
                          {caseData?.patient_info.age || '--'} 岁
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" sx={{ color: 'secondary.light' }}>
                          性别
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.primary' }}>
                          {caseData?.patient_info.gender}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" sx={{ color: 'secondary.light' }}>
                          身高
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.primary' }}>
                          {caseData?.patient_info.height}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" sx={{ color: 'secondary.light' }}>
                          体重
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.primary' }}>
                          {caseData?.patient_info.weight}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" sx={{ color: 'secondary.light' }}>
                          血型
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.primary' }}>
                          {caseData?.patient_info.bloodType}
                        </Typography>
                      </Box>
                    </Box>

                    <Divider sx={{ my: 0.5 }} />

                    <Box>
                      <Typography variant="caption" sx={{ color: 'secondary.light', display: 'block', mb: 0.5 }}>
                        过敏史
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                        {caseData?.patient_info.allergies.map((a) => (
                          <Chip
                            key={a}
                            label={a}
                            size="small"
                            color="error"
                            variant="outlined"
                            sx={{ fontWeight: 500 }}
                          />
                        ))}
                      </Box>
                    </Box>
                  </Box>
                )}
              </CardContent>
            </Card>

            {/* 自然语言指令入口 */}
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <HealingIcon color="primary" />
                  <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>
                    自然语言指令
                  </Typography>
                </Box>

                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5 }}>
                  用自然语言告诉 Agent 您的诊疗安排，例如：
                </Typography>

                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 2 }}>
                  {EXAMPLE_INSTRUCTIONS.map((text) => (
                    <Button
                      key={text}
                      size="small"
                      variant="outlined"
                      onClick={() => setInstructionInput(text)}
                      sx={{
                        borderColor: 'secondary.light',
                        color: 'text.secondary',
                        textTransform: 'none',
                        fontWeight: 500,
                        borderRadius: 2,
                        '&:hover': { borderColor: 'primary.main', color: 'primary.main', bgcolor: 'primary.light' },
                      }}
                    >
                      {text}
                    </Button>
                  ))}
                </Box>

                <TextField
                  fullWidth
                  multiline
                  minRows={2}
                  maxRows={4}
                  placeholder="输入指令，例如：安排一周后复查血常规..."
                  value={instructionInput}
                  onChange={(e) => setInstructionInput(e.target.value)}
                  sx={{
                    '& .MuiOutlinedInput-root': {
                      bgcolor: '#F5F7FA',
                    },
                  }}
                  slotProps={{
                    input: {
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton
                            color="primary"
                            disabled={!instructionInput.trim() || sendingInstruction}
                            onClick={handleSendInstruction}
                            edge="end"
                          >
                            {sendingInstruction ? <CircularProgress size={20} color="inherit" /> : <SendIcon />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    },
                  }}
                />

                {sendingInstruction && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2, color: 'text.secondary' }}>
                    <CircularProgress size={16} />
                    <Typography variant="body2">Agent 正在处理指令...</Typography>
                  </Box>
                )}

                {instructionError && !sendingInstruction && (
                  <Alert severity="error" sx={{ mt: 2 }}>
                    {instructionError}
                  </Alert>
                )}

                {instructionResult && !sendingInstruction && (
                  <Box sx={{ mt: 2 }}>
                    <Paper
                      variant="outlined"
                      sx={{ p: 2, borderRadius: 2, bgcolor: 'primary.light', borderColor: '#90CAF9' }}
                    >
                      <Box sx={flexRowGap1Mb1}>
                        <AssignmentTurnedInIcon color="primary" sx={{ fontSize: 20 }} />
                        <Typography variant="body2" sx={{ fontWeight: 600, color: '#1976D2' }}>
                          Agent 已生成任务
                        </Typography>
                      </Box>
                      <Typography variant="body2" sx={{ color: 'text.primary', mb: 1 }}>
                        {instructionResult.message}
                      </Typography>
                      <Box component="ul" sx={{ m: 0, pl: 2 }}>
                        {instructionResult.tasks_created.map((task, idx) => (
                          <Box component="li" key={idx} sx={{ mb: 0.5 }}>
                            <Typography variant="body2" sx={{ color: 'text.primary' }}>
                              {task.description}
                              {task.due_date && (
                                <Typography component="span" variant="caption" sx={{ color: 'text.secondary', ml: 0.5 }}>
                                  <ScheduleIcon sx={{ fontSize: 12, verticalAlign: 'middle', mr: 0.25 }} />
                                  {task.due_date}
                                </Typography>
                              )}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    </Paper>
                  </Box>
                )}
              </CardContent>
            </Card>

            {/* 创建随访计划 */}
            <Card sx={{ borderRadius: 3, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <CardContent>
                <Box sx={flexRowGap1Mb1}>
                  <HealingIcon color="primary" />
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>创建随访计划</Typography>
                </Box>
                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
                  为该患者制定随访计划，计划将以 active 状态创建，患者可在手机端查看。
                </Typography>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={() => setPlanDialogOpen(true)}
                  startIcon={<AssignmentTurnedInIcon />}
                >
                  新建随访计划
                </Button>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>

      {/* 创建随访计划对话框 */}
      <Dialog open={planDialogOpen} onClose={() => setPlanDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>创建随访计划</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            label="计划标题"
            fullWidth
            sx={{ mt: 1, mb: 2 }}
            value={planTitle}
            onChange={(e) => setPlanTitle(e.target.value)}
            placeholder="例如：高血压术后随访计划"
          />
          <TextField
            label="目标（每行一个）"
            fullWidth
            multiline
            rows={3}
            sx={{ mb: 2 }}
            value={planGoals}
            onChange={(e) => setPlanGoals(e.target.value)}
            placeholder="血压控制在 140/90 以下&#10;每周运动 3 次"
          />
          <TextField
            label="任务（每行一个）"
            fullWidth
            multiline
            rows={3}
            value={planTasks}
            onChange={(e) => setPlanTasks(e.target.value)}
            placeholder="每日测量血压&#10;低盐饮食&#10;每月复诊"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPlanDialogOpen(false)} color="inherit">取消</Button>
          <Button
            variant="contained"
            onClick={handleCreatePlan}
            disabled={!planTitle.trim() || creatingPlan}
          >
            {creatingPlan ? '创建中...' : '创建'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}