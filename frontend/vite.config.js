import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5175,
    host: true,
    strictPort: false,
    proxy: {
      '/query': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/debug': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/chunks': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/knowledge-graph': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/stats': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/operators': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/characters': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/stories': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/eval': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/health': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/status': {
        target: 'http://localhost:8889',
        changeOrigin: true
      },
      '/agent': {
        target: 'http://localhost:8889',
        changeOrigin: true
      }
    }
  }
})
