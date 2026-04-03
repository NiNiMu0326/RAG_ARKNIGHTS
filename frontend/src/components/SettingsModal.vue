<template>
  <div class="modal-overlay" :class="{ active: isOpen }" @click.self="close">
    <div class="modal-content">
      <div class="modal-header">
        <h2>设置</h2>
        <button class="modal-close" @click="close">&times;</button>
      </div>
      <div class="modal-body">
        <div class="settings-section">
          <h3>主题</h3>
          <div class="settings-toggle-item">
            <span>深色模式</span>
            <button class="toggle-btn" :class="{ active: settingsStore.theme !== 'light' }" @click="settingsStore.toggleTheme()">
              {{ settingsStore.theme === 'light' ? '关' : '开' }}
            </button>
          </div>
        </div>

        <div class="settings-section">
          <h3>RAG 功能</h3>
          <div class="settings-toggle-item">
            <span>CRAG 判断</span>
            <button class="toggle-btn" :class="{ active: settingsStore.useCrag }" @click="settingsStore.toggleCrag()">
              {{ settingsStore.useCrag ? '开' : '关' }}
            </button>
          </div>
          <div class="settings-toggle-item">
            <span>知识图谱</span>
            <button class="toggle-btn" :class="{ active: settingsStore.useGraphrag }" @click="settingsStore.toggleGraphrag()">
              {{ settingsStore.useGraphrag ? '开' : '关' }}
            </button>
          </div>
          <div class="settings-toggle-item">
            <span>Parent文档扩展</span>
            <button class="toggle-btn" :class="{ active: settingsStore.useParentDoc }" @click="settingsStore.toggleParentDoc()">
              {{ settingsStore.useParentDoc ? '开' : '关' }}
            </button>
          </div>
        </div>

        <div class="settings-section">
          <h3>关于系统</h3>
          <div class="about-info" v-if="stats">
            <div class="about-item"><span>版本</span><span>1.0.0</span></div>
            <div class="about-item"><span>状态</span><span class="status-online">在线</span></div>
            <div class="about-item"><span>干员数据</span><span>{{ stats.operators }} 条</span></div>
            <div class="about-item"><span>故事数据</span><span>{{ stats.stories }} 条</span></div>
            <div class="about-item"><span>知识数据</span><span>{{ stats.knowledge }} 条</span></div>
            <div class="about-item"><span>关系数据</span><span>{{ stats.relations }} 条</span></div>
          </div>
          <div class="about-info" v-else>
            <div class="about-item"><span>版本</span><span>1.0.0</span></div>
            <div class="about-item"><span>状态</span><span class="status-offline">离线</span></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { api } from '../api'

const settingsStore = useSettingsStore()
const isOpen = ref(false)
const stats = ref(null)

function open() {
  isOpen.value = true
  loadStats()
}

function close() {
  isOpen.value = false
}

async function loadStats() {
  try {
    stats.value = await api.getStats()
  } catch (e) {
    stats.value = null
  }
}

function handleOpenSettings() {
  open()
}

onMounted(() => {
  window.addEventListener('open-settings', handleOpenSettings)
})

onUnmounted(() => {
  window.removeEventListener('open-settings', handleOpenSettings)
})
</script>