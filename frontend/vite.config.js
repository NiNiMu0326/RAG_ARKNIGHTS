import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 8889,
    host: true,
    strictPort: false,
    proxy: {
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/conversations': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/agent': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },

      '/chunks': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/knowledge-graph': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/stats': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/operators': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/characters': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/stories': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/quick-questions': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },

      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/status': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
