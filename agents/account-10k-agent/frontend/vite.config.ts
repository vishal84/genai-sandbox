import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../app/static',
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/a2a': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/feedback': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
});

