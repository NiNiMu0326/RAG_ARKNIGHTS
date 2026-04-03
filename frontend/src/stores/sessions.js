import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useSessionStore = defineStore('sessions', () => {
  const sessions = ref({})
  const currentSessionId = ref(null)

  function loadSessions() {
    const saved = localStorage.getItem('arknights_rag_sessions')
    if (saved) {
      sessions.value = JSON.parse(saved)
    }
    const lastActive = localStorage.getItem('arknights_rag_last_session')
    const sessionIds = Object.keys(sessions.value)
    if (sessionIds.length === 0) {
      createNewSession('新会话')
    } else if (lastActive && sessions.value[lastActive]) {
      currentSessionId.value = lastActive
    } else {
      currentSessionId.value = sessionIds[0]
    }
  }

  function saveSessions() {
    localStorage.setItem('arknights_rag_sessions', JSON.stringify(sessions.value))
    localStorage.setItem('arknights_rag_last_session', currentSessionId.value)
  }

  function createNewSession(name = null) {
    const id = 'session_' + Date.now()
    const sessionName = name || '新会话 ' + (Object.keys(sessions.value).length + 1)
    sessions.value[id] = {
      id,
      name: sessionName,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now()
    }
    currentSessionId.value = id
    saveSessions()
    return id
  }

  function deleteSession(sessionId) {
    if (Object.keys(sessions.value).length <= 1) return false
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
    const session = sessions.value[currentSessionId.value]
    if (session) {
      session.messages.push({ role, content, timestamp: Date.now() })
      session.updatedAt = Date.now()
      saveSessions()
    }
  }

  function setLastResult(result) {
    const session = sessions.value[currentSessionId.value]
    if (session) {
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