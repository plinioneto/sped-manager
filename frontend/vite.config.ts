import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/kpis': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/consultor': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
    allowedHosts: ['.ngrok-free.dev', '.ngrok-free.app'],
  },
})
