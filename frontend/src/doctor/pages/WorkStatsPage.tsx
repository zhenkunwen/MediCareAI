import { useState, useEffect } from 'react';
import { Box, Typography, Card, CardContent, Grid, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Skeleton } from '@mui/material';
import { PendingActions, CheckCircle, Schedule, TrendingUp } from '@mui/icons-material';
import { API_BASE, authHeaders } from '../../api/client';

export default function WorkStatsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const load = () => {
      fetch(`${API_BASE}/doctor/stats/work`, { headers: authHeaders() })
        .then(r => r.json())
        .then(d => { if (mounted) setData(d); })
        .catch(err => console.error('[WorkStats] error:', err))
        .finally(() => { if (mounted) setLoading(false); });
    };
    load();
    const timer = setInterval(load, 30000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);

  if (loading) return <Box sx={{ p: 3 }}>{[1,2,3,4].map(i => <Skeleton key={i} variant="rectangular" height={100} sx={{ mb: 2, borderRadius: 2 }} />)}</Box>;

  const statsCards = [
    { label: '今日接诊', value: data?.today_count ?? 0, icon: <PendingActions color="primary" />, color: 'primary.main' },
    { label: '待处理', value: data?.pending_count ?? 0, icon: <Schedule color="warning" />, color: 'warning.main' },
    { label: '已完成', value: data?.completed_count ?? 0, icon: <CheckCircle color="success" />, color: 'success.main' },
    { label: '累计病例', value: data?.total_count ?? 0, icon: <TrendingUp color="info" />, color: 'info.main' },
  ];

  const diagnoses = data?.common_diagnoses ?? [];
  return (
    <Box>
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>工作统计</Typography>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        {statsCards.map(s => (
          <Grid key={s.label} size={{ xs: 6, md: 3 }}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Box sx={{ mb: 1 }}>{s.icon}</Box>
                <Typography variant="h4" sx={{ fontWeight: 700, color: s.color }}>{s.value}</Typography>
                <Typography variant="body2" color="text.secondary">{s.label}</Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>常见诊断统计</Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>诊断</TableCell>
                  <TableCell align="right">例数</TableCell>
                  <TableCell align="right">趋势</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {diagnoses.length === 0 ? (
                  <TableRow><TableCell colSpan={3} align="center">暂无数据</TableCell></TableRow>
                ) : diagnoses.map((d: any) => (
                  <TableRow key={d.diagnosis}>
                    <TableCell>{d.diagnosis}</TableCell>
                    <TableCell align="right">{d.count}</TableCell>
                    <TableCell align="right">—</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  );
}
