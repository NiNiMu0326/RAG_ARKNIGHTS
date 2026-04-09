import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useSessionStore = defineStore('sessions', () => {
  const sessions = ref({})
  const currentSessionId = ref(null)
  const lastActiveSessionId = ref(null)

  function loadSessions() {
    const saved = localStorage.getItem('arknights_rag_sessions')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        // 清理没有有效名字的会话（空字符串或只有空白字符）
        Object.keys(parsed).forEach(id => {
          const s = parsed[id]
          if (!s.name || s.name.trim() === '') {
            delete parsed[id]
          }
        })
        sessions.value = parsed
      } catch (e) {
        console.warn('Failed to parse sessions from localStorage:', e)
        sessions.value = {}
      }
    }
    const lastActive = localStorage.getItem('arknights_rag_last_session')
    const sessionIds = Object.keys(sessions.value)

    // 只有存在有效会话时才设置 currentSessionId
    if (sessionIds.length > 0) {
      if (lastActive && sessions.value[lastActive]) {
        currentSessionId.value = lastActive
      } else {
        currentSessionId.value = sessionIds[0]
      }
      lastActiveSessionId.value = currentSessionId.value
    } else {
      // 如果没有有效会话，创建一个默认会话
      const defaultSessionId = 'session_' + Date.now()
      sessions.value[defaultSessionId] = {
        id: defaultSessionId,
        name: '新会话',
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now()
      }
      currentSessionId.value = defaultSessionId
      lastActiveSessionId.value = defaultSessionId
      saveSessions()
    }
  }

  function saveSessions() {
    localStorage.setItem('arknights_rag_sessions', JSON.stringify(sessions.value))
    localStorage.setItem('arknights_rag_last_session', currentSessionId.value)
  }

  function createNewSession() {
    // 创建新会话并保存
    const id = 'session_' + Date.now()
    sessions.value[id] = {
      id,
      name: '新会话',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now()
    }
    currentSessionId.value = id
    lastActiveSessionId.value = id
    saveSessions()
    return id
  }

  function deleteSession(sessionId) {
    const sessionIds = Object.keys(sessions.value)
    if (sessionIds.length <= 1) {
      // 删除最后一个会话，清空所有状态
      delete sessions.value[sessionId]
      currentSessionId.value = null
      lastActiveSessionId.value = null
      saveSessions()
      return true
    }
    delete sessions.value[sessionId]
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = Object.keys(sessions.value)[0]
    }
    saveSessions()
    return true
  }

  function switchSession(sessionId) {
    if (sessions.value[sessionId]) {
      currentSessionId.value = sessionId
      localStorage.setItem('arknights_rag_last_session', sessionId)
    }
  }

  function renameSession(sessionId, newName) {
    if (sessions.value[sessionId]) {
      sessions.value[sessionId].name = newName
      sessions.value[sessionId].updatedAt = Date.now()
      saveSessions()
    }
  }

  function addMessage(role, content) {
    let targetSessionId = currentSessionId.value

    // 如果没有目标会话，创建一个新会话（必须保存）
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
      // 如果是用户的第一条消息，用这条消息作为会话名称
      if (role === 'user' && session.messages.length === 0) {
        const trimmed = content.trim()
        if (trimmed.length > 0) {
          session.name = trimmed.length > 6 ? trimmed.substring(0, 6) + '...' : trimmed
        } else {
          session.name = '新会话'
        }
        lastActiveSessionId.value = targetSessionId
      }
      session.messages.push({ role, content, timestamp: Date.now() })
      session.updatedAt = Date.now()
      saveSessions()
    }
  }

  function setLastResult(result) {
    const targetSessionId = currentSessionId.value
    const session = sessions.value[targetSessionId]
    if (!session) return
    // Only save essential display data, not full document contents
    session.lastResult = {
      crag_level: result.crag_level,
      avg_score: result.avg_score,
      num_docs_used: result.num_docs_used,
      used_web_search: result.used_web_search,
      total_time_ms: result.total_time_ms,
      pipeline_steps: result.pipeline_steps,
      retrieved_documents: result.retrieved_documents?.map(d => ({
        chunk_id: d.chunk_id,
        relevance_score: d.relevance_score,
        content: d.content?.substring(0, 200) // Only first 200 chars
      })),
      graph_results: result.graph_results
    }
    session.updatedAt = Date.now()
    try {
      saveSessions()
    } catch (e) {
      console.warn('Failed to save lastResult:', e)
    }
  }

  const currentSession = computed(() => sessions.value[currentSessionId.value])
  const sessionList = computed(() =>
    Object.values(sessions.value).sort((a, b) => b.updatedAt - a.updatedAt)
  )

  loadSessions()

  return {
    sessions,
    currentSessionId,
    currentSession,
    sessionList,
    createNewSession,
    deleteSession,
    switchSession,
    renameSession,
    addMessage,
    setLastResult,
    saveSessions
  }
})