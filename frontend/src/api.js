/* ================================================
   ARKNIGHTS RAG - API CLIENT (Vue version)
   ================================================ */

// API base URL - using relative path for Vite proxy
// For development, requests are proxied to http://localhost:8888
// For production, set VITE_API_BASE environment variable
const API_BASE = import.meta.env.VITE_API_BASE || ''

export const api = {
  async query(question, options = {}, signal = null) {
    const fetchOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, ...options })
    }
    if (signal) {
      fetchOptions.signal = signal
    }
    const response = await fetch(`${API_BASE}/query`, fetchOptions)
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

  async runEvaluation() {
    const response = await fetch(`${API_BASE}/eval`)
    if (!response.ok) throw new Error('Evaluation failed')
    return response.json()
  },

  // Alias for backward compatibility
  async runEval() {
    return this.runEvaluation()
  },

  async getStats() {
    const response = await fetch(`${API_BASE}/stats`)
    return response.json()
  },

  async debugStep(question, step, options = {}) {
    const response = await fetch(`${API_BASE}/debug/step`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, step, ...options })
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Debug step failed')
    }
    return response.json()
  },

  async getOperators() {
    const response = await fetch(`${API_BASE}/operators`)
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Failed to get operators')
    }
    return response.json()
  },

  async getCharacters() {
    const response = await fetch(`${API_BASE}/characters`)
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Failed to get characters')
    }
    return response.json()
  },

  async getStories() {
    const response = await fetch(`${API_BASE}/stories`)
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Failed to get stories')
    }
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

export function debounce(fn, delay = 300) {
  let timeout
  return (...args) => {
    clearTimeout(timeout)
    timeout = setTimeout(() => fn(...args), delay)
  }
}

export function escapeHtml(str) {
  if (!str) return ''
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

export function truncate(str, len = 100) {
  if (str.length <= len) return str
  return str.slice(0, len) + '...'
}
