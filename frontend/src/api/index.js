// API base URL - can be configured via environment variable VITE_API_BASE
// Default to localhost:8000 if not set
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export const api = {
  async query(question, options = {}) {
    const response = await fetch(`${API_BASE}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, ...options })
    })
    if (!response.ok) throw new Error('Query failed')
    return response.json()
  },

  async getStatus() {
    const response = await fetch(`${API_BASE}/status`)
    return response.json()
  },

  async getChunks(collection = 'operators') {
    const response = await fetch(`${API_BASE}/chunks/${collection}`)
    return response.json()
  },

  async getChunk(collection, filename) {
    const response = await fetch(`${API_BASE}/chunks/${collection}/${filename}`)
    return response.json()
  },

  async getGraphData() {
    const response = await fetch(`${API_BASE}/graph`)
    return response.json()
  },

  async getStats() {
    const response = await fetch(`${API_BASE}/stats`)
    return response.json()
  },

  async runDebugStep(question, step, options = {}) {
    const response = await fetch(`${API_BASE}/debug/step`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, step, ...options })
    })
    if (!response.ok) throw new Error('Debug step failed')
    return response.json()
  },

  async runEval() {
    const response = await fetch(`${API_BASE}/eval`)
    if (!response.ok) throw new Error('Evaluation failed')
    return response.json()
  }
}

export function formatTime(date) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(date)
}

export function escapeHtml(str) {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

export function debounce(fn, delay = 300) {
  let timeout
  return (...args) => {
    clearTimeout(timeout)
    timeout = setTimeout(() => fn(...args), delay)
  }
}