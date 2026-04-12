/* ================================================
   ARKNIGHTS RAG - API CLIENT (Vue version)
   ================================================ */

// API base URL - using relative path for Vite proxy
// For development, requests are proxied to http://localhost:8888
// For production, set VITE_API_BASE environment variable
const API_BASE = import.meta.env.VITE_API_BASE || ''

export const api = {
  // ===== Auth APIs =====

  async register(account, username, password) {
    const response = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account, username, password })
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || '注册失败')
    }
    return response.json()
  },

  async login(account, password) {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account, password })
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || '登录失败')
    }
    return response.json()
  },

  async getMe() {
    const token = localStorage.getItem('arknights_rag_token')
    const response = await fetch(`${API_BASE}/auth/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!response.ok) throw new Error('未登录')
    return response.json()
  },

  async changePassword(oldPassword, newPassword) {
    const token = localStorage.getItem('arknights_rag_token')
    const response = await fetch(`${API_BASE}/auth/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
    })
    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || '修改密码失败')
    }
    return response.json()
  },

  // ===== Conversation APIs =====

  async listConversations() {
    const token = localStorage.getItem('arknights_rag_token')
    const response = await fetch(`${API_BASE}/conversations`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!response.ok) throw new Error('获取会话列表失败')
    return response.json()
  },

  async getConversationMessages(sessionId) {
    const token = localStorage.getItem('arknights_rag_token')
    const response = await fetch(`${API_BASE}/conversations/${sessionId}/messages`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!response.ok) throw new Error('获取消息失败')
    return response.json()
  },

  async syncConversations(conversations) {
    const token = localStorage.getItem('arknights_rag_token')
    const response = await fetch(`${API_BASE}/conversations/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ conversations })
    })
    if (!response.ok) throw new Error('同步会话失败')
    return response.json()
  },

  async deleteConversation(sessionId) {
    const token = localStorage.getItem('arknights_rag_token')
    const response = await fetch(`${API_BASE}/conversations/${sessionId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!response.ok) throw new Error('删除会话失败')
    return response.json()
  },

  async renameConversation(sessionId, name) {
    const token = localStorage.getItem('arknights_rag_token')
    const response = await fetch(`${API_BASE}/conversations/${sessionId}/rename?name=${encodeURIComponent(name)}`, {
      method: 'PUT',
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!response.ok) throw new Error('重命名失败')
    return response.json()
  },

  // ===== RAG Query APIs =====
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
    const response = await fetch(`${API_BASE}/knowledge-graph`)
    return response.json()
  },

  async getStats() {
    const response = await fetch(`${API_BASE}/stats`)
    return response.json()
  },

  async runEval() {
    const response = await fetch(`${API_BASE}/eval/run`, { method: 'POST' })
    if (!response.ok) throw new Error('Eval run failed')
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
  },

  // ===== AgenticRAG APIs =====

  async createAgentSession() {
    const response = await fetch(`${API_BASE}/agent/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) throw new Error('Failed to create session')
    return response.json()
  },

  async deleteAgentSession(sessionId) {
    const response = await fetch(`${API_BASE}/agent/session/${sessionId}`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error('Failed to delete session')
    return response.json()
  },

  async getModels() {
    const response = await fetch(`${API_BASE}/agent/models`)
    if (!response.ok) throw new Error('Failed to get models')
    return response.json()
  },

  async getAgentSessionMessages(sessionId) {
    const response = await fetch(`${API_BASE}/agent/session/${sessionId}/messages`)
    if (!response.ok) throw new Error('Failed to get messages')
    return response.json()
  },

  /**
   * Agent chat with SSE streaming.
   * @param {string} sessionId - Backend session ID
   * @param {string} message - User message
   * @param {function} onToolCallsStart - Callback for tool_calls_start event
   * @param {function} onToolCallResult - Callback for tool_call_result event
   * @param {function} onAnswerDelta - Callback for answer_delta event
   * @param {function} onAnswerDone - Callback for answer_done event
   * @param {function} onThinkingDelta - Callback for thinking_delta event
   * @param {function} onError - Callback for error event
   * @param {AbortSignal} signal - AbortController signal
   * @returns {Promise<void>}
   */
  async agentChat({ sessionId, message, model, onNewSessionId, onToolCallsStart, onToolCallResult, onAnswerDelta, onAnswerDone, onThinkingDelta, onError, signal }) {
    const body = { session_id: sessionId, message }
    if (model) body.model = model

    const response = await fetch(`${API_BASE}/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })

    // Check if server auto-created a new session (X-New-Session-Id header)
    const newSid = response.headers.get('X-New-Session-Id')
    if (newSid && newSid.trim()) {
      onNewSessionId?.(newSid.trim())
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(err.detail || 'Agent chat failed')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const jsonStr = line.slice(6).trim()
        if (!jsonStr) continue

        try {
          const event = JSON.parse(jsonStr)
          switch (event.type) {
            case 'tool_calls_start':
              onToolCallsStart?.(event)
              break
            case 'tool_call_result':
              onToolCallResult?.(event)
              break
            case 'thinking_delta':
              onThinkingDelta?.(event)
              break
            case 'answer_delta':
              onAnswerDelta?.(event)
              break
            case 'answer_done':
              onAnswerDone?.(event)
              break
            case 'error':
              onError?.(event)
              break
          }
        } catch (e) {
          console.warn('Failed to parse SSE event:', jsonStr, e)
        }
      }
    }

    // Process any remaining data in buffer after stream ends
    if (buffer.trim().startsWith('data: ')) {
      const jsonStr = buffer.trim().slice(6).trim()
      if (jsonStr) {
        try {
          const event = JSON.parse(jsonStr)
          switch (event.type) {
            case 'tool_calls_start': onToolCallsStart?.(event); break
            case 'tool_call_result': onToolCallResult?.(event); break
            case 'thinking_delta': onThinkingDelta?.(event); break
            case 'answer_delta': onAnswerDelta?.(event); break
            case 'answer_done': onAnswerDone?.(event); break
            case 'error': onError?.(event); break
          }
        } catch (e) {
          console.warn('Failed to parse final SSE event:', jsonStr, e)
        }
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
