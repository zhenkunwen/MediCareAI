import { Component, type ReactNode } from 'react';
import { Box, Typography, Button, Paper } from '@mui/material';
import ErrorIcon from '@mui/icons-material/Error';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string }) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', bgcolor: '#F5F7FA', p: 2 }}>
          <Paper sx={{ maxWidth: 480, p: 4, textAlign: 'center', borderRadius: 3 }}>
            <ErrorIcon sx={{ fontSize: 64, color: '#E53935', mb: 2 }} />
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              页面出错了
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              请尝试刷新页面。如果问题持续，请联系管理员。
            </Typography>
            {import.meta.env.DEV && this.state.error && (
              <Typography
                variant="caption"
                sx={{ display: 'block', mb: 2, p: 1, bgcolor: '#FFF3E0', borderRadius: 1, color: '#E65100', textAlign: 'left', fontFamily: 'monospace', fontSize: '0.7rem', wordBreak: 'break-all' }}
              >
                {this.state.error.message}
                {'\n'}
                {this.state.error.stack}
              </Typography>
            )}
            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
              <Button variant="contained" onClick={this.handleReload} sx={{ textTransform: 'none', borderRadius: 2 }}>
                刷新页面
              </Button>
            </Box>
          </Paper>
        </Box>
      );
    }

    return this.props.children;
  }
}
