<template>
  <div class="admin-page">
    <nav class="nav-tabs">
      <button class="nav-tab" :class="{ active: activeTab === 'chunk' }" @click="activeTab = 'chunk'">
        <span>1</span> Chunk 可视化
      </button>
      <button class="nav-tab" :class="{ active: activeTab === 'dashboard' }" @click="activeTab = 'dashboard'">
        <span>2</span> 数据仪表板
      </button>
      <button class="nav-tab" :class="{ active: activeTab === 'traces' }" @click="activeTab = 'traces'">
        <span>3</span> 观测追踪
      </button>
    </nav>

    <div class="admin-content" :data-page="activeTab">
      <!-- KeepAlive 保持各 tab 组件状态（选中项、分页、展开详情等），且懒加载 -->
      <KeepAlive>
        <component :is="activeComponent" v-bind="activeProps" />
      </KeepAlive>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import ChunkBrowser from '../components/admin/ChunkBrowser.vue'
import DataDashboard from '../components/admin/DataDashboard.vue'
import TracePanel from '../components/admin/TracePanel.vue'

const route = useRoute()
const activeTab = ref('chunk')

const tabComponents = {
  chunk: ChunkBrowser,
  dashboard: DataDashboard,
  traces: TracePanel,
}
const activeComponent = computed(() => tabComponents[activeTab.value])

// 支持 /admin?collection=operators&chunk=xxx 直接定位到某个 chunk
const activeProps = computed(() => {
  if (activeTab.value !== 'chunk') return {}
  const collection = route.query.collection
  return {
    initialCollection: ['operators', 'stories', 'knowledge'].includes(collection) ? collection : 'operators',
    initialChunk: route.query.chunk || '',
  }
})
</script>

<style scoped>
.admin-page { padding: var(--spacing-xl); display: flex; flex-direction: column; flex: 1; min-height: 0; }
.nav-tabs { display: flex; gap: var(--spacing-sm); padding: var(--spacing-md); background: var(--bg-panel); border-bottom: 1px solid var(--border-color); }
.nav-tab { padding: var(--spacing-sm) var(--spacing-lg); background: transparent; border: 1px solid var(--border-color); border-radius: var(--radius-md); color: var(--text-secondary); font-family: var(--font-display); font-size: 0.85rem; letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; transition: all var(--transition-fast); display: flex; align-items: center; gap: var(--spacing-sm); }
.nav-tab:hover { background: var(--bg-panel-hover); border-color: var(--color-primary-dim); color: var(--text-primary); }
.nav-tab.active { background: var(--color-primary); border-color: var(--color-primary); color: var(--bg-deep); box-shadow: 0 0 15px var(--color-primary-glow); }
.admin-content { padding: var(--spacing-lg) 0; flex: 1; min-height: 0; display: flex; flex-direction: column; overflow-y: auto; }
.admin-content[data-page="chunk"] { overflow-y: auto; }

@media (max-width: 768px) {
  .admin-page { padding: var(--spacing-md); padding-bottom: calc(var(--spacing-md) + env(safe-area-inset-bottom)); }
  .nav-tabs { flex-wrap: wrap; gap: var(--spacing-xs); }
  .nav-tab { padding: var(--spacing-xs) var(--spacing-md); font-size: 0.75rem; }
  .admin-content[data-page="chunk"] { overflow-y: auto; }
}
</style>
