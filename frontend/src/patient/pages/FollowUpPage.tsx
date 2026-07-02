import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Box,
  Typography,
  Card,
  CardContent,
  Tabs,
  Tab,
  Checkbox,
  Chip,
  IconButton,
  Divider,
  Stack,
  LinearProgress,
  Alert,
} from '@mui/material';
import ArrowBackIosNewIcon from '@mui/icons-material/ArrowBackIosNew';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import FlagIcon from '@mui/icons-material/Flag';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import { listCarePlans, ackTask } from '../../api/patient';
import type { CarePlan } from '../../api/patient';
import { flexRowGap05Mb05, pageHeader } from '../../styles/sxUtils';


const warmText = '#1E293B';
const warmPrimary = '#14B8A6';
const warmBg = '#F0FDFA';

/* ---------- 演示数据 ---------- */
const fallbackPlans: CarePlan[] = [
  {
    id: 'plan-001',
    title: '高血压随访计划（第1季度）',
    status: 'active',
    goals: ['血压控制在140/90 mmHg以下', '体重减少2kg', '每日步数达到8000步'],
    start_date: '2026-01-01',
    end_date: '2026-03-31',
    tasks: [
      { id: 't1', description: '每周测量血压并记录', due_date: '2026-03-31', status: 'completed' },
      { id: 't2', description: '每月复诊一次', due_date: '2026-01-31', status: 'completed' },
      { id: 't3', description: '调整低盐饮食方案', due_date: '2026-02-15', status: 'pending' },
      { id: 't4', description: '完成季度血液检查', due_date: '2026-03-20', status: 'pending' },
    ],
  },
  {
    id: 'plan-002',
    title: '2型糖尿病管理计划',
    status: 'active',
    goals: ['空腹血糖维持在7.0 mmol/L以下', '糖化血红蛋白<7%'],
    start_date: '2026-02-01',
    end_date: '2026-05-01',
    tasks: [
      { id: 't5', description: '每日空腹测血糖', due_date: '2026-05-01', status: 'pending' },
      { id: 't6', description: '按时服用二甲双胍', due_date: '2026-02-10', status: 'pending' },
      { id: 't7', description: '每两周复查血糖曲线', due_date: '2026-02-28', status: 'pending' },
    ],
  },
  {
    id: 'plan-003',
    title: '术后康复随访（阑尾切除）',
    status: 'completed',
    goals: ['伤口愈合良好', '恢复正常饮食', '术后1个月复查B超'],
    start_date: '2025-10-01',
    end_date: '2025-11-15',
    tasks: [
      { id: 't8', description: '术后3天换药', due_date: '2025-10-04', status: 'completed' },
      { id: 't9', description: '术后1周拆线', due_date: '2025-10-08', status: 'completed' },
      { id: 't10', description: '术后1月复查B超', due_date: '2025-11-01', status: 'completed' },
    ],
  },
];

/* ---------- 工具函数 ---------- */
function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function isExpired(plan: CarePlan): boolean {
  if (plan.status === 'cancelled') return true;
  if (!plan.end_date) return false;
  return plan.end_date < todayStr();
}

function isAllCompleted(plan: CarePlan): boolean {
  if (plan.status === 'completed') return true;
  return plan.tasks.length > 0 && plan.tasks.every((t) => t.status === 'completed');
}

function getPlanStatus(plan: CarePlan): '进行中' | '已完成' | '已过期' {
  if (plan.status === 'completed' || isAllCompleted(plan)) return '已完成';
  if (isExpired(plan)) return '已过期';
  return '进行中';
}

function completionRate(plan: CarePlan): number {
  if (!plan.tasks.length) return 0;
  return Math.round((plan.tasks.filter((t) => t.status === 'completed').length / plan.tasks.length) * 100);
}

/* ---------- 组件 ---------- */
export default function FollowUpPage() {
  const navigate = useNavigate();
  const [plans, setPlans] = useState<CarePlan[]>(fallbackPlans);
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showFallbackBanner, setShowFallbackBanner] = useState(false);

  useEffect(() => {
    let mounted = true;
    listCarePlans()
      .then((data) => {
        if (mounted) {
          if (!data.length) {
            setShowFallbackBanner(true);
          }
          setPlans(data.length ? data : fallbackPlans);
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) {
          setPlans(fallbackPlans);
          setShowFallbackBanner(true);
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const processingTasks = useRef(new Set<string>());

  const handleToggleTask = async (planId: string, taskId: string) => {
    const key = `${planId}:${taskId}`;
    if (processingTasks.current.has(key)) return;
    processingTasks.current.add(key);

    setPlans((prev) =>
      prev.map((plan) => {
        if (plan.id !== planId) return plan;
        const updatedTasks = plan.tasks.map((t) =>
          t.id === taskId && t.status !== 'completed' ? { ...t, status: 'completed' as const } : t
        );
        return { ...plan, tasks: updatedTasks };
      })
    );

    try {
      await ackTask(planId, taskId);
    } catch (err) {
      console.error('完成任务失败:', err);
      // 如果 API 失败，已在本地切换状态，保持演示体验
    } finally {
      processingTasks.current.delete(key);
    }
  };

  const { active, pending, history } = useMemo(() => {
    const t = todayStr();
    const activeList: CarePlan[] = [];
    const pendingList: CarePlan[] = [];
    const historyList: CarePlan[] = [];

    plans.forEach((plan) => {
      const expired = isExpired(plan);
      const allDone = isAllCompleted(plan);
      const inRange = plan.start_date <= t && (!plan.end_date || plan.end_date >= t);

      if (allDone || expired) {
        historyList.push(plan);
      } else if (inRange && plan.tasks.some((t) => t.status === 'completed')) {
        activeList.push(plan);
      } else {
        pendingList.push(plan);
      }
    });

    return { active: activeList, pending: pendingList, history: historyList };
  }, [plans]);

  const tabs = [
    { label: `进行中 (${active.length})`, list: active },
    { label: `待完成 (${pending.length})`, list: pending },
    { label: `历史记录 (${history.length})`, list: history },
  ];

  const statusColor: Record<string, string> = {
    进行中: '#14B8A6',
    已完成: '#66BB6A',
    已过期: '#B0B0B0',
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: warmBg, pb: 6 }}>
      <Container maxWidth="md">
        {/* Header */}
        <Box sx={pageHeader}>
          <IconButton onClick={() => navigate('/chat')} sx={{ color: warmText }}>
            <ArrowBackIosNewIcon />
          </IconButton>
          <Typography variant="h5" sx={{ fontWeight: 700, color: warmText, flex: 1 }}>
            随访计划
          </Typography>
        </Box>

        {showFallbackBanner && (
          <Alert severity="warning" sx={{ mb: 2, borderRadius: 2 }}>
            数据加载失败，当前显示的是演示数据，不代表真实情况
          </Alert>
        )}

        {/* Tabs */}
        <Box sx={{ mb: 2 }}>
          <Tabs
            value={tab}
            onChange={(_, v) => setTab(v)}
            textColor="inherit"
            indicatorColor="primary"
            sx={{
              '& .MuiTabs-flexContainer': { gap: 1 },
              '& .MuiTab-root': {
                textTransform: 'none',
                borderRadius: 2,
                minHeight: 36,
                color: '#64748B',
                bgcolor: 'transparent',
                fontWeight: 500,
              },
              '& .Mui-selected': {
                color: '#fff !important',
                bgcolor: warmPrimary,
                fontWeight: 700,
              },
            }}
          >
            {tabs.map((t, idx) => (
              <Tab key={idx} label={t.label} />
            ))}
          </Tabs>
        </Box>

        {loading && (
          <Typography sx={{ color: warmText, textAlign: 'center', py: 4 }}>加载中…</Typography>
        )}

        {/* Plan Cards */}
        <Stack spacing={2}>
          {tabs[tab].list.length === 0 && !loading && (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <AssignmentTurnedInIcon sx={{ fontSize: 48, color: '#D7CCC8', mb: 1 }} />
              <Typography sx={{ color: '#64748B' }}>
                该分类下暂无随访计划
              </Typography>
            </Box>
          )}

          {tabs[tab].list.map((plan) => {
            const status = getPlanStatus(plan);
            const rate = completionRate(plan);
            return (
              <Card key={plan.id} sx={{ borderRadius: 3, boxShadow: '0 2px 8px rgba(15,23,42,0.06)' }}>
                <CardContent>
                  {/* Title + Badge */}
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1.5 }}>
                    <Typography variant="h6" sx={{ fontWeight: 700, color: warmText, lineHeight: 1.3 }}>
                      {plan.title}
                    </Typography>
                    <Chip
                      label={status}
                      size="small"
                      sx={{
                        bgcolor: `${statusColor[status]}14`,
                        color: statusColor[status],
                        fontWeight: 700,
                        borderRadius: 1.5,
                        ml: 1,
                        flexShrink: 0,
                      }}
                    />
                  </Box>

                  {/* Date range */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 2 }}>
                    <CalendarTodayIcon sx={{ fontSize: 16, color: '#64748B' }} />
                    <Typography variant="body2" sx={{ color: '#64748B' }}>
                      {plan.start_date}
                      {plan.end_date ? `  至  ${plan.end_date}` : ' 起'}
                    </Typography>
                  </Box>

                  {/* Progress bar */}
                  <Box sx={{ mb: 2 }}>
                    <LinearProgress
                      variant="determinate"
                      value={rate}
                      sx={{
                        height: 6,
                        borderRadius: 3,
                        bgcolor: 'rgba(20,184,166,0.15)',
                        '& .MuiLinearProgress-bar': {
                          bgcolor: status === '已过期' ? '#B0B0B0' : warmPrimary,
                          borderRadius: 3,
                        },
                      }}
                    />
                    <Typography variant="caption" sx={{ color: '#64748B', mt: 0.5, display: 'block' }}>
                      完成进度 {rate}%
                    </Typography>
                  </Box>

                  {/* Goals */}
                  <Box sx={{ mb: 2 }}>
                    <Box sx={flexRowGap05Mb05}>
                      <FlagIcon sx={{ fontSize: 16, color: warmPrimary }} />
                      <Typography variant="subtitle2" sx={{ color: warmText, fontWeight: 600 }}>
                        目标
                      </Typography>
                    </Box>
                    <Stack component="ul" spacing={0.5} sx={{ pl: 2, m: 0, color: warmText }}>
                      {plan.goals.map((g, i) => (
                        <Typography component="li" variant="body2" key={i}>
                          {g}
                        </Typography>
                      ))}
                    </Stack>
                  </Box>

                  <Divider sx={{ my: 1.5, borderColor: 'rgba(15,23,42,0.08)' }} />

                  {/* Tasks */}
                  <Box>
                    <Typography variant="subtitle2" sx={{ color: warmText, fontWeight: 600, mb: 1 }}>
                      任务清单
                    </Typography>
                    <Stack spacing={1}>
                      {plan.tasks.map((task) => (
                        <Box
                          key={task.id}
                          onClick={() => {
                            if (task.status !== 'completed') {
                              handleToggleTask(plan.id, task.id);
                            }
                          }}
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1,
                            p: 1,
                            borderRadius: 2,
                            bgcolor: task.status === 'completed' ? 'rgba(102,187,106,0.06)' : 'rgba(20,184,166,0.04)',
                            transition: 'background 0.2s',
                            cursor: task.status !== 'completed' ? 'pointer' : 'default',
                            '&:hover': task.status !== 'completed' ? { bgcolor: 'rgba(20,184,166,0.08)' } : {},
                          }}
                        >
                          <Checkbox
                            checked={task.status === 'completed'}
                            onChange={(e) => {
                              e.stopPropagation();
                              handleToggleTask(plan.id, task.id);
                            }}
                            sx={{
                              color: warmPrimary,
                              '&.Mui-checked': { color: '#66BB6A' },
                              p: 0.5,
                            }}
                            disabled={task.status === 'completed'}
                          />
                          <Box sx={{ flex: 1 }}>
                            <Typography
                              variant="body2"
                              sx={{
                                color: task.status === 'completed' ? '#B0B0B0' : warmText,
                                textDecoration: task.status === 'completed' ? 'line-through' : 'none',
                                fontWeight: task.status === 'completed' ? 400 : 500,
                              }}
                            >
                              {task.description}
                            </Typography>
                            {task.due_date && (
                              <Typography variant="caption" sx={{ color: '#64748B' }}>
                                截止: {task.due_date}
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      ))}
                    </Stack>
                  </Box>
                </CardContent>
              </Card>
            );
          })}
        </Stack>
      </Container>
    </Box>
  );
}