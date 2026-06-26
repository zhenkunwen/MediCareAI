import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Paper, Avatar, Button, Divider, List, ListItem,
  ListItemButton, ListItemIcon, ListItemText, Chip, Switch,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import BadgeIcon from '@mui/icons-material/Verified';
import PeopleIcon from '@mui/icons-material/People';
import EventNoteIcon from '@mui/icons-material/EventNote';
import HistoryIcon from '@mui/icons-material/History';
import BarChartIcon from '@mui/icons-material/BarChart';
import StarIcon from '@mui/icons-material/Star';
import SecurityIcon from '@mui/icons-material/Security';
import VisibilityIcon from '@mui/icons-material/Visibility';
import NotificationsIcon from '@mui/icons-material/Notifications';
import SettingsIcon from '@mui/icons-material/Settings';
import InfoIcon from '@mui/icons-material/Info';
import LogoutIcon from '@mui/icons-material/Logout';
import EditIcon from '@mui/icons-material/Edit';
import CameraAltIcon from '@mui/icons-material/CameraAlt';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { API_BASE, authHeaders } from '../../api/client';
import { getMe, logout } from '../../api/auth';
import type { UserInfo } from '../../api/auth';

const warmBg = '#F5F7FA';
const cardRadius = 3;

interface DoctorStats {
  total_patients: number;
  completed_cases: number;
  pending_cases: number;
  satisfaction_rate: number;
}

export default function DoctorProfile() {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [stats, setStats] = useState<DoctorStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const avatarInputRef = useRef<HTMLInputElement>(null);

  // Profile edit form
  const [editForm, setEditForm] = useState({
    full_name: '', phone: '', hospital: '', department: '', title: '', license_number: '',
  });

  const loadProfile = useCallback(async () => {
    try {
      const u = await getMe();
      setUser(u);
      setEditForm({
        full_name: u.full_name || '',
        phone: u.phone || '',
        hospital: u.hospital || '',
        department: u.department || '',
        title: u.title || '',
        license_number: u.license_number || '',
      });
    } catch { navigate('/login'); }
    setLoading(false);
  }, [navigate]);

  useEffect(() => { loadProfile(); }, [loadProfile]);

  // Load stats
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/doctor/stats/work`, { headers: authHeaders() });
        const d = await r.json();
        setStats({
          total_patients: (d.total_cases || 0),
          completed_cases: (d.completed || 0),
          pending_cases: (d.pending || 0),
          satisfaction_rate: d.satisfaction_rate || 98,
        });
      } catch {}
    })();
  }, []);

  // ── Avatar upload ─────────────────────────────────────────────
  const handleAvatarClick = () => {
    avatarInputRef.current?.click();
  };

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingAvatar(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const uploadRes = await fetch(`${API_BASE}/upload`, {
        method: 'POST', headers: authHeaders(), body: formData,
      });
      if (!uploadRes.ok) throw new Error('Upload failed');
      const { url } = await uploadRes.json();
      // Save avatar URL to user profile
      const patchRes = await fetch(`${API_BASE}/auth/me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ avatar_url: url }),
      });
      if (patchRes.ok) {
        const updated = await patchRes.json();
        setUser(prev => prev ? { ...prev, avatar_url: url } : prev);
      }
    } catch (err) { console.error('[Profile] avatar upload error:', err); }
    setUploadingAvatar(false);
    if (avatarInputRef.current) avatarInputRef.current.value = '';
  };

  const handleEditOpen = () => setEditOpen(true);
  const handleEditClose = () => setEditOpen(false);

  const handleSaveProfile = async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(editForm),
      });
      if (res.ok) {
        const updated = await res.json();
        setUser(prev => prev ? { ...prev, ...updated } : prev);
        handleEditClose();
      }
    } catch { /* keep old values */ }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <Paper sx={{ borderRadius: cardRadius, mb: 2, overflow: 'hidden' }}>
      <Typography variant="subtitle2" sx={{ px: 2.5, py: 1.5, fontWeight: 700, bgcolor: '#FAFBFC', borderBottom: '1px solid #F0F0F0' }}>
        {title}
      </Typography>
      {children}
    </Paper>
  );

  const SettingItem = ({
    icon, label, right, onClick,
  }: {
    icon: React.ReactNode; label: string;
    right?: React.ReactNode; onClick?: () => void;
  }) => (
    <ListItem disablePadding>
      <ListItemButton onClick={onClick} sx={{ px: 2.5, py: 1.5 }}>
        <ListItemIcon sx={{ minWidth: 36, color: 'text.secondary' }}>{icon}</ListItemIcon>
        <ListItemText primary={label} slotProps={{ primary: { fontSize: '0.9rem' } }} />
        {right || <ChevronRightIcon sx={{ color: 'text.disabled', fontSize: 20 }} />}
      </ListItemButton>
    </ListItem>
  );

  // Get initial from name
  const initial = (user?.full_name || user?.email || 'D')[0].toUpperCase();

  return (
    <Box sx={{ maxWidth: 640, mx: 'auto' }}>

      {/* ── Header Card ────────────────────────────────────────────── */}
      <Paper sx={{ borderRadius: cardRadius, mb: 2, p: 3, textAlign: 'center' }}>
        <Box sx={{ position: 'relative', display: 'inline-block', cursor: 'pointer' }} onClick={handleAvatarClick}>
          <Avatar
            src={user?.avatar_url || undefined}
            sx={{
              width: 80, height: 80, mx: 'auto', mb: 1.5,
              bgcolor: user?.avatar_url ? 'transparent' : 'primary.main',
              fontSize: 32, fontWeight: 700,
            }}
          >
            {!user?.avatar_url && initial}
          </Avatar>
          <Box sx={{
            position: 'absolute', bottom: 4, right: 0,
            bgcolor: 'rgba(0,0,0,0.5)', borderRadius: '50%',
            width: 26, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            {uploadingAvatar
              ? <CircularProgress size={14} sx={{ color: '#fff' }} />
              : <EditIcon sx={{ fontSize: 14, color: '#fff' }} />
            }
          </Box>
        </Box>
        <input type="file" accept="image/*" ref={avatarInputRef} style={{ display: 'none' }} onChange={handleAvatarChange} />
        <Typography variant="h6" sx={{ fontWeight: 700 }}>{user?.full_name || '医生'}</Typography>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
          <Typography variant="body2" color="text.secondary">
            {user?.department || '未设置科室'}
            {user?.title ? ` · ${user?.title}` : ''}
          </Typography>
          {user?.is_verified && (
            <Chip icon={<BadgeIcon />} label="已认证" size="small" color="primary" variant="outlined" sx={{ height: 22, fontSize: 11 }} />
          )}
        </Box>
        {user?.license_number && (
          <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 0.5 }}>
            执业编号: {user.license_number}
          </Typography>
        )}
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5, mb: 2, maxWidth: 400, mx: 'auto', lineHeight: 1.6 }}>
          {user?.hospital ? `就职于 ${user.hospital}` : '暂无医院信息'}
        </Typography>
        <Button size="small" startIcon={<EditIcon />} variant="outlined" onClick={handleEditOpen} sx={{ borderRadius: 2, textTransform: 'none' }}>
          编辑资料
        </Button>
      </Paper>

      {/* ── Work Stats ─────────────────────────────────────────────── */}
      <Paper sx={{ borderRadius: cardRadius, mb: 2, p: 2.5 }}>
        <Box sx={{ display: 'flex', textAlign: 'center' }}>
          {[
            { label: '服务患者', value: stats?.total_patients ?? 0, icon: <PeopleIcon /> },
            { label: '已完成', value: stats?.completed_cases ?? 0, icon: <BarChartIcon /> },
            { label: '待处理', value: stats?.pending_cases ?? 0, icon: <HistoryIcon /> },
            { label: '好评率', value: `${stats?.satisfaction_rate ?? 98}%`, icon: <StarIcon /> },
          ].map(item => (
            <Box key={item.label} sx={{ flex: 1 }}>
              <Box sx={{ color: 'primary.main', mb: 0.5, opacity: 0.7 }}>{item.icon}</Box>
              <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.1rem' }}>{item.value}</Typography>
              <Typography variant="caption" color="text.secondary">{item.label}</Typography>
            </Box>
          ))}
        </Box>
      </Paper>

      {/* ── Patient Interaction ────────────────────────────────────── */}
      <Section title="患者互动">
        <List disablePadding>
          <SettingItem icon={<PeopleIcon />} label="我的患者" onClick={() => navigate('/doctor/cases')} />
          <SettingItem icon={<EventNoteIcon />} label="随访计划" onClick={() => navigate('/doctor/cases')} />
          <SettingItem icon={<HistoryIcon />} label="在线问诊记录" onClick={() => navigate('/doctor/messages')} />
        </List>
      </Section>

      {/* ── System Settings ────────────────────────────────────────── */}
      <Section title="系统设置">
        <List disablePadding>
          <SettingItem icon={<SecurityIcon />} label="账号安全" />
          <SettingItem icon={<VisibilityIcon />} label="隐私设置" right={<Switch size="small" defaultChecked />} />
          <SettingItem icon={<NotificationsIcon />} label="消息通知" right={<Switch size="small" defaultChecked />} />
          <SettingItem icon={<SettingsIcon />} label="通用设置" />
          <SettingItem icon={<InfoIcon />} label="关于" />
          <Divider />
          <ListItem disablePadding>
            <ListItemButton onClick={handleLogout} sx={{ px: 2.5, py: 1.5 }}>
              <ListItemIcon sx={{ minWidth: 36, color: '#E53935' }}><LogoutIcon /></ListItemIcon>
              <ListItemText primary="退出登录" slotProps={{ primary: { fontSize: '0.9rem', color: '#E53935' } }} />
            </ListItemButton>
          </ListItem>
        </List>
      </Section>

      {/* ── Edit Profile Dialog ────────────────────────────────────── */}
      <Dialog open={editOpen} onClose={handleEditClose} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>编辑个人资料</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField label="姓名" size="small" value={editForm.full_name}
              onChange={e => setEditForm(f => ({ ...f, full_name: e.target.value }))} />
            <TextField label="手机号" size="small" value={editForm.phone}
              onChange={e => setEditForm(f => ({ ...f, phone: e.target.value }))} />
            <TextField label="医院" size="small" value={editForm.hospital}
              onChange={e => setEditForm(f => ({ ...f, hospital: e.target.value }))} />
            <TextField label="科室" size="small" value={editForm.department}
              onChange={e => setEditForm(f => ({ ...f, department: e.target.value }))} />
            <TextField label="职称" size="small" value={editForm.title}
              onChange={e => setEditForm(f => ({ ...f, title: e.target.value }))} />
            <TextField label="执业编号" size="small" value={editForm.license_number}
              onChange={e => setEditForm(f => ({ ...f, license_number: e.target.value }))} />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={handleEditClose} sx={{ textTransform: 'none' }}>取消</Button>
          <Button variant="contained" onClick={handleSaveProfile} sx={{ textTransform: 'none', borderRadius: 2 }}>
            保存
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
