import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true,
    proxy: {
      '/translate': 'http://127.0.0.1:8000',
      '/tts': 'http://127.0.0.1:8000',
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
      '/health': 'http://127.0.0.1:8000',
      '/ready': 'http://127.0.0.1:8000',
      '/debug': 'http://127.0.0.1:8000',
      '/diagnostics': 'http://127.0.0.1:8000',
      '/analytics': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/sessions': 'http://127.0.0.1:8000',
      '/metrics': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8000',
    },
  },
});
