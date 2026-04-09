import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: true,
    strictPort: false,
    proxy: {
      '/query': {
        target: 'http://localhost:8888',
        changeOrigin: true
      },
      '/debug': {
        target: 'http://localhost:8888',
        changeOrigin: true
      },
      '/chunks': {
        target: 'http://localhost:8888',
        changeOrigin: true
      },
      '/graph': {
        target: 'http://localhost:8888',
        changeOrigin: true
      },
      '/stats': {
        target: 'http://localhost:8888',
        changeOrigin: true
      },
      '/operators': {
        target: 'http://localhost:8888',
        changeOrigin: true
      },
      '/characters': {
        target: 'http://localhost:8888',
        changeOrigin: true
      },
      '/stories': {
        target: 'http://localhost:8888',
        changeOrigin: true
      },
      '/eval': {
        target: 'http://localhost:8888',
        changeOrigin: true
      },
      '/health': {
        target: 'http://localhost:8888',
        changeOrigin: true
      },
      '/status': {
        target: 'http://localhost:8888',
        changeOrigin: true
      }
    }
  }
})
