import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ command }) => {
  if (command === 'build' && process.env.VITE_SYNTHETIC_DEMO === 'true') {
    throw new Error('Synthetic demo cannot be compiled into a release. Use pnpm dev:web and ?demo=1.');
  }
  const target = process.env.CASHPROOF_DEV_BACKEND || 'http://127.0.0.1:8000';
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173, strictPort: true,
      // Test harnesses and generated reports must not reload an authenticated UI.
      watch: { ignored: ['**/tests/**', '**/dist/**', '**/__pycache__/**'] },
      proxy: { '/api': { target, changeOrigin: true }, '/health': { target, changeOrigin: true } },
    },
    build: { sourcemap: false },
  };
});
