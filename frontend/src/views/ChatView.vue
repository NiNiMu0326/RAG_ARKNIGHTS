<template>
  <div class="chat-page">
    <div class="chat-main">
      <div class="chat-panel">
        <div class="chat-messages" ref="messagesContainer">
          <div v-if="sessionStore.currentSession?.messages?.length === 0" class="empty-state">
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
              <div class="chat-bubble">
                <div class="chat-role">{{ msg.role === 'user' ? 'You' : 'Arknights RAG' }}</div>
                <div class="chat-text">{{ msg.content }}</div>
              </div>
              <div class="chat-time">{{ formatTime(new Date(msg.timestamp)) }}</div>
            </div>
          </div>

          <div v-if="isLoading" class="chat-message assistant">
            <div class="chat-bubble">
              <div class="chat-role">Arknights RAG</div>
              <div class="streaming-status" v-if="streamingStatus">
                <div class="streaming-spinner"></div>
                <span class="streaming-status-text">{{ streamingStatus }}</span>
              </div>
              <div class="streaming-answer" v-if="streamingAnswer">{{ streamingAnswer }}</div>
              <div class="typing-indicator" v-else>
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>

          <!-- Pending message queue -->
          <div v-if="messageQueue.length > 0" class="pending-messages">
            <div v-for="(msg, idx) in messageQueue" :key="idx" class="pending-message">
              <span class="pending-label">等待发送:</span>
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
            <button type="submit" class="chat-submit" :disabled="isLoading">
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

      <div class="chat-sidebar">
        <div class="sidebar-tabs">
          <button class="sidebar-tab" :class="{ active: activeTab === 'results' }" @click="activeTab = 'results'">检索结果</button>
          <button class="sidebar-tab" :class="{ active: activeTab === 'metrics' }" @click="activeTab = 'metrics'">评估指标</button>
          <button class="sidebar-tab" :class="{ active: activeTab === 'graph' }" @click="activeTab = 'graph'">知识图谱</button>
        </div>

        <div class="sidebar-content">
          <div class="sidebar-panel" :class="{ active: activeTab === 'results' }">
            <div class="crag-status" v-if="lastResult">
              <span class="status-badge" :class="cragStatusClass">{{ lastResult.crag_level }}</span>
              <span class="crag-desc">{{ cragStatusDesc }}</span>
            </div>
            <div class="crag-status" v-else>
              <span class="status-badge status-high">READY</span>
              <span class="crag-desc">等待查询</span>
            </div>

            <div class="results-header">
              <span class="results-count">检索文档</span>
            </div>

            <div id="docs-list">
              <div v-if="!lastResult?.retrieved_documents?.length" class="empty-state" style="padding: 40px 20px;">
                <div class="empty-state-title">暂无结果</div>
                <div class="empty-state-desc">发送消息查看检索文档</div>
              </div>
              <div v-else>
                <div
                  v-for="(doc, i) in lastResult.retrieved_documents"
                  :key="i"
                  class="doc-card"
                  :class="{ expanded: expandedDocs.includes(i) }"
                >
                  <div class="doc-header" @click="toggleDoc(i)">
                    <span class="doc-title">{{ doc.chunk_id || `Doc ${i+1}` }}</span>
                    <span class="doc-meta">
                      <span class="text-dim">{{ (doc.relevance_score || 0).toFixed(2) }}</span>
                      <span class="doc-expand-icon">▼</span>
                    </span>
                  </div>
                  <div class="doc-content" v-if="expandedDocs.includes(i)">{{ doc.content }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="sidebar-panel" :class="{ active: activeTab === 'metrics' }">
            <h3 class="section-title mb-md">评估指标</h3>

            <div class="metrics-grid">
              <div class="metric-mini">
                <div class="metric-mini-value">{{ lastResult?.avg_score?.toFixed(3) || '--' }}</div>
                <div class="metric-mini-label">相关性</div>
              </div>
              <div class="metric-mini">
                <div class="metric-mini-value">{{ lastResult?.num_docs_used ?? '--' }}</div>
                <div class="metric-mini-label">文档数</div>
              </div>
              <div class="metric-mini">
                <div class="metric-mini-value">{{ lastResult?.used_web_search ? '是' : '--' }}</div>
                <div class="metric-mini-label">网络搜索</div>
              </div>
              <div class="metric-mini">
                <div class="metric-mini-value">{{ lastResult?.total_time_ms ? `${lastResult.total_time_ms}ms` : '--' }}</div>
                <div class="metric-mini-label">耗时 (ms)</div>
              </div>
            </div>

            <div class="expander" :class="{ open: pipelineExpanded }">
              <div class="expander-header" @click="pipelineExpanded = !pipelineExpanded">
                <span>流程详情</span>
                <svg class="expander-icon" viewBox="0 0 24 24" width="20" height="20" :style="{ transform: pipelineExpanded ? 'rotate(180deg)' : '' }">
                  <path fill="currentColor" d="M7 10l5 5 5-5z"/>
                </svg>
              </div>
              <div class="expander-content">
                <div class="expander-inner">
                  <div v-if="!lastResult || !lastResult.pipeline_steps || lastResult.pipeline_steps.length === 0" class="pipeline-steps-empty">发送问题后查看流程详情</div>
                  <div v-else>
                    <div
                      v-for="step in lastResult.pipeline_steps"
                      :key="step.step"
                      class="pipeline-step-card"
                      :class="{ expanded: expandedSteps.includes(step.step) }"
                    >
                      <div class="pipeline-step-header" @click="toggleStep(step.step)">
                        <span class="step-number">{{ step.step }}</span>
                        <span class="step-name">{{ step.name_cn || step.name }}</span>
                        <span class="step-desc">{{ step.description }}</span>
                        <span class="step-time">{{ step.time_ms }}ms</span>
                        <span class="step-toggle">{{ expandedSteps.includes(step.step) ? '▲' : '▼' }}</span>
                      </div>
                      <div class="pipeline-step-body" v-if="expandedSteps.includes(step.step)">
                        <div class="pipeline-step-content">
                          <div class="pipeline-step-section">
                            <h4>输入</h4>
                            <pre>{{ formatStepData(step.input_data) }}</pre>
                          </div>
                          <div class="pipeline-step-section">
                            <h4>输出</h4>
                            <pre>{{ formatStepData(step.output_data) }}</pre>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="sidebar-panel" :class="{ active: activeTab === 'graph' }">
            <h3 class="section-title mb-md">知识图谱关系</h3>
            <div v-if="!lastResult?.graph_results?.results?.length" class="empty-state" style="padding: 40px 20px;">
              <div class="empty-state-title">暂无关系</div>
              <div class="empty-state-desc">询问干员关系查看知识图谱</div>
            </div>
            <div v-else>
              <div
                v-for="(r, i) in lastResult.graph_results.results"
                :key="i"
                class="kg-relation"
              >
                <div class="kg-relation-title">
                  <strong>{{ r.operator1 }}</strong>
                  <span class="text-primary"> --{{ r.relation }}--></span>
                  <strong>{{ r.operator2 }}</strong>
                </div>
                <div v-if="r.description" class="kg-relation-desc">{{ r.description }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useSessionStore } from '../stores/sessions'
import { useSettingsStore } from '../stores/settings'
import { useQuickQuestionsStore } from '../stores/quickQuestions'
import { api, formatTime } from '../api'
import { generateQuickQuestions } from '../utils/quickQuestions'

const sessionStore = useSessionStore()
const settingsStore = useSettingsStore()
const quickQuestionsStore = useQuickQuestionsStore()
const route = useRoute()

const inputText = ref('')
const isLoading = ref(false)
const streamingStatus = ref('')
const streamingAnswer = ref('')
const activeTab = ref('results')
const pipelineExpanded = ref(false)
const expandedDocs = ref([])
const expandedSteps = ref([])
const lastResult = ref(null)
const messagesContainer = ref(null)
const messageQueue = ref([])
const abortController = ref(null)

// Initialize lastResult from session storage on mount
onMounted(() => {
  console.log('[ChatView] mounted, currentSession:', sessionStore.currentSession?.id, 'lastResult:', sessionStore.currentSession?.lastResult)
  if (sessionStore.currentSession?.lastResult) {
    lastResult.value = sessionStore.currentSession.lastResult
    console.log('[ChatView] restored lastResult')
  }

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

// 组件卸载时中止所有待处理的请求
onUnmounted(() => {
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
    console.log('[ChatView] 组件卸载，已中止待处理请求')
  }
})

// Watch for session changes to update lastResult
watch(() => sessionStore.currentSessionId, (newId, oldId) => {
  console.log('[ChatView] session changed from', oldId, 'to', newId)
  if (sessionStore.currentSession?.lastResult) {
    lastResult.value = sessionStore.currentSession.lastResult
    console.log('[ChatView] restored lastResult for new session')
  } else {
    lastResult.value = null
  }

  // 切换会话时滚动到底部
  nextTick(() => scrollToBottom())

  // 如果是新建的会话（消息为空），刷新快速问题
  if (sessionStore.currentSession?.messages?.length === 0) {
    console.log('[ChatView] New session detected, refreshing quick actions')
    refreshQuickActions()
  }
})

// Also watch for changes in the current session's lastResult
watch(() => sessionStore.currentSession?.lastResult, (newResult) => {
  if (newResult) {
    console.log('[ChatView] lastResult updated in store')
    lastResult.value = newResult
  }
})


const cragStatusClass = computed(() => {
  const level = lastResult.value?.crag_level
  return {
    'status-high': level === 'HIGH',
    'status-medium': level === 'MEDIUM',
    'status-low': level === 'LOW'
  }
})

const cragStatusDesc = computed(() => {
  const level = lastResult.value?.crag_level
  return {
    'HIGH': '检索结果高质量',
    'MEDIUM': '检索结果中等',
    'LOW': '检索结果低质量'
  }[level] || '等待查询'
})

function toggleDoc(idx) {
  const i = expandedDocs.value.indexOf(idx)
  if (i > -1) {
    expandedDocs.value.splice(i, 1)
  } else {
    expandedDocs.value.push(idx)
  }
}

function toggleStep(step) {
  const i = expandedSteps.value.indexOf(step)
  if (i > -1) {
    expandedSteps.value.splice(i, 1)
  } else {
    expandedSteps.value.push(step)
  }
}

function formatStepData(data) {
  if (data === null || data === undefined) return '无数据'
  if (typeof data === 'object') return JSON.stringify(data, null, 2)
  return String(data)
}

function autoResize(e) {
  const textarea = e.target
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px'
}

async function sendMessage() {
  const content = inputText.value.trim()
  if (!content) return

  // If already loading, add to queue (max 2 messages)
  if (isLoading.value) {
    if (messageQueue.value.length < 2) {
      messageQueue.value.push(content)
    }
    return
  }

  isLoading.value = true
  inputText.value = ''
  streamingStatus.value = ''
  streamingAnswer.value = ''
  expandedDocs.value = []

  sessionStore.addMessage('user', content)
  // 用户发送消息后立即滚动到底部
  nextTick(() => scrollToBottom())

  // 创建 AbortController 用于取消请求
  if (abortController.value) {
    abortController.value.abort()
  }
  const controller = new AbortController()
  abortController.value = controller

  try {
    const history = sessionStore.currentSession.messages
      .slice(0, -1)
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .slice(-6)
      .map(m => ({ role: m.role, content: m.content }))

    const result = await api.query(content, {
      conversation_history: history,
      ...settingsStore.getRAGSettings()
    }, controller.signal)

    lastResult.value = result
    sessionStore.setLastResult(result)
    sessionStore.addMessage('assistant', result.answer)
  } catch (error) {
    // 如果是请求被中止，添加提示消息
    if (error.name === 'AbortError') {
      console.log('[ChatView] 请求被用户中止')
      sessionStore.addMessage('assistant', '请求被中断，请重新发送消息')
    } else {
      sessionStore.addMessage('assistant', `错误: ${error.message}`)
    }
  }

  // 清理 AbortController
  abortController.value = null

  isLoading.value = false
  nextTick(() => scrollToBottom())

  // Process queue if there's a pending message
  if (messageQueue.value.length > 0) {
    const nextContent = messageQueue.value.shift()
    inputText.value = nextContent
    sendMessage()
  }
}

async function loadQuickQuestionsData() {
  if (quickQuestionsStore.isLoading) return;

  quickQuestionsStore.setLoading(true);
  try {
    console.log('正在加载快速问题数据...');

    // 并行获取所有数据
    const [operatorsRes, charactersRes, storiesRes] = await Promise.allSettled([
      api.getOperators(),
      api.getCharacters(),
      api.getStories()
    ]);

    const data = {};

    // 处理operators
    if (operatorsRes.status === 'fulfilled') {
      data.operators = operatorsRes.value.operators || [];
      console.log(`已加载 ${data.operators.length} 个干员`);
    } else {
      console.error('获取干员数据失败:', operatorsRes.reason);
      data.operators = [];
    }

    // 处理characters
    if (charactersRes.status === 'fulfilled') {
      data.characters = charactersRes.value.characters || [];
      console.log(`已加载 ${data.characters.length} 个角色`);
    } else {
      console.error('获取角色数据失败:', charactersRes.reason);
      data.characters = data.operators; // 回退到干员数据
    }

    // 处理stories
    if (storiesRes.status === 'fulfilled') {
      data.stories = storiesRes.value.stories || [];
      console.log(`已加载 ${data.stories.length} 个故事`);
    } else {
      console.error('获取故事数据失败:', storiesRes.reason);
      data.stories = [];
    }

    quickQuestionsStore.setQuickQuestionsData(data);
    console.log('快速问题数据加载完成:', data);
  } catch (error) {
    console.error('加载快速问题数据失败:', error);
  } finally {
    // 无论API成功还是失败，都生成快速问题
    refreshQuickActions();
    quickQuestionsStore.setLoading(false);
  }
}

function refreshQuickActions() {
  console.log('[ChatView] refreshQuickActions called, hasInitialized:', quickQuestionsStore.hasInitialized)
  // 添加旋转动画效果
  const refreshIcon = document.querySelector('.refresh-icon');
  if (refreshIcon) {
    refreshIcon.classList.remove('rotating');
    // 强制重排以重置动画
    void refreshIcon.offsetWidth;
    refreshIcon.classList.add('rotating');

    // 动画结束后移除类
    setTimeout(() => {
      refreshIcon.classList.remove('rotating');
    }, 600);
  }

  try {
    const data = quickQuestionsStore.quickQuestionsData;
    const options = { shuffle: false };

    if (data) {
      options.data = data;
      console.log('使用API数据生成快速问题');
    } else {
      console.log('使用示例数据生成快速问题');
    }

    const newActions = generateQuickQuestions(options);
    quickQuestionsStore.setQuickActions(newActions);
    console.log('快速问题已刷新:', newActions);
  } catch (error) {
    console.error('刷新快速问题失败:', error);
    // 如果生成失败，使用备用的静态问题
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

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}
</script>

<style scoped>
.chat-page { display: flex; flex-direction: column; height: calc(100vh - 80px); }
.chat-main { flex: 1; display: flex; overflow: hidden; }
.chat-panel { flex: 1; display: flex; flex-direction: column; border-right: 1px solid var(--border-color); }
.chat-messages { flex: 1; overflow-y: auto; padding: var(--spacing-lg); }
.chat-input-area { padding: var(--spacing-lg); background: var(--bg-panel); border-top: 1px solid var(--border-color); }
.chat-form { display: flex; gap: var(--spacing-md); align-items: center; }
.chat-input-wrapper { flex: 1; position: relative; }
.chat-input { width: 100%; padding: var(--spacing-md); padding-right: 44px; resize: none; min-height: 50px; max-height: 150px; box-sizing: border-box; }
.chat-submit { width: 44px; height: 44px; padding: 0; margin-top: -6px; background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dim) 100%); border: none; border-radius: 12px; color: var(--bg-deep); cursor: pointer; transition: all var(--transition-fast); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.chat-submit:hover { transform: scale(1.05); box-shadow: 0 0 20px var(--color-primary-glow); }
.chat-submit:active { transform: scale(0.95); }
.chat-submit:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.chat-sidebar { width: 380px; display: flex; flex-direction: column; background: var(--bg-dark); overflow: hidden; }
.sidebar-tabs { display: flex; border-bottom: 1px solid var(--border-color); }
.sidebar-tab { flex: 1; padding: var(--spacing-md); background: transparent; border: none; color: var(--text-secondary); font-family: var(--font-display); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; cursor: pointer; transition: all var(--transition-fast); position: relative; }
.sidebar-tab:hover { color: var(--text-primary); background: var(--bg-panel); }
.sidebar-tab.active { color: var(--color-primary); }
.sidebar-tab.active::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px; background: var(--color-primary); box-shadow: 0 0 10px var(--color-primary-glow); }
.sidebar-content { flex: 1; overflow-y: auto; padding: var(--spacing-lg); max-height: calc(100vh - 80px - 50px); }
.sidebar-panel { display: none; }
.sidebar-panel.active { display: block; }
.crag-status { display: flex; align-items: center; gap: var(--spacing-md); padding: var(--spacing-md); background: var(--bg-card); border-radius: var(--radius-md); margin-bottom: var(--spacing-lg); }
.results-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--spacing-md); }
.results-count { font-size: 0.85rem; color: var(--text-secondary); }
.metrics-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--spacing-md); margin-bottom: var(--spacing-lg); }
.metric-mini { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: var(--spacing-md); text-align: center; }
.metric-mini-value { font-family: var(--font-mono); font-size: 1.25rem; color: var(--color-primary); }
.metric-mini-label { font-size: 0.7rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-top: var(--spacing-xs); }
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
.chat-text { line-height: 1.6; white-space: pre-wrap; }
.chat-time { font-size: 0.7rem; opacity: 0.5; margin-top: var(--spacing-xs); text-align: right; }
.typing-indicator { display: flex; gap: 4px; padding: var(--spacing-md); }
.typing-indicator span { width: 8px; height: 8px; background: var(--text-secondary); border-radius: 50%; animation: typingBounce 1.4s infinite ease-in-out; }
.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
.typing-indicator span:nth-child(3) { animation-delay: 0s; }
@keyframes typingBounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }
.streaming-status { display: flex; align-items: center; gap: var(--spacing-sm); font-size: 0.85rem; color: var(--color-primary); margin-bottom: var(--spacing-sm); padding: var(--spacing-xs) var(--spacing-sm); background: rgba(0, 229, 204, 0.1); border-radius: var(--radius-sm); }
.streaming-spinner { width: 16px; height: 16px; border: 2px solid var(--border-color); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.streaming-answer { white-space: pre-wrap; word-break: break-word; line-height: 1.6; }
.doc-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); margin-bottom: var(--spacing-sm); overflow: hidden; }
.doc-header { display: flex; justify-content: space-between; align-items: center; padding: var(--spacing-sm) var(--spacing-md); cursor: pointer; transition: background var(--transition-fast); }
.doc-header:hover { background: var(--bg-panel-hover); }
.doc-title { font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-primary); }
.doc-meta { display: flex; align-items: center; gap: var(--spacing-sm); }
.doc-expand-icon { font-size: 0.6rem; color: var(--text-dim); transition: transform var(--transition-fast); }
.doc-card.expanded .doc-expand-icon { transform: rotate(180deg); }
.doc-content { display: none; padding: var(--spacing-md); border-top: 1px solid var(--border-color); font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6; max-height: 300px; overflow-y: auto; white-space: pre-wrap; }
.doc-card.expanded .doc-content { display: block; }
.expander { border: 1px solid var(--border-color); border-radius: var(--radius-md); overflow: hidden; }
.expander-header { padding: var(--spacing-md); background: var(--bg-panel); cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: background var(--transition-fast); }
.expander-header:hover { background: var(--bg-panel-hover); }
.expander-icon { transition: transform var(--transition-fast); }
.expander-content { max-height: 0; overflow: hidden; transition: max-height var(--transition-normal); }
.expander.open .expander-content { max-height: 800px; overflow-y: auto; }
.expander-inner { padding: var(--spacing-md); background: var(--bg-dark); border-top: 1px solid var(--border-color); }
.pipeline-steps-empty { padding: var(--spacing-lg); text-align: center; color: var(--text-dim); font-size: 0.85rem; }
.pipeline-step-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); overflow: hidden; margin-bottom: var(--spacing-sm); }
.pipeline-step-header { display: flex; align-items: center; padding: var(--spacing-sm) var(--spacing-md); gap: var(--spacing-sm); }
.pipeline-step-card .step-number { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; background: var(--color-primary); color: var(--bg-deep); border-radius: 50%; font-family: var(--font-mono); font-size: 0.7rem; font-weight: 600; flex-shrink: 0; }
.pipeline-step-card .step-name { font-size: 0.85rem; font-weight: 500; color: var(--text-primary); min-width: 100px; }
.pipeline-step-card .step-desc { font-size: 0.75rem; color: var(--text-dim); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pipeline-step-card .step-time { font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-primary); margin-left: auto; }
.pipeline-step-card .step-toggle { font-size: 0.6rem; color: var(--text-dim); margin-left: var(--spacing-xs); }
.pipeline-step-card .pipeline-step-header { cursor: pointer; }
.pipeline-step-card .pipeline-step-body { border-top: 1px solid var(--border-color); background: var(--bg-panel); }
.pipeline-step-card .pipeline-step-content { padding: var(--spacing-sm) var(--spacing-md); }
.pipeline-step-card .pipeline-step-section { margin-bottom: var(--spacing-sm); }
.pipeline-step-card .pipeline-step-section:last-child { margin-bottom: 0; }
.pipeline-step-card .pipeline-step-section h4 { font-size: 0.75rem; color: var(--text-secondary); margin-bottom: var(--spacing-xs); text-transform: uppercase; letter-spacing: 0.05em; }
.pipeline-step-card .pipeline-step-section pre { background: var(--bg-dark); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: var(--spacing-sm); font-size: 0.7rem; color: var(--text-secondary); overflow-x: auto; white-space: pre-wrap; word-break: break-all; max-height: 150px; overflow-y: auto; }
.kg-relation { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: var(--spacing-md); margin-bottom: var(--spacing-sm); }
.kg-relation-title { font-family: var(--font-mono); font-size: 0.85rem; margin-bottom: var(--spacing-xs); }
.kg-relation-desc { font-size: 0.8rem; color: var(--text-secondary); }
@keyframes fadeSlideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes rotate360 { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.mb-md { margin-bottom: var(--spacing-md); }
.section-title { font-family: var(--font-display); font-size: 0.9rem; color: var(--text-primary); }
.pending-messages { display: flex; flex-direction: column; gap: var(--spacing-sm); padding: var(--spacing-md); }
.pending-message { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-sm) var(--spacing-md); background: var(--bg-panel); border: 1px dashed var(--border-color); border-radius: var(--radius-md); font-size: 0.85rem; opacity: 0.7; }
.pending-label { color: var(--text-dim); font-size: 0.75rem; flex-shrink: 0; }
.pending-text { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>