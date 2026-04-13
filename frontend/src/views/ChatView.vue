<template>
  <div class="chat-page">
    <div class="chat-main">
      <div class="chat-panel">
        <div class="chat-messages" ref="messagesContainer">
          <div v-if="!sessionStore.currentSession || sessionStore.currentSession.messages?.length === 0" class="empty-state">
            <svg class="empty-state-icon" viewBox="0 0 100 100" style="width: 48px; height: 48px;">
              <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" stroke-width="2"/>
              <path d="M30 50 L45 65 L70 35" fill="none" stroke="currentColor" stroke-width="3"/>
            </svg>
            <div class="empty-state-title">准备就绪</div>
            <div class="empty-state-desc">向我询问关于明日方舟干员、剧情和游戏知识的问题</div>
          </div>
          <div v-else>
            <div
              v-for="(msg, idx) in sessionStore.currentSession?.messages"
              :key="idx"
              class="chat-message"
              :class="msg.role"
            >
              <!-- User message -->
              <template v-if="msg.role === 'user'">
                <div class="chat-bubble">
                  <div class="chat-role">You</div>
                  <div class="chat-text">{{ escapeHtml(msg.content) }}</div>
                </div>
                <div class="chat-time">{{ formatTime(new Date(msg.timestamp)) }}</div>
              </template>

              <!-- Assistant message -->
              <template v-else-if="msg.role === 'assistant'">
                <div class="chat-bubble">
                  <div class="chat-role">Arknights RAG</div>
                  <div class="chat-text">{{ escapeHtml(msg.content) }}</div>
                </div>
                <div class="chat-time">{{ formatTime(new Date(msg.timestamp)) }}</div>
              </template>

              <!-- Thinking display (independent, before tool calls and answer) -->
              <template v-else-if="msg.role === 'thinking'">
                <div class="thinking-card" @click="handleThinkingClick(idx)">
                  <div class="thinking-card-header">
                    <span class="thinking-card-round">Round {{ msg.round }}</span>
                    <span class="thinking-card-label">思考过程</span>
                    <span class="thinking-card-time" v-if="msg.time_ms">{{ formatTimeMs(msg.time_ms) }}</span>
                  </div>
                  <div class="thinking-card-preview" v-if="!expandedThinking.includes(idx)">
                    {{ msg.content.length > 60 ? msg.content.substring(0, 60) + '...' : msg.content }}
                  </div>
                  <div class="thinking-card-content" v-if="expandedThinking.includes(idx)">{{ msg.content }}</div>
                </div>
              </template>

              <!-- Tool call display -->
              <template v-else-if="msg.role === 'tool_call'">
                <div class="tool-call-card">
                  <div class="tool-call-header">
                    <span class="tool-call-round">Round {{ msg.round }}</span>
                    <span class="tool-call-count">{{ msg.calls?.length || 0 }} tools</span>
                  </div>
                  <div class="tool-call-list">
                    <div
                      v-for="call in msg.calls"
                      :key="call.id"
                      :ref="el => { if (el) toolItemRefs[call.id] = el }"
                      class="tool-call-item"
                      :class="{ 'has-result': msg.results?.[call.id], 'is-expanded': expandedTools.includes(call.id) }"
                      @click="handleToolItemClick(call.id, $event)"
                    >
                      <div class="tool-call-name-row">
                        <div class="tool-call-name">
                          <span class="tool-icon">{{ getToolIcon(call.name) }}</span>
                          {{ getToolDisplayName(call.name) }}
                        </div>
                        <div class="tool-call-meta">
                          <span class="tool-call-args" v-if="call.arguments_summary">{{ call.arguments_summary }}</span>
                          <span class="tool-result-time" v-if="msg.results?.[call.id]">{{ Math.round(msg.results[call.id].time_ms) }}ms</span>
                        </div>
                      </div>
                      <div class="tool-result-summary" v-if="msg.results?.[call.id] && !expandedTools.includes(call.id)">
                        {{ msg.results[call.id].summary }}
                      </div>
                      <div class="tool-call-pending" v-if="!msg.results?.[call.id]">
                        <span class="pending-dot"></span> 执行中...
                      </div>
                      <div class="tool-result-detail" v-if="msg.results?.[call.id] && expandedTools.includes(call.id)">
                        <div class="tool-detail-summary">{{ msg.results[call.id].summary }}</div>
                        <div class="tool-detail-content" v-if="msg.results[call.id].data">
                          <template v-if="call.name === 'arknights_rag_search'">
                            <div v-for="(doc, i) in (Array.isArray(msg.results[call.id].data) ? msg.results[call.id].data : [])" :key="i" class="tool-detail-doc">
                              <div class="tool-detail-doc-header">
                                <span class="tool-detail-doc-source">{{ doc.source || 'unknown' }}</span>
                                <span class="tool-detail-doc-score">{{ doc.score ? doc.score.toFixed(4) : '' }}</span>
                              </div>
                              <div class="tool-detail-doc-content">{{ doc.content || doc.error || '' }}</div>
                            </div>
                          </template>
                          <template v-else-if="call.name === 'arknights_graphrag_search'">
                            <div class="tool-detail-graph">
                              <template v-if="msg.results[call.id].data.mode === 'path'">
                                <div class="tool-detail-graph-path">
                                  路径: <span v-for="(node, i) in msg.results[call.id].data.path" :key="i"><span class="graph-node">{{ node }}</span><span v-if="i < msg.results[call.id].data.path.length - 1" class="graph-arrow"> → </span></span>
                                </div>
                                <div v-for="(edge, i) in msg.results[call.id].data.edges" :key="i" class="tool-detail-graph-edge">
                                  <span class="graph-node">{{ edge.from }}</span>
                                  <span class="graph-relation">--{{ edge.relation }}--></span>
                                  <span class="graph-node">{{ edge.to }}</span>
                                  <div v-if="edge.description" class="graph-edge-desc">{{ edge.description }}</div>
                                </div>
                              </template>
                              <template v-else-if="msg.results[call.id].data.mode === 'neighbors'">
                                <div class="tool-detail-graph-entity">实体: {{ msg.results[call.id].data.entity }}</div>
                                <!-- Outgoing relations -->
                                <template v-if="msg.results[call.id].data.relations?.outgoing?.length">
                                  <div class="graph-direction-label">→ 出边</div>
                                  <div v-for="(rel, i) in msg.results[call.id].data.relations.outgoing" :key="'out'+i" class="tool-detail-graph-edge">
                                    <span class="graph-node">{{ msg.results[call.id].data.entity }}</span>
                                    <span class="graph-relation">--{{ rel.relation }}--></span>
                                    <span class="graph-node">{{ rel.entity }}</span>
                                    <div v-if="rel.description" class="graph-edge-desc">{{ rel.description }}</div>
                                  </div>
                                </template>
                                <!-- Incoming relations -->
                                <template v-if="msg.results[call.id].data.relations?.incoming?.length">
                                  <div class="graph-direction-label">← 入边</div>
                                  <div v-for="(rel, i) in msg.results[call.id].data.relations.incoming" :key="'in'+i" class="tool-detail-graph-edge">
                                    <span class="graph-node">{{ rel.entity }}</span>
                                    <span class="graph-relation">--{{ rel.relation }}--></span>
                                    <span class="graph-node">{{ msg.results[call.id].data.entity }}</span>
                                    <div v-if="rel.description" class="graph-edge-desc">{{ rel.description }}</div>
                                  </div>
                                </template>
                              </template>
                              <template v-else>
                                <pre>{{ formatToolResult(msg.results[call.id].data) }}</pre>
                              </template>
                            </div>
                          </template>
                          <template v-else-if="call.name === 'web_search'">
                            <div v-for="(item, i) in (Array.isArray(msg.results[call.id].data) ? msg.results[call.id].data : [])" :key="i" class="tool-detail-web">
                              <div class="tool-detail-web-title">
                                <a v-if="item.url" :href="item.url" target="_blank" rel="noopener">{{ item.title || `结果 ${i+1}` }}</a>
                                <span v-else>{{ item.title || `结果 ${i+1}` }}</span>
                              </div>
                              <div class="tool-detail-web-content">{{ item.content || item.message || item.error || '' }}</div>
                            </div>
                          </template>
                          <template v-else>
                            <pre>{{ formatToolResult(msg.results[call.id].data) }}</pre>
                          </template>
                        </div>
                        <div class="tool-detail-empty" v-else>无详细数据</div>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <div v-if="isLoading">
            <div class="thinking-card" v-if="currentThinking" @click="handleThinkingClick('current')">
              <div class="thinking-card-header">
                <span class="thinking-card-round">Round {{ currentRound }}</span>
                <span class="thinking-card-label">思考过程</span>
                <span class="thinking-card-time" v-if="currentThinkingTimeMs">{{ formatTimeMs(currentThinkingTimeMs) }}</span>
              </div>
              <div class="thinking-card-preview" v-if="!expandedThinking.includes('current')">
                {{ currentThinking.length > 60 ? currentThinking.substring(0, 60) + '...' : currentThinking }}
              </div>
              <div class="thinking-card-content" v-if="expandedThinking.includes('current')">{{ currentThinking }}</div>
            </div>
            <div class="chat-message assistant" v-if="currentAnswer">
              <div class="chat-bubble">
                <div class="chat-role">Arknights RAG</div>
                <div class="current-answer">{{ escapeHtml(currentAnswer) }}</div>
              </div>
            </div>
            <div class="chat-message assistant" v-if="!currentAnswer && !currentThinking">
              <div class="chat-bubble">
                <div class="chat-role">Arknights RAG</div>
                <div class="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>

          <!-- Pending message queue -->
          <div v-if="messageQueue.length > 0" class="pending-messages">
            <div class="pending-header">
              <span class="pending-badge">{{ messageQueue.length }}</span>
              <span class="pending-label">消息队列</span>
              <button class="pending-clear" @click="clearMessageQueue" title="清空队列">✕</button>
            </div>
            <div v-for="(msg, idx) in messageQueue" :key="idx" class="pending-message">
              <span class="pending-idx">{{ idx + 1 }}</span>
              <span class="pending-text">{{ msg }}</span>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <form class="chat-form" @submit.prevent="sendMessage">
            <div class="chat-input-wrapper">
              <textarea
                class="input chat-input"
                v-model="inputText"
                placeholder="询问关于明日方舟的问题..."
                rows="1"
                @keydown.enter.exact.prevent="sendMessage"
                @input="autoResize"
              ></textarea>
            </div>
          <button type="submit" class="chat-submit" :class="{ 'is-queued': isLoading && inputText.trim() }" title="发送">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1">
              <path d="M22 2L11 13"/>
              <path d="M22 2l-7 20-4-9-9-4 20-7z"/>
            </svg>
          </button>
          </form>

          <div class="quick-actions">
            <button
              v-for="(action, idx) in quickQuestionsStore.quickActions"
              :key="idx"
              class="quick-action"
              @click="inputText = action.question"
              :title="action.question"
            >
              {{ action.label }}
            </button>
            <button class="quick-action refresh refresh-fixed" @click="refreshQuickActions" title="刷新问题">
              <svg class="refresh-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M23 4v6h-6"/>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onUnmounted, onActivated, onDeactivated, watch, nextTick } from 'vue'
import { useSessionStore } from '../stores/sessions'
import { useQuickQuestionsStore } from '../stores/quickQuestions'
import { useSettingsStore } from '../stores/settings'
import { api, formatTime, escapeHtml } from '../api'

const sessionStore = useSessionStore()
const quickQuestionsStore = useQuickQuestionsStore()
const settingsStore = useSettingsStore()

const inputText = ref('')
const isLoading = ref(false)
const currentAnswer = ref('')
const expandedTools = ref([])
const expandedThinking = ref([])
const toolItemRefs = reactive({})
const currentThinking = ref('')
const currentThinkingTimeMs = ref(0)
const thinkingStartTime = ref(0)
const messagesContainer = ref(null)
const messageQueue = ref([])
const abortController = ref(null)

// Initialize on mount
onMounted(() => {
  console.log('[ChatView] mounted, currentSession:', sessionStore.currentSession?.id)

  // 只初始化一次快速问题
  if (!quickQuestionsStore.hasInitialized) {
    console.log('[ChatView] First time initializing quick actions')

    // 初始化快速问题（加载真实数据）
    loadQuickQuestionsData()
    console.log('[ChatView] started loading quick actions data')

    quickQuestionsStore.markAsInitialized()
  } else {
    console.log('[ChatView] Quick actions already initialized, skipping')
  }

  // 页面加载时滚动到底部
  nextTick(() => scrollToBottom())
})

// Component deactivated (switched to another page) — keep request running in background
onDeactivated(() => {
  console.log('[ChatView] deactivated, request continues in background')
})

// Component reactivated (switched back) — restore UI state
onActivated(() => {
  console.log('[ChatView] activated, isLoading:', isLoading.value)
  nextTick(() => scrollToBottom())
})

// Only abort on true unmount (e.g. HMR, app destroy)
onUnmounted(() => {
  console.log('[ChatView] unmounted')
})

// Watch for session changes to update lastResult
watch(() => sessionStore.currentSessionId, (newId, oldId) => {
  console.log('[ChatView] session changed from', oldId, 'to', newId)

  // 只有真正切换到不同会话时才清理流式输出状态
  if (newId !== oldId) {
    // 如果是从null到有效ID，可能是初始加载，不中止请求
    if (oldId !== null) {
      // Save any in-progress content before aborting
      if (isLoading.value && currentThinking.value) {
        const thinkTime = thinkingStartTime.value ? Date.now() - thinkingStartTime.value : 0
        sessionStore.addThinkingMessage(currentRound, currentThinking.value, Math.round(thinkTime))
      }
      if (isLoading.value && currentAnswer.value) {
        sessionStore.addMessage('assistant', currentAnswer.value)
      }
      // 中止正在进行的请求
      if (abortController.value) {
        abortController.value.abort()
        abortController.value = null
      }
      isLoading.value = false
      currentAnswer.value = ''
      currentThinking.value = ''
      currentThinkingTimeMs.value = 0
    }
  }

  // 切换会话时滚动到底部
  nextTick(() => scrollToBottom())

  // 如果是新建的会话（消息为空），刷新快速问题
  if (!sessionStore.currentSession || sessionStore.currentSession.messages?.length === 0) {
    console.log('[ChatView] New session detected, refreshing quick actions')
    refreshQuickActions()
  }
})


function handleThinkingClick(idx) {
  const selection = window.getSelection()
  // Allow expansion during streaming (idx === 'current') even with tiny selections
  if (idx !== 'current' && selection && selection.toString().length > 3) return
  toggleThinking(idx)
}

function handleToolItemClick(toolCallId, event) {
  // If user selected text, don't toggle (they were trying to copy)
  const selection = window.getSelection()
  if (selection && selection.toString().length > 0) return
  toggleToolResult(toolCallId)
}

function toggleToolResult(toolCallId) {
  const i = expandedTools.value.indexOf(toolCallId)
  if (i > -1) {
    expandedTools.value.splice(i, 1)
    nextTick(() => {
      const el = toolItemRefs[toolCallId]
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })
  } else {
    expandedTools.value.push(toolCallId)
  }
}

function formatTimeMs(ms) {
  if (!ms || ms <= 0) return ''
  return `${Math.round(ms)}ms`
}

function formatToolResult(data) {
  if (data === null || data === undefined) return '无数据'
  if (typeof data === 'object') return JSON.stringify(data, null, 2)
  return String(data)
}

function toggleThinking(idx) {
  const i = expandedThinking.value.indexOf(idx)
  if (i > -1) {
    expandedThinking.value.splice(i, 1)
  } else {
    expandedThinking.value.push(idx)
  }
}

/**
 * Extract <think/> or <think ...>...</think > content from text.
 * Some models embed reasoning inside <think/> tags in the content field.
 * Returns { text: cleanedText, thinking: extractedThinking }
 */
function extractThinkContent(text) {
  if (!text) return { text: '', thinking: '' }
  let thinking = ''
  let cleaned = text
  // Match <think ...>...</think > (including self-closing <think/>)
  // Use global regex to handle multiple think blocks
  const thinkRegex = /<think[^>]*>([\s\S]*?)<\/think\s*>/gi
  let match
  while ((match = thinkRegex.exec(text)) !== null) {
    thinking += match[1].trim()
  }
  cleaned = text.replace(thinkRegex, '').trim()
  // Also handle self-closing <think/> or <think /> with no content
  cleaned = cleaned.replace(/<think\s*\/>/gi, '').trim()
  return { text: cleaned, thinking }
}

function clearMessageQueue() {
  messageQueue.value = []
}

function autoResize(e) {
  const textarea = e.target
  const content = textarea.value.trim()
  if (!content) {
    textarea.style.height = 'auto'
    textarea.style.overflowY = 'hidden'
    textarea.style.minHeight = '50px'
  } else {
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px'
    textarea.style.overflowY = textarea.scrollHeight > 150 ? 'auto' : 'hidden'
  }
}

async function sendMessage() {
  const content = inputText.value.trim()
  if (!content) return

  // If already loading, add to queue (max 2 messages)
  if (isLoading.value) {
    if (messageQueue.value.length < 20) {
      messageQueue.value.push(content)
    }
    return
  }

  isLoading.value = true
  inputText.value = ''
  currentAnswer.value = ''
  expandedTools.value = []
  expandedThinking.value = []
  currentThinking.value = ''
  currentThinkingTimeMs.value = 0
  thinkingStartTime.value = 0

  sessionStore.addMessage('user', content)
  nextTick(() => scrollToBottom())

  // Create AbortController for cancellation
  if (abortController.value) {
    abortController.value.abort()
  }
  const controller = new AbortController()
  abortController.value = controller

  // Get or create backend session
  let backendSessionId = sessionStore.getBackendSessionId()
  if (!backendSessionId) {
    try {
      const result = await api.createAgentSession()
      backendSessionId = result.session_id
      if (sessionStore.currentSessionId) {
        sessionStore.backendSessionIds[sessionStore.currentSessionId] = backendSessionId
        localStorage.setItem('arknights_rag_backend_sessions', JSON.stringify(sessionStore.backendSessionIds))
      }
    } catch (e) {
      console.error('Failed to create backend session:', e)
      sessionStore.addMessage('assistant', '错误: 无法创建会话，请重试')
      isLoading.value = false
      return
    }
  }

  let currentRound = 0
  let currentToolCallMsg = null

  try {
    await api.agentChat({
      sessionId: backendSessionId,
      message: content,
      model: settingsStore.currentModel || undefined,
      signal: controller.signal,

      onNewSessionId(newSid) {
        // Server auto-created a new session (old one expired)
        console.log('[ChatView] Session expired, server created new session:', newSid)
        backendSessionId = newSid
        if (sessionStore.currentSessionId) {
          sessionStore.backendSessionIds[sessionStore.currentSessionId] = newSid
          localStorage.setItem('arknights_rag_backend_sessions', JSON.stringify(sessionStore.backendSessionIds))
        }
      },

      onThinkingStart(event) {
        currentRound = event.round || currentRound + 1
        currentThinking.value = ''
        currentThinkingTimeMs.value = 0
        thinkingStartTime.value = event.timestamp_ms || Date.now()
        nextTick(() => scrollToBottom())
      },

      onToolCallsStart(event) {
        // Save any accumulated thinking content as a thinking message
        if (currentThinking.value) {
          const thinkTime = thinkingStartTime.value ? Date.now() - thinkingStartTime.value : 0
          sessionStore.addThinkingMessage(currentRound, currentThinking.value, Math.round(thinkTime))
          currentThinking.value = ''
          currentThinkingTimeMs.value = 0
        }
        // Discard any stray answer content (tool round doesn't produce final answer)
        currentAnswer.value = ''
        currentRound = event.round || currentRound + 1
        const calls = event.tool_calls.map(tc => ({
          id: tc.id,
          name: tc.name,
          arguments_summary: summarizeToolArgs(tc.name, tc.arguments),
        }))
        sessionStore.addToolCallMessage(calls, currentRound)
        currentToolCallMsg = calls
        nextTick(() => scrollToBottom())
      },

      onToolExecuting(event) {
        // A tool has started executing — update UI to show progress
        // This helps when tool_calls_start and tool_call_result arrive too close together
        nextTick(() => scrollToBottom())
      },

      onToolCallResult(event) {
        sessionStore.updateToolCallResult(event.tool_call_id, {
          summary: event.summary || '完成',
          time_ms: event.time_ms || 0,
          tool_name: event.tool_name || '',
          result: event.result || null,
        })
        nextTick(() => scrollToBottom())
      },

      onAnswerDelta(event) {
        const delta = event.delta || ''
        // Backend already parses <think/> tags, so content_delta is pure answer text
        currentAnswer.value += delta
        nextTick(() => scrollToBottom())
      },

      onThinkingDelta(event) {
        currentThinking.value += event.content || ''
        if (thinkingStartTime.value) {
          currentThinkingTimeMs.value = Date.now() - thinkingStartTime.value
        }
        nextTick(() => scrollToBottom())
      },

      onAnswerDone(event) {
        const thinkTime = thinkingStartTime.value ? Date.now() - thinkingStartTime.value : 0
        // Save thinking as independent message if present
        if (currentThinking.value) {
          sessionStore.addThinkingMessage(currentRound, currentThinking.value, Math.round(thinkTime))
        }
        // Filter <think/> tags from the final answer
        const rawAnswer = event.answer || currentAnswer.value
        const { text: cleanAnswer, thinking: trailingThinking } = extractThinkContent(rawAnswer)
        if (trailingThinking && !currentThinking.value) {
          sessionStore.addThinkingMessage(currentRound, trailingThinking)
        }
        // Finalize: add complete answer as assistant message
        sessionStore.addMessage('assistant', cleanAnswer)
        currentAnswer.value = ''
        currentThinking.value = ''
        currentThinkingTimeMs.value = 0
        thinkingStartTime.value = 0
      },

      onError(event) {
        console.error('Agent error:', event.message)
        sessionStore.addMessage('assistant', `错误: ${event.message || '未知错误'}`)
      },
    })
  } catch (error) {
    // Save partial thinking and answer before clearing
    const partialThinking = currentThinking.value
    const partialAnswer = currentAnswer.value

    isLoading.value = false
    currentThinking.value = ''
    currentThinkingTimeMs.value = 0

    if (error.name === 'AbortError') {
      console.log('[ChatView] Request aborted')
      if (partialThinking) {
        const thinkTime = thinkingStartTime.value ? Date.now() - thinkingStartTime.value : 0
        sessionStore.addThinkingMessage(currentRound, partialThinking, Math.round(thinkTime))
      }
      if (partialAnswer) {
        sessionStore.addMessage('assistant', partialAnswer)
      }
    } else {
      console.error('[ChatView] Agent chat error:', error)
      if (partialThinking) {
        sessionStore.addThinkingMessage(currentRound, partialThinking, 0)
      }
      sessionStore.addMessage('assistant', partialAnswer || `错误: ${error.message}`)
    }
  }

  abortController.value = null
  isLoading.value = false
  nextTick(() => scrollToBottom())

  // Process queue
  if (messageQueue.value.length > 0) {
    const nextContent = messageQueue.value.shift()
    inputText.value = nextContent
    sendMessage()
  }
}

function summarizeToolArgs(toolName, args) {
  // args is already a parsed object (not a string) from the SSE event
  if (!args || typeof args === 'string') {
    try { args = JSON.parse(args || '{}') } catch { return String(args).substring(0, 80) }
  }
  switch (toolName) {
    case 'arknights_rag_search':
      return `查询: "${args.query || ''}"`
    case 'arknights_graphrag_search':
      return args.entity1 && args.entity2
        ? `关系: ${args.entity1} → ${args.entity2}`
        : `实体: ${args.entity || ''}`
    case 'web_search':
      return `搜索: "${args.query || ''}"`
    default:
      return JSON.stringify(args).substring(0, 80)
  }
}

function getToolIcon(name) {
  switch (name) {
    case 'arknights_rag_search': return '📚'
    case 'arknights_graphrag_search': return '🕸️'
    case 'web_search': return '🌐'
    default: return '🔧'
  }
}

function getToolDisplayName(name) {
  switch (name) {
    case 'arknights_rag_search': return '知识库检索'
    case 'arknights_graphrag_search': return '图谱查询'
    case 'web_search': return '网络搜索'
    default: return name
  }
}

async function loadQuickQuestionsData() {
  if (quickQuestionsStore.isLoading) return;

  quickQuestionsStore.setLoading(true);
  try {
    console.log('正在从后端加载快速问题...');
    const res = await api.getQuickQuestions();
    const questions = res.questions || [];
    if (questions.length > 0) {
      quickQuestionsStore.setQuickActions(questions);
      console.log('快速问题加载完成:', questions);
    } else {
      throw new Error('Empty questions');
    }
  } catch (error) {
    console.error('加载快速问题失败:', error);
    // fallback
    const fallbackActions = [
      { label: '银灰技能', question: '银灰的技能是什么？', type: 'skill' },
      { label: '陈/史尔特尔', question: '陈和史尔特尔的关系', type: 'relation' },
      { label: '伊芙利特背景', question: '伊芙利特背景故事', type: 'background' },
      { label: '靶向药物故事', question: '靶向药物故事内容', type: 'story' },
      { label: '阿米娅别名', question: '阿米娅别名有什么', type: 'alias' }
    ];
    quickQuestionsStore.setQuickActions(fallbackActions);
  } finally {
    quickQuestionsStore.setLoading(false);
  }
}

async function refreshQuickActions() {
  console.log('[ChatView] refreshQuickActions called')
  // 添加旋转动画效果
  const refreshIcon = document.querySelector('.refresh-icon');
  if (refreshIcon) {
    refreshIcon.classList.remove('rotating');
    void refreshIcon.offsetWidth;
    refreshIcon.classList.add('rotating');
    setTimeout(() => {
      refreshIcon.classList.remove('rotating');
    }, 600);
  }

  try {
    const res = await api.getQuickQuestions();
    const questions = res.questions || [];
    if (questions.length > 0) {
      quickQuestionsStore.setQuickActions(questions);
      console.log('快速问题已刷新:', questions);
    } else {
      throw new Error('Empty questions');
    }
  } catch (error) {
    console.error('刷新快速问题失败:', error);
    // fallback
    const fallbackActions = [
      { label: '银灰技能', question: '银灰的技能是什么？', type: 'skill' },
      { label: '陈/史尔特尔', question: '陈和史尔特尔的关系', type: 'relation' },
      { label: '伊芙利特背景', question: '伊芙利特背景故事', type: 'background' },
      { label: '靶向药物故事', question: '靶向药物故事内容', type: 'story' },
      { label: '阿米娅别名', question: '阿米娅别名有什么', type: 'alias' }
    ];
    quickQuestionsStore.setQuickActions(fallbackActions);
  }
}

let _scrollRafId = null
function scrollToBottom() {
  if (_scrollRafId !== null) return
  _scrollRafId = requestAnimationFrame(() => {
    _scrollRafId = null
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}
</script>

<style scoped>
.chat-page { display: flex; flex-direction: column; height: calc(100vh - 80px); }
.chat-main { flex: 1; display: flex; overflow: hidden; }
.chat-panel { flex: 1; display: flex; flex-direction: column; }
.chat-messages { flex: 1; overflow-y: auto; padding: var(--spacing-lg); min-height: 0; }
.chat-input-area { padding: var(--spacing-lg); background: var(--bg-panel); border-top: 1px solid var(--border-color); }
.chat-form { display: flex; gap: var(--spacing-md); align-items: center; }
.chat-input-wrapper { flex: 1; position: relative; }
.chat-input { width: 100%; padding: var(--spacing-md); padding-right: 44px; resize: none; min-height: 50px; max-height: 150px; box-sizing: border-box; overflow: hidden; }
.chat-submit { width: 44px; height: 44px; padding: 0; margin-top: -6px; background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dim) 100%); border: none; border-radius: 12px; color: var(--bg-deep); cursor: pointer; transition: all var(--transition-fast); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.chat-submit:hover { transform: scale(1.05); box-shadow: 0 0 20px var(--color-primary-glow); }
.chat-submit:active { transform: scale(0.95); }
.chat-submit:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.chat-submit.is-queued { opacity: 1; cursor: pointer; }
.chat-submit.is-queued:hover { transform: scale(1.05); box-shadow: 0 0 20px var(--color-primary-glow); }


/* Mobile: hide sidebar, full-screen chat */
@media (max-width: 768px) {
  .chat-page { height: calc(100vh - 60px); }
  .chat-input-area { padding: var(--spacing-md); }
  .chat-messages { padding: var(--spacing-md); }
  .quick-actions { gap: var(--spacing-xs); }
  .quick-action { font-size: 0.75rem; padding: var(--spacing-xs) var(--spacing-sm); }
  .chat-message { max-width: 95%; }
  .chat-bubble { padding: var(--spacing-sm) var(--spacing-md); }
  /* Thinking card: 固定宽度，不左右滚动 */
  .thinking-card { max-width: 95%; }
  .thinking-card-preview { white-space: normal; word-break: break-all; }
  .thinking-card-content { max-height: 150px; }
  /* Tool card */
  .tool-call-card { max-width: 95%; }
  .tool-call-name { font-size: 0.7rem; }
  .tool-call-args { font-size: 0.65rem; }
}
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: var(--spacing-xl); }
.empty-state-title { font-family: var(--font-display); font-size: 1.25rem; color: var(--text-secondary); margin-bottom: var(--spacing-sm); }
.empty-state-desc { font-size: 0.9rem; color: var(--text-dim); max-width: 300px; }
.quick-actions { display: flex; flex-wrap: wrap; gap: var(--spacing-sm); margin-top: var(--spacing-md); }
.quick-action { padding: var(--spacing-xs) var(--spacing-md); background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: var(--radius-lg); color: var(--text-secondary); font-size: 0.8rem; cursor: pointer; transition: all var(--transition-fast); }
.quick-action:hover { border-color: var(--color-primary-dim); color: var(--color-primary); }
.quick-action.refresh:hover { border-color: var(--color-primary); }
.refresh-fixed { margin-left: auto; flex-shrink: 0; }
.quick-action.refresh {
  background: var(--bg-panel);
  color: var(--color-primary);
  padding: var(--spacing-xs);
  border-color: var(--color-primary-dim);
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 38px;
  min-height: 38px;
}
.quick-action.refresh:focus, .quick-action.refresh:active { outline: none; background: var(--bg-panel); }
.refresh-icon {
  transition: transform var(--transition-fast);
  width: 18px;
  height: 18px;
}
.quick-action.refresh:hover .refresh-icon {
  transform: rotate(180deg);
}
.refresh-icon.rotating {
  animation: rotate360 0.6s ease-out;
}
.chat-message { max-width: 85%; margin-bottom: var(--spacing-md); animation: fadeSlideIn 0.3s ease-out; }
.chat-message.user { margin-left: auto; }
.chat-message.assistant { margin-right: auto; }
.chat-bubble { padding: var(--spacing-md) var(--spacing-lg); border-radius: var(--radius-lg); position: relative; }
.chat-message.user .chat-bubble { background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dim) 100%); color: var(--bg-deep); border-bottom-right-radius: var(--radius-sm); }
.chat-message.assistant .chat-bubble { background: var(--bg-panel); border: 1px solid var(--border-color); border-bottom-left-radius: var(--radius-sm); }
.chat-role { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: var(--spacing-xs); opacity: 0.7; }
.chat-text { line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.chat-time { font-size: 0.7rem; opacity: 0.5; margin-top: var(--spacing-xs); text-align: right; }
/* Thinking card (clickable whole card to expand/collapse) */
.thinking-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: var(--spacing-sm) var(--spacing-md); max-width: 85%; margin-bottom: var(--spacing-md); animation: fadeSlideIn 0.3s ease-out; margin-right: auto; cursor: pointer; user-select: none; transition: border-color var(--transition-fast); }
.thinking-card:hover { border-color: var(--color-primary-dim); }
.thinking-card-header { display: flex; align-items: center; gap: var(--spacing-sm); }
.thinking-card-round { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-dim); }
.thinking-card-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-dim); font-style: italic; }
.thinking-card-time { margin-left: auto; font-size: 0.65rem; color: var(--text-dim); font-family: var(--font-mono); }
.thinking-card-preview { font-size: 0.72rem; color: var(--text-dim); padding: var(--spacing-xs) 0 0 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.thinking-card-content { font-size: 0.75rem; color: var(--text-dim); background: var(--bg-dark); border: 1px dashed var(--border-color); border-radius: var(--radius-sm); padding: var(--spacing-sm); margin-top: var(--spacing-xs); max-height: 200px; overflow-y: auto; white-space: pre-wrap; line-height: 1.5; word-break: break-word; cursor: text; user-select: text; }
.typing-indicator { display: flex; gap: 4px; padding: var(--spacing-md); }
.typing-indicator span { width: 8px; height: 8px; background: var(--text-secondary); border-radius: 50%; animation: typingBounce 1.4s infinite ease-in-out; }
.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
.typing-indicator span:nth-child(3) { animation-delay: 0s; }
@keyframes typingBounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }
.current-answer { white-space: pre-wrap; word-break: break-word; line-height: 1.6; }
@keyframes fadeSlideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes rotate360 { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.pending-messages { display: flex; flex-direction: column; gap: var(--spacing-xs); padding: var(--spacing-sm) var(--spacing-md); background: var(--bg-panel); border: 1px dashed var(--border-color); border-radius: var(--radius-md); margin-bottom: var(--spacing-md); }
.pending-header { display: flex; align-items: center; gap: var(--spacing-sm); padding-bottom: var(--spacing-xs); border-bottom: 1px solid var(--border-color); margin-bottom: 2px; }
.pending-badge { font-size: 0.65rem; font-weight: 700; color: var(--color-primary); background: var(--bg-dark); border: 1px solid var(--color-primary-dim); border-radius: 8px; padding: 0 6px; line-height: 18px; }
.pending-label { font-size: 0.75rem; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; flex: 1; }
.pending-clear { background: none; border: none; color: var(--text-dim); font-size: 0.7rem; cursor: pointer; padding: 2px 6px; border-radius: 4px; transition: color var(--transition-fast); }
.pending-clear:hover { color: var(--text-secondary); }
.pending-message { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-xs) var(--spacing-sm); border-radius: var(--radius-sm); background: var(--bg-dark); }
.pending-idx { font-size: 0.65rem; color: var(--text-dim); font-weight: 600; min-width: 16px; font-family: var(--font-mono); opacity: 0.6; }
.pending-text { font-size: 0.82rem; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.quick-action { padding: var(--spacing-xs) var(--spacing-md); background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: var(--radius-lg); color: var(--text-secondary); font-size: 0.8rem; cursor: pointer; transition: all var(--transition-fast); }
.quick-action:hover { border-color: var(--color-primary-dim); color: var(--color-primary); }
.quick-action.refresh:hover { border-color: var(--color-primary); }
.refresh-fixed { margin-left: auto; flex-shrink: 0; }
.quick-action.refresh { background: var(--bg-panel); color: var(--color-primary); padding: var(--spacing-xs); border-color: var(--color-primary-dim); display: flex; align-items: center; justify-content: center; min-width: 38px; min-height: 38px; }
.refresh-icon { transition: transform var(--transition-fast); width: 18px; height: 18px; }
.quick-action.refresh:hover .refresh-icon { transform: rotate(180deg); }
.refresh-icon.rotating { animation: rotate360 0.6s ease-out; }

/* Tool call display */
.tool-call-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: var(--spacing-md); max-width: 85%; margin-bottom: var(--spacing-md); animation: fadeSlideIn 0.3s ease-out; margin-right: auto; }
.tool-call-header { display: flex; align-items: center; gap: var(--spacing-sm); margin-bottom: var(--spacing-sm); }
.tool-call-round { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-dim); }
.tool-call-count { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-dim); }
.tool-call-list { display: flex; flex-direction: column; gap: var(--spacing-xs); }
.tool-call-item { display: flex; flex-direction: column; gap: 2px; padding: var(--spacing-xs) var(--spacing-sm); background: var(--bg-panel); border-radius: var(--radius-sm); border-left: 3px solid var(--text-dim); transition: border-color var(--transition-fast); cursor: pointer; position: relative; }
.tool-call-item.has-result { border-left-color: var(--color-primary); }
.tool-call-name-row { display: flex; justify-content: space-between; align-items: center; gap: var(--spacing-sm); }
.tool-call-name { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-dim); display: flex; align-items: center; gap: var(--spacing-xs); flex-shrink: 0; }
.tool-icon { font-size: 0.85rem; }
.tool-call-meta { display: flex; align-items: center; gap: var(--spacing-sm); flex-wrap: wrap; justify-content: flex-end; }
.tool-call-args { font-size: 0.7rem; color: var(--text-dim); }
.tool-result-time { font-size: 0.65rem; color: var(--text-dim); font-family: var(--font-mono); flex-shrink: 0; }
.tool-result-summary { font-size: 0.7rem; color: var(--text-dim); padding-left: 22px; }
.tool-result-detail { padding: var(--spacing-sm) 0 0 22px; position: relative; cursor: text; user-select: text; }
.tool-result-detail pre { background: var(--bg-dark); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: var(--spacing-sm); font-size: 0.7rem; color: var(--text-secondary); overflow-x: auto; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; margin: 0; }
.tool-call-pending { font-size: 0.7rem; color: var(--text-dim); padding-left: 22px; display: flex; align-items: center; gap: 4px; }
.pending-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-dim); animation: pendingPulse 1s infinite ease-in-out; }
@keyframes pendingPulse { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }

/* Tool detail expanded content */
.tool-call-item.is-expanded { border-left-color: var(--color-primary); }
.tool-detail-summary { font-size: 0.75rem; color: var(--text-secondary); margin-bottom: var(--spacing-sm); padding-bottom: var(--spacing-xs); border-bottom: 1px dashed var(--border-color); }
.tool-detail-content { display: flex; flex-direction: column; gap: var(--spacing-sm); margin-top: var(--spacing-xs); }
.tool-detail-empty { font-size: 0.75rem; color: var(--text-dim); font-style: italic; }

/* RAG search docs */
.tool-detail-doc { background: var(--bg-dark); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: var(--spacing-sm); }
.tool-detail-doc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--spacing-xs); }
.tool-detail-doc-source { font-size: 0.7rem; color: var(--text-secondary); font-weight: 500; max-width: 70%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-detail-doc-score { font-size: 0.65rem; color: var(--text-dim); font-family: var(--font-mono); background: var(--bg-panel); padding: 1px 6px; border-radius: 4px; }
.tool-detail-doc-content { font-size: 0.72rem; color: var(--text-secondary); line-height: 1.5; max-height: 160px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; }

/* GraphRAG results */
.tool-detail-graph { display: flex; flex-direction: column; gap: var(--spacing-sm); }
.tool-detail-graph-path { font-size: 0.75rem; color: var(--text-secondary); padding: var(--spacing-xs) var(--spacing-sm); background: var(--bg-dark); border-radius: var(--radius-sm); }
.tool-detail-graph-edge { font-size: 0.72rem; color: var(--text-secondary); padding: var(--spacing-xs) var(--spacing-sm); background: var(--bg-dark); border-radius: var(--radius-sm); }
.graph-node { color: var(--text-primary); font-weight: 500; }
.graph-relation { color: var(--text-secondary); font-style: italic; margin: 0 4px; }
.graph-arrow { color: var(--text-secondary); margin: 0 2px; }
.graph-edge-desc { font-size: 0.65rem; color: var(--text-secondary); margin-top: 2px; padding-left: 8px; font-style: italic; }
.graph-direction-label { font-size: 0.7rem; color: var(--text-dim); font-weight: 500; margin-top: var(--spacing-xs); padding: 2px 0; }
.tool-detail-graph-entity { font-size: 0.75rem; color: var(--text-primary); font-weight: 500; margin-bottom: var(--spacing-xs); }

/* Web search results */
.tool-detail-web { background: var(--bg-dark); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: var(--spacing-sm); }
.tool-detail-web-title { font-size: 0.78rem; margin-bottom: var(--spacing-xs); }
.tool-detail-web-title a { color: var(--text-secondary); text-decoration: none; font-weight: 500; }
.tool-detail-web-title a:hover { text-decoration: underline; }
.tool-detail-web-content { font-size: 0.72rem; color: var(--text-secondary); line-height: 1.5; max-height: 120px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; }
</style>