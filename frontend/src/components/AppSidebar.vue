<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-logo">
        <span class="logo-icon">A</span>
        <div class="logo-text">
          <span class="logo-title">Arknights</span>
          <span class="logo-subtitle">RAG System</span>
        </div>
      </div>
    </div>

    <nav class="sidebar-nav">
      <router-link to="/chat" class="nav-item" :class="{ active: $route.path === '/chat' }">
        <span class="nav-icon">Q</span>
        <span class="nav-text">问答助手</span>
      </router-link>
      <router-link to="/admin" class="nav-item" :class="{ active: $route.path === '/admin' }">
        <span class="nav-icon">G</span>
        <span class="nav-text">管理后台</span>
      </router-link>
      <router-link to="/graph" class="nav-item" :class="{ active: $route.path === '/graph' }">
        <span class="nav-icon">N</span>
        <span class="nav-text">知识图谱</span>
      </router-link>
    </nav>

    <!-- Graph Controls - Only show on /graph route -->
    <div class="sidebar-graph-controls" v-if="showGraphControls">
      <!-- Search Section -->
      <div class="sidebar-section">
        <div class="sidebar-section-title">搜索节点</div>
        <div class="kg-search-box">
          <input type="text" v-model="gc.searchQuery.value" placeholder="输入干员名称..." @input="gc.handleSearch(gc.searchQuery.value)" @focus="gc.onSearchFocus" @blur="gc.onSearchBlur">
          <div class="kg-search-results" v-show="gc.searchFocused.value || gc.searchResults.value.length">
            <div v-for="result in gc.searchResults.value" :key="result.entity" class="kg-search-result-item" @mousedown="gc.addNodeSelection(result.entity)">
              <span class="kg-result-name">{{ result.entity }}</span>
              <span class="kg-result-type">{{ result.type || '干员' }}</span>
            </div>
            <div v-if="gc.searchResults.value.length === 0" class="kg-search-result-item kg-no-results">无结果</div>
          </div>
        </div>
      </div>

      <!-- Selected Nodes Section -->
      <div class="sidebar-section">
        <div class="sidebar-section-title">
          已选节点
          <span class="kg-selected-count">{{ gc.selectedNodes.value.length }}</span>
        </div>
        <div class="kg-selected-nodes">
          <div v-if="gc.selectedNodes.value.length === 0" class="kg-empty-hint">点击图上节点或搜索添加</div>
          <div v-else>
            <div v-for="nodeId in gc.selectedNodes.value" :key="nodeId" class="kg-selected-node">
              <span class="kg-selected-node-name">{{ nodeId }}</span>
              <button class="kg-selected-node-remove" @click="gc.removeNodeSelection(nodeId)">X</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Graph Stats -->
      <div class="sidebar-section kg-stats">
        <div class="kg-stat-item">
          <span class="kg-stat-label">节点</span>
          <span class="kg-stat-value">{{ gc.stats.nodes }}</span>
        </div>
        <div class="kg-stat-item">
          <span class="kg-stat-label">边</span>
          <span class="kg-stat-value">{{ gc.stats.edges }}</span>
        </div>
      </div>

      <!-- Level Control -->
      <div class="sidebar-section">
        <div class="sidebar-section-title">邻居层级</div>
        <div class="kg-level-control">
          <button class="kg-level-btn" :class="{ active: gc.neighborLevel.value === 1 }" @click="gc.setNeighborLevel(1)">1度</button>
          <button class="kg-level-btn" :class="{ active: gc.neighborLevel.value === 2 }" @click="gc.setNeighborLevel(2)">2度</button>
        </div>
      </div>

      <!-- Relation Type Filter -->
      <div class="sidebar-section">
        <div class="sidebar-section-title">关系类型筛选</div>
        <div class="kg-rel-search-box">
          <input type="text" v-model="gc.relSearchQuery.value" placeholder="搜索关系类型..." @input="gc.handleRelSearch(gc.relSearchQuery.value)" @focus="gc.onRelSearchFocus" @blur="gc.onRelSearchBlur">
          <div class="kg-rel-search-results" v-show="gc.relSearchFocused.value || gc.relSearchResults.value.length">
            <div v-for="rel in gc.relSearchResults.value" :key="rel" class="kg-rel-search-item" :class="{ active: gc.selectedRelations.value.includes(rel) }" @mousedown="gc.toggleRelationSelection(rel)">
              {{ rel }}
            </div>
            <div v-if="gc.relSearchResults.value.length === 0" class="kg-rel-search-item kg-no-results">无结果</div>
          </div>
        </div>
        <div class="kg-selected-relations" v-if="gc.selectedRelations.value.length">
          <div v-for="rel in gc.selectedRelations.value" :key="rel" class="kg-relation-chip">
            {{ rel }}
            <button class="kg-relation-chip-remove" @click="gc.toggleRelationSelection(rel)">X</button>
          </div>
        </div>
      </div>

      <div class="sidebar-section">
        <button class="kg-reset-btn" @click="gc.clearSelection">
          <span>R</span> 重置选择
        </button>
      </div>
    </div>

    <div class="session-manager" :class="{ expanded: sessionExpanded }" v-if="showSessionManager">
      <div class="session-manager-header" @click="sessionExpanded = !sessionExpanded">
        <span class="session-manager-title">
          <span class="nav-icon">S</span>
          <span class="nav-text">会话管理</span>
        </span>
        <span class="session-manager-toggle">▶</span>
      </div>
      <div class="session-manager-body">
        <div class="sidebar-session-list">
          <div
            v-for="session in sessionStore.sessionList"
            :key="session.id"
            class="sidebar-session-item"
            :class="{ active: session.id === sessionStore.currentSessionId }"
            @click="sessionStore.switchSession(session.id)"
          >
            <div class="sidebar-session-info">
              <span class="sidebar-session-name">{{ session.name }}</span>
              <span class="sidebar-session-time">{{ formatTime(new Date(session.updatedAt)) }}</span>
            </div>
            <div class="sidebar-session-actions">
              <button class="sidebar-session-action-btn" @click.stop="promptRename(session.id)" title="重命名">编</button>
              <button class="sidebar-session-action-btn delete" @click.stop="confirmDelete(session.id)" title="删除">X</button>
            </div>
          </div>
        </div>
        <div class="session-manager-actions">
          <button class="btn btn-primary w-full" @click="sessionStore.createNewSession()">
            <span>+</span> 新建会话
          </button>
        </div>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="sidebar-status">
        <span class="status-dot"></span>
        <span class="status-text">System Online</span>
      </div>
    </div>

    <div class="modal-overlay" :class="{ active: showRenameModal }" @click.self="showRenameModal = false">
      <div class="modal-content modal-sm">
        <div class="modal-header">
          <h2>重命名会话</h2>
          <button class="modal-close" @click="showRenameModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <input type="text" class="modal-input" v-model="renameInput" placeholder="输入新名称..." @keydown.enter="confirmRename">
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showRenameModal = false">取消</button>
          <button class="btn btn-primary" @click="confirmRename">确定</button>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSessionStore } from '../stores/sessions'
import { useGraphController } from '../composables/useGraphController'
import { formatTime } from '../api'

const route = useRoute()
const sessionStore = useSessionStore()
const gc = useGraphController()

const sessionExpanded = ref(false)
const showRenameModal = ref(false)
const renameInput = ref('')
const renameTargetId = ref(null)

// Show session manager only on chat page
const showSessionManager = computed(() => route.path === '/chat')

// Show graph controls only on graph page
const showGraphControls = computed(() => route.path === '/graph')

// Load graph data when graph page is shown
watch(showGraphControls, (show) => {
  if (show && gc.graphData.value.entities.length === 0) {
    gc.loadGraphData()
  }
}, { immediate: true })

onMounted(() => {
  // Load data if on graph page and data not loaded
  if (showGraphControls.value && gc.graphData.value.entities.length === 0) {
    gc.loadGraphData()
  }
})

function promptRename(sessionId) {
  renameTargetId.value = sessionId
  renameInput.value = sessionStore.sessions[sessionId]?.name || ''
  showRenameModal.value = true
}

function confirmRename() {
  if (renameInput.value.trim() && renameTargetId.value) {
    sessionStore.renameSession(renameTargetId.value, renameInput.value.trim())
  }
  showRenameModal.value = false
}

function confirmDelete(sessionId) {
  if (Object.keys(sessionStore.sessions).length <= 1) {
    alert('至少保留一个会话')
    return
  }
  if (confirm('确定删除这个会话?')) {
    sessionStore.deleteSession(sessionId)
  }
}
</script>

<style scoped>
/* Graph Controls Styles */
.sidebar-graph-controls {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
  border-top: 1px solid var(--border-color);
  margin-top: var(--spacing-md);
}

.sidebar-section {
  margin-bottom: var(--spacing-lg);
}

.sidebar-section-title {
  font-size: 0.75rem;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--spacing-sm);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kg-search-box {
  position: relative;
}

.kg-search-box input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 0.85rem;
}

.kg-search-box input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.kg-search-results {
  position: absolute;
  top: 100%;
  left: 0;
  width: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  max-height: 200px;
  overflow-y: auto;
  z-index: 200;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  display: block;
}


.kg-search-result-item {
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background var(--transition-fast);
  font-size: 0.85rem;
}

.kg-search-result-item:hover {
  background: var(--bg-dark);
}

.kg-search-result-item.kg-no-results {
  color: var(--text-dim);
  cursor: default;
}

.kg-result-name {
  color: var(--text-primary);
  font-size: 0.85rem;
}

.kg-result-type {
  color: var(--text-dim);
  font-size: 0.7rem;
}

.kg-selected-nodes {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  max-height: 200px;
  overflow-y: auto;
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: var(--spacing-sm);
}

.kg-empty-hint {
  color: var(--text-dim);
  font-size: 0.8rem;
  font-style: italic;
  text-align: center;
  padding: var(--spacing-md);
}

.kg-selected-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: rgba(0, 229, 204, 0.1);
  border: 1px solid var(--color-primary-dim);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.kg-selected-node:hover {
  background: rgba(0, 229, 204, 0.2);
  border-color: var(--color-primary);
}

.kg-selected-node-name {
  font-size: 0.8rem;
  color: var(--color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kg-selected-node-remove {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--color-primary-dim);
  border-radius: 50%;
  color: var(--color-primary);
  font-size: 0.6rem;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.kg-selected-node-remove:hover {
  background: var(--color-primary);
  color: var(--bg-deep);
}

.kg-selected-count {
  color: var(--color-primary);
  font-size: 0.7rem;
  font-weight: 600;
}

.kg-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-sm);
}

.kg-stat-item {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: var(--spacing-sm);
  text-align: center;
}

.kg-stat-label {
  display: block;
  font-size: 0.7rem;
  color: var(--text-dim);
  margin-bottom: 2px;
}

.kg-stat-value {
  font-family: var(--font-mono);
  font-size: 1rem;
  color: var(--color-primary);
}

.kg-level-control {
  display: flex;
  gap: var(--spacing-xs);
}

.kg-level-btn {
  flex: 1;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.kg-level-btn:hover {
  border-color: var(--color-primary-dim);
}

.kg-level-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--bg-deep);
  font-weight: 500;
}

.kg-rel-search-box {
  position: relative;
}

.kg-rel-search-box input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 0.85rem;
}

.kg-rel-search-box input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.kg-rel-search-results {
  position: absolute;
  top: 100%;
  left: 0;
  width: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  max-height: 200px;
  overflow-y: auto;
  z-index: 200;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  display: block;
}

.kg-rel-search-item {
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  transition: background var(--transition-fast);
  font-size: 0.85rem;
  color: var(--text-primary);
}

.kg-rel-search-item:hover {
  background: var(--bg-dark);
}

.kg-rel-search-item.active {
  background: rgba(0, 229, 204, 0.1);
  color: var(--color-primary);
}

.kg-rel-search-item.kg-no-results {
  color: var(--text-dim);
  cursor: default;
}

.kg-selected-relations {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-sm);
}

.kg-relation-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--bg-dark);
  border: 1px solid var(--color-primary-dim);
  border-radius: 12px;
  font-size: 0.75rem;
  color: var(--color-primary);
}

.kg-relation-chip-remove {
  background: none;
  border: none;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 0.65rem;
  padding: 0;
  line-height: 1;
}

.kg-relation-chip-remove:hover {
  color: var(--color-danger);
}

.kg-reset-btn {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 0.85rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  transition: all var(--transition-fast);
}

.kg-reset-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.kg-reset-btn span {
  font-size: 0.9rem;
}
</style>
