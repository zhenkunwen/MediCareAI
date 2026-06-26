import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container, Box, Typography, Card, CardContent, IconButton, Button,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField, Chip,
  LinearProgress, Stack, Divider, Switch, FormControlLabel,
} from '@mui/material';
import ArrowBackIosNewIcon from '@mui/icons-material/ArrowBackIosNew';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import {
  getTodayMedications, takeMedication, listMedications, createMedication, deleteMedication,
} from '../../api/patient';
import type { TodayMedicationItem, MedicationReminder } from '../../api/patient';
import { flexRowGap05Mb05, pageHeader } from '../../styles/sxUtils';

const warmText = '#1E293B';
const warmPrimary = '#14B8A6';
const warmBg = '#F0FDFA';

export default function MedicationPage() {
  const navigate = useNavigate();
  const [today, setToday] = useState<TodayMedicationResponse | null>(null);
  const [reminders, setReminders] = useState<MedicationReminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState('');
  const [dosage, setDosage] = useState('');
  const [frequency, setFrequency] = useState('');
  const [times, setTimes] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);
  const [remindEnabled, setRemindEnabled] = useState(true);
  const [leadMinutes, setLeadMinutes] = useState(15);

  const loadToday = async () => {
    try {
      const [t, r] = await Promise.all([getTodayMedications(), listMedications()]);
      setToday(t);
      setReminders(r);
    } catch {
      setToday({ items: [], taken_count: 0, pending_count: 0, total_count: 0 });
    }
    setLoading(false);
  };

  useEffect(() => { loadToday(); }, []);

  const handleTake = async (rid: string) => {
    try {
      await takeMedication(rid);
      loadToday();
    } catch { /* ignore */ }
  };

  const handleAdd = async () => {
    if (!name.trim() || !dosage.trim()) return;
    try {
      const slots = times.split(/[,，\s]+/).filter(Boolean);
      await createMedication({
        name: name.trim(), dosage: dosage.trim(),
        frequency: frequency.trim() || '每日一次',
        time_slots: slots.length ? slots : ['08:00', '20:00'],
        lead_minutes: leadMinutes,
        remind_enabled: remindEnabled,
      });
      setAddOpen(false);
      setName(''); setDosage(''); setFrequency(''); setTimes(''); setLeadMinutes(15); setRemindEnabled(true);
      loadToday();
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteMedication(id);
      setDeleting(null);
      loadToday();
    } catch { /* ignore */ }
  };

  const rate = today?.total_count ? Math.round((today.taken_count / today.total_count) * 100) : 0;
  const pending = today?.items.filter(i => i.status === 'pending') || [];
  const completed = today?.items.filter(i => i.status === 'completed') || [];

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: warmBg, pb: 6 }}>
      <Container maxWidth="md">
        {/* Header */}
        <Box sx={pageHeader}>
          <IconButton onClick={() => navigate('/chat')} sx={{ color: warmText }}>
            <ArrowBackIosNewIcon />
          </IconButton>
          <Typography variant="h5" sx={{ fontWeight: 700, color: warmText, flex: 1 }}>
            用药提醒
          </Typography>
        </Box>

        {/* Today Overview */}
        <Card sx={{ borderRadius: 3, mb: 2, boxShadow: '0 2px 8px rgba(15,23,42,0.06)' }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, color: warmText, mb: 1.5 }}>
              今日服药进度
            </Typography>
            <LinearProgress
              variant="determinate" value={rate}
              sx={{ height: 8, borderRadius: 4, mb: 1, bgcolor: 'rgba(20,184,166,0.15)',
                '& .MuiLinearProgress-bar': { bgcolor: warmPrimary, borderRadius: 4 } }}
            />
            <Typography variant="body2" sx={{ color: '#64748B' }}>
              已完成 {today?.taken_count || 0}/{today?.total_count || 0} 次
            </Typography>
          </CardContent>
        </Card>

        {/* Pending */}
        {pending.length > 0 && (
          <Card sx={{ borderRadius: 3, mb: 2, boxShadow: '0 2px 8px rgba(15,23,42,0.06)' }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, color: warmText, mb: 1 }}>
                待服用
              </Typography>
              <Stack spacing={1}>
                {pending.map((item) => (
                  <Box key={item.record_id} sx={{
                    display: 'flex', alignItems: 'center', gap: 1.5, p: 1, borderRadius: 2,
                    bgcolor: 'rgba(20,184,166,0.04)',
                  }}>
                    <IconButton onClick={() => handleTake(item.reminder_id)} sx={{ p: 0, color: warmPrimary }}>
                      <RadioButtonUncheckedIcon />
                    </IconButton>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="body2" sx={{ fontWeight: 500, color: warmText }}>
                        {item.name} {item.dosage}
                      </Typography>
                      <Typography variant="caption" sx={{ color: '#64748B' }}>
                        {item.scheduled_time}
                      </Typography>
                    </Box>
                    <Chip label={item.scheduled_time} size="small" sx={{ bgcolor: 'rgba(20,184,166,0.12)', color: warmPrimary, fontWeight: 600 }} />
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>
        )}

        {/* Completed */}
        {completed.length > 0 && (
          <Card sx={{ borderRadius: 3, mb: 2, boxShadow: '0 2px 8px rgba(15,23,42,0.06)' }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, color: warmText, mb: 1 }}>
                已服用
              </Typography>
              <Stack spacing={1}>
                {completed.map((item) => (
                  <Box key={item.record_id} sx={{
                    display: 'flex', alignItems: 'center', gap: 1.5, p: 1, borderRadius: 2,
                    bgcolor: 'rgba(102,187,106,0.06)',
                  }}>
                    <CheckCircleIcon sx={{ color: '#66BB6A', fontSize: 20 }} />
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="body2" sx={{ color: '#B0B0B0', textDecoration: 'line-through' }}>
                        {item.name} {item.dosage}
                      </Typography>
                    </Box>
                    <Chip label={item.scheduled_time} size="small" sx={{ bgcolor: 'rgba(102,187,106,0.1)', color: '#66BB6A', fontWeight: 600 }} />
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>
        )}

        {/* Medication List */}
        <Card sx={{ borderRadius: 3, boxShadow: '0 2px 8px rgba(15,23,42,0.06)' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, color: warmText }}>
                我的药品
              </Typography>
              <Button size="small" variant="contained" startIcon={<AddIcon />}
                onClick={() => setAddOpen(true)}
                sx={{ bgcolor: warmPrimary, borderRadius: 2, textTransform: 'none', '&:hover': { bgcolor: '#0D9488' } }}>
                添加
              </Button>
            </Box>
            <Divider sx={{ mb: 1 }} />
            {reminders.length === 0 && !loading && (
              <Typography variant="body2" sx={{ color: '#64748B', textAlign: 'center', py: 2 }}>
                暂无药品，点击"添加"开始
              </Typography>
            )}
            {reminders.map((r) => (
              <Box key={r.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 500, color: warmText }}>
                    {r.name} {r.dosage}
                  </Typography>
                  <Typography variant="caption" sx={{ color: '#64748B' }}>
                    {r.frequency} · {r.time_slots?.join(' / ')}
                  </Typography>
                  {r.remind_enabled !== false && (
                    <Typography variant="caption" sx={{ color: '#14B8A6', display: 'block' }}>
                      SMS 提醒 · 提前{r.lead_minutes ?? 15}分钟
                    </Typography>
                  )}
                </Box>
                <Chip label={r.status === 'active' ? '服用中' : '已停用'} size="small"
                  color={r.status === 'active' ? 'success' : 'default'} variant="outlined" />
                <Button size="small" color="error" onClick={() => setDeleting(r.id)}
                  sx={{ minWidth: 'auto', fontSize: 12 }}>停用</Button>
              </Box>
            ))}
          </CardContent>
        </Card>
      </Container>

      {/* Add Dialog */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>添加药品</DialogTitle>
        <DialogContent>
          <TextField autoFocus label="药品名" fullWidth sx={{ mt: 1, mb: 2 }} value={name}
            onChange={e => setName(e.target.value)} placeholder="如：硝苯地平" />
          <TextField label="剂量" fullWidth sx={{ mb: 2 }} value={dosage}
            onChange={e => setDosage(e.target.value)} placeholder="如：5mg" />
          <TextField label="频率" fullWidth sx={{ mb: 2 }} value={frequency}
            onChange={e => setFrequency(e.target.value)} placeholder="如：每日两次" />
          <TextField label="服药时间（空格/逗号分隔）" fullWidth value={times}
            onChange={e => setTimes(e.target.value)} placeholder="如：08:00 20:00" />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 1 }}>
            <FormControlLabel
              control={<Switch checked={remindEnabled} onChange={e => setRemindEnabled(e.target.checked)} />}
              label="短信提醒"
            />
            {remindEnabled && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="caption" sx={{ color: '#64748B' }}>提前</Typography>
                <TextField
                  type="number" size="small" value={leadMinutes}
                  onChange={e => setLeadMinutes(Math.max(1, Math.min(1440, Number(e.target.value))))}
                  sx={{ width: 70 }}
                  inputProps={{ min: 1, max: 1440 }}
                />
                <Typography variant="caption" sx={{ color: '#64748B' }}>分钟</Typography>
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)} color="inherit">取消</Button>
          <Button variant="contained" onClick={handleAdd} disabled={!name.trim() || !dosage.trim()}
            sx={{ bgcolor: warmPrimary, '&:hover': { bgcolor: '#0D9488' } }}>添加</Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirm */}
      <Dialog open={!!deleting} onClose={() => setDeleting(null)}>
        <DialogTitle>停用药品</DialogTitle>
        <DialogContent><Typography>确定停用该药品吗？停用后不再生成服药提醒。</Typography></DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleting(null)} color="inherit">取消</Button>
          <Button color="error" variant="contained" onClick={() => deleting && handleDelete(deleting)}>停用</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
