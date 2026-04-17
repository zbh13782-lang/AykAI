import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies /api requests to the Go backend so that the browser
// can reach the auth + AI endpoints without CORS gymnastics.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9030',
        changeOrigin: true,
      },
    },
  },
})
