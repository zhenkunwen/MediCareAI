import { Box, Typography, Button, Chip, LinearProgress } from '@mui/material';
import LoginIcon from '@mui/icons-material/Login';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import type { GuestStatus } from '../types/agent';
import { flexRowGap15 } from '../styles/sxUtils';


interface Props {
  status: GuestStatus | null;
  onRegister: () => void;
  onLogin: () => void;
}

export default function GuestBanner({ status, onRegister, onLogin }: Props) {
  if (!status) return null;

  const progress = ((status.max_interactions - status.remaining) / status.max_interactions) * 100;
  const isNearLimit = status.remaining <= 1;

  return (
    <Box sx={{ bgcolor: isNearLimit ? '#FFF3E0' : '#F0FDFA', borderBottom: '1px solid #E2E8F0', px: 2, py: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
        <Box sx={flexRowGap15}>
          <Chip label="访客模式" size="small"
            sx={{ bgcolor: isNearLimit ? '#FFB300' : '#E2E8F0', color: '#1E293B', fontWeight: 500, fontSize: 12 }} />
          <Typography variant="body2" color={isNearLimit ? 'error' : 'text.secondary'}>
            已使用 {status.interaction_count} / {status.max_interactions} 轮对话
          </Typography>
          {isNearLimit && (
            <Typography variant="caption" color="error" sx={{ fontWeight: 500 }}>
              ⚠️ 即将达到上限，请注册以继续
            </Typography>
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button size="small" variant="outlined" startIcon={<LoginIcon fontSize="small" />} onClick={onLogin}
            sx={{ borderColor: '#14B8A6', color: '#14B8A6', textTransform: 'none', borderRadius: 2, '&:hover': { borderColor: '#0D9488', bgcolor: '#F0FDFA' } }}>
            登录
          </Button>
          <Button size="small" variant="contained" startIcon={<PersonAddIcon fontSize="small" />} onClick={onRegister}
            sx={{ bgcolor: '#14B8A6', textTransform: 'none', borderRadius: 2, '&:hover': { bgcolor: '#0D9488' } }}>
            注册
          </Button>
        </Box>
      </Box>

      <LinearProgress variant="determinate" value={progress}
        sx={{ mt: 1, height: 4, borderRadius: 2, bgcolor: '#E2E8F0', '& .MuiLinearProgress-bar': { bgcolor: isNearLimit ? '#E57373' : '#14B8A6', borderRadius: 2 } }} />
    </Box>
  );
}