<template>
  <div class="source-drawer-overlay" :class="{ active: store.isOpen }" @click.self="store.close()"></div>
  <div class="source-drawer-panel" :class="{ active: store.isOpen }">
    <div class="source-drawer-header">
      <div class="source-drawer-title-group">
        <span class="source-drawer-icon">📄</span>
        <span class="source-drawer-title" :title="sourceTitle">{{ sourceTitle }}</span>
      </div>
      <div class="source-drawer-actions">
        <button
          v-if="store.activeSource?.url"
          class="source-drawer-external"
          @click="openExternal"
          title="在新标签页打开"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </button>
        <button class="source-drawer-close" @click="store.close()">&times;</button>
      </div>
    </div>

    <div class="source-drawer-body">
      <!-- Loading -->
      <div v-if="store.loading" class="source-drawer-loading">
        <div class="source-drawer-spinner"></div>
        <span>加载中...</span>
      </div>

      <!-- Error -->
      <div v-else-if="store.error" class="source-drawer-error">
        <span>{{ store.error }}</span>
      </div>

      <!-- Web source -->
      <div v-else-if="store.activeSource?.url && !store.activeSource?.chunk_id" class="source-drawer-web">
        <div class="source-drawer-web-url">{{ store.activeSource.url }}</div>
        <p class="source-drawer-web-hint">点击右上角图标在新标签页中打开完整网页</p>
      </div>

      <!-- Chunk content -->
      <div v-else class="source-drawer-content">
        <div class="source-drawer-meta" v-if="store.activeSource">
          <span class="source-drawer-collection">{{ store.activeSource.collection }}</span>
          <span class="source-drawer-chunk-id">{{ store.activeSource.chunk_id }}</span>
        </div>
        <pre class="source-drawer-text">{{ store.content }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSourceDrawerStore } from '../stores/sourceDrawer'

const store = useSourceDrawerStore()

const sourceTitle = computed(() => {
  if (!store.activeSource) return ''
  if (store.activeSource.title) return store.activeSource.title
  if (store.activeSource.chunk_id) {
    // Convert operators_char_103_angel → char_103_angel
    const parts = store.activeSource.chunk_id.split('_')
    if (parts.length >= 2) {
      return parts.slice(1).join('_')
    }
    return store.activeSource.chunk_id
  }
  return '来源'
})

function openExternal() {
  if (store.activeSource?.url) {
    window.open(store.activeSource.url, '_blank', 'noopener,noreferrer')
  }
}
</script>

<style scoped>
/* Overlay */
.source-drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 500;
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--transition-normal, 250ms ease);
}
.source-drawer-overlay.active {
  opacity: 1;
  pointer-events: auto;
}

/* Panel */
.source-drawer-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 480px;
  max-width: 100vw;
  height: 100vh;
  background: var(--bg-panel, #111922);
  border-left: 1px solid var(--border-color, rgba(0, 229, 204, 0.2));
  z-index: 501;
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform var(--transition-normal, 250ms ease);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.4);
}
.source-drawer-panel.active {
  transform: translateX(0);
}

/* Header */
.source-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md, 16px) var(--spacing-lg, 24px);
  border-bottom: 1px solid var(--border-color, rgba(0, 229, 204, 0.2));
  flex-shrink: 0;
}
.source-drawer-title-group {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 8px);
  min-width: 0;
  flex: 1;
}
.source-drawer-icon {
  font-size: 1.1rem;
  flex-shrink: 0;
}
.source-drawer-title {
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary, #e8f4f0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-drawer-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs, 4px);
  flex-shrink: 0;
}
.source-drawer-external,
.source-drawer-close {
  background: none;
  border: none;
  color: var(--text-dim, #5a7068);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm, 4px);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color var(--transition-fast, 150ms ease);
}
.source-drawer-external:hover,
.source-drawer-close:hover {
  color: var(--text-primary, #e8f4f0);
}
.source-drawer-close {
  font-size: 1.4rem;
  line-height: 1;
}

/* Body */
.source-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

/* Loading */
.source-drawer-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md, 16px);
  padding: var(--spacing-xl, 32px);
  color: var(--text-dim, #5a7068);
  font-size: 0.85rem;
}
.source-drawer-spinner {
  width: 28px;
  height: 28px;
  border: 2px solid var(--border-color, rgba(0, 229, 204, 0.2));
  border-top-color: var(--color-primary, #00e5cc);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Error */
.source-drawer-error {
  padding: var(--spacing-xl, 32px);
  color: var(--color-danger, #ff4757);
  font-size: 0.85rem;
  text-align: center;
}

/* Web source */
.source-drawer-web {
  padding: var(--spacing-lg, 24px);
}
.source-drawer-web-url {
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 0.8rem;
  color: var(--color-primary, #00e5cc);
  word-break: break-all;
  margin-bottom: var(--spacing-md, 16px);
}
.source-drawer-web-hint {
  font-size: 0.8rem;
  color: var(--text-dim, #5a7068);
}

/* Chunk content */
.source-drawer-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.source-drawer-meta {
  display: flex;
  gap: var(--spacing-sm, 8px);
  padding: var(--spacing-sm, 8px) var(--spacing-lg, 24px);
  border-bottom: 1px solid var(--border-color, rgba(0, 229, 204, 0.2));
  flex-shrink: 0;
}
.source-drawer-collection {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-dim, #5a7068);
  background: var(--bg-dark, #0a0e14);
  padding: 2px 8px;
  border-radius: var(--radius-sm, 4px);
}
.source-drawer-chunk-id {
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 0.7rem;
  color: var(--text-dim, #5a7068);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-drawer-text {
  flex: 1;
  margin: 0;
  padding: var(--spacing-lg, 24px);
  font-family: var(--font-body, 'Noto Sans SC', sans-serif);
  font-size: 0.85rem;
  line-height: 1.8;
  color: var(--text-primary, #e8f4f0);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-y: auto;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Mobile: full-width panel */
@media (max-width: 768px) {
  .source-drawer-panel {
    width: 100vw;
  }
  .source-drawer-overlay {
    background: rgba(0, 0, 0, 0.5);
  }
}
</style>
