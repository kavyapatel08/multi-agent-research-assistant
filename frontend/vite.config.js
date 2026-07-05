import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // During development, proxy /research to the backend
      // so you can run without setting VITE_API_URL
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('react-markdown') || id.includes('remark-gfm')) return 'markdown';
          if (id.includes('react') || id.includes('react-dom')) return 'vendor';
        },
      },
    },
  },
})
