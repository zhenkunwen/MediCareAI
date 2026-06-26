import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Card, CardContent, Typography, TextField, InputAdornment,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Chip, Avatar, TablePagination, Paper, CircularProgress, Alert,
} from '@mui/material';
import { Search as SearchIcon, Person as PersonIcon } from '@mui/icons-material';
import { listPatients } from '../../api/doctor';
import type { PatientSummary } from '../../api/doctor';

const statusMap: Record<string, { label: string; color: 'warning' | 'info' | 'success' | 'error' | 'default' }> = {
  pending_review: { label: '待处理', color: 'warning' },
  in_progress: { label: '进行中', color: 'info' },
  resolved: { label: '已解决', color: 'success' },
  awaiting_patient: { label: '待患者', color: 'default' },
};

function fmtTime(iso: string) {
  if (!iso) return '-';
  try { const d = new Date(iso); if (isNaN(d.getTime())) return iso; return d.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return iso; }
}

export default function PatientListPage() {
  const navigate = useNavigate();
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  useEffect(() => {
    listPatients()
      .then(setPatients)
      .catch((err) => console.error('[PatientList] error:', err))
      .finally(() => setLoading(false));
  }, []);

  const filtered = patients.filter(p =>
    !search || p.name.includes(search) || p.agent_summary?.includes(search)
  );

  const paged = filtered.slice(page * rowsPerPage, (page + 1) * rowsPerPage);

  return (
    <Box>
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>患者管理</Typography>

      <TextField
        size="small"
        placeholder="搜索患者姓名或病情..."
        value={search}
        onChange={e => { setSearch(e.target.value); setPage(0); }}
        slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchIcon /></InputAdornment> } }}
        sx={{ mb: 2, width: 360 }}
      />

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
      ) : (
        <Paper variant="outlined">
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>患者</TableCell>
                  <TableCell>病情摘要</TableCell>
                  <TableCell>状态</TableCell>
                  <TableCell>最近活动</TableCell>
                  <TableCell align="right">操作</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paged.map(p => (
                  <TableRow
                    key={p.id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/doctor/cases/${p.id}`)}
                  >
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main', fontSize: 14 }}>
                          {p.name[0]}
                        </Avatar>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{p.name}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {p.agent_summary || '暂无摘要'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={statusMap[p.status]?.label || p.status} color={statusMap[p.status]?.color || 'default'} />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">{fmtTime(p.last_activity)}</Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Chip size="small" label="查看" clickable onClick={e => { e.stopPropagation(); navigate(`/doctor/cases/${p.id}`); }} />
                    </TableCell>
                  </TableRow>
                ))}
                {paged.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} align="center">
                      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>暂无患者数据</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            component="div"
            count={filtered.length}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={e => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
            labelRowsPerPage="每页"
          />
        </Paper>
      )}
    </Box>
  );
}
