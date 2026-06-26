import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, List, ListItem, ListItemText, ListItemIcon,
  Chip, IconButton, Divider, Paper, Alert, Skeleton,
} from '@mui/material';
import {
  CheckCircle as CheckIcon, Warning as WarningIcon,
  Info as InfoIcon, LocalHospital as MedIcon,
} from '@mui/icons-material';
import { API_BASE, authHeaders } from '../../api/client';

interface Notification {
  id: string; type: string; message: string;
  link?: string; read: boolean; time: string;
}

function fmtTime(iso: string) {
  if (!iso || iso.includes('分钟前') || iso.includes('小时前') || iso.includes('昨天')) return iso;
  try { const d = new Date(iso); if (isNaN(d.getTime())) return iso; return d.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return iso; }
}

const typeIcon = (t: string) => {
  switch (t) {
    case 'warning': case 'high': return <WarningIcon color="error" />;
    case 'success': return <CheckIcon color="success" />;
    default: return <InfoIcon color="info" />;
  }
};

export default function NotificationCenter() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const load = () => {
      fetch(`${API_BASE}/doctor/notifications`, { headers: authHeaders() })
        .then(r => r.json())
        .then(data => { if (mounted) setNotifications(data.items || []); })
        .catch(err => console.error('[NotificationCenter] load error:', err))
        .finally(() => { if (mounted) setLoading(false); });
    };
    load();
    const timer = setInterval(load, 30000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);

  const markRead = async (id: string) => {
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
    try {
      await fetch(`${API_BASE}/doctor/notifications/${id}/read`, { method: 'PUT', headers: authHeaders() });
    } catch (err) { console.error('[NotificationCenter] markRead error:', err); }
  };

  const unread = notifications.filter(n => !n.read).length;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>通知中心</Typography>
        {unread > 0 && <Chip label={`${unread} 条未读`} size="small" color="error" />}
      </Box>

      {loading ? (
        <Box sx={{ p: 2 }}>{[1,2,3].map(i => <Skeleton key={i} variant="rectangular" height={60} sx={{ mb: 1, borderRadius: 2 }} />)}</Box>
      ) : notifications.length === 0 ? (
        <Alert severity="info">暂无通知</Alert>
      ) : (
        <Paper variant="outlined">
          <List disablePadding>
            {notifications.map((n, i) => (
              <Box key={n.id}>
                {i > 0 && <Divider component="li" />}
                <ListItem
                  secondaryAction={
                    !n.read ? (
                      <IconButton edge="end" size="small" onClick={() => markRead(n.id)}>
                        <CheckIcon fontSize="small" />
                      </IconButton>
                    ) : null
                  }
                  sx={{ bgcolor: n.read ? 'transparent' : 'action.hover', cursor: n.link ? 'pointer' : 'default' }}
                  onClick={() => { if (n.link) navigate(n.link); markRead(n.id); }}
                >
                  <ListItemIcon>{typeIcon(n.type)}</ListItemIcon>
                  <ListItemText
                    primary={n.message}
                    secondary={fmtTime(n.time)}
                    slotProps={{ primary: { fontWeight: n.read ? 400 : 600 } }}
                  />
                </ListItem>
              </Box>
            ))}
          </List>
        </Paper>
      )}
    </Box>
  );
}
