import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, List, ListItem, ListItemButton, ListItemAvatar, ListItemText,
  Avatar, Chip, Divider, TextField, IconButton, InputAdornment, Paper, Badge, Skeleton, Alert,
  CircularProgress, Menu, MenuItem, ListItemIcon,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import ImageIcon from '@mui/icons-material/Image';
import SearchIcon from '@mui/icons-material/Search';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DeleteIcon from '@mui/icons-material/Delete';
import UndoIcon from '@mui/icons-material/Undo';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import { API_BASE, authHeaders } from '../../api/client';
import { getMe } from '../../api/auth';
import { flexRowGap1, flexRowBetweenMb2 } from '../../styles/sxUtils';

interface Conversation {
  id: string; case_id?: string; other_name: string; other_avatar?: string;
  last_message?: string; last_message_at?: string;
  unread_count: number; status: string;
}

interface Message {
  id: string; sender_role: string; content?: string | null;
  message_type: string; created_at: string; revoked?: boolean; is_read: boolean;
  media_url?: string | null;
}

function fmtTime(iso: string) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

function ConversationList({ convs, activeId, onSelect, onDelete, loading }: {
  convs: Conversation[]; activeId?: string;
  onSelect: (c: Conversation) => void; onDelete: (id: string) => void; loading: boolean;
}) {
  const [search, setSearch] = useState('');
  const filtered = search ? convs.filter(c => c.other_name.includes(search)) : convs;

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, pb: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>医患消息</Typography>
        <TextField
          size="small" placeholder="搜索患者..." value={search}
          onChange={e => setSearch(e.target.value)}
          slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> } }}
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2, bgcolor: '#F5F7FA' } }}
        />
      </Box>
      <Divider />
      <List sx={{ flexGrow: 1, overflow: 'auto', py: 0 }}>
        {loading ? (
          [1,2,3,4].map(i => (
            <ListItem key={i}><Skeleton variant="rectangular" height={60} sx={{ width: '100%', borderRadius: 2 }} /></ListItem>
          ))
        ) : filtered.length === 0 ? (
          <Box sx={{ p: 3, textAlign: 'center' }}><Typography variant="body2" color="text.secondary">暂无会话</Typography></Box>
        ) : filtered.map(c => (
          <ListItem key={c.id} disablePadding secondaryAction={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              {c.unread_count > 0 && <Chip label={c.unread_count} size="small" color="error" sx={{ minWidth: 20, height: 20, fontSize: '0.7rem' }} />}
              <IconButton size="small" onClick={(e) => { e.stopPropagation(); onDelete(c.id); }} sx={{ color: 'text.disabled' }}>
                <DeleteSweepIcon fontSize="small" />
              </IconButton>
            </Box>
          }>
            <ListItemButton selected={c.id === activeId} onClick={() => onSelect(c)} sx={{ py: 1.5, px: 2 }}>
              <ListItemAvatar>
                <Avatar src={c.other_avatar || undefined} sx={{ bgcolor: c.other_avatar ? 'transparent' : 'primary.main', width: 40, height: 40, fontSize: '0.9rem' }}>
                  {!c.other_avatar && (c.other_name[0])}
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
    </Box>
  );
}

const POLL_INTERVAL = 5000;

export default function DoctorMessages() {
  const navigate = useNavigate();
  const [convs, setConvs] = useState<Conversation[]>([]);

  const authFetch = useCallback(async (url: string, opts?: RequestInit) => {
    const r = await fetch(url, { ...opts, headers: { ...authHeaders(), ...(opts?.headers || {}) } });
    if (r.status === 401) { navigate('/login'); throw new Error('Unauthorized'); }
    return r;
  }, [navigate]);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [ctxMenu, setCtxMenu] = useState<{ anchor: HTMLElement; message: Message } | null>(null);
  const [myAvatar, setMyAvatar] = useState<string | undefined>(undefined);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval>>();
  const imageInputRef = useRef<HTMLInputElement>(null);

  // Fetch conversations
  const loadConvs = async () => {
    try {
      const r = await authFetch(`${API_BASE}/doctor/messages/conversations`);
      const data = await r.json();
      setConvs(data.items || []);
    } catch (err) { console.error('[Msg] convs error:', err); }
    setLoading(false);
  };

  // Fetch messages for active conversation
  const loadMessages = async (convId: string) => {
    try {
      const r = await authFetch(`${API_BASE}/doctor/messages/conversations/${convId}`);
      const data = await r.json();
      setMessages(data.items || []);
      // Mark read
      await authFetch(`${API_BASE}/doctor/messages/conversations/${convId}/read`, { method: 'PUT' });
      // Update local unread count
      setConvs(prev => prev.map(c => c.id === convId ? { ...c, unread_count: 0 } : c));
    } catch (err) { console.error('[Msg] load error:', err); }
  };

  useEffect(() => { loadConvs(); }, []);
  useEffect(() => { getMe().then(u => setMyAvatar(u.avatar_url)).catch(() => {}); }, []);

  // Poll for new messages
  useEffect(() => {
    if (!activeConv) return;
    pollRef.current = setInterval(() => { loadMessages(activeConv.id); }, POLL_INTERVAL);
    return () => clearInterval(pollRef.current);
  }, [activeConv?.id]);

  // Auto-poll conversations list
  useEffect(() => {
    const timer = setInterval(() => {
      loadConvs();
      if (activeConv) loadMessages(activeConv.id);
    }, 30000);
    return () => clearInterval(timer);
  }, [activeConv?.id]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const handleSelectConv = (c: Conversation) => {
    setActiveConv(c);
    loadMessages(c.id);
  };

  const handleSend = async () => {
    if (!input.trim() || !activeConv || sending) return;
    setSending(true);
    const content = input.trim();
    setInput('');
    // Optimistic update
    const tempId = 'temp-' + Date.now();
    setMessages(prev => [...prev, { id: tempId, sender_role: 'doctor', content, message_type: 'text', created_at: new Date().toISOString(), is_read: false }]);
    try {
      const r = await authFetch(`${API_BASE}/doctor/messages/conversations/${activeConv.id}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      if (r.ok) {
        const sent = await r.json();
        setMessages(prev => prev.map(m => m.id === tempId ? { ...m, id: sent.id } : m));
      }
    } catch (err) { console.error('[Msg] send error:', err); }
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
      // Send as image message
      const tempId = 'temp-' + Date.now();
      setMessages(prev => [...prev, {
        id: tempId, sender_role: 'doctor', content: null,
        message_type: 'image', created_at: new Date().toISOString(),
        is_read: false, media_url: url,
      }]);
      const r = await authFetch(`${API_BASE}/doctor/messages/conversations/${activeConv.id}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_type: 'image', media_url: url }),
      });
      if (r.ok) {
        const sent = await r.json();
        setMessages(prev => prev.map(m => m.id === tempId ? { ...m, id: sent.id } : m));
      }
    } catch (err) { console.error('[Msg] image error:', err); }
    setUploading(false);
    // Reset input so same file can be picked again
    if (imageInputRef.current) imageInputRef.current.value = '';
  };

  // ── Context menu (right-click on own messages) ──────────────────────
  const handleCtxMenu = (e: React.MouseEvent, m: Message) => {
    if (m.sender_role !== 'doctor') return;
    e.preventDefault();
    setCtxMenu({ anchor: e.currentTarget as HTMLElement, message: m });
  };

  const closeCtxMenu = () => setCtxMenu(null);

  const handleDeleteMessage = async (msgId: string) => {
    closeCtxMenu();
    setMessages(prev => prev.filter(m => m.id !== msgId));
    try {
      await authFetch(`${API_BASE}/doctor/messages/${msgId}`, { method: 'DELETE' });
    } catch (err) { console.error('[Msg] delete error:', err); }
  };

  const handleRevokeMessage = async (msgId: string) => {
    closeCtxMenu();
    setMessages(prev => prev.map(m =>
      m.id === msgId ? { ...m, revoked: true, content: null } : m
    ));
    try {
      await authFetch(`${API_BASE}/doctor/messages/${msgId}/revoke`, { method: 'POST' });
    } catch (err) { console.error('[Msg] revoke error:', err); }
  };

  const handleDeleteConv = async (convId: string) => {
    setConvs(prev => prev.filter(c => c.id !== convId));
    setActiveConv(null);
    try {
      await authFetch(`${API_BASE}/doctor/messages/conversations/${convId}`, { method: 'DELETE' });
    } catch (err) { console.error('[Msg] delete conv error:', err); }
  };

  const canRevoke = (m: Message) => {
    if (!m.created_at || m.revoked) return false;
    const diff = Date.now() - new Date(m.created_at).getTime();
    return diff < 120_000;
  };

  return (
    <Box sx={{ display: 'flex', height: 'calc(100vh - 100px)', gap: 1 }}>
      {/* Left panel: conversation list */}
      <Paper variant="outlined" sx={{ width: 340, flexShrink: 0, borderRadius: 3, overflow: 'hidden' }}>
        <ConversationList convs={convs} activeId={activeConv?.id} onSelect={handleSelectConv} onDelete={handleDeleteConv} loading={loading} />
      </Paper>

      {/* Right panel: chat window */}
      <Paper variant="outlined" sx={{ flexGrow: 1, borderRadius: 3, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {!activeConv ? (
          <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography variant="body1" color="text.secondary">选择一个会话开始聊天</Typography>
          </Box>
        ) : (
          <>
            {/* Header */}
            <Box sx={{ px: 2.5, py: 1.5, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Avatar src={activeConv.other_avatar || undefined} sx={{ bgcolor: activeConv.other_avatar ? 'transparent' : 'primary.main', width: 36, height: 36, fontSize: '0.85rem' }}>
                {!activeConv.other_avatar && activeConv.other_name[0]}
              </Avatar>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{activeConv.other_name}</Typography>
                <Typography variant="caption" color="text.secondary">{activeConv.case_id ? '关联病例' : ''}</Typography>
              </Box>
            </Box>

            {/* Messages */}
            <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {messages.map(m => {
                const isMe = m.sender_role === 'doctor';
                return (
                  <Box key={m.id} sx={{ display: 'flex', gap: 1, alignItems: 'flex-end', flexDirection: isMe ? 'row-reverse' : 'row' }}
                    onContextMenu={isMe ? (e) => handleCtxMenu(e, m) : undefined}>
                    {isMe ? (
                      <Avatar src={myAvatar || undefined} sx={{ width: 28, height: 28, bgcolor: myAvatar ? 'transparent' : 'primary.main', fontSize: '0.75rem' }}>
                        {!myAvatar ? '我' : null}
                      </Avatar>
                    ) : (
                      <Avatar sx={{ width: 28, height: 28, bgcolor: 'primary.main', fontSize: '0.75rem' }}>{activeConv?.other_name?.[0] || '?'}</Avatar>
                    )}
                    <Box sx={{
                      maxWidth: '70%', px: 2, py: 1, borderRadius: 3,
                      bgcolor: m.revoked ? '#F5F5F5' : isMe ? '#1976D2' : '#F0F3F7',
                      color: m.revoked ? '#999' : isMe ? '#fff' : '#333',
                      fontSize: '0.9rem', wordBreak: 'break-word',
                    }}>
                      {m.revoked ? '你撤回了一条消息' : m.message_type === 'image' && m.media_url ? (
                        <Box component="img" src={m.media_url} alt="图片"
                          sx={{ maxWidth: 240, maxHeight: 240, borderRadius: 2, display: 'block', cursor: 'pointer' }}
                          onClick={() => window.open(m.media_url!, '_blank')}
                        />
                      ) : m.content}
                      <Typography variant="caption" sx={{
                        display: 'block', textAlign: 'right', mt: 0.3, opacity: 0.7,
                        fontSize: '0.65rem', color: m.revoked ? '#999' : isMe ? 'rgba(255,255,255,0.8)' : '#999',
                      }}>
                        {fmtTime(m.created_at)}
                      </Typography>
                    </Box>
                  </Box>
                );
              })}
              <div ref={messagesEndRef} />
            </Box>

            {/* Input */}
            <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
              <TextField
                fullWidth size="small" placeholder="输入消息..." value={input}
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
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton size="small" onClick={handleSend} disabled={!input.trim() || sending} color="primary">
                          {sending ? <CircularProgress size={20} /> : <SendIcon />}
                        </IconButton>
                      </InputAdornment>
                    ),
                    sx: { borderRadius: 3, bgcolor: '#F5F7FA' },
                  }
                }}
              />
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
