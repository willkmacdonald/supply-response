import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The browser only ever talks to the FastAPI backend. Fabric, Foundry and
// Work IQ credentials must never reach frontend code.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true
  }
});
