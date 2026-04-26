import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5300,
    host: true,
    strictPort: false,
    proxy: {
      '/agent': 'http://localhost:8100',
      '/auth': 'http://localhost:8100',
      '/conversations': 'http://localhost:8100',
      '/health': 'http://localhost:8100',
      '/status': 'http://localhost:8100',
      '/stats': 'http://localhost:8100',
      '/chunks': 'http://localhost:8100',
      '/knowledge-graph': 'http://localhost:8100',
      '/operators': 'http://localhost:8100',
      '/characters': 'http://localhost:8100',
      '/stories': 'http://localhost:8100',
      '/quick-questions': 'http://localhost:8100',
      '/api': 'http://localhost:8100',
    }
  }
})
