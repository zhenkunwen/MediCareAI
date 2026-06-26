import { useState } from 'react';
import {
  Box, Typography, Button, Card, CardContent, TextField, Grid,
  IconButton, Paper, Autocomplete,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Print as PrintIcon } from '@mui/icons-material';

interface MedItem {
  name: string; dosage: string; frequency: string; days: number; route: string;
}

const emptyMed = (): MedItem => ({ name: '', dosage: '', frequency: '', days: 7, route: '口服' });

const commonMeds = ['阿莫西林', '头孢克肟', '布洛芬', '奥美拉唑', '硝苯地平', '二甲双胍', '阿托伐他汀'];

/** HTML 转义 — 防止 XSS */
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

export default function PrescriptionPage() {
  const [patientName, setPatientName] = useState('');
  const [diagnosis, setDiagnosis] = useState('');
  const [medications, setMedications] = useState<MedItem[]>([emptyMed()]);
  const [notes, setNotes] = useState('');

  const updateMed = (i: number, field: keyof MedItem, value: any) => {
    setMedications(prev => prev.map((m, idx) => idx === i ? { ...m, [field]: value } : m));
  };

  const addMed = () => setMedications(prev => [...prev, emptyMed()]);
  const removeMed = (i: number) => setMedications(prev => prev.filter((_, idx) => idx !== i));

  const handlePrint = () => {
    const printWin = window.open('', '_blank');
    if (!printWin) return;
    const rows = medications.filter(m => m.name).map(m =>
      `<tr><td>${escapeHtml(m.name)}</td><td>${escapeHtml(m.dosage)}</td><td>${escapeHtml(m.frequency)}</td><td>${escapeHtml(m.route)}</td><td>${m.days}天</td></tr>`
    ).join('');
    printWin.document.write(`
      <html><head><meta charset="utf-8"><title>处方笺</title>
      <style>body{font-family:serif;padding:40px}table{width:100%;border-collapse:collapse}td,th{border:1px solid #333;padding:8px;text-align:left}
      .header{text-align:center;margin-bottom:24px}.footer{margin-top:24px}</style>
      </head><body>
      <div class="header"><h2>处方笺</h2><p>${new Date().toLocaleDateString('zh-CN')}</p></div>
      <p><strong>患者：</strong>${escapeHtml(patientName || '________')}</p>
      <p><strong>诊断：</strong>${escapeHtml(diagnosis || '________')}</p>
      <table><thead><tr><th>药品</th><th>剂量</th><th>频次</th><th>途径</th><th>疗程</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="footer"><p><strong>备注：</strong>${escapeHtml(notes || '________')}</p><br><p>医师签名：______________</p></div>
      <script>window.print()</script>
      </body></html>
    `);
    printWin.document.close();
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>处方开立</Typography>
        <Button variant="contained" startIcon={<PrintIcon />} onClick={handlePrint} disabled={!medications.some(m => m.name)}>
          打印处方
        </Button>
      </Box>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" label="患者姓名" value={patientName} onChange={e => setPatientName(e.target.value)} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" label="诊断" value={diagnosis} onChange={e => setDiagnosis(e.target.value)} />
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="subtitle1" fontWeight={600}>用药明细</Typography>
            <Button size="small" startIcon={<AddIcon />} onClick={addMed}>添加</Button>
          </Box>
          {medications.map((med, i) => (
            <Paper key={i} variant="outlined" sx={{ p: 1.5, mb: 1 }}>
              <Grid container spacing={1} alignItems="center">
                <Grid size={{ xs: 12, sm: 3 }}>
                  <Autocomplete
                    freeSolo size="small" options={commonMeds}
                    value={med.name} onInputChange={(_, v) => updateMed(i, 'name', v)}
                    renderInput={params => <TextField {...params} label="药品" />}
                  />
                </Grid>
                <Grid size={{ xs: 4, sm: 2 }}><TextField fullWidth size="small" label="剂量" value={med.dosage} onChange={e => updateMed(i, 'dosage', e.target.value)} placeholder="500mg" /></Grid>
                <Grid size={{ xs: 4, sm: 2 }}><TextField fullWidth size="small" label="频次" value={med.frequency} onChange={e => updateMed(i, 'frequency', e.target.value)} placeholder="tid" /></Grid>
                <Grid size={{ xs: 2, sm: 1.5 }}><TextField fullWidth size="small" label="天数" type="number" value={med.days} onChange={e => updateMed(i, 'days', parseInt(e.target.value) || 1)} /></Grid>
                <Grid size={{ xs: 2, sm: 1.5 }}>
                  <TextField fullWidth size="small" label="途径" value={med.route} onChange={e => updateMed(i, 'route', e.target.value)} />
                </Grid>
                <Grid size={{ xs: 2, sm: 1 }}>
                  <IconButton size="small" color="error" onClick={() => removeMed(i)}><DeleteIcon /></IconButton>
                </Grid>
              </Grid>
            </Paper>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <TextField fullWidth multiline rows={2} size="small" label="备注" value={notes} onChange={e => setNotes(e.target.value)} />
        </CardContent>
      </Card>
    </Box>
  );
}
