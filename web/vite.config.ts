import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The Python API (NASA Project/api) runs on port 8000; proxy it so the app can call /api/... directly.
export default defineConfig({
  plugins: [react()],
  // three.js alone is ~600 kB minified; one bundle is fine for this app.
  build: { chunkSizeWarningLimit: 1500 },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
