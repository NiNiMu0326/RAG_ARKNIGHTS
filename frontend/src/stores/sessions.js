import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api'
import { useAuthStore } from './auth'

export const useSessionStore = defineStore('sessions', () => {
  const sessions = ref({})
  const currentSessionId = ref(null)
  const lastActiveSessionId = ref(null)
  // Backend agent session ID mapping: frontendSessionId -> backendSessionId
  const backendSessionIds = ref({})

  function _isEmptySession(s) {
    return s.isEmpty || !s.name || s.name.trim() === '' ||
      (s.name === '新会话' && (!s.messages || s.messages.length === 0))
  }

  function _loadFromLocalStorage() {
    const saved = localStorage.getItem('arknights_rag_sessions')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        Object.keys(parsed).forEach(id => {
          if (_isEmptySession(parsed[id])) delete parsed[id]
        })
        sessions.value = parsed
      } catch (e) {
        console.warn('Failed to parse sessions from localStorage:', e)
        sessions.value = {}
      }
    }
  }

  async function loadSessions() {
    const authStore = useAuthStore()
    if (authStore.isLoggedIn) {
      try {
        const res = await api.listConversations()
        const newSessions = {}
        for (const conv of res.conversations) {
          let messages = []
          try {
            const msgRes = await api.getConversationMessages(conv.session_id)
            messages = msgRes.messages.map(m => ({
              role: m.role,
              content: m.content,
              timestamp: new Date(m.created_at).getTime(),
              ...(m.metadata || {})
            }))
          } catch (e) {
            console.warn(`Failed to load messages for ${conv.session_id}:`, e)
          }
          newSessions[conv.session_id] = {
            id: conv.session_id,
            name: conv.name,
            messages,
            createdAt: new Date(conv.created_at).getTime(),
            updatedAt: new Date(conv.updated_at).getTime(),
          }
        }
        sessions.value = newSessions
      } catch (e) {
        console.warn('Failed to load sessions from server, falling back to localStorage:', e)
        _loadFromLocalStorage()
      }
    } else {
      _loadFromLocalStorage()
    }

    // Don't auto-select a session — show welcome page on page load
    // Sessions are listed in sidebar for user to click
    if (Object.keys(sessions.value).length === 0) {
      createNewSession()
    }
  }

  async function saveSessions() {
    const toSave = {}
    Object.keys(sessions.value).forEach(id => {
      if (!_isEmptySession(sessions.value[id])) {
        toSave[id] = sessions.value[id]
      }
    })

    // Always save to localStorage as cache
    localStorage.setItem('arknights_rag_sessions', JSON.stringify(toSave))
    if (currentSessionId.value && !_isEmptySession(sessions.value[currentSessionId.value])) {
      localStorage.setItem('arknights_rag_last_session', currentSessionId.value)
    }

    // Sync to server if logged in
    const authStore = useAuthStore()
    if (authStore.isLoggedIn) {
      try {
        const convs = Object.values(toSave).map(s => ({
          session_id: s.id,
          name: s.name || '',
          created_at: new Date(s.createdAt).toISOString(),
          updated_at: new Date(s.updatedAt).toISOString(),
          messages: (s.messages || []).map(m => ({
            role: m.role,
            content: m.content,
            metadata: {
              timestamp: m.timestamp,
              ...(m.results ? { results: m.results } : {}),
              ...(m.round ? { round: m.round } : {}),
              ...(m.calls ? { calls: m.calls } : {})
            },
            created_at: new Date(m.timestamp).toISOString(),
          }))
        }))
        await api.syncConversations(convs)
      } catch (e) {
        console.warn('Failed to sync sessions to server:', e)
      }
    }
  }

  async function createNewSession() {
    // If current session is already empty, reuse it instead of creating a new one
    const current = sessions.value[currentSessionId.value]
    if (current && _isEmptySession(current)) {
      return currentSessionId.value
    }

    // Create frontend session with isEmpty flag (won't show in sidebar until first message)
    const id = 'session_' + Date.now()
    sessions.value[id] = {
      id,
      name: '',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
      isEmpty: true
    }
    currentSessionId.value = id
    lastActiveSessionId.value = id

    // Create backend agent session
    try {
      const result = await api.createAgentSession()
      backendSessionIds.value[id] = result.session_id
      localStorage.setItem('arknights_rag_backend_sessions', JSON.stringify(backendSessionIds.value))
    } catch (e) {
      console.error('Failed to create backend session:', e)
    }

    saveSessions()
    return id
  }

  function getBackendSessionId(frontendId) {
    return backendSessionIds.value[frontendId || currentSessionId.value]
  }

  async function deleteSession(sessionId) {
    // Delete backend agent session
    const backendId = backendSessionIds.value[sessionId]
    if (backendId) {
      try { await api.deleteAgentSession(backendId) } catch (e) { console.warn('Failed to delete backend session:', e) }
      delete backendSessionIds.value[sessionId]
      localStorage.setItem('arknights_rag_backend_sessions', JSON.stringify(backendSessionIds.value))
    }

    // Delete from server if logged in
    const authStore = useAuthStore()
    if (authStore.isLoggedIn) {
      try { await api.deleteConversation(sessionId) } catch (e) { console.warn('Failed to delete conversation from server:', e) }
    }

    delete sessions.value[sessionId]
    if (currentSessionId.value === sessionId) {
      const remaining = Object.keys(sessions.value).sort(
        (a, b) => sessions.value[b].updatedAt - sessions.value[a].updatedAt
      )
      if (remaining.length > 0) {
        currentSessionId.value = remaining[0]
      } else {
        createNewSession()
      }
    }
    if (lastActiveSessionId.value === sessionId) {
      lastActiveSessionId.value = currentSessionId.value
    }
    saveSessions()
    return true
  }

  function switchSession(sessionId) {
    if (sessions.value[sessionId]) {
      currentSessionId.value = sessionId
      lastActiveSessionId.value = sessionId
      localStorage.setItem('arknights_rag_last_session', sessionId)
    }
  }

  async function renameSession(sessionId, newName) {
    if (sessions.value[sessionId]) {
      sessions.value[sessionId].name = newName
      sessions.value[sessionId].updatedAt = Date.now()
      // Rename on server if logged in
      const authStore = useAuthStore()
      if (authStore.isLoggedIn) {
        try { await api.renameConversation(sessionId, newName) } catch (e) { console.warn('Failed to rename on server:', e) }
      }
      saveSessions()
    }
  }

  function addMessage(role, content, extra = {}) {
    let targetSessionId = currentSessionId.value

    // If current session doesn't exist, create it
    if (!targetSessionId || !sessions.value[targetSessionId]) {
      targetSessionId = 'session_' + Date.now()
      sessions.value[targetSessionId] = {
        id: targetSessionId,
        name: '',
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now()
      }
      currentSessionId.value = targetSessionId
    }

    const session = sessions.value[targetSessionId]
    if (session) {
      // Use first user message as session name
      if (role === 'user' && session.messages.length === 0) {
        const trimmed = content.trim()
        if (trimmed.length > 0) {
          session.name = trimmed.length > 6 ? trimmed.substring(0, 6) + '...' : trimmed
        } else {
          session.name = '新会话'
        }
        lastActiveSessionId.value = targetSessionId
        if (session.isEmpty) {
          delete session.isEmpty
        }
      }
      session.messages.push({ role, content, timestamp: Date.now(), ...extra })
      session.updatedAt = Date.now()
      saveSessions()
    }
  }

  function addThinkingMessage(roundNum, content, timeMs = 0) {
    let targetSessionId = currentSessionId.value
    if (!targetSessionId || !sessions.value[targetSessionId]) return

    const session = sessions.value[targetSessionId]
    session.messages.push({
      role: 'thinking',
      round: roundNum,
      content: content,
      timestamp: Date.now(),
      time_ms: timeMs,
    })
    session.updatedAt = Date.now()
    saveSessions()
  }

  function addToolCallMessage(toolCalls, roundNum) {
    let targetSessionId = currentSessionId.value
    if (!targetSessionId || !sessions.value[targetSessionId]) return

    const session = sessions.value[targetSessionId]
    session.messages.push({
      role: 'tool_call',
      round: roundNum,
      calls: toolCalls,
      timestamp: Date.now(),
    })
    session.updatedAt = Date.now()
    saveSessions()
  }

  function updateToolCallResult(toolCallId, result) {
    let targetSessionId = currentSessionId.value
    if (!targetSessionId || !sessions.value[targetSessionId]) return

    const session = sessions.value[targetSessionId]
    const msgIdx = session.messages.findIndex(
      m => m.role === 'tool_call' && m.calls?.some(c => c.id === toolCallId)
    )
    if (msgIdx !== -1) {
      // Replace the message object entirely to guarantee Vue reactivity
      const msg = session.messages[msgIdx]
      const newResults = { ...(msg.results || {}), [toolCallId]: {
        summary: result.summary || '完成',
        time_ms: result.time_ms || 0,
        tool_name: result.tool_name || '',
        data: result.result || null,
      }}
      session.messages.splice(msgIdx, 1, { ...msg, results: newResults })
      saveSessions()
    }
  }

  async function mergeLocalToServer() {
    const authStore = useAuthStore()
    if (!authStore.isLoggedIn) return

    const toSave = {}
    Object.keys(sessions.value).forEach(id => {
      if (!_isEmptySession(sessions.value[id])) toSave[id] = sessions.value[id]
    })

    if (Object.keys(toSave).length > 0) {
      try {
        const convs = Object.values(toSave).map(s => ({
          session_id: s.id,
          name: s.name || '',
          created_at: new Date(s.createdAt).toISOString(),
          updated_at: new Date(s.updatedAt).toISOString(),
          messages: (s.messages || []).map(m => ({
            role: m.role,
            content: m.content,
            metadata: {
              timestamp: m.timestamp,
              ...(m.results ? { results: m.results } : {}),
              ...(m.round ? { round: m.round } : {}),
              ...(m.calls ? { calls: m.calls } : {})
            },
            created_at: new Date(m.timestamp).toISOString(),
          }))
        }))
        await api.syncConversations(convs)
      } catch (e) {
        console.warn('Failed to merge local sessions to server:', e)
      }
    }

    // Reload from server
    await loadSessions()
  }

  const currentSession = computed(() => sessions.value[currentSessionId.value] || null)
  const sessionList = computed(() =>
    Object.values(sessions.value)
      .filter(s => !s.isEmpty)
      .sort((a, b) => b.updatedAt - a.updatedAt)
  )

  // Load backend session mapping
  const savedBackendSessions = localStorage.getItem('arknights_rag_backend_sessions')
  if (savedBackendSessions) {
    try {
      backendSessionIds.value = JSON.parse(savedBackendSessions)
    } catch (e) {
      backendSessionIds.value = {}
    }
  }

  loadSessions()

  return {
    sessions,
    currentSessionId,
    currentSession,
    sessionList,
    backendSessionIds,
    createNewSession,
    deleteSession,
    switchSession,
    renameSession,
    addMessage,
    addThinkingMessage,
    addToolCallMessage,
    updateToolCallResult,
    saveSessions,
    getBackendSessionId,
    loadSessions,
    mergeLocalToServer
  }
})
