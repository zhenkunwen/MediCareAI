import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Container,
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Chip,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Grid,
  Stack,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import ArrowBackIosNewIcon from '@mui/icons-material/ArrowBackIosNew';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import { getProfile, updateProfile } from '../../api/patient';
import { getMe, updateMe } from '../../api/auth';
import type { PatientProfile, BackendProfile } from '../../api/patient';
import { flexRowBetweenMb2, pageHeader } from '../../styles/sxUtils';


const warmText = '#1E293B';
const warmPrimary = '#14B8A6';
const warmBg = '#F0FDFA';

const GENDER_OPTIONS = [
  { value: 'male', label: '男' },
  { value: 'female', label: '女' },
  { value: 'other', label: '其他' },
  { value: 'prefer_not_to_say', label: '不透露' },
];

const BLOOD_TYPE_OPTIONS = [
  { value: 'A', label: 'A 型' },
  { value: 'B', label: 'B 型' },
  { value: 'AB', label: 'AB 型' },
  { value: 'O', label: 'O 型' },
  { value: 'Rh+', label: 'Rh 阳性' },
  { value: 'Rh-', label: 'Rh 阴性' },
  { value: '未知', label: '未知' },
];

function genderLabel(value: string | undefined): string {
  return GENDER_OPTIONS.find(o => o.value === value)?.label || value || '—';
}

function bloodTypeLabel(value: string | undefined): string {
  return BLOOD_TYPE_OPTIONS.find(o => o.value === value)?.label || value || '—';
}

function emptyProfile(): PatientProfile {
  return {
    id: '',
    name: '',
    email: '',
    phone: '',
    date_of_birth: '',
    gender: undefined,
    blood_type: undefined,
    height: undefined,
    weight: undefined,
    allergies: [],
    chronic_diseases: [],
    medications: [],
  };
}

export default function HealthProfilePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<PatientProfile>(emptyProfile);
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);

  // 用于编辑时的临时状态
  const [editProfile, setEditProfile] = useState<PatientProfile>(emptyProfile);
  const editProfileRef = useRef(editProfile);
  editProfileRef.current = editProfile;
  const [newAllergy, setNewAllergy] = useState('');
  const [newDisease, setNewDisease] = useState('');
  const [saveError, setSaveError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      getProfile().catch(() => null),
      getMe().catch(() => null),
    ]).then(([profileData, userData]) => {
      if (!mounted) return;
      const u = (userData as unknown as Record<string, unknown>) || {};
      const p = profileData as BackendProfile | null;
      const merged: PatientProfile = {
        ...emptyProfile(),
        id: (u.id as string) || '',
        name: (u.full_name as string) || (u.name as string) || '',
        email: (u.email as string) || '',
        phone: (u.phone as string) || '',
        date_of_birth: p?.date_of_birth || '',
        gender: p?.gender || undefined,
        blood_type: p?.blood_type || undefined,
        height: p?.height ?? undefined,
        weight: p?.weight ?? undefined,
        allergies: p?.allergies || [],
        chronic_diseases: p?.chronic_diseases || [],
        medications: p?.medications || [],
      };
      setProfile(merged);
      setEditProfile(merged);
      setLoading(false);
    });
    return () => { mounted = false; };
  }, []);

  const handleToggleEdit = () => {
    if (isEditing) {
      // 取消编辑，恢复原始数据
      setEditProfile(profile);
    }
    setIsEditing(!isEditing);
  };

  const handleSave = async () => {
    setSaveError('');
    setSaving(true);
    const current = editProfileRef.current;
    try {
      // 收集输入框中未点击"添加"的值
      const pendingAllergy = newAllergy.trim();
      const pendingDisease = newDisease.trim();
      const allergiesToSave = pendingAllergy
        ? [...(current.allergies || []), pendingAllergy]
        : (current.allergies || []);
      const chronicToSave = pendingDisease
        ? [...(current.chronic_diseases || []), pendingDisease]
        : (current.chronic_diseases || []);

      // 1. 保存用户身份信息（name/phone → PATCH /auth/me）
      if (current.name || current.phone) {
        await updateMe({
          full_name: current.name || undefined,
          phone: current.phone || undefined,
        });
      }

      // 2. 保存健康档案医疗数据（PATCH /patient/profile）
      const profilePayload: Record<string, unknown> = {};
      if (current.date_of_birth) profilePayload.date_of_birth = current.date_of_birth;
      profilePayload.gender = current.gender || null;
      profilePayload.blood_type = current.blood_type || null;
      if (current.height) profilePayload.height = current.height;
      if (current.weight) profilePayload.weight = current.weight;
      profilePayload.allergies = allergiesToSave;
      profilePayload.chronic_diseases = chronicToSave;
      profilePayload.medications = (current.medications || []).map(m => ({
        ...m,
        start_date: m.start_date || new Date().toISOString().split('T')[0],
      }));
      const saved = await updateProfile(profilePayload);

      // 3. 直接使用保存返回的数据刷新页面
      const freshMerged: PatientProfile = {
        ...emptyProfile(),
        id: current.id || '',
        name: current.name || '',
        email: current.email || '',
        phone: current.phone || '',
        date_of_birth: saved?.date_of_birth || '',
        gender: saved?.gender || undefined,
        blood_type: saved?.blood_type || undefined,
        height: saved?.height ?? undefined,
        weight: saved?.weight ?? undefined,
        allergies: saved?.allergies || [],
        chronic_diseases: saved?.chronic_diseases || [],
        medications: saved?.medications || [],
      };
      setProfile(freshMerged);
      setEditProfile(freshMerged);
      // 清空待添加输入
      setNewAllergy('');
      setNewDisease('');
      setIsEditing(false);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : '保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field: keyof PatientProfile, value: string | number) => {
    setEditProfile((prev) => ({ ...prev, [field]: value }));
  };

  const handleAddAllergy = () => {
    const val = newAllergy.trim();
    if (!val) return;
    setEditProfile((prev) => {
      const next = [...(prev.allergies || []), val];
      return { ...prev, allergies: next };
    });
    setNewAllergy('');
  };

  const handleRemoveAllergy = (index: number) => {
    setEditProfile((prev) => ({
      ...prev,
      allergies: (prev.allergies || []).filter((_, i) => i !== index),
    }));
  };

  const handleAddDisease = () => {
    const val = newDisease.trim();
    if (!val) return;
    setEditProfile((prev) => {
      const next = [...(prev.chronic_diseases || []), val];
      return { ...prev, chronic_diseases: next };
    });
    setNewDisease('');
  };

  const handleRemoveDisease = (index: number) => {
    setEditProfile((prev) => ({
      ...prev,
      chronic_diseases: (prev.chronic_diseases || []).filter((_, i) => i !== index),
    }));
  };

  const handleMedicationChange = (
    index: number,
    field: 'name' | 'dosage' | 'frequency' | 'start_date',
    value: string
  ) => {
    setEditProfile((prev) => {
      const meds = [...(prev.medications || [])];
      meds[index] = { ...meds[index], [field]: value };
      return { ...prev, medications: meds };
    });
  };

  const handleAddMedication = () => {
    const today = new Date().toISOString().split('T')[0];
    setEditProfile((prev) => ({
      ...prev,
      medications: [...(prev.medications || []), { name: '', dosage: '', frequency: '', start_date: today }],
    }));
  };

  const handleRemoveMedication = (index: number) => {
    setEditProfile((prev) => ({
      ...prev,
      medications: (prev.medications || []).filter((_, i) => i !== index),
    }));
  };

  const display = isEditing ? editProfile : profile;

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: warmBg, pb: 6 }}>
      <Container maxWidth="md">
        {/* Header */}
        <Box sx={pageHeader}>
          <IconButton onClick={() => navigate('/chat')} sx={{ color: warmText }}>
            <ArrowBackIosNewIcon />
          </IconButton>
          <Typography variant="h5" sx={{ fontWeight: 700, color: warmText, flex: 1 }}>
            健康档案
          </Typography>
          <Button
            variant={isEditing ? 'outlined' : 'contained'}
            startIcon={isEditing ? undefined : <EditIcon />}
            onClick={handleToggleEdit}
            sx={{
              borderRadius: 3,
              textTransform: 'none',
              color: isEditing ? warmPrimary : '#fff',
              borderColor: warmPrimary,
              bgcolor: isEditing ? 'transparent' : warmPrimary,
              '&:hover': {
                bgcolor: isEditing ? 'rgba(20,184,166,0.08)' : '#0D9488',
                borderColor: warmPrimary,
              },
            }}
          >
            {isEditing ? '取消' : '编辑'}
          </Button>
          {isEditing && (
            <Button
              variant="contained"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              sx={{
                borderRadius: 3,
                textTransform: 'none',
                bgcolor: warmPrimary,
                '&:hover': { bgcolor: '#0D9488' },
              }}
            >
              保存
            </Button>
          )}
        </Box>

        {loading ? (
          <Typography sx={{ color: warmText, textAlign: 'center', py: 4 }}>
            加载中...
          </Typography>
        ) : (
        <>

        {saveError && (
          <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }} onClose={() => setSaveError('')}>
            {saveError}
          </Alert>
        )}

        {/* 基础信息 */}
        <Card sx={{ mb: 2, borderRadius: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ color: warmText, mb: 2, fontWeight: 600 }}>
              基础信息
            </Typography>
            <Grid container spacing={2}>
              {[
                { label: '姓名', field: 'name' as const, type: 'text' },
                { label: '邮箱', field: 'email' as const, type: 'email', readonly: true },
                { label: '手机', field: 'phone' as const, type: 'tel' },
                { label: '出生日期', field: 'date_of_birth' as const, type: 'date' },
                { label: '性别', field: 'gender' as const, type: 'select' },
                { label: '身高 (cm)', field: 'height' as const, type: 'number' },
                { label: '体重 (kg)', field: 'weight' as const, type: 'number' },
              ].map((item) => (
                <Grid size={{ xs: 12, sm: 6 }} key={item.field}>
                  {isEditing ? (
                    item.readonly ? (
                      <Box>
                        <Typography variant="caption" sx={{ color: '#64748B' }}>
                          {item.label}
                        </Typography>
                        <Typography variant="body1" sx={{ color: warmText, fontWeight: 500 }}>
                          {display[item.field] ?? '—'}
                        </Typography>
                      </Box>
                    ) : item.field === 'gender' ? (
                      <FormControl fullWidth sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2 } }}>
                        <InputLabel>性别</InputLabel>
                        <Select
                          value={display.gender && GENDER_OPTIONS.some(o => o.value === display.gender) ? display.gender : ''}
                          label="性别"
                          onChange={(e) => handleChange('gender', e.target.value)}
                        >
                          <MenuItem value="" disabled>请选择性别</MenuItem>
                          {GENDER_OPTIONS.map(o => (
                            <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    ) : (
                    <TextField
                      fullWidth
                      label={item.label}
                      type={item.type}
                      value={display[item.field] ?? ''}
                      onChange={(e) =>
                        handleChange(
                          item.field,
                          item.type === 'number' ? Number(e.target.value) : e.target.value
                        )
                      }
                      slotProps={{ inputLabel: item.type === 'date' ? { shrink: true } : undefined }}
                      sx={{
                        '& .MuiOutlinedInput-root': {
                          borderRadius: 2,
                        },
                      }}
                    />
                  )
                ) : (
                    <Box>
                      <Typography variant="caption" sx={{ color: '#64748B' }}>
                        {item.label}
                      </Typography>
                      <Typography variant="body1" sx={{ color: warmText, fontWeight: 500 }}>
                        {item.field === 'gender' ? genderLabel(display.gender) : (display[item.field] ?? '—')}
                      </Typography>
                    </Box>
                  )}
                </Grid>
              ))}
              {/* 血型 */}
              <Grid size={{ xs: 12, sm: 6 }}>
                {isEditing ? (
                  <FormControl fullWidth sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2 } }}>
                    <InputLabel>血型</InputLabel>
                    <Select
                      value={display.blood_type && BLOOD_TYPE_OPTIONS.some(o => o.value === display.blood_type) ? display.blood_type : ''}
                      label="血型"
                      onChange={(e) => handleChange('blood_type', e.target.value)}
                    >
                      <MenuItem value="" disabled>请选择血型</MenuItem>
                      {BLOOD_TYPE_OPTIONS.map(o => (
                        <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                ) : (
                  <Box>
                    <Typography variant="caption" sx={{ color: '#64748B' }}>
                      血型
                    </Typography>
                    <Typography variant="body1" sx={{ color: warmText, fontWeight: 500 }}>
                      {bloodTypeLabel(display.blood_type)}
                    </Typography>
                  </Box>
                )}
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {/* 过敏史 */}
        <Card sx={{ mb: 2, borderRadius: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ color: warmText, mb: 2, fontWeight: 600 }}>
              过敏史
            </Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
              {(display.allergies || []).map((allergy, idx) => (
                <Chip
                  key={`${allergy}-${idx}`}
                  label={allergy}
                  onDelete={isEditing ? () => handleRemoveAllergy(idx) : undefined}
                  sx={{
                    bgcolor: 'rgba(20,184,166,0.12)',
                    color: warmPrimary,
                    fontWeight: 500,
                    '& .MuiChip-deleteIcon': { color: warmPrimary },
                  }}
                />
              ))}
              {!(display.allergies || []).length && !isEditing && (
                <Typography variant="body2" sx={{ color: '#64748B' }}>
                  暂无记录
                </Typography>
              )}
            </Stack>
            {isEditing && (
              <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                <TextField
                  size="small"
                  placeholder="添加过敏源"
                  value={newAllergy}
                  onChange={(e) => setNewAllergy(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleAddAllergy();
                  }}
                  sx={{ flex: 1, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
                />
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={handleAddAllergy}
                  sx={{
                    bgcolor: warmPrimary,
                    '&:hover': { bgcolor: '#0D9488' },
                    borderRadius: 2,
                    textTransform: 'none',
                  }}
                >
                  添加
                </Button>
              </Box>
            )}
          </CardContent>
        </Card>

        {/* 慢性病 */}
        <Card sx={{ mb: 2, borderRadius: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ color: warmText, mb: 2, fontWeight: 600 }}>
              慢性病
            </Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
              {(display.chronic_diseases || []).map((disease, idx) => (
                <Chip
                  key={`${disease}-${idx}`}
                  label={disease}
                  onDelete={isEditing ? () => handleRemoveDisease(idx) : undefined}
                  sx={{
                    bgcolor: 'rgba(139,115,85,0.12)',
                    color: '#64748B',
                    fontWeight: 500,
                    '& .MuiChip-deleteIcon': { color: '#64748B' },
                  }}
                />
              ))}
              {!(display.chronic_diseases || []).length && !isEditing && (
                <Typography variant="body2" sx={{ color: '#64748B' }}>
                  暂无记录
                </Typography>
              )}
            </Stack>
            {isEditing && (
              <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                <TextField
                  size="small"
                  placeholder="添加慢性病"
                  value={newDisease}
                  onChange={(e) => setNewDisease(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleAddDisease();
                  }}
                  sx={{ flex: 1, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
                />
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={handleAddDisease}
                  sx={{
                    bgcolor: warmPrimary,
                    '&:hover': { bgcolor: '#0D9488' },
                    borderRadius: 2,
                    textTransform: 'none',
                  }}
                >
                  添加
                </Button>
              </Box>
            )}
          </CardContent>
        </Card>

        {/* 用药记录 */}
        <Card sx={{ borderRadius: 3 }}>
          <CardContent>
            <Box sx={flexRowBetweenMb2}>
              <Typography variant="h6" sx={{ color: warmText, fontWeight: 600 }}>
                用药记录
              </Typography>
              {isEditing && (
                <Button
                  variant="outlined"
                  startIcon={<AddIcon />}
                  onClick={handleAddMedication}
                  sx={{
                    borderRadius: 2,
                    textTransform: 'none',
                    color: warmPrimary,
                    borderColor: warmPrimary,
                    '&:hover': { borderColor: '#0D9488', bgcolor: 'rgba(20,184,166,0.06)' },
                  }}
                >
                  添加药物
                </Button>
              )}
            </Box>
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: 'rgba(20,184,166,0.08)' }}>
                    <TableCell sx={{ color: warmText, fontWeight: 600 }}>药物名称</TableCell>
                    <TableCell sx={{ color: warmText, fontWeight: 600 }}>剂量</TableCell>
                    <TableCell sx={{ color: warmText, fontWeight: 600 }}>频率</TableCell>
                    <TableCell sx={{ color: warmText, fontWeight: 600 }}>开始日期</TableCell>
                    {isEditing && <TableCell sx={{ color: warmText, fontWeight: 600 }}>操作</TableCell>}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(display.medications || []).map((med, idx) => (
                    <TableRow key={idx}>
                      <TableCell>
                        {isEditing ? (
                          <TextField
                            size="small"
                            fullWidth
                            value={med.name}
                            onChange={(e) => handleMedicationChange(idx, 'name', e.target.value)}
                            placeholder="药物名称"
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                          />
                        ) : (
                          <Typography variant="body2" sx={{ color: warmText }}>
                            {med.name || '—'}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        {isEditing ? (
                          <TextField
                            size="small"
                            fullWidth
                            value={med.dosage}
                            onChange={(e) => handleMedicationChange(idx, 'dosage', e.target.value)}
                            placeholder="剂量"
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                          />
                        ) : (
                          <Typography variant="body2" sx={{ color: warmText }}>
                            {med.dosage || '—'}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        {isEditing ? (
                          <TextField
                            size="small"
                            fullWidth
                            value={med.frequency}
                            onChange={(e) => handleMedicationChange(idx, 'frequency', e.target.value)}
                            placeholder="频率"
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                          />
                        ) : (
                          <Typography variant="body2" sx={{ color: warmText }}>
                            {med.frequency || '—'}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        {isEditing ? (
                          <TextField
                            size="small"
                            type="date"
                            fullWidth
                            value={med.start_date || ''}
                            onChange={(e) => handleMedicationChange(idx, 'start_date', e.target.value)}
                            slotProps={{ inputLabel: { shrink: true } }}
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                          />
                        ) : (
                          <Typography variant="body2" sx={{ color: warmText }}>
                            {med.start_date || '—'}
                          </Typography>
                        )}
                      </TableCell>
                      {isEditing && (
                        <TableCell>
                          <IconButton
                            size="small"
                            onClick={() => handleRemoveMedication(idx)}
                            sx={{ color: '#E57373' }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                  {!(display.medications || []).length && (
                    <TableRow>
                      <TableCell colSpan={isEditing ? 5 : 4} align="center">
                        <Typography variant="body2" sx={{ color: '#64748B', py: 2 }}>
                          暂无用药记录
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      </>
    )}
      </Container>
    </Box>
  );
}