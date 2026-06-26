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
  Chip,
  Divider,
  CircularProgress,
  IconButton,
  LinearProgress,
  Autocomplete,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Alert,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton as IconBtn,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import { fetchPendingConsultations, finalizeConsultation } from '../../api/doctor-enhance';
import type {
  PendingConsultationItem,
  MedicationItem,
  VitalSigns,
} from '../../types/doctor';
import { flexRowGap1, flexRowGap2, flexRowBetween } from '../../styles/sxUtils';

// Common ICD-11 codes for reference
const ICD11_OPTIONS = [
  { code: 'CA40.0', label: '社区获得性肺炎' },
  { code: 'CA40.1', label: '医院获得性肺炎' },
  { code: 'CA20.0', label: '急性支气管炎' },
  { code: 'CA23.0', label: '慢性阻塞性肺疾病急性加重' },
  { code: '1B91.0', label: '2型糖尿病' },
  { code: 'BA00.0', label: '原发性高血压' },
  { code: '8A60.0', label: '焦虑障碍' },
  { code: 'AA11.0', label: '缺铁性贫血' },
  { code: 'DA00.0', label: '急性咽炎' },
  { code: '1A00.0', label: '轮状病毒性肠炎' },
];

interface FormState {
  finalDiagnosis: string;
  icd11Code: string;
  doctorNotes: string;
  physicalExam: VitalSigns;
  medications: MedicationItem[];
  advice: string;
  rejectedSuggestions: string[];
}

const EMPTY_VITALS: VitalSigns = {
  temperature: undefined,
  heart_rate: undefined,
  respiratory_rate: undefined,
  blood_pressure_systolic: undefined,
  blood_pressure_diastolic: undefined,
  oxygen_saturation: undefined,
  weight: undefined,
  height: undefined,
};

const INITIAL_FORM: FormState = {
  finalDiagnosis: '',
  icd11Code: '',
  doctorNotes: '',
  physicalExam: { ...EMPTY_VITALS },
  medications: [{ name: '', dosage: '', frequency: '', days: 7, route: '口服' }],
  advice: '',
  rejectedSuggestions: [],
};

function getConfidenceColor(score: number): string {
  if (score >= 0.7) return 'success.main';
  if (score >= 0.4) return 'warning.main';
  return 'error.main';
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN');
  } catch {
    return iso;
  }
}

export default function ConsultationPage() {
  const { consultationId } = useParams<{ consultationId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [consultation, setConsultation] = useState<PendingConsultationItem | null>(null);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [allConsultations, setAllConsultations] = useState<PendingConsultationItem[]>([]);

  useEffect(() => {
    loadData();
  }, [consultationId]);

  async function loadData() {
    setLoading(true);
    setError('');
    try {
      const data = await fetchPendingConsultations();
      setAllConsultations(data.consultations);

      if (consultationId) {
        const found = data.consultations.find(c => c.consultation_id === consultationId);
        if (found) {
          setConsultation(found);
          // Pre-fill form from pre-diagnosis
          const topDisease = found.pre_diagnosis?.possible_diseases?.[0];
          setForm(prev => ({
            ...prev,
            finalDiagnosis: topDisease?.disease || '',
          }));
        } else {
          setError('未找到该咨询记录');
        }
      }
    } catch (e: any) {
      setError(e.message || '加载数据失败');
    } finally {
      setLoading(false);
    }
  }

  function handleVitalChange(field: keyof VitalSigns, value: string) {
    const num = value === '' ? undefined : parseFloat(value);
    setForm(prev => ({
      ...prev,
      physicalExam: { ...prev.physicalExam, [field]: isNaN(num ?? NaN) ? undefined : num },
    }));
  }

  function handleMedicationChange(index: number, field: keyof MedicationItem, value: any) {
    setForm(prev => {
      const meds = [...prev.medications];
      meds[index] = { ...meds[index], [field]: value };
      return { ...prev, medications: meds };
    });
  }

  function addMedication() {
    setForm(prev => ({
      ...prev,
      medications: [...prev.medications, { name: '', dosage: '', frequency: '', days: 7, route: '口服' }],
    }));
  }

  function removeMedication(index: number) {
    setForm(prev => ({
      ...prev,
      medications: prev.medications.filter((_, i) => i !== index),
    }));
  }

  function toggleRejectedSuggestion(suggestion: string) {
    setForm(prev => {
      const exists = prev.rejectedSuggestions.includes(suggestion);
      return {
        ...prev,
        rejectedSuggestions: exists
          ? prev.rejectedSuggestions.filter(s => s !== suggestion)
          : [...prev.rejectedSuggestions, suggestion],
      };
    });
  }

  async function handleSubmit() {
    if (!consultation) return;
    if (!form.finalDiagnosis.trim()) {
      setError('请填写最终诊断');
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      const result = await finalizeConsultation({
        consultation_id: consultation.consultation_id,
        final_diagnosis: form.finalDiagnosis,
        icd11_code: form.icd11Code || undefined,
        treatment_plan: {
          medications: form.medications.filter(m => m.name.trim()),
          advice: form.advice.split('\n').filter(a => a.trim()),
        },
        doctor_notes: form.doctorNotes || undefined,
        physical_exam: Object.values(form.physicalExam).some(v => v !== undefined)
          ? form.physicalExam
          : undefined,
        rejected_suggestions: form.rejectedSuggestions.length > 0
          ? form.rejectedSuggestions
          : undefined,
      });

      setSuccess(`诊断已记录（ID: ${result.consultation_id}）`);
      setTimeout(() => navigate('/doctor/cases'), 2000);
    } catch (e: any) {
      setError(e.message || '提交失败');
    } finally {
      setSubmitting(false);
      setConfirmOpen(false);
    }
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!consultation) {
    return (
      <Box sx={{ p: 3 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/doctor/cases')}>
          返回
        </Button>
        <Alert severity="info" sx={{ mt: 2 }}>
          暂无待处理的诊断决策。选择左侧待办列表中的病例进行审核。
        </Alert>
        {/* Show pending list if no specific consultation selected */}
        {allConsultations.length > 0 && (
          <Box sx={{ mt: 3 }}>
            <Typography variant="h6" gutterBottom>待处理诊断</Typography>
            {allConsultations.map(c => (
              <Card key={c.consultation_id} sx={{ mb: 1, cursor: 'pointer' }}
                onClick={() => navigate(`/doctor/consultation/${c.consultation_id}`)}>
                <CardContent>
                  <Typography variant="subtitle1">{c.patient_name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {c.chief_complaint}
                  </Typography>
                </CardContent>
              </Card>
            ))}
          </Box>
        )}
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ ...flexRowBetween, mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton onClick={() => navigate('/doctor/cases')}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h5">诊断决策</Typography>
        </Box>
        <Chip
          label={`咨询 #${consultation.consultation_id.slice(0, 8)}`}
          size="small"
          color="primary"
          variant="outlined"
        />
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Grid container spacing={3}>
        {/* LEFT PANEL: Patient Info & Pre-diagnosis */}
        <Grid size={{ xs: 12, md: 5 }}>
          {/* Patient Info Card */}
          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>患者信息</Typography>
              <Divider sx={{ mb: 1.5 }} />
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Typography><strong>姓名：</strong>{consultation.patient_name}</Typography>
                <Typography><strong>主诉：</strong>{consultation.chief_complaint}</Typography>
                <Typography><strong>创建时间：</strong>{formatDate(consultation.created_at)}</Typography>
                {consultation.allergies?.length > 0 && (
                  <Box>
                    <Typography><strong>过敏史：</strong></Typography>
                    <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
                      {consultation.allergies.map((a, i) => (
                        <Chip key={i} label={a} size="small" color="error" variant="outlined" />
                      ))}
                    </Box>
                  </Box>
                )}
              </Box>
            </CardContent>
          </Card>

          {/* Vital Signs Card */}
          {consultation.vitals && Object.values(consultation.vitals).some(v => v != null) && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>生命体征</Typography>
                <Divider sx={{ mb: 1.5 }} />
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>指标</TableCell>
                        <TableCell>数值</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {consultation.vitals.temperature != null && (
                        <TableRow><TableCell>体温</TableCell><TableCell>{consultation.vitals.temperature}°C</TableCell></TableRow>
                      )}
                      {consultation.vitals.heart_rate != null && (
                        <TableRow><TableCell>心率</TableCell><TableCell>{consultation.vitals.heart_rate} bpm</TableCell></TableRow>
                      )}
                      {consultation.vitals.respiratory_rate != null && (
                        <TableRow><TableCell>呼吸</TableCell><TableCell>{consultation.vitals.respiratory_rate} /min</TableCell></TableRow>
                      )}
                      {consultation.vitals.blood_pressure_systolic != null && (
                        <TableRow><TableCell>血压</TableCell><TableCell>{consultation.vitals.blood_pressure_systolic}/{consultation.vitals.blood_pressure_diastolic} mmHg</TableCell></TableRow>
                      )}
                      {consultation.vitals.oxygen_saturation != null && (
                        <TableRow><TableCell>血氧</TableCell><TableCell>{consultation.vitals.oxygen_saturation}%</TableCell></TableRow>
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          )}

          {/* Pre-diagnosis Card */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>AI 预诊断</Typography>
              <Divider sx={{ mb: 1.5 }} />

              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                可能疾病（置信度）
              </Typography>
              {consultation.pre_diagnosis?.possible_diseases?.map((d, i) => (
                <Box key={i} sx={{ mb: 1.5 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">{d.disease}</Typography>
                    <Typography variant="body2" sx={{ color: getConfidenceColor(d.confidence), fontWeight: 600 }}>
                      {(d.confidence * 100).toFixed(0)}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={d.confidence * 100}
                    sx={{
                      height: 8,
                      borderRadius: 4,
                      bgcolor: 'grey.200',
                      '& .MuiLinearProgress-bar': {
                        bgcolor: getConfidenceColor(d.confidence),
                      },
                    }}
                  />
                </Box>
              ))}

              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  建议检查
                </Typography>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  {consultation.pre_diagnosis?.suggested_tests?.map((test, i) => (
                    <Chip key={i} label={test} size="small" icon={<CheckCircleIcon />} />
                  ))}
                </Box>
              </Box>

              <Box sx={{ mt: 2 }}>
                <Chip
                  label={`优先级: ${consultation.pre_diagnosis?.urgency || 'medium'}`}
                  size="small"
                  color={consultation.pre_diagnosis?.urgency === 'high' || consultation.pre_diagnosis?.urgency === 'emergency' ? 'error' : 'default'}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* RIGHT PANEL: Doctor Input Form */}
        <Grid size={{ xs: 12, md: 7 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>医生决策</Typography>
              <Divider sx={{ mb: 2 }} />

              {/* Physical Exam */}
              <Typography variant="subtitle1" gutterBottom sx={{ mt: 1 }}>
                体格检查
              </Typography>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                {[
                  { label: '体温 (°C)', field: 'temperature' as const },
                  { label: '心率 (bpm)', field: 'heart_rate' as const },
                  { label: '呼吸 (/min)', field: 'respiratory_rate' as const },
                  { label: '收缩压 (mmHg)', field: 'blood_pressure_systolic' as const },
                  { label: '舒张压 (mmHg)', field: 'blood_pressure_diastolic' as const },
                  { label: '血氧 (%)', field: 'oxygen_saturation' as const },
                  { label: '体重 (kg)', field: 'weight' as const },
                  { label: '身高 (cm)', field: 'height' as const },
                ].map(item => (
                  <Grid size={{ xs: 6, sm: 3 }} key={item.field}>
                    <TextField
                      fullWidth
                      size="small"
                      label={item.label}
                      type="number"
                      value={form.physicalExam[item.field] ?? ''}
                      onChange={e => handleVitalChange(item.field, e.target.value)}
                    />
                  </Grid>
                ))}
              </Grid>

              <Divider sx={{ my: 2 }} />

              {/* Final Diagnosis */}
              <Typography variant="subtitle1" gutterBottom>
                最终诊断 <span style={{ color: 'red' }}>*</span>
              </Typography>
              <TextField
                fullWidth
                size="small"
                placeholder="输入最终诊断名称"
                value={form.finalDiagnosis}
                onChange={e => setForm(prev => ({ ...prev, finalDiagnosis: e.target.value }))}
                sx={{ mb: 1.5 }}
              />

              {/* ICD-11 Code */}
              <Typography variant="subtitle2" gutterBottom color="text.secondary">
                ICD-11 编码
              </Typography>
              <Autocomplete
                freeSolo
                options={ICD11_OPTIONS}
                getOptionLabel={option => typeof option === 'string' ? option : `${option.code} - ${option.label}`}
                value={form.icd11Code}
                onInputChange={(_, v) => setForm(prev => ({ ...prev, icd11Code: v }))}
                renderInput={params => (
                  <TextField {...params} size="small" placeholder="搜索或输入 ICD-11 编码" fullWidth />
                )}
                sx={{ mb: 2 }}
              />

              <Divider sx={{ my: 2 }} />

              {/* Treatment Plan - Medications */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="subtitle1">治疗方案 - 药物</Typography>
                <Button size="small" startIcon={<AddIcon />} onClick={addMedication}>
                  添加药品
                </Button>
              </Box>

              {form.medications.map((med, index) => (
                <Paper key={index} variant="outlined" sx={{ p: 1.5, mb: 1 }}>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                    <Grid container spacing={1} sx={{ flex: 1 }}>
                      <Grid size={{ xs: 12, sm: 3 }}>
                        <TextField
                          fullWidth size="small" label="药品名称"
                          value={med.name}
                          onChange={e => handleMedicationChange(index, 'name', e.target.value)}
                        />
                      </Grid>
                      <Grid size={{ xs: 4, sm: 2 }}>
                        <TextField
                          fullWidth size="small" label="剂量"
                          value={med.dosage}
                          onChange={e => handleMedicationChange(index, 'dosage', e.target.value)}
                          placeholder="500mg"
                        />
                      </Grid>
                      <Grid size={{ xs: 4, sm: 2 }}>
                        <TextField
                          fullWidth size="small" label="频次"
                          value={med.frequency}
                          onChange={e => handleMedicationChange(index, 'frequency', e.target.value)}
                          placeholder="tid"
                        />
                      </Grid>
                      <Grid size={{ xs: 2, sm: 1.5 }}>
                        <TextField
                          fullWidth size="small" label="天数" type="number"
                          value={med.days}
                          onChange={e => handleMedicationChange(index, 'days', parseInt(e.target.value) || 1)}
                        />
                      </Grid>
                      <Grid size={{ xs: 2, sm: 1.5 }}>
                        <TextField
                          fullWidth size="small" label="途径"
                          value={med.route}
                          onChange={e => handleMedicationChange(index, 'route', e.target.value)}
                        />
                      </Grid>
                    </Grid>
                    <IconBtn size="small" color="error" onClick={() => removeMedication(index)}>
                      <DeleteIcon fontSize="small" />
                    </IconBtn>
                  </Box>
                </Paper>
              ))}

              {form.medications.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  未添加药品，如有需要请点击"添加药品"
                </Typography>
              )}

              {/* Lifestyle Advice */}
              <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                生活建议
              </Typography>
              <TextField
                fullWidth
                size="small"
                multiline
                rows={3}
                placeholder="每行一条建议，如：&#10;休息&#10;多饮水&#10;3天后复诊"
                value={form.advice}
                onChange={e => setForm(prev => ({ ...prev, advice: e.target.value }))}
                sx={{ mb: 2 }}
              />

              <Divider sx={{ my: 2 }} />

              {/* Doctor Notes */}
              <Typography variant="subtitle1" gutterBottom>
                医生备注
              </Typography>
              <TextField
                fullWidth
                size="small"
                multiline
                rows={3}
                placeholder="输入临床备注..."
                value={form.doctorNotes}
                onChange={e => setForm(prev => ({ ...prev, doctorNotes: e.target.value }))}
                sx={{ mb: 2 }}
              />

              {/* Rejected Suggestions */}
              {consultation.pre_diagnosis?.possible_diseases?.length > 1 && (
                <Box sx={{ mt: 1, mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom color="text.secondary">
                    拒绝的预诊断（如有）
                  </Typography>
                  {consultation.pre_diagnosis.possible_diseases.slice(1).map((d, i) => (
                    <Chip
                      key={i}
                      label={d.disease}
                      size="small"
                      variant={form.rejectedSuggestions.includes(d.disease) ? 'filled' : 'outlined'}
                      color="default"
                      onClick={() => toggleRejectedSuggestion(d.disease)}
                      sx={{ mr: 0.5, mb: 0.5, cursor: 'pointer' }}
                    />
                  ))}
                  <Typography variant="caption" display="block" color="text.secondary">
                    点击标记为拒绝
                  </Typography>
                </Box>
              )}

              <Divider sx={{ my: 2 }} />

              {/* Submit Button */}
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
                <Button variant="outlined" onClick={() => navigate('/doctor/cases')}>
                  取消
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  size="large"
                  startIcon={<WarningIcon />}
                  onClick={() => setConfirmOpen(true)}
                  disabled={submitting || !form.finalDiagnosis.trim()}
                >
                  {submitting ? '提交中...' : '确认提交诊断'}
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Confirmation Dialog */}
      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <DialogTitle>确认提交最终诊断</DialogTitle>
        <DialogContent>
          <DialogContentText>
            请确认以下诊断信息无误：
          </DialogContentText>
          <Paper variant="outlined" sx={{ p: 2, mt: 1 }}>
            <Typography><strong>最终诊断：</strong>{form.finalDiagnosis}</Typography>
            {form.icd11Code && <Typography><strong>ICD-11：</strong>{form.icd11Code}</Typography>}
            {form.medications.filter(m => m.name).length > 0 && (
              <Typography><strong>药品数：</strong>{form.medications.filter(m => m.name).length} 种</Typography>
            )}
          </Paper>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>返回修改</Button>
          <Button variant="contained" color="error" onClick={handleSubmit} disabled={submitting}>
            确认提交
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
