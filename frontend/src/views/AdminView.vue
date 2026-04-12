<template>
  <div class="admin-page">
    <nav class="nav-tabs">
      <button class="nav-tab" :class="{ active: activeTab === 'chunk' }" @click="activeTab = 'chunk'">
        <span>1</span> Chunk 可视化
      </button>
      <button class="nav-tab" :class="{ active: activeTab === 'dashboard' }" @click="activeTab = 'dashboard'">
        <span>2</span> 数据仪表板
      </button>
      <button class="nav-tab" :class="{ active: activeTab === 'eval' }" @click="activeTab = 'eval'">
        <span>3</span> 评估面板
      </button>
    </nav>

    <div class="admin-content" :data-page="activeTab">
      <div v-if="activeTab === 'chunk'" class="tab-content">
        <div class="section-header">
          <h2 class="section-title">Chunk Browser</h2>
        </div>
        <div class="chunk-browser">
          <div class="chunk-list">
            <div class="chunk-list-header">
              <div class="form-group">
                <select class="input select" v-model="chunkCollection" @change="loadChunks">
                  <option value="operators">Operators</option>
                  <option value="stories">Stories</option>
                  <option value="knowledge">Knowledge</option>
                </select>
              </div>
              <div class="form-group" style="position: relative;">
                <input type="text" class="input" v-model="chunkSearch" placeholder="搜索文档..." @input="debouncedSearch" @focus="onSearchFocus" @blur="onSearchBlur">
                <div class="chunk-search-results" v-if="searchFocused || searchResults.length" :class="{ active: searchFocused || searchResults.length }">
                  <div v-for="r in (searchResults.length ? searchResults : chunks)" :key="r.filename" class="chunk-search-item" @mousedown.prevent="selectChunk(r)">
                    {{ r.name }}
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="chunk-preview">
            <div class="chunk-preview-header">
              <span class="chunk-preview-title">{{ selectedChunk?.name || 'Select a chunk' }}</span>
              <div class="chunk-preview-stats" v-if="selectedChunk">
                <span>{{ selectedChunk.char_count }} 字符</span>
                <span>{{ selectedChunk.lines }} 行</span>
                <span>{{ selectedChunk.tokens }} tokens</span>
              </div>
              <div class="chunk-nav-inline" v-if="chunks.length">
                <button class="btn btn-small" @click="navigateChunk(-1)">&lt;</button>
                <input type="number" class="chunk-nav-input" v-model="chunkNavInput" min="1" :max="chunks.length" @keypress.enter="jumpToChunk">
                <span class="chunk-nav-info">/ {{ chunks.length }}</span>
                <button class="btn btn-small" @click="navigateChunk(1)">&gt;</button>
              </div>
            </div>
            <div class="chunk-preview-content">{{ selectedChunkContent || 'Content will be displayed here...' }}</div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'dashboard'" class="tab-content">
        <div class="section-header">
          <h2 class="section-title">Data Dashboard</h2>
        </div>

        <!-- Stats Row -->
        <div class="stats-row" v-if="stats">
          <div class="stat-card">
            <div class="stat-label">OPERATORS</div>
            <div class="stat-value">{{ stats.operators }}<span class="stat-unit">条</span></div>
            <div class="stat-sub">干员数据</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">STORIES</div>
            <div class="stat-value">{{ stats.stories }}<span class="stat-unit">篇</span></div>
            <div class="stat-sub">故事文本</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">KNOWLEDGES</div>
            <div class="stat-value">{{ stats.knowledge }}<span class="stat-unit">条</span></div>
            <div class="stat-sub">知识条目</div>
          </div>
        </div>

        <div class="grid-2">
          <!-- Graph Stats -->
          <div class="panel">
            <div class="panel-header">
              <h3>知识图谱</h3>
            </div>
            <div class="panel-body">
              <div class="graph-stats-grid" v-if="graphData">
                <div class="graph-stat-mini">
                  <div class="graph-stat-value">{{ entityCount }}</div>
                  <div class="graph-stat-label">节点</div>
                </div>
                <div class="graph-stat-mini">
                  <div class="graph-stat-value">{{ graphData.relations?.length || 0 }}</div>
                  <div class="graph-stat-label">边</div>
                </div>
                <div class="graph-stat-mini">
                  <div class="graph-stat-value">{{ relationTypesCount }}</div>
                  <div class="graph-stat-label">关系类型</div>
                </div>
              </div>
              <div class="graph-stats-grid" v-else>
                <div class="graph-stat-mini"><div class="graph-stat-value">--</div><div class="graph-stat-label">节点</div></div>
                <div class="graph-stat-mini"><div class="graph-stat-value">--</div><div class="graph-stat-label">边</div></div>
                <div class="graph-stat-mini"><div class="graph-stat-value">--</div><div class="graph-stat-label">关系类型</div></div>
              </div>

              <div class="relation-type-section" v-if="pagedRelations.length > 0">
                <div class="relation-section-header">
                  <div class="relation-section-left">
                    <h4>关系类型</h4>
                    <div class="relation-pagination" v-if="allRelationTypes.length > 5">
                      <button class="btn btn-small" :disabled="relationPage === 1" @click="relationPage--">&lt;</button>
                      <span class="relation-page-info">{{ relationPage }} / {{ totalRelationPages }}</span>
                      <button class="btn btn-small" :disabled="relationPage >= totalRelationPages" @click="relationPage++">&gt;</button>
                    </div>
                  </div>
                </div>
                <div class="relation-chart">
                  <div class="vertical-bar-chart">
                    <div v-for="item in pagedRelations" :key="item.type" class="vertical-bar-item clickable" @click="openRelationDetail(item.type)">
                      <div class="vertical-bar-value">{{ item.count }}</div>
                      <div class="vertical-bar-track">
                        <div class="vertical-bar-fill" :style="{ height: (pageMaxCount > 0 ? (item.count / pageMaxCount * 100) : 0) + '%' }"></div>
                      </div>
                      <div class="vertical-bar-label" :title="item.type">{{ item.type.length > 6 ? item.type.slice(0, 6) + '..' : item.type }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="empty-state" style="padding: 40px;">
                <div class="empty-state-title">暂无关系数据</div>
              </div>
            </div>
          </div>

          <!-- Collection Stats -->
          <div class="panel">
            <div class="panel-header">
              <h3>数据分布</h3>
            </div>
            <div class="panel-body">
              <div class="pie-chart-container" v-if="stats">
                <div class="pie-chart" :style="{ background: pieChartGradient }"></div>
                <div class="pie-legend">
                  <div class="pie-legend-item">
                    <span class="pie-legend-color" style="background: #00e5c7"></span>
                    <span class="pie-legend-name">Operators</span>
                    <span class="pie-legend-value">{{ stats.operators }}</span>
                  </div>
                  <div class="pie-legend-item">
                    <span class="pie-legend-color" style="background: #ff6b9d"></span>
                    <span class="pie-legend-name">Stories</span>
                    <span class="pie-legend-value">{{ stats.stories }}</span>
                  </div>
                  <div class="pie-legend-item">
                    <span class="pie-legend-color" style="background: #7c5cff"></span>
                    <span class="pie-legend-name">Knowledge</span>
                    <span class="pie-legend-value">{{ stats.knowledge }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="empty-state" style="padding: 40px;">
                <div class="empty-state-title">暂无数据</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'eval'" class="tab-content">
        <div class="section-header">
          <h2 class="section-title">评估面板</h2>
        </div>
        <div class="panel">
          <div class="panel-header">
            <h3>批量评估</h3>
            <button class="btn btn-primary" @click="runEvaluation" :disabled="evalRunning">
              <span>&gt;</span> {{ evalRunning ? '评估中...' : '开始评估' }}
            </button>
          </div>
          <div class="panel-body">
            <div v-if="evalRunning" class="eval-progress">
              <div class="mb-md">正在评估...</div>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: evalProgress + '%' }"></div>
              </div>
            </div>

            <div v-if="evalResults">
              <div class="eval-result-summary">
                <h4>评估结果</h4>
                <div class="eval-metrics">
                  <div class="eval-metric">
                    <div class="eval-metric-value">{{ evalResults.avg_score?.toFixed(1) || '--' }}</div>
                    <div class="eval-metric-label">平均分数</div>
                  </div>
                  <div class="eval-metric">
                    <div class="eval-metric-value">{{ evalResults.total_questions || 0 }}</div>
                    <div class="eval-metric-label">总问题数</div>
                  </div>
                </div>
              </div>

              <!-- Result Cards -->
              <div class="eval-result-cards">
                <div v-for="result in evalResults.results" :key="result.question_id" class="eval-result-card" :class="{ expanded: result.expanded }">
                  <div class="eval-card-header" @click="toggleEvalResultExpandedByResult(result)">
                    <div class="eval-card-summary">
                      <span class="eval-card-id">#{{ result.question_id }}</span>
                      <span class="eval-card-question">{{ escapeHtml(result.question) }}</span>
                    </div>
                    <div class="eval-card-scores">
                      <span class="eval-score-badge" :class="getScoreClass(result.score)">
                        {{ result.score?.toFixed(1) || '--' }}
                      </span>
                      <span class="eval-card-toggle">{{ result.expanded ? '▲' : '▼' }}</span>
                    </div>
                  </div>
                  <div class="eval-card-body" v-if="result.expanded">
                    <div class="eval-card-section">
                      <h5>RAG 回答</h5>
                      <p class="eval-answer">{{ result.answer ? escapeHtml(result.answer) : '(无回答)' }}</p>
                    </div>
                    <div class="eval-card-section">
                      <h5>评估结果</h5>
                      <div class="eval-scores-detail">
                        <div class="eval-score-item">
                          <span class="eval-score-label">相关性</span>
                          <span class="eval-score-value">{{ result.relevance?.toFixed(1) || result.score?.toFixed(1) || '--' }}</span>
                        </div>
                        <div class="eval-score-item">
                          <span class="eval-score-label">准确性</span>
                          <span class="eval-score-value">{{ result.accuracy?.toFixed(1) || '--' }}</span>
                        </div>
                        <div class="eval-score-item">
                          <span class="eval-score-label">完整性</span>
                          <span class="eval-score-value">{{ result.completeness?.toFixed(1) || '--' }}</span>
                        </div>
                        <div class="eval-score-item">
                          <span class="eval-score-label">综合</span>
                          <span class="eval-score-value">{{ result.score?.toFixed(1) || '--' }}</span>
                        </div>
                        <div class="eval-score-item" v-if="result.evaluation_method">
                          <span class="eval-score-label">评估方法</span>
                          <span class="eval-score-value">{{ result.evaluation_method === 'llm' ? 'LLM评估' : '关键词评估' }}</span>
                        </div>
                      </div>
                      <p class="eval-reasoning" v-if="result.reasoning">{{ escapeHtml(result.reasoning) }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="empty-state" style="padding: 60px;">
              <div class="empty-state-title">暂无评估结果</div>
              <div class="empty-state-desc">点击"开始评估"运行批量测试</div>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- 确认弹窗 -->
    <div class="modal-overlay" :class="{ active: showConfirmModal }" @click.self="showConfirmModal = false">
      <div class="modal-content modal-sm">
        <div class="modal-header">
          <h2>{{ confirmTitle }}</h2>
          <button class="modal-close" @click="showConfirmModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <p>{{ confirmMessage }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="confirmCancel">取消</button>
          <button class="btn btn-primary" @click="confirmOk">确定</button>
        </div>
      </div>
    </div>

    <!-- 提示弹窗 -->
    <div class="modal-overlay" :class="{ active: showAlertModal }" @click.self="showAlertModal = false">
      <div class="modal-content modal-sm">
        <div class="modal-body text-center">
          <h2>{{ alertTitle }}</h2>
          <p>{{ alertMessage }}</p>
          <button class="btn btn-primary" @click="showAlertModal = false">确定</button>
        </div>
      </div>
    </div>

    <!-- 关系详情弹窗 -->
    <div class="modal-overlay" :class="{ active: showRelationDetailModal }" @click.self="showRelationDetailModal = false">
      <div class="modal-content relation-detail-modal">
        <div class="modal-header">
          <h2>{{ relationDetailType }}</h2>
          <span class="relation-detail-count">{{ relationDetailItems.length }} 条关系</span>
          <button class="modal-close" @click="showRelationDetailModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <input type="text" class="input" v-model="relationDetailSearch" placeholder="搜索实体..." style="margin-bottom: var(--spacing-md);">
          <div class="relation-detail-list">
            <div v-for="(item, idx) in filteredRelationDetailItems" :key="idx" class="relation-detail-item" :class="{ expanded: item.expanded }" @click="item.expanded = !item.expanded">
              <div class="relation-detail-triple">
                <span class="relation-detail-entity">{{ item.source }}</span>
                <span class="relation-detail-arrow">&rarr;</span>
                <span class="relation-detail-rel">{{ item.relation }}</span>
                <span class="relation-detail-arrow">&rarr;</span>
                <span class="relation-detail-entity">{{ item.target }}</span>
                <span class="relation-detail-expand">{{ item.expanded ? '▲' : '▼' }}</span>
              </div>
              <div class="relation-detail-desc" v-if="item.expanded && item.description">
                {{ item.description }}
              </div>
            </div>
            <div v-if="filteredRelationDetailItems.length === 0" class="empty-state" style="padding: 20px;">
              <div class="empty-state-title">无匹配结果</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api, debounce, escapeHtml } from '../api'

const activeTab = ref('chunk')
const chunkCollection = ref('operators')
const chunks = ref([])
const selectedChunk = ref(null)
const selectedChunkContent = ref('')
const chunkSearch = ref('')
const searchResults = ref([])
const searchFocused = ref(false)
const loadingChunks = ref(false)
const stats = ref(null)
const graphData = ref(null)
const chunkNavInput = ref(1)

onMounted(() => {
  loadChunks()
  loadStats()
  loadGraphData()
})

async function loadChunks() {
  loadingChunks.value = true
  chunkSearch.value = ''
  searchResults.value = []
  selectedChunk.value = null
  selectedChunkContent.value = ''
  chunks.value = []
  try {
    chunks.value = await api.getChunks(chunkCollection.value)
    if (chunks.value.length > 0) {
      selectChunk(chunks.value[0])
    }
    if (searchFocused.value && !chunkSearch.value.trim()) {
      searchResults.value = chunks.value
    }
  } catch (e) {
    chunks.value = []
  }
  loadingChunks.value = false
}

async function selectChunk(chunk) {
  if (chunk.placeholder) return
  selectedChunk.value = chunk
  chunkSearch.value = ''
  searchResults.value = []
  try {
    const result = await api.getChunk(chunkCollection.value, chunk.filename)
    selectedChunkContent.value = result.content
  } catch (e) {
    selectedChunkContent.value = '加载失败'
  }
  const idx = chunks.value.findIndex(c => c.filename === chunk.filename)
  if (idx >= 0) chunkNavInput.value = idx + 1
}

function navigateChunk(dir) {
  const idx = chunks.value.findIndex(c => c.filename === selectedChunk.value?.filename)
  const newIdx = Math.max(0, Math.min(chunks.value.length - 1, idx + dir))
  if (chunks.value[newIdx]) selectChunk(chunks.value[newIdx])
}

function jumpToChunk() {
  const idx = Math.max(0, Math.min(chunks.value.length - 1, chunkNavInput.value - 1))
  if (chunks.value[idx]) selectChunk(chunks.value[idx])
}

const debouncedSearch = debounce(() => {
  if (!chunkSearch.value.trim()) {
    searchResults.value = []
    return
  }
  searchResults.value = chunks.value.filter(c =>
    (c.name || c.filename || '').toLowerCase().includes(chunkSearch.value.toLowerCase())
  )
}, 200)

function onSearchFocus() {
  searchFocused.value = true
  if (!chunkSearch.value.trim()) {
    if (loadingChunks.value) {
      searchResults.value = [{ name: '加载中...', filename: '', placeholder: true }]
    } else {
      searchResults.value = chunks.value
    }
  }
}

function onSearchBlur() {
  searchFocused.value = false
  setTimeout(() => {
    searchResults.value = []
  }, 200)
}

async function loadStats() {
  try {
    stats.value = await api.getStats()
  } catch (e) {
    stats.value = null
  }
}

async function loadGraphData() {
  try {
    graphData.value = await api.getGraphData()
  } catch (e) {
    graphData.value = null
  }
}

// Computed properties for dashboard
const entityCount = computed(() => {
  const entities = graphData.value?.entities
  if (!entities) return 0
  if (typeof entities === 'object' && !Array.isArray(entities)) {
    return Object.values(entities).flat().length
  }
  return Array.isArray(entities) ? entities.length : 0
})

const relationTypesCount = computed(() => {
  if (!graphData.value?.relations) return 0
  const types = new Set(graphData.value.relations.map(r => r.relation))
  return types.size
})

const allRelationTypes = computed(() => {
  if (!graphData.value?.relations) return []
  const relationCounts = {}
  graphData.value.relations.forEach(r => {
    relationCounts[r.relation] = (relationCounts[r.relation] || 0) + 1
  })
  const sorted = Object.entries(relationCounts)
    .sort((a, b) => b[1] - a[1])
  const maxCount = sorted.length > 0 ? sorted[0][1] : 0
  return sorted.map(([type, count]) => ({ type, count, maxCount }))
})

const relationPage = ref(1)
const totalRelationPages = computed(() => Math.ceil(allRelationTypes.value.length / 5) || 1)

const pagedRelations = computed(() => {
  const start = (relationPage.value - 1) * 5
  const items = allRelationTypes.value.slice(start, start + 5)
  const pageMax = items.length > 0 ? items[0].count : 0
  return items.map(item => ({ ...item, maxCount: pageMax }))
})

const pageMaxCount = computed(() => {
  if (pagedRelations.value.length === 0) return 0
  return pagedRelations.value[0].count
})

// Relation detail modal
const showRelationDetailModal = ref(false)
const relationDetailType = ref('')
const relationDetailItems = ref([])
const relationDetailSearch = ref('')

function openRelationDetail(type) {
  relationDetailType.value = type
  relationDetailSearch.value = ''
  const items = (graphData.value?.relations || [])
    .filter(r => r.relation === type)
    .map(r => ({
      source: r.source || r.head || '',
      target: r.target || r.tail || '',
      relation: r.relation,
      description: r.description || r.desc || '',
      expanded: false
    }))
  relationDetailItems.value = items
  showRelationDetailModal.value = true
}

const filteredRelationDetailItems = computed(() => {
  if (!relationDetailSearch.value.trim()) return relationDetailItems.value
  const q = relationDetailSearch.value.toLowerCase()
  return relationDetailItems.value.filter(item =>
    item.source.toLowerCase().includes(q) ||
    item.target.toLowerCase().includes(q) ||
    item.description.toLowerCase().includes(q)
  )
})

const pieChartGradient = computed(() => {
  if (!stats.value) return 'conic-gradient(#ccc 0deg 360deg)'
  const data = [
    { name: 'Operators', value: stats.value.operators || 0, color: '#00e5c7' },
    { name: 'Stories', value: stats.value.stories || 0, color: '#ff6b9d' },
    { name: 'Knowledge', value: stats.value.knowledge || 0, color: '#7c5cff' }
  ]
  const total = data.reduce((sum, d) => sum + d.value, 0)
  if (total === 0) return 'conic-gradient(#ccc 0deg 360deg)'
  const gradients = data.map((d, i) => {
    const percent = (d.value / total * 100)
    const prevPercent = data.slice(0, i).reduce((sum, d) => sum + (d.value / total * 100), 0)
    return `${d.color} ${prevPercent}% ${prevPercent + percent}%`
  }).join(', ')
  return `conic-gradient(${gradients})`
})

// Evaluation functionality
const evalRunning = ref(false)
const evalProgress = ref(0)
const evalResults = ref(null)

async function runEvaluation() {
  if (evalRunning.value) return

  evalRunning.value = true
  evalProgress.value = 10
  evalResults.value = null

  try {
    evalProgress.value = 30
    const result = await api.runEval()
    evalProgress.value = 90
    if (result.results) {
      result.results.forEach(r => r.expanded = false)
    }
    evalResults.value = result
    evalProgress.value = 100
  } catch (error) {
    showAlert('错误', `评估出错: ${error.message}`)
    evalRunning.value = false
    evalProgress.value = 0
  }
  evalRunning.value = false
}

function getScoreClass(score) {
  if (score === undefined || score === null) return ''
  if (score >= 7) return 'score-high'
  if (score >= 4) return 'score-mid'
  return 'score-low'
}

function toggleEvalResultExpandedByResult(result) {
  result.expanded = !result.expanded
}

// Modal state
const showConfirmModal = ref(false)
const showAlertModal = ref(false)
const confirmTitle = ref('确认')
const confirmMessage = ref('')
const confirmResolve = ref(null)
const alertTitle = ref('提示')
const alertMessage = ref('')

function showAlert(title, message) {
  alertTitle.value = title
  alertMessage.value = message
  showAlertModal.value = true
}

function showConfirm(title, message) {
  return new Promise((resolve) => {
    confirmTitle.value = title
    confirmMessage.value = message
    showConfirmModal.value = true
    confirmResolve.value = resolve
  })
}

function confirmOk() {
  showConfirmModal.value = false
  if (confirmResolve.value) confirmResolve.value(true)
}

function confirmCancel() {
  showConfirmModal.value = false
  if (confirmResolve.value) confirmResolve.value(false)
}
</script>

<style scoped>
.admin-page { padding: var(--spacing-xl); }
.nav-tabs { display: flex; gap: var(--spacing-sm); padding: var(--spacing-md); background: var(--bg-panel); border-bottom: 1px solid var(--border-color); }
.nav-tab { padding: var(--spacing-sm) var(--spacing-lg); background: transparent; border: 1px solid var(--border-color); border-radius: var(--radius-md); color: var(--text-secondary); font-family: var(--font-display); font-size: 0.85rem; letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; transition: all var(--transition-fast); display: flex; align-items: center; gap: var(--spacing-sm); }
.nav-tab:hover { background: var(--bg-panel-hover); border-color: var(--color-primary-dim); color: var(--text-primary); }
.nav-tab.active { background: var(--color-primary); border-color: var(--color-primary); color: var(--bg-deep); box-shadow: 0 0 15px var(--color-primary-glow); }
.admin-content { padding: var(--spacing-lg) 0; }
.tab-content { display: block; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--spacing-lg); }
.section-title { font-family: var(--font-display); font-size: 1.1rem; color: var(--text-primary); text-transform: uppercase; }
.chunk-browser { display: grid; grid-template-columns: 300px 1fr; gap: var(--spacing-lg); min-height: 600px; }
.chunk-list { background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: var(--radius-lg); overflow: hidden; display: flex; flex-direction: column; }
.chunk-list-header { padding: var(--spacing-md); border-bottom: 1px solid var(--border-color); background: var(--bg-card); }
.chunk-list-header .form-group { margin-bottom: var(--spacing-sm); }
.chunk-list-header .form-group:last-child { margin-bottom: 0; }
.chunk-search-results { position: absolute; top: 100%; left: 0; width: 100%; background: var(--bg-dark); border: 1px solid var(--border-color); border-radius: var(--radius-md); max-height: 600px; overflow-y: auto; z-index: 100; display: none; }
.chunk-search-results.active { display: block; }
.chunk-search-item { padding: var(--spacing-sm) var(--spacing-md); cursor: pointer; font-size: 0.85rem; border-bottom: 1px solid var(--border-color); transition: background var(--transition-fast); }
.chunk-search-item:hover { background: var(--bg-panel-hover); }
.chunk-list-body { flex: 1; overflow-y: auto; }
.chunk-item { padding: var(--spacing-md); border-bottom: 1px solid var(--border-color); cursor: pointer; transition: all var(--transition-fast); }
.chunk-item:hover { background: var(--bg-panel-hover); }
.chunk-item.active { background: var(--color-primary-glow); border-left: 3px solid var(--color-primary); }
.chunk-item-title { font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-primary); margin-bottom: var(--spacing-xs); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chunk-item-meta { display: flex; gap: var(--spacing-md); font-size: 0.75rem; color: var(--text-dim); }
.chunk-preview { background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: var(--radius-lg); display: flex; flex-direction: column; overflow: hidden; }
.chunk-preview-header { padding: var(--spacing-md) var(--spacing-lg); border-bottom: 1px solid var(--border-color); background: var(--bg-card); display: flex; flex-wrap: wrap; align-items: center; gap: var(--spacing-sm); }
.chunk-preview-title { font-family: var(--font-mono); font-size: 1rem; color: var(--color-primary); }
.chunk-preview-stats { display: flex; gap: var(--spacing-lg); font-size: 0.8rem; color: var(--text-secondary); }
.chunk-nav-inline { display: flex; align-items: center; gap: var(--spacing-xs); margin-left: auto; }
.chunk-nav-info { font-size: 0.85rem; color: var(--text-secondary); padding: 0 var(--spacing-xs); }
.chunk-nav-input { width: 60px; padding: var(--spacing-xs); background: var(--bg-dark); border: 1px solid var(--border-color); border-radius: var(--radius-sm); color: var(--text-primary); font-size: 0.85rem; text-align: center; }
.chunk-nav-input:focus { outline: none; border-color: var(--color-primary); }
.chunk-preview-content { flex: 1; padding: var(--spacing-lg); overflow-y: auto; background: var(--bg-dark); font-size: 0.9rem; line-height: 1.8; white-space: pre-wrap; word-break: break-all; }
.empty-state { padding: var(--spacing-xl); text-align: center; color: var(--text-dim); }
.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--spacing-lg); margin-bottom: var(--spacing-xl); }
.stat-card { background: linear-gradient(135deg, var(--bg-panel) 0%, var(--bg-card) 100%); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: var(--spacing-lg); position: relative; overflow: hidden; transition: all var(--transition-fast); }
.stat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, var(--color-primary) 0%, transparent 100%); }
.stat-card:hover { border-color: var(--color-primary-dim); transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.3); }
.stat-label { font-size: 0.85rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.1em; }
.stat-value { font-family: var(--font-display); font-size: 2rem; color: var(--color-primary); text-shadow: 0 0 20px var(--color-primary-glow); }
.stat-unit { font-family: var(--font-display); font-size: 2rem; color: var(--color-primary); text-shadow: 0 0 20px var(--color-primary-glow); margin-left: 2px; }
.stat-sub { font-size: 0.8rem; color: var(--text-secondary); margin-top: 2px; }
.btn-small { padding: var(--spacing-xs) var(--spacing-sm); font-size: 0.8rem; }

/* Evaluation styles */
.panel { background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: var(--radius-lg); overflow: hidden; }
.panel-header { display: flex; justify-content: space-between; align-items: center; padding: var(--spacing-lg); border-bottom: 1px solid var(--border-color); background: var(--bg-card); }
.panel-header h3 { font-size: 0.9rem; color: var(--text-primary); margin: 0; }
.panel-body { padding: var(--spacing-lg); }
.eval-progress { padding: var(--spacing-lg) 0; }
.progress-bar { height: 8px; background: var(--bg-dark); border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, var(--color-primary) 0%, var(--color-primary-dim) 100%); transition: width var(--transition-normal); }
.eval-result-summary { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: var(--spacing-lg); margin-bottom: var(--spacing-lg); }
.eval-metrics { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--spacing-lg); }
.eval-metric { text-align: center; }
.eval-metric-value { font-family: var(--font-display); font-size: 1.5rem; color: var(--color-primary); }
.eval-metric-label { font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-top: var(--spacing-xs); }

/* Eval Result Cards */
.eval-result-cards { display: flex; flex-direction: column; gap: var(--spacing-sm); margin-top: var(--spacing-lg); }
.eval-result-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); overflow: hidden; }
.eval-result-card.expanded { border-color: var(--color-primary-dim); }
.eval-card-header { display: flex; justify-content: space-between; align-items: center; padding: var(--spacing-md) var(--spacing-lg); cursor: pointer; transition: background var(--transition-fast); }
.eval-card-header:hover { background: var(--bg-panel-hover); }
.eval-card-summary { display: flex; align-items: center; gap: var(--spacing-md); flex: 1; min-width: 0; }
.eval-card-id { font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-dim); flex-shrink: 0; }
.eval-card-question { font-size: 0.9rem; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.eval-card-scores { display: flex; align-items: center; gap: var(--spacing-md); flex-shrink: 0; }
.eval-score-badge { font-family: var(--font-mono); font-size: 0.9rem; font-weight: 600; padding: var(--spacing-xs) var(--spacing-sm); border-radius: var(--radius-sm); }
.eval-score-badge.score-high { background: rgba(0, 230, 118, 0.2); color: #00e676; }
.eval-score-badge.score-mid { background: rgba(255, 193, 7, 0.2); color: #ffc107; }
.eval-score-badge.score-low { background: rgba(255, 71, 87, 0.2); color: #ff4757; }
.eval-card-toggle { font-size: 0.75rem; color: var(--text-dim); }
.eval-card-body { border-top: 1px solid var(--border-color); padding: var(--spacing-lg); background: var(--bg-dark); }
.eval-card-section { margin-bottom: var(--spacing-lg); }
.eval-card-section:last-child { margin-bottom: 0; }
.eval-card-section h5 { font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--spacing-sm); }
.eval-answer { font-size: 0.9rem; color: var(--text-primary); line-height: 1.6; margin: 0; white-space: pre-wrap; }
.eval-scores-detail { display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--spacing-md); margin-bottom: var(--spacing-sm); }
.eval-score-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: var(--spacing-sm); text-align: center; }
.eval-score-label { display: block; font-size: 0.7rem; color: var(--text-secondary); margin-bottom: var(--spacing-xs); }
.eval-score-value { font-family: var(--font-mono); font-size: 1rem; font-weight: 600; color: var(--color-primary); }
.eval-reasoning { font-size: 0.85rem; color: var(--text-secondary); font-style: italic; margin: 0; }

/* Dashboard styles */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-xl); margin-top: var(--spacing-xl); }
.graph-stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--spacing-md); margin-bottom: var(--spacing-lg); }
.graph-stat-mini { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: var(--spacing-md); text-align: center; }
.graph-stat-value { font-family: var(--font-display); font-size: 1.5rem; color: var(--color-primary); }
.graph-stat-label { font-size: 0.75rem; color: var(--text-secondary); margin-top: var(--spacing-xs); }
.relation-type-section h4 { font-size: 0.85rem; color: var(--text-secondary); margin: 0; }
.relation-section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--spacing-md); }
.relation-section-left { display: flex; align-items: center; gap: var(--spacing-md); }
.relation-pagination { display: flex; align-items: center; gap: var(--spacing-xs); }
.relation-page-info { font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-dim); }
.vertical-bar-item.clickable { cursor: pointer; transition: transform var(--transition-fast); }
.vertical-bar-item.clickable:hover { transform: scale(1.05); }
.vertical-bar-item.clickable:hover .vertical-bar-fill { box-shadow: 0 0 10px var(--color-primary-glow); }

/* Relation detail modal */
.relation-detail-modal { width: 600px; max-height: 85vh; }
.relation-detail-count { font-size: 0.8rem; color: var(--text-dim); margin-left: var(--spacing-sm); }
.relation-detail-list { display: flex; flex-direction: column; gap: 4px; max-height: 50vh; overflow-y: auto; }
.relation-detail-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: var(--spacing-sm) var(--spacing-md); cursor: pointer; transition: all var(--transition-fast); }
.relation-detail-item:hover { border-color: var(--color-primary-dim); }
.relation-detail-item.expanded { border-color: var(--color-primary); }
.relation-detail-triple { display: flex; align-items: center; gap: var(--spacing-sm); font-size: 0.85rem; flex-wrap: wrap; }
.relation-detail-entity { color: var(--color-primary); font-weight: 500; }
.relation-detail-arrow { color: var(--text-dim); font-size: 0.75rem; }
.relation-detail-rel { color: var(--text-secondary); background: var(--bg-panel); padding: 1px 6px; border-radius: var(--radius-sm); font-size: 0.8rem; }
.relation-detail-expand { margin-left: auto; font-size: 0.7rem; color: var(--text-dim); }
.relation-detail-desc { margin-top: var(--spacing-sm); padding-top: var(--spacing-sm); border-top: 1px solid var(--border-color); font-size: 0.8rem; color: var(--text-secondary); line-height: 1.6; }
.relation-chart { height: 280px; overflow-y: auto; }
.vertical-bar-chart { display: flex; align-items: flex-end; justify-content: space-around; height: 220px; padding: var(--spacing-md); gap: var(--spacing-sm); }
.vertical-bar-item { display: flex; flex-direction: column; align-items: center; flex: 1; max-width: 60px; height: 100%; }
.vertical-bar-value { font-family: var(--font-mono); font-size: 0.7rem; color: var(--color-primary); margin-bottom: var(--spacing-xs); }
.vertical-bar-track { flex: 1; width: 100%; background: var(--bg-dark); border-radius: var(--radius-sm) var(--radius-sm) 0 0; overflow: hidden; display: flex; align-items: flex-end; }
.vertical-bar-fill { width: 100%; background: linear-gradient(180deg, var(--color-primary) 0%, var(--color-primary-dim) 100%); transition: height var(--transition-normal); border-radius: var(--radius-sm) var(--radius-sm) 0 0; }
.vertical-bar-label { font-size: 0.65rem; color: var(--text-secondary); text-align: center; margin-top: var(--spacing-xs); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.pie-chart-container { display: flex; align-items: center; gap: var(--spacing-xl); }
.pie-chart { width: 180px; height: 180px; border-radius: 50%; flex-shrink: 0; }
.pie-legend { display: flex; flex-direction: column; gap: var(--spacing-sm); }
.pie-legend-item { display: flex; align-items: center; gap: var(--spacing-sm); }
.pie-legend-color { width: 14px; height: 14px; border-radius: 3px; flex-shrink: 0; }
.pie-legend-name { font-size: 0.85rem; color: var(--text-secondary); }
.pie-legend-value { font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-primary); margin-left: auto; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

/* Modal styles */
.modal-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.7); z-index: 1000; align-items: center; justify-content: center; }
.modal-overlay.active { display: flex; }
.modal-content { background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: var(--radius-lg); width: 380px; max-height: 80vh; overflow: hidden; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5); }
.modal-sm { width: 320px; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: var(--spacing-lg); border-bottom: 1px solid var(--border-color); }
.modal-header h2 { font-family: var(--font-display); font-size: 1.1rem; color: var(--text-primary); margin: 0; }
.modal-close { background: none; border: none; color: var(--text-dim); font-size: 1.5rem; cursor: pointer; padding: 0; line-height: 1; }
.modal-close:hover { color: var(--text-primary); }
.modal-body { padding: var(--spacing-lg); }
.modal-body p { color: var(--text-secondary); margin: 0; line-height: 1.6; }
.modal-body.text-center { text-align: left; }
.modal-body.text-center h2 { font-family: var(--font-display); font-size: 1.1rem; color: var(--text-primary); margin: 0 0 var(--spacing-sm) 0; }
.modal-body.text-center p { color: var(--text-secondary); margin: 0 0 var(--spacing-lg) 0; }
.modal-body.text-center .btn { margin-top: var(--spacing-sm); float: right; }
.modal-footer { display: flex; justify-content: flex-end; gap: var(--spacing-sm); padding: var(--spacing-lg); border-top: 1px solid var(--border-color); }

/* Mobile responsive */
@media (max-width: 768px) {
  .admin-page { padding: var(--spacing-md); }
  .nav-tabs { flex-wrap: wrap; gap: var(--spacing-xs); }
  .nav-tab { padding: var(--spacing-xs) var(--spacing-md); font-size: 0.75rem; }
  .chunk-browser { grid-template-columns: 1fr; min-height: auto; }
  .chunk-preview { min-height: 400px; }
  .stats-row { grid-template-columns: repeat(3, 1fr); gap: var(--spacing-sm); }
  .stat-card { padding: var(--spacing-md); }
  .stat-value { font-size: 1.2rem; }
  .stat-unit { font-size: 1.2rem; }
  .grid-2 { grid-template-columns: 1fr; }
  .eval-scores-detail { grid-template-columns: repeat(3, 1fr); }
  .relation-section-header { flex-direction: column; align-items: flex-start; }
  .relation-section-left { flex-wrap: wrap; }
  .relation-detail-modal { width: calc(100vw - 32px) !important; }
  .relation-detail-triple { font-size: 0.8rem; }
}
</style>
