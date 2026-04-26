import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5300,
    host: true,
    strictPort: false,
    proxy: {
      '/agent': 'http://localhost:8010',
      '/auth': 'http://localhost:8010',
      '/conversations': 'http://localhost:8010',
      '/health': 'http://localhost:8010',
      '/status': 'http://localhost:8010',
      '/stats': 'http://localhost:8010',
      '/chunks': 'http://localhost:8010',
      '/knowledge-graph': 'http://localhost:8010',
      '/operators': 'http://localhost:8010',
      '/characters': 'http://localhost:8010',
      '/stories': 'http://localhost:8010',
      '/quick-questions': 'http://localhost:8010',
      '/api': 'http://localhost:8010',
    }
  }
})
