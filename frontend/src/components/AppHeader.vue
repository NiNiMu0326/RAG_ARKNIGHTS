<template>
  <header class="header">
    <div class="header-left">
      <button class="mobile-menu-btn" @click="emit('toggle-sidebar')">☰</button>
      <div class="header-title">
        <h1>{{ pageTitle }}</h1>
      </div>
    </div>
    <div class="header-actions">
      <button class="btn btn-icon" @click="openSettings" title="设置">
        <span>S</span>
      </button>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const emit = defineEmits(['toggle-sidebar'])
const route = useRoute()

const pageTitles = {
  '/chat': '明日方舟 RAG 助手',
  '/admin': 'Arknights RAG Admin',
  '/graph': '知识图谱'
}

const pageTitle = computed(() => pageTitles[route.path] || 'Arknights RAG')

function openSettings() {
  window.dispatchEvent(new CustomEvent('open-settings'))
}
</script>