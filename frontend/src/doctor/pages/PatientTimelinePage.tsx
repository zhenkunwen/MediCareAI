import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Typography, Button, Card, CardContent, CircularProgress, Alert,
} from '@mui/material';
import {
  Timeline, TimelineItem, TimelineSeparator, TimelineConnector,
  TimelineContent, TimelineDot,
} from '@mui/lab';
import {
  ArrowBack as ArrowBackIcon, Healing, Science, Medication,
} from '@mui/icons-material';
import { getCaseDetail } from '../../api/doctor';

interface TimelineEvent {
  type: string; time?: string; intent?: string; summary?: string;
}

interface CaseTimelineResponse {
  patient_name: string;
  diagnosis?: string;
  agent_summary?: string;
  timeline: TimelineEvent[];
}

const typeConfig: Record<string, { icon: React.ReactNode; color: 'primary' | 'success' | 'warning' | 'info' }> = {
  diagnosis: { icon: <Healing fontSize="small" />, color: 'primary' },
  lab: { icon: <Science fontSize="small" />, color: 'info' },
  prescription: { icon: <Medication fontSize="small" />, color: 'success' },
};

export default function PatientTimelinePage() {
  const { patientId } = useParams<{ patientId: string }>();
  const navigate = useNavigate();
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [patientName, setPatientName] = useState('');
  const [summary, setSummary] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!patientId) return;
    getCaseDetail(patientId)
      .then(data => {
        setPatientName(data.patient_name);
        const resp = data as unknown as CaseTimelineResponse;
        setSummary(resp.diagnosis || resp.agent_summary || '');
        setTimeline(resp.timeline || []);
      })
      .catch((err) => console.error('[PatientTimeline] error:', err))
      .finally(() => setLoading(false));
  }, [patientId]);

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>;
  if (!patientName) return <Alert severity="info">未找到患者数据</Alert>;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <Button size="small" startIcon={<ArrowBackIcon />} onClick={() => navigate('/doctor/patients')}>返回</Button>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>{patientName} - 时间轴</Typography>
      </Box>

      {summary && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="subtitle2" color="text.secondary">诊断摘要</Typography>
            <Typography variant="body1" sx={{ mt: 0.5 }}>{summary}</Typography>
          </CardContent>
        </Card>
      )}

      {timeline.length === 0 ? (
        <Alert severity="info">暂无历史记录</Alert>
      ) : (
        <Timeline>
          {timeline.map((event: TimelineEvent, i: number) => {
            const cfg = typeConfig[event.type] || { icon: <Healing fontSize="small" />, color: 'primary' as const };
            return (
              <TimelineItem key={i}>
                <TimelineSeparator>
                  <TimelineDot color={cfg.color}>{cfg.icon}</TimelineDot>
                  {i < timeline.length - 1 && <TimelineConnector />}
                </TimelineSeparator>
                <TimelineContent>
                  <Typography variant="body2" fontWeight={600}>{event.intent || event.type}</Typography>
                  <Typography variant="caption" color="text.secondary">{event.time ? new Date(event.time).toLocaleString('zh-CN') : ''}</Typography>
                  {event.summary && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{event.summary}</Typography>}
                </TimelineContent>
              </TimelineItem>
            );
          })}
        </Timeline>
      )}
    </Box>
  );
}
