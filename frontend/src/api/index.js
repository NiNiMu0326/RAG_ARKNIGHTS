// API base URL - can be configured via environment variable VITE_API_BASE
// Default to empty string (use relative path for Vite proxy)
const API_BASE = import.meta.env.VITE_API_BASE || ''

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
    // Use polling instead of SSE (Cloudflare Tunnel buffers SSE)
    // 1. Start evaluation
    const startResp = await fetch(`${API_BASE}/eval/start`, { method: 'POST' })
    if (!startResp.ok) throw new Error('Failed to start evaluation')
    const startData = await startResp.json()
    if (startData.status === 'already_running') throw new Error('评估已在运行中')

    // 2. Poll progress every 2s until done
    while (true) {
      await new Promise(r => setTimeout(r, 2000))
      const progResp = await fetch(`${API_BASE}/eval/progress`)
      if (!progResp.ok) continue
      const prog = await progResp.json()

      if (!prog.running) {
        if (prog.error) throw new Error(prog.error)
        if (prog.results) return prog.results
        throw new Error('评估异常结束')
      }
    }
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