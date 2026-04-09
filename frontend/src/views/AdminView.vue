<template>
  <div class="admin-page">
    <nav class="nav-tabs">
      <button class="nav-tab" :class="{ active: activeTab === 'chunk' }" @click="activeTab = 'chunk'">
        <span>1</span> Chunk 可视化
      </button>
      <button class="nav-tab" :class="{ active: activeTab === 'debug' }" @click="activeTab = 'debug'">
        <span>2</span> RAG 调试
      </button>
      <button class="nav-tab" :class="{ active: activeTab === 'dashboard' }" @click="activeTab = 'dashboard'">
        <span>3</span> 数据仪表板
      </button>
      <button class="nav-tab" :class="{ active: activeTab === 'eval' }" @click="activeTab = 'eval'">
        <span>4</span> 评估面板
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
            <div class="stat-icon">O</div>
            <div class="stat-value">{{ stats.operators }}</div>
            <div class="stat-label">Operators</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">S</div>
            <div class="stat-value">{{ stats.stories }}</div>
            <div class="stat-label">Stories</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">K</div>
            <div class="stat-value">{{ stats.knowledge }}</div>
            <div class="stat-label">Knowledge</div>
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
                  <div class="graph-stat-value">{{ graphData.entities?.length || 0 }}</div>
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

              <div class="relation-type-section" v-if="topRelations.length > 0">
                <h4>Top 10 关系类型</h4>
                <div class="relation-chart">
                  <div class="vertical-bar-chart">
                    <div v-for="item in topRelations" :key="item.type" class="vertical-bar-item">
                      <div class="vertical-bar-value">{{ item.count }}</div>
                      <div class="vertical-bar-track">
                        <div class="vertical-bar-fill" :style="{ height: (item.maxCount > 0 ? (item.count / item.maxCount * 100) : 0) + '%' }"></div>
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

      <div v-if="activeTab === 'debug'" class="tab-content">
        <div class="section-header">
          <h2 class="section-title">RAG 调试</h2>
        </div>
        <div class="debug-container">
          <div class="debug-sidebar">
            <div class="debug-section">
              <h3>测试问题</h3>
              <input type="text" class="input" v-model="debugQuestion" placeholder="输入测试问题...">
            </div>

            <div class="debug-section" v-if="!compareMode">
              <h3>RAG 功能</h3>
              <div class="debug-toggle-item">
                <span>CRAG 判断</span>
                <button class="toggle-btn" :class="{ active: debugUseCrag }" @click="debugUseCrag = !debugUseCrag">
                  {{ debugUseCrag ? '开' : '关' }}
                </button>
              </div>
              <div class="debug-toggle-item">
                <span>知识图谱</span>
                <button class="toggle-btn" :class="{ active: debugUseGraphrag }" @click="debugUseGraphrag = !debugUseGraphrag">
                  {{ debugUseGraphrag ? '开' : '关' }}
                </button>
              </div>
              <div class="debug-toggle-item">
                <span>Parent文档</span>
                <button class="toggle-btn" :class="{ active: debugUseParentDoc }" @click="debugUseParentDoc = !debugUseParentDoc">
                  {{ debugUseParentDoc ? '开' : '关' }}
                </button>
              </div>
            </div>

            <div class="debug-section" v-if="!compareMode">
              <h3>召回数量</h3>
              <div class="debug-param">
                <label>每库召回</label>
                <input type="number" class="input input-small" v-model.number="debugTopKPerChannel" min="1" max="50">
              </div>
              <div class="debug-param">
                <label>重排数量</label>
                <input type="number" class="input input-small" v-model.number="debugRerankTopK" min="1" max="50">
              </div>
            </div>

            <!-- 对比模式 -->
            <div class="debug-section" v-if="!compareMode">
              <button class="btn btn-primary btn-full" @click="stepDebug">
                <span>&gt;</span> {{ currentDebugStep > 0 ? '下一步' : '单步调试' }}
              </button>
              <button class="btn btn-primary btn-full" @click="runAllDebugSteps" style="margin-top: 8px;">
                <span>&gt;&gt;</span> 运行全部步骤
              </button>
              <button class="btn btn-secondary btn-full" @click="toggleCompareMode" style="margin-top: 8px;">
                <span>=</span> 对比模式
              </button>
            </div>

            <!-- 对比模式配置 -->
            <div class="debug-section" v-if="compareMode">
              <h3>对比配置</h3>
              <div class="compare-configs">
                <div v-for="config in compareConfigs" :key="config.id" class="compare-config-card">
                  <div class="compare-config-header">
                    <span class="compare-config-title">{{ config.name }}</span>
                    <button v-if="compareConfigs.length > 1" class="compare-config-remove" @click="removeCompareConfig(config.id)">&times;</button>
                  </div>
                  <div class="compare-config-toggle">
                    <span>CRAG</span>
                    <button class="toggle-btn" :class="{ active: config.use_crag }" @click="config.use_crag = !config.use_crag">
                      {{ config.use_crag ? '开' : '关' }}
                    </button>
                  </div>
                  <div class="compare-config-toggle">
                    <span>GraphRAG</span>
                    <button class="toggle-btn" :class="{ active: config.use_graphrag }" @click="config.use_graphrag = !config.use_graphrag">
                      {{ config.use_graphrag ? '开' : '关' }}
                    </button>
                  </div>
                  <div class="compare-config-toggle">
                    <span>ParentDoc</span>
                    <button class="toggle-btn" :class="{ active: config.use_parent_doc }" @click="config.use_parent_doc = !config.use_parent_doc">
                      {{ config.use_parent_doc ? '开' : '关' }}
                    </button>
                  </div>
                  <div class="compare-config-param">
                    <label>干员库</label>
                    <input type="number" class="input input-small" v-model.number="config.top_k_operators" min="1" max="50">
                  </div>
                  <div class="compare-config-param">
                    <label>故事库</label>
                    <input type="number" class="input input-small" v-model.number="config.top_k_stories" min="1" max="50">
                  </div>
                  <div class="compare-config-param">
                    <label>知识库</label>
                    <input type="number" class="input input-small" v-model.number="config.top_k_knowledge" min="1" max="50">
                  </div>
                  <div class="compare-config-param">
                    <label>每库召回</label>
                    <input type="number" class="input input-small" v-model.number="config.top_k_per_channel" min="1" max="50">
                  </div>
                  <div class="compare-config-param">
                    <label>重排数</label>
                    <input type="number" class="input input-small" v-model.number="config.rerank_top_k" min="1" max="50">
                  </div>
                </div>
              </div>
              <button class="btn btn-small" @click="addCompareConfig" style="margin-top: 8px;">
                <span>+</span> 添加配置
              </button>
              <button class="btn btn-secondary btn-full" @click="toggleCompareMode" style="margin-top: 8px;">
                <span>&lt;</span> 返回单步
              </button>
              <button class="btn btn-primary btn-full" @click="runCompare" style="margin-top: 8px;">
                <span>&gt;</span> 运行对比
              </button>
            </div>
          </div>

          <div class="debug-main">
            <!-- 单步模式 -->
            <div v-if="!compareMode" class="pipeline-steps-container">
              <div class="pipeline-steps">
                <div v-for="step in debugSteps" :key="step.id" class="pipeline-step-card" :class="step.status">
                  <div class="pipeline-step-header" @click="step.expanded = !step.expanded">
                    <span class="pipeline-step-number">{{ step.id }}</span>
                    <span class="pipeline-step-name">{{ step.name }}</span>
                    <span class="pipeline-step-time">{{ step.time || '--' }}</span>
                    <span class="pipeline-step-status" :class="step.status"></span>
                    <div class="pipeline-step-actions">
                      <button class="btn btn-small" @click.stop="runDebugStep(step.id)" :disabled="debugRunning">
                        {{ debugRunning && currentStep === step.id ? '...' : '运行' }}
                      </button>
                    </div>
                  </div>
                  <div class="pipeline-step-body" :class="{ open: step.expanded }">
                    <div class="pipeline-step-content">
                      <h4>输入</h4>
                      <pre>{{ step.input || '等待执行...' }}</pre>
                      <h4>输出</h4>
                      <pre>{{ step.output || '等待执行...' }}</pre>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <!-- 对比模式结果 -->
            <div v-if="compareMode" class="compare-results">
              <div class="compare-header">
                <h3>对比结果</h3>
              </div>
              <div v-if="compareRunning" class="compare-loading">
                <span>运行中...</span>
                <div class="spinner"></div>
              </div>
              <div v-else-if="compareResults.length === 0" class="empty-state">
                <div class="empty-state-title">暂无对比结果</div>
                <div class="empty-state-desc">点击"运行对比"开始对比</div>
              </div>
              <div v-else class="compare-container">
                <div v-for="result in compareResults" :key="result.config.id" class="compare-result-card" :class="{ expanded: result.expanded }">
                  <div class="compare-result-header" @click="toggleCompareResultExpanded(result.config.id)">
                    <div class="compare-result-summary">
                      <span class="compare-result-name">{{ result.config.name }}</span>
                      <span class="compare-result-meta">
                        召回数:{{ result.config.top_k_operators + result.config.top_k_stories + result.config.top_k_knowledge }} |
                        重排:{{ result.config.rerank_top_k }} |
                        CRAG:{{ result.config.use_crag ? '✓' : '✗' }} |
                        GraphRAG:{{ result.config.use_graphrag ? '✓' : '✗' }} |
                        ParentDoc:{{ result.config.use_parent_doc ? '✓' : '✗' }} |
                        耗时:{{ result.elapsed }}ms
                      </span>
                      <span class="compare-result-answer" v-if="result.answer">{{ escapeHtml(result.answer.substring(0, 80)) }}{{ result.answer.length > 80 ? '...' : '' }}</span>
                    </div>
                    <span class="compare-result-toggle">{{ result.expanded ? '▲ 点击收起' : '▼ 点击展开' }}</span>
                  </div>
                  <div class="compare-result-body" v-if="result.expanded">
                    <div v-if="result.error" class="compare-error">{{ escapeHtml(result.error) }}</div>
                    <div v-else-if="result.pipeline_steps && result.pipeline_steps.length > 0" class="compare-steps">
                      <div v-for="step in result.pipeline_steps" :key="step.step" class="compare-step-card">
                        <div class="compare-step-header">
                          <span class="compare-step-number">{{ step.step }}</span>
                          <span class="compare-step-name">{{ step.name_cn || step.name }}</span>
                          <span class="compare-step-time">{{ step.time_ms }}ms</span>
                          <span class="compare-step-toggle" @click="toggleCompareStepExpandedByStep(step)">{{ step.expanded ? '▲' : '▼' }}</span>
                        </div>
                        <div class="compare-step-body" v-if="step.expanded">
                          <pre class="compare-step-content">{{ formatStepData(step.input_data) }}</pre>
                          <pre class="compare-step-content">{{ formatStepData(step.output_data) }}</pre>
                        </div>
                      </div>
                    </div>
                    <div v-else class="compare-empty">无步骤数据</div>
                  </div>
                </div>
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
  chunks.value = [] // 立即清空，避免显示旧数据
  try {
    chunks.value = await api.getChunks(chunkCollection.value)
    // Auto-select first chunk after loading
    if (chunks.value.length > 0) {
      selectChunk(chunks.value[0])
    }
    // 如果搜索框已聚焦且没有搜索内容，更新下拉列表
    if (searchFocused.value && !chunkSearch.value.trim()) {
      searchResults.value = chunks.value
    }
  } catch (e) {
    chunks.value = []
  }
  loadingChunks.value = false
}

async function selectChunk(chunk) {
  if (chunk.placeholder) return // 忽略占位项
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
  // Filter from already loaded chunks
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
  // 延迟清空搜索结果，确保点击事件能先触发
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
const relationTypesCount = computed(() => {
  if (!graphData.value?.relations) return 0
  const types = new Set(graphData.value.relations.map(r => r.relation))
  return types.size
})

const topRelations = computed(() => {
  if (!graphData.value?.relations) return []
  const relationCounts = {}
  graphData.value.relations.forEach(r => {
    relationCounts[r.relation] = (relationCounts[r.relation] || 0) + 1
  })
  const sorted = Object.entries(relationCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
  const maxCount = sorted.length > 0 ? sorted[0][1] : 0
  return sorted.map(([type, count]) => ({ type, count, maxCount }))
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

// Debug functionality
const debugQuestion = ref('')
const debugUseCrag = ref(true)
const debugUseGraphrag = ref(true)
const debugUseParentDoc = ref(true)
const debugTopKPerChannel = ref(8)
const debugRerankTopK = ref(5)
const debugRunning = ref(false)
const currentStep = ref(null)
const currentDebugStep = ref(0) // 0 = not started, 1-8 = current step for step debugging
const stepResults = ref({})
const debugSteps = ref([
  { id: 1, name: '查询改写', status: 'pending', time: null, input: null, output: null, expanded: false },
  { id: 2, name: '多通道召回', status: 'pending', time: null, input: null, output: null, expanded: false },
  { id: 3, name: '交叉编码重排', status: 'pending', time: null, input: null, output: null, expanded: false },
  { id: 4, name: 'CRAG 判断', status: 'pending', time: null, input: null, output: null, expanded: false },
  { id: 5, name: '知识图谱查询', status: 'pending', time: null, input: null, output: null, expanded: false },
  { id: 6, name: 'Parent文档扩展', status: 'pending', time: null, input: null, output: null, expanded: false },
  { id: 7, name: '网络搜索', status: 'pending', time: null, input: null, output: null, expanded: false },
  { id: 8, name: '答案生成', status: 'pending', time: null, input: null, output: null, expanded: false }
])

// Compare mode
const compareMode = ref(false)
const compareConfigs = ref([])
const compareResults = ref([])
const compareRunning = ref(false)
let compareConfigIdCounter = 0

// Modal state
const showConfirmModal = ref(false)
const showAlertModal = ref(false)
const confirmTitle = ref('确认')
const confirmMessage = ref('')
const confirmResolve = ref(null)
const alertTitle = ref('提示')
const alertMessage = ref('')

// Toggle functions for reactive state (avoid direct mutation in template)
function toggleDebugStepExpanded(stepId) {
  const step = debugSteps.value.find(s => s.id === stepId)
  if (step) {
    step.expanded = !step.expanded
  }
}

function toggleCompareResultExpanded(resultId) {
  const result = compareResults.value.find(r => r.config.id === resultId)
  if (result) {
    result.expanded = !result.expanded
  }
}

function toggleCompareStepExpandedByStep(step) {
  // Toggle directly on step object from v-for (Vue tracks the mutation)
  step.expanded = !step.expanded
}

function toggleEvalResultExpandedByResult(result) {
  // Toggle directly on result object from v-for
  result.expanded = !result.expanded
}

function toggleDebugStepStatus(stepId, status) {
  const step = debugSteps.value.find(s => s.id === stepId)
  if (step) {
    step.status = status
  }
}

function toggleCompareMode() {
  compareMode.value = !compareMode.value
  if (compareMode.value) {
    // Initialize with default config
    compareConfigs.value = [{
      id: ++compareConfigIdCounter,
      name: '配置 A',
      use_crag: true,
      use_graphrag: true,
      use_parent_doc: true,
      top_k_operators: 8,
      top_k_stories: 8,
      top_k_knowledge: 8,
      top_k_per_channel: 8,
      rerank_top_k: 5
    }]
    compareResults.value = []
  }
}

function addCompareConfig() {
  const id = ++compareConfigIdCounter
  const letter = String.fromCharCode(64 + id)
  compareConfigs.value.push({
    id,
    name: `配置 ${letter}`,
    use_crag: true,
    use_graphrag: true,
    use_parent_doc: true,
    top_k_operators: 10,
    top_k_stories: 10,
    top_k_knowledge: 10,
    rerank_top_k: 5
  })
}

function removeCompareConfig(id) {
  if (compareConfigs.value.length > 1) {
    compareConfigs.value = compareConfigs.value.filter(c => c.id !== id)
  }
}

function getConfigSignature(config) {
  return [
    config.use_crag ? '1' : '0',
    config.use_graphrag ? '1' : '0',
    config.use_parent_doc ? '1' : '0',
    config.top_k_operators,
    config.top_k_stories,
    config.top_k_knowledge,
    config.rerank_top_k
  ].join('-')
}

async function runCompare() {
  if (!debugQuestion.value.trim()) {
    console.log('runCompare: empty question, showing alert')
    showAlert('提示', '请输入测试问题')
    return
  }

  // Check for duplicate configs
  const signatures = compareConfigs.value.map(c => getConfigSignature(c))
  const uniqueSignatures = new Set(signatures)
  if (signatures.length !== uniqueSignatures.size) {
    const confirmed = await showConfirm('检测到相同配置', '有相同配置，是否强制运行？')
    if (!confirmed) return
  }

  compareRunning.value = true
  compareResults.value = []

  for (const config of compareConfigs.value) {
    const startTime = Date.now()
    try {
      const result = await api.query(debugQuestion.value, {
        conversation_history: [],
        ...config
      })
      const elapsed = Date.now() - startTime

      compareResults.value.push({
        config,
        result,
        elapsed,
        answer: result.answer || '无答案',
        pipeline_steps: result.pipeline_steps || [],
        expanded: false,
        error: null
      })
    } catch (error) {
      const elapsed = Date.now() - startTime
      compareResults.value.push({
        config,
        result: null,
        elapsed,
        answer: '错误: ' + error.message,
        pipeline_steps: [],
        expanded: false,
        error: error.message
      })
    }
  }

  compareRunning.value = false
}

function showAlert(title, message) {
  console.log('showAlert:', title, message)
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

async function runDebugStep(stepId) {
  if (!debugQuestion.value.trim()) {
    console.log('runDebugStep: empty question, showing alert')
    showAlert('提示', '请输入测试问题')
    return
  }
  debugRunning.value = true
  currentStep.value = stepId

  const step = debugSteps.value.find(s => s.id === stepId)
  step.status = 'running'

  try {
    const result = await api.debugStep(debugQuestion.value, stepId, {
      use_crag: debugUseCrag.value,
      use_graphrag: debugUseGraphrag.value,
      use_parent_doc: debugUseParentDoc.value,
      top_k_per_channel: debugTopKPerChannel.value,
      rerank_top_k: debugRerankTopK.value,
      conversation_history: [],
      step_results: stepResults.value
    })

    step.status = 'executed'
    step.time = `${result.time_ms}ms`
    step.input = formatStepData(result.input_data)
    step.output = formatStepData(result.output_data)
    stepResults.value[stepId] = result.output_data
    step.expanded = true
  } catch (error) {
    step.status = 'pending'
    step.output = `错误: ${error.message}`
    step.expanded = true
    showAlert('错误', `步骤${stepId}执行出错: ${error.message}`)
  }

  debugRunning.value = false
  currentStep.value = null
}

// 单步调试：如果没有在调试，从第一步开始；如果在调试，运行下一步
async function stepDebug() {
  if (!debugQuestion.value.trim()) {
    console.log('stepDebug: empty question, showing alert')
    showAlert('提示', '请输入测试问题')
    return
  }

  // 如果currentDebugStep为0，说明还没开始调试，先重置
  if (currentDebugStep.value === 0) {
    stepResults.value = {}
    debugSteps.value.forEach(step => {
      step.status = 'pending'
      step.time = null
      step.input = null
      step.output = null
    })
    currentDebugStep.value = 1
  } else {
    // 已经有上一步了，currentDebugStep已经是下一步的编号
    // 检查上一步是否成功
    const prevStep = debugSteps.value.find(s => s.id === currentDebugStep.value - 1)
    if (prevStep && prevStep.status !== 'executed') {
      showAlert('提示', '上一步执行失败，请先解决问题或重置调试')
      return
    }
    // 如果上一步返回disabled，停止调试
    if (prevStep && stepResults.value[prevStep.id]?.disabled) {
      showAlert('提示', '流程已结束')
      currentDebugStep.value = 0
      return
    }
  }

  // 如果已经到第8步，停止
  if (currentDebugStep.value > 8) {
    showAlert('提示', '已到达最后一步')
    currentDebugStep.value = 0
    return
  }

  await runDebugStep(currentDebugStep.value)

  // 如果步骤失败，重置
  const step = debugSteps.value.find(s => s.id === currentDebugStep.value)
  if (step.status !== 'executed') {
    currentDebugStep.value = 0
    return
  }

  // 如果步骤返回disabled，停止
  if (stepResults.value[currentDebugStep.value]?.disabled) {
    currentDebugStep.value = 0
    return
  }

  // 准备下一步
  currentDebugStep.value++
}

async function runAllDebugSteps() {
  if (!debugQuestion.value.trim()) {
    console.log('runAllDebugSteps: empty question, showing alert')
    showAlert('提示', '请输入测试问题')
    return
  }

  // Reset all steps
  stepResults.value = {}
  currentDebugStep.value = 0
  debugSteps.value.forEach(step => {
    step.status = 'pending'
    step.time = null
    step.input = null
    step.output = null
  })

  debugRunning.value = true
  for (let i = 1; i <= 8; i++) {
    await runDebugStep(i)
    const step = debugSteps.value.find(s => s.id === i)
    // 如果某个步骤失败，停止
    if (step.status !== 'executed') break
    // 如果步骤返回 disabled（可忽略的步骤），停止后续步骤
    // 但 Web Search 被禁用时允许继续，因为 Answer Generation 不依赖它
    if (stepResults.value[i]?.disabled && i !== 7) break
  }
  debugRunning.value = false
}

function formatStepData(data) {
  if (data === null || data === undefined) return '无数据'
  if (typeof data === 'object') return JSON.stringify(data, null, 2)
  return String(data)
}

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
    // Add expanded state to each result
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
.stat-icon { width: 48px; height: 48px; background: var(--color-primary-glow); border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; font-size: 1.5rem; margin-bottom: var(--spacing-md); }
.stat-value { font-family: var(--font-display); font-size: 2rem; color: var(--color-primary); text-shadow: 0 0 20px var(--color-primary-glow); }
.stat-label { font-size: 0.85rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.1em; margin-top: var(--spacing-xs); }
.btn-small { padding: var(--spacing-xs) var(--spacing-sm); font-size: 0.8rem; }

/* Debug styles */
.debug-container { display: flex; gap: var(--spacing-lg); min-height: 600px; }
.debug-sidebar { width: 280px; background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: var(--spacing-lg); }
.debug-main { flex: 1; background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: var(--spacing-lg); display: flex; flex-direction: column; }
.debug-section { margin-bottom: var(--spacing-lg); }
.debug-section:last-child { margin-bottom: 0; }
.debug-section h3 { font-size: 0.85rem; color: var(--color-primary); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: var(--spacing-md); padding-bottom: var(--spacing-xs); border-bottom: 1px solid var(--border-color); }
.debug-toggle-item { display: flex; justify-content: space-between; align-items: center; padding: var(--spacing-sm) 0; border-bottom: 1px solid var(--border-color); }
.debug-toggle-item:last-child { border-bottom: none; }
.debug-param { display: flex; justify-content: space-between; align-items: center; padding: var(--spacing-xs) 0; }
.debug-param label { font-size: 0.8rem; color: var(--text-secondary); }
.input-small { width: 60px; padding: var(--spacing-xs); font-size: 0.8rem; }
.pipeline-steps { display: flex; flex-direction: column; gap: var(--spacing-sm); }
.pipeline-steps-container { flex: 1; overflow-y: auto; max-height: calc(100vh - 150px); border: 1px solid var(--border-color); border-radius: var(--radius-md); background: var(--bg-card); }
.pipeline-step-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); overflow: hidden; }
.pipeline-step-card.pending { opacity: 0.7; }
.pipeline-step-card.running { border-color: var(--color-primary); box-shadow: 0 0 10px var(--color-primary-glow); }
.pipeline-step-card.executed { border-color: #00e676; }
.pipeline-step-header { display: flex; align-items: center; padding: var(--spacing-sm) var(--spacing-md); gap: var(--spacing-sm); cursor: pointer; transition: background var(--transition-fast); }
.pipeline-step-header:hover { background: var(--bg-panel-hover); }
.pipeline-step-number { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; background: var(--color-primary); color: var(--bg-deep); border-radius: 50%; font-family: var(--font-mono); font-size: 0.7rem; font-weight: 600; flex-shrink: 0; }
.pipeline-step-name { font-size: 0.85rem; font-weight: 500; color: var(--text-primary); min-width: 100px; }
.pipeline-step-time { font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-primary); margin-left: auto; }
.pipeline-step-status { width: 10px; height: 10px; border-radius: 50%; margin-left: var(--spacing-sm); }
.pipeline-step-status.pending { background: var(--text-dim); }
.pipeline-step-status.running { background: var(--color-primary); animation: pulse 1s infinite; }
.pipeline-step-status.executed { background: #00e676; }
.pipeline-step-actions { margin-left: auto; }
.pipeline-step-body { display: none; border-top: 1px solid var(--border-color); background: var(--bg-dark); }
.pipeline-step-body.open { display: block; }
.pipeline-step-content { padding: var(--spacing-md); }
.pipeline-step-content h4 { font-size: 0.8rem; color: var(--text-secondary); margin-bottom: var(--spacing-xs); }
.pipeline-step-content pre { background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: var(--spacing-sm); font-size: 0.75rem; color: var(--text-secondary); overflow-x: auto; white-space: pre-wrap; max-height: 200px; overflow-y: auto; margin-top: var(--spacing-xs); }

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
.relation-type-section h4 { font-size: 0.85rem; color: var(--text-secondary); margin-bottom: var(--spacing-md); }
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

/* Compare mode styles */
.compare-configs { display: flex; flex-direction: column; gap: var(--spacing-sm); max-height: 300px; overflow-y: auto; }
.compare-config-card { background: var(--bg-dark); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: var(--spacing-sm); }
.compare-config-header { display: flex; justify-content: space-between; align-items: center; padding-bottom: var(--spacing-xs); border-bottom: 1px solid var(--border-color); margin-bottom: var(--spacing-xs); }
.compare-config-title { font-size: 0.85rem; color: var(--color-primary); font-weight: 500; }
.compare-config-remove { background: none; border: none; color: var(--text-dim); font-size: 1rem; cursor: pointer; padding: 0; }
.compare-config-remove:hover { color: #ff6b7a; }
.compare-config-toggle { display: flex; justify-content: space-between; align-items: center; padding: 2px 0; }
.compare-config-toggle span { font-size: 0.75rem; color: var(--text-secondary); }
.compare-config-param { display: flex; justify-content: space-between; align-items: center; padding: 2px 0; }
.compare-config-param label { font-size: 0.75rem; color: var(--text-secondary); }

/* Compare results styles */
.compare-results { flex: 1; overflow-y: auto; }
.compare-header { padding: var(--spacing-md) 0; border-bottom: 1px solid var(--border-color); margin-bottom: var(--spacing-md); }
.compare-header h3 { font-size: 1rem; color: var(--text-primary); margin: 0; }
.compare-loading { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px; gap: var(--spacing-md); color: var(--text-dim); }
.spinner { width: 30px; height: 30px; border: 3px solid var(--border-color); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 1s linear infinite; }
.compare-container { display: flex; flex-direction: column; gap: var(--spacing-sm); }
.compare-result-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); overflow: hidden; }
.compare-result-card:hover { border-color: var(--color-primary-dim); }
.compare-result-card.expanded { border-color: var(--color-primary); box-shadow: 0 0 20px var(--color-primary-glow); }
.compare-result-header { display: flex; flex-direction: column; gap: var(--spacing-xs); padding: var(--spacing-md); background: rgba(0, 229, 204, 0.03); cursor: pointer; }
.compare-result-header:hover { background: rgba(0, 229, 204, 0.06); }
.compare-result-summary { display: flex; flex-direction: column; gap: 2px; }
.compare-result-name { font-weight: 600; color: var(--color-primary); font-size: 0.9rem; }
.compare-result-meta { font-size: 0.75rem; color: var(--text-secondary); }
.compare-result-answer { font-size: 0.8rem; color: var(--text-dim); margin-top: var(--spacing-xs); }
.compare-result-toggle { font-size: 0.75rem; color: var(--color-primary); }
.compare-result-body { border-top: 1px solid var(--border-color); padding: var(--spacing-md); background: var(--bg-dark); }
.compare-error { color: #ff6b7a; padding: var(--spacing-md); text-align: center; }
.compare-steps { display: flex; flex-direction: column; gap: var(--spacing-xs); }
.compare-step-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-sm); overflow: hidden; }
.compare-step-header { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-xs) var(--spacing-sm); cursor: pointer; background: var(--bg-panel); }
.compare-step-header:hover { background: var(--bg-panel-hover); }
.compare-step-number { width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; background: var(--color-primary); color: var(--bg-deep); border-radius: 50%; font-size: 0.65rem; font-weight: 600; }
.compare-step-name { font-size: 0.75rem; color: var(--text-primary); }
.compare-step-time { font-family: var(--font-mono); font-size: 0.7rem; color: var(--color-primary); margin-left: auto; }
.compare-step-toggle { font-size: 0.7rem; color: var(--color-primary); }
.compare-step-body { padding: var(--spacing-sm); border-top: 1px solid var(--border-color); display: none; }
.compare-step-body:parent { display: block; }
.compare-step-content { background: var(--bg-dark); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: var(--spacing-xs); font-size: 0.7rem; color: var(--text-secondary); white-space: pre-wrap; word-break: break-all; max-height: 150px; overflow-y: auto; margin-bottom: var(--spacing-xs); }
.compare-empty { padding: var(--spacing-lg); text-align: center; color: var(--text-dim); }

@keyframes spin { to { transform: rotate(360deg); } }
</style>