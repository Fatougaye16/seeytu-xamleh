import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The FastAPI backend (`fastapi dev` in backend/) listens on :8000.
// Proxying keeps the browser on one origin, so the backend needs no CORS setup in dev.
const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: BACKEND_URL, changeOrigin: true },
      '/users': { target: BACKEND_URL, changeOrigin: true },
    },
  },
})
