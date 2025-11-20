import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    hmr: false, // Disable Hot Module Replacement to prevent random reloads
    watch: null, // Disable file watching to prevent automatic reloads
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/avatars': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/office_layout': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/home_layout': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  }
})

