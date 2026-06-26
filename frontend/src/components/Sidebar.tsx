import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Typography,
  IconButton,
  Divider,
  Button,
  Collapse,
  Badge,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ChatIcon from '@mui/icons-material/Chat';
import HealingIcon from '@mui/icons-material/Healing';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import MedicationIcon from '@mui/icons-material/Medication';
import MessageIcon from '@mui/icons-material/Message';
import { API_BASE } from '../api/client';
import { getToken } from '../api/client';
import type { ChatSession } from '../types/agent';

interface Props {
  sessions: ChatSession[];
  currentSessionId?: string;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  drawerWidth?: number;
}

const DRAWER_WIDTH = 260;

function groupSessionsByDate(sessions: ChatSession[]): Record<string, ChatSession[]> {
  const groups: Record<string, ChatSession[]> = {};
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();

  for (const s of sessions) {
    const d = new Date(s.updated_at);
    const dateStr = d.toDateString();
    let label = d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    if (dateStr === today) label = '今天';
    else if (dateStr === yesterday) label = '昨天';

    if (!groups[label]) groups[label] = [];
    groups[label].push(s);
  }
  return groups;
}

export default function Sidebar({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewChat,
  mobileOpen,
  onCloseMobile,
  drawerWidth = DRAWER_WIDTH,
}: Props) {
  const [historyOpen, setHistoryOpen] = useState(true);
  const [patMsgUnread, setPatMsgUnread] = useState(0);
  const grouped = groupSessionsByDate(sessions);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch(`${API_BASE}/patient/messages/unread`, { headers: { Authorization: 'Bearer ' + getToken() } });
        const d = await r.json();
        setPatMsgUnread(d.unread_total || 0);
      } catch {}
    };
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  const drawerContent = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>🩺 医智云·AI</Typography>
        <IconButton size="small" onClick={onNewChat} sx={{ color: 'primary.main' }}>
          <AddIcon />
        </IconButton>
      </Box>

      <Divider sx={{ borderColor: '#E2E8F0' }} />

      <Box sx={{ p: 1.5 }}>
        <Button fullWidth variant="contained" startIcon={<AddIcon />} onClick={onNewChat}
          sx={{ borderRadius: 2, textTransform: 'none', bgcolor: 'primary.main', '&:hover': { bgcolor: 'primary.dark' } }}>
          新建会话
        </Button>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', px: 1 }}>
        <ListItemButton onClick={() => setHistoryOpen(!historyOpen)} sx={{ borderRadius: 2, py: 0.5 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary', flex: 1 }}>
            🗂️ 会话历史
          </Typography>
          {historyOpen ? <ExpandLessIcon sx={{ color: 'text.secondary' }} /> : <ExpandMoreIcon sx={{ color: 'text.secondary' }} />}
        </ListItemButton>

        <Collapse in={historyOpen}>
          <List dense sx={{ py: 0 }}>
            {Object.entries(grouped).map(([label, items]) => (
              <Box key={label}>
                <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 0.5, display: 'block', fontSize: 11 }}>
                  {label}
                </Typography>
                {items.map((s) => (
                  <ListItem key={s.id} disablePadding sx={{ mb: 0.5 }}>
                    <ListItemButton selected={s.id === currentSessionId} onClick={() => onSelectSession(s.id)}
                      sx={{
                        borderRadius: 2, py: 0.75,
                        '&.Mui-selected': { bgcolor: '#E2E8F0', '&:hover': { bgcolor: '#E2E8F0' } },
                        '&:hover': { bgcolor: '#F0FDFA' },
                      }}>
                      <ChatIcon sx={{ fontSize: 16, color: 'text.secondary', mr: 1 }} />
                      <ListItemText primary={s.title || '新对话'}
                        slotProps={{ primary: { variant: 'body2', noWrap: true, sx: { color: s.id === currentSessionId ? 'text.primary' : 'text.secondary', fontWeight: s.id === currentSessionId ? 500 : 400 } } }}
                      />
                    </ListItemButton>
                  </ListItem>
                ))}
              </Box>
            ))}
            {sessions.length === 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 1, display: 'block' }}>
                暂无会话记录
              </Typography>
            )}
          </List>
        </Collapse>
      </Box>

      <Divider sx={{ borderColor: '#E2E8F0' }} />

      <Box sx={{ p: 1 }}>
        <List dense>
          <ListItem disablePadding>
            <ListItemButton sx={{ borderRadius: 2, py: 0.75 }} onClick={() => navigate('/patient/messages')}>
              <Badge badgeContent={patMsgUnread} color="error" max={99}>
                <MessageIcon sx={{ fontSize: 18, color: 'primary.main', mr: 1.5 }} />
              </Badge>
              <ListItemText primary="💬 消息" slotProps={{ primary: { variant: 'body2', sx: { color: 'text.primary' } } }} />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton sx={{ borderRadius: 2, py: 0.75 }} onClick={() => navigate('/health')}>
              <HealingIcon sx={{ fontSize: 18, color: 'primary.main', mr: 1.5 }} />
              <ListItemText primary="📊 健康档案" slotProps={{ primary: { variant: 'body2', sx: { color: 'text.primary' } } }} />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton sx={{ borderRadius: 2, py: 0.75 }} onClick={() => navigate('/followups')}>
              <CalendarMonthIcon sx={{ fontSize: 18, color: 'primary.main', mr: 1.5 }} />
              <ListItemText primary="📅 随访计划" slotProps={{ primary: { variant: 'body2', sx: { color: 'text.primary' } } }} />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton sx={{ borderRadius: 2, py: 0.75 }} onClick={() => navigate('/medications')}>
              <MedicationIcon sx={{ fontSize: 18, color: 'primary.main', mr: 1.5 }} />
              <ListItemText primary="💊 用药提醒" slotProps={{ primary: { variant: 'body2', sx: { color: 'text.primary' } } }} />
            </ListItemButton>
          </ListItem>
        </List>
      </Box>
    </Box>
  );

  return (
    <>
      <Drawer variant="permanent" sx={{
        width: drawerWidth, flexShrink: 0, display: { xs: 'none', md: 'block' },
        '& .MuiDrawer-paper': { width: drawerWidth, boxSizing: 'border-box', borderRight: '1px solid #E2E8F0', bgcolor: '#F0FDFA' },
      }} open>
        {drawerContent}
      </Drawer>
      <Drawer variant="temporary" open={mobileOpen} onClose={onCloseMobile} ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': { width: drawerWidth, boxSizing: 'border-box', borderRight: '1px solid #E2E8F0', bgcolor: '#F0FDFA' },
        }}>
        {drawerContent}
      </Drawer>
    </>
  );
}
