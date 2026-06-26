import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, List, ListItem, ListItemButton, ListItemAvatar, ListItemText,
  Avatar, Chip, Divider, TextField, IconButton, InputAdornment, Paper, Skeleton,
  CircularProgress, Menu, MenuItem, ListItemIcon,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import ImageIcon from '@mui/icons-material/Image';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DeleteIcon from '@mui/icons-material/Delete';
import UndoIcon from '@mui/icons-material/Undo';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import BadgeIcon from '@mui/icons-material/Verified';
import MedicalServicesIcon from '@mui/icons-material/LocalHospital';
import { API_BASE, getToken } from '../../api/client';
import { getMe } from '../../api/auth';

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: 'Bearer ' + t } : {};
}

interface Conversation {
  id: string; other_name: string; other_avatar?: string; other_role: string;
  last_message?: string; last_message_at?: string;
  unread_count: number;
  other_department?: string;
  other_title?: string;
  other_hospital?: string;
  other_is_verified?: boolean;
  other_license_number?: string;
}

interface Message {
  id: string; sender_role: string; content?: string | null;
  message_type: string; created_at: string; revoked?: boolean;
  media_url?: string | null;
}

function fmtTime(iso: string) {
  if (!iso) return '';
  try { const d = new Date(iso); return isNaN(d.getTime()) ? iso : d.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch { return iso; }
}

export default function PatientMessages() {
  const navigate = useNavigate();
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [ctxMenu, setCtxMenu] = useState<{ anchor: HTMLElement; message: Message } | null>(null);
  const [myName, setMyName] = useState('我');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  const authFetch = useCallback(async (url: string, opts?: RequestInit) => {
    const r = await fetch(url, { ...opts, headers: { ...authHeaders(), ...(opts?.headers || {}) } });
    if (r.status === 401) { navigate('/login'); throw new Error('Unauthorized'); }
    return r;
  }, [navigate]);

  const loadConvs = async () => {
    try {
      const r = await authFetch(`${API_BASE}/patient/messages/conversations`);
      const d = await r.json();
      setConvs(d.items || []);
    } catch (err) { console.error('[PatMsg] convs error:', err); }
    setLoading(false);
  };

  const loadMessages = async (convId: string) => {
    try {
      const r = await authFetch(`${API_BASE}/patient/messages/conversations/${convId}`);
      const d = await r.json();
      setMessages(d.items || []);
      await authFetch(`${API_BASE}/patient/messages/conversations/${convId}/read`, { method: 'PUT' });
      setConvs(prev => prev.map(c => c.id === convId ? { ...c, unread_count: 0 } : c));
    } catch (err) { console.error('[PatMsg] load error:', err); }
  };

  useEffect(() => { loadConvs(); }, []);
  useEffect(() => { getMe().then(u => setMyName(u.full_name?.[0] || '我')).catch(() => {}); }, []);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  useEffect(() => {
    if (!activeConv) return;
    const timer = setInterval(() => loadMessages(activeConv.id), 5000);
    return () => clearInterval(timer);
  }, [activeConv?.id]);

  useEffect(() => {
    const timer = setInterval(() => { loadConvs(); if (activeConv) loadMessages(activeConv.id); }, 30000);
    return () => clearInterval(timer);
  }, [activeConv?.id]);

  const handleSend = async () => {
    if (!input.trim() || !activeConv || sending) return;
    setSending(true);
    const content = input.trim();
    setInput('');
    setMessages(prev => [...prev, { id: 'temp-' + Date.now(), sender_role: 'patient', content, message_type: 'text', created_at: new Date().toISOString() }]);
    try {
      await authFetch(`${API_BASE}/patient/messages/conversations/${activeConv.id}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
    } catch (err) { console.error('[PatMsg] send error:', err); }
    setSending(false);
  };

  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeConv) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const uploadRes = await authFetch(`${API_BASE}/upload`, { method: 'POST', body: formData });
      if (!uploadRes.ok) throw new Error('Upload failed');
      const { url } = await uploadRes.json();
      const tempId = 'temp-' + Date.now();
      setMessages(prev => [...prev, {
        id: tempId, sender_role: 'patient', content: null,
        message_type: 'image', created_at: new Date().toISOString(), media_url: url,
      }]);
      const r = await authFetch(`${API_BASE}/patient/messages/conversations/${activeConv.id}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_type: 'image', media_url: url }),
      });
      if (r.ok) {
        const sent = await r.json();
        setMessages(prev => prev.map(m => m.id === tempId ? { ...m, id: sent.id } : m));
      }
    } catch (err) { console.error('[PatMsg] image error:', err); }
    setUploading(false);
    if (imageInputRef.current) imageInputRef.current.value = '';
  };

  // ── Context menu (right-click on own messages) ──────────────────────
  const handleCtxMenu = (e: React.MouseEvent, m: Message) => {
    if (m.sender_role !== 'patient') return; // only own messages
    e.preventDefault();
    setCtxMenu({ anchor: e.currentTarget as HTMLElement, message: m });
  };

  const closeCtxMenu = () => setCtxMenu(null);

  const handleDeleteMessage = async (msgId: string) => {
    closeCtxMenu();
    setMessages(prev => prev.filter(m => m.id !== msgId));
    try {
      await authFetch(`${API_BASE}/patient/messages/${msgId}`, { method: 'DELETE' });
    } catch (err) { console.error('[PatMsg] delete error:', err); }
  };

  const handleRevokeMessage = async (msgId: string) => {
    closeCtxMenu();
    setMessages(prev => prev.map(m =>
      m.id === msgId ? { ...m, revoked: true, content: null } : m
    ));
    try {
      await authFetch(`${API_BASE}/patient/messages/${msgId}/revoke`, { method: 'POST' });
    } catch (err) { console.error('[PatMsg] revoke error:', err); }
  };

  const handleDeleteConv = async (convId: string) => {
    setConvs(prev => prev.filter(c => c.id !== convId));
    setActiveConv(null);
    try {
      await authFetch(`${API_BASE}/patient/messages/conversations/${convId}`, { method: 'DELETE' });
    } catch (err) { console.error('[PatMsg] delete conv error:', err); }
  };

  // ── Check if message is within 2-minute revoke window ──────────────
  const canRevoke = (m: Message) => {
    if (!m.created_at || m.revoked) return false;
    const diff = Date.now() - new Date(m.created_at).getTime();
    return diff < 120_000; // 2 minutes
  };

  // ── Doctor introduction card ─────────────────────────────────────
  const DoctorIntroCard = ({ conv }: { conv: Conversation }) => (
    <Box sx={{ textAlign: 'center', py: 3, px: 2 }}>
      <Avatar
        src={conv.other_avatar || undefined}
        sx={{ width: 64, height: 64, mx: 'auto', mb: 1.5, bgcolor: conv.other_avatar ? 'transparent' : 'primary.main', fontSize: 28, fontWeight: 700 }}
      >
        {!conv.other_avatar && conv.other_name[0]}
      </Avatar>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>{conv.other_name}</Typography>
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
        {conv.other_department && (
          <Typography variant="body2" color="text.secondary">{conv.other_department}</Typography>
        )}
        {conv.other_title && (
          <Typography variant="body2" color="text.secondary">{conv.other_title}</Typography>
        )}
      </Box>
      {conv.other_hospital && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
          <MedicalServicesIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'text-top' }} />
          {conv.other_hospital}
        </Typography>
      )}
      {conv.other_is_verified && (
        <Chip
          icon={<BadgeIcon />}
          label="已认证"
          size="small"
          color="primary"
          variant="outlined"
          sx={{ mt: 1, height: 22, fontSize: 11 }}
        />
      )}
      {conv.other_license_number && (
        <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 0.5 }}>
          执业编号: {conv.other_license_number}
        </Typography>
      )}
      <Divider sx={{ mt: 2 }} />
    </Box>
  );

  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', p: { xs: 1, sm: 2 }, height: 'calc(100vh - 80px)', display: 'flex', flexDirection: 'column' }}>
      <Paper variant="outlined" sx={{ flexGrow: 1, borderRadius: 3, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {!activeConv ? (
          <>
            <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>我的消息</Typography>
            </Box>
            <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
              {loading ? (
                [1,2,3].map(i => <Skeleton key={i} variant="rectangular" height={60} sx={{ m: 1, borderRadius: 2 }} />)
              ) : convs.length === 0 ? (
                <Box sx={{ p: 4, textAlign: 'center' }}><Typography color="text.secondary">暂无消息</Typography></Box>
              ) : (
                <List disablePadding>
                  {convs.map(c => (
                    <ListItem key={c.id} disablePadding secondaryAction={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        {c.unread_count > 0 && <Chip label={c.unread_count} size="small" color="error" sx={{ minWidth: 20, height: 20 }} />}
                        <IconButton size="small" onClick={(e) => { e.stopPropagation(); handleDeleteConv(c.id); }} sx={{ color: 'text.disabled' }}>
                          <DeleteSweepIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    }>
                      <ListItemButton onClick={() => { setActiveConv(c); setMessages([]); loadMessages(c.id); }} sx={{ py: 1.5 }}>
                        <ListItemAvatar>
                          <Avatar src={c.other_avatar || undefined} sx={{ bgcolor: c.other_avatar ? 'transparent' : 'primary.main' }}>
                            {!c.other_avatar && c.other_name[0]}
                          </Avatar>
                        </ListItemAvatar>
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Typography variant="body2" sx={{ fontWeight: c.unread_count ? 700 : 500, noWrap: true }}>
                              {c.other_name}
                            </Typography>
                            {c.last_message_at && (
                              <Typography variant="caption" sx={{ color: 'text.disabled', fontSize: '0.65rem', ml: 1, whiteSpace: 'nowrap' }}>
                                {fmtTime(c.last_message_at)}
                              </Typography>
                            )}
                          </Box>
                          <Typography variant="caption" sx={{
                            display: 'block', noWrap: true, mt: 0.25,
                            color: c.unread_count ? 'text.primary' : 'text.secondary',
                          }}>
                            {c.last_message || '暂无消息'}
                          </Typography>
                        </Box>
                      </ListItemButton>
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>
          </>
        ) : (
          <>
            <Box sx={{ px: 2, py: 1, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
              <IconButton size="small" onClick={() => setActiveConv(null)}><ArrowBackIcon /></IconButton>
              <Avatar src={activeConv.other_avatar || undefined} sx={{ width: 32, height: 32, bgcolor: activeConv.other_avatar ? 'transparent' : 'primary.main', fontSize: '0.8rem' }}>
                {!activeConv.other_avatar && activeConv.other_name[0]}
              </Avatar>
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{activeConv.other_name}</Typography>
            </Box>
            <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {activeConv && messages.length === 0 && !activeConv.last_message && <DoctorIntroCard conv={activeConv} />}
              {messages.map(m => {
                const isMe = m.sender_role === 'patient';
                return (
                  <Box key={m.id} sx={{ display: 'flex', gap: 1, alignItems: 'flex-end', flexDirection: isMe ? 'row-reverse' : 'row' }}
                    onContextMenu={isMe ? (e) => handleCtxMenu(e, m) : undefined}>
                    {isMe ? (
                      <Avatar sx={{ width: 28, height: 28, bgcolor: '#1976D2', fontSize: '0.75rem' }}>{myName}</Avatar>
                    ) : (
                      <Avatar src={activeConv?.other_avatar || undefined} sx={{ width: 28, height: 28, bgcolor: activeConv?.other_avatar ? 'transparent' : 'primary.main', fontSize: '0.75rem' }}>
                        {!activeConv?.other_avatar ? (activeConv?.other_name?.[0] || '?') : null}
                      </Avatar>
                    )}
                    <Box sx={{ maxWidth: '70%', px: 2, py: 1, borderRadius: 3,
                      bgcolor: m.revoked ? '#F5F5F5' : isMe ? '#1976D2' : '#F0F3F7',
                      color: m.revoked ? '#999' : isMe ? '#fff' : '#333', fontSize: '0.9rem', wordBreak: 'break-word' }}>
                      {m.revoked ? '你撤回了一条消息' : m.message_type === 'image' && m.media_url ? (
                        <Box component="img" src={m.media_url} alt="图片"
                          sx={{ maxWidth: 240, maxHeight: 240, borderRadius: 2, display: 'block', cursor: 'pointer' }}
                          onClick={() => window.open(m.media_url!, '_blank')}
                        />
                      ) : m.content}
                      <Typography variant="caption" sx={{ display: 'block', textAlign: 'right', mt: 0.3, opacity: 0.7, fontSize: '0.65rem' }}>
                        {fmtTime(m.created_at)}
                      </Typography>
                    </Box>
                  </Box>
                );
              })}
              <div ref={messagesEndRef} />
            </Box>
            <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
              <TextField fullWidth size="small" placeholder="输入消息..." value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                slotProps={{
                  input: {
                    startAdornment: (
                      <InputAdornment position="start">
                        <IconButton size="small" onClick={() => imageInputRef.current?.click()} disabled={uploading} sx={{ color: 'text.secondary' }}>
                          {uploading ? <CircularProgress size={20} /> : <ImageIcon />}
                        </IconButton>
                      </InputAdornment>
                    ),
                    endAdornment: <InputAdornment position="end"><IconButton size="small" onClick={handleSend} disabled={!input.trim() || sending} color="primary">{sending ? <CircularProgress size={20} /> : <SendIcon />}</IconButton></InputAdornment>,
                    sx: { borderRadius: 3, bgcolor: '#F5F7FA' },
                  }
                }} />
              <input type="file" accept="image/*" ref={imageInputRef} style={{ display: 'none' }} onChange={handleImageSelect} />
            </Box>
          </>
        )}
      </Paper>

      {/* Right-click context menu */}
      <Menu
        anchorEl={ctxMenu?.anchor}
        open={!!ctxMenu}
        onClose={closeCtxMenu}
        anchorOrigin={{ vertical: 'center', horizontal: 'center' }}
        transformOrigin={{ vertical: 'center', horizontal: 'center' }}
      >
        {ctxMenu && canRevoke(ctxMenu.message) && (
          <MenuItem onClick={() => handleRevokeMessage(ctxMenu.message.id)}>
            <ListItemIcon><UndoIcon fontSize="small" /></ListItemIcon>
            撤回消息
          </MenuItem>
        )}
        {ctxMenu && (
          <MenuItem onClick={() => handleDeleteMessage(ctxMenu.message.id)}>
            <ListItemIcon><DeleteIcon fontSize="small" /></ListItemIcon>
            删除消息
          </MenuItem>
        )}
      </Menu>
    </Box>
  );
}
