import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    hmr: { clientPort: 443 },
    allowedHosts: 'all',
    proxy: {
      '/ws': {
        target: 'http://backend:8000',
        ws: true,
        changeOrigin: true,
      },
      '/roi': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/feed': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    }
  }
})