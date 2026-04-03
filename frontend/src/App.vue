<template>
  <div class="app-container" :class="{ 'light-theme': isLightTheme }">
    <AppSidebar />
    <main class="main-content">
      <AppHeader />
      <keep-alive>
        <router-view />
      </keep-alive>
    </main>
    <SettingsModal />
    <Toast />
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useSettingsStore } from './stores/settings'
import AppSidebar from './components/AppSidebar.vue'
import AppHeader from './components/AppHeader.vue'
import SettingsModal from './components/SettingsModal.vue'
import Toast from './components/Toast.vue'

const settingsStore = useSettingsStore()
const isLightTheme = computed(() => settingsStore.theme === 'light')

// Apply theme class to documentElement for CSS :root selector
watch(isLightTheme, (isLight) => {
  if (isLight) {
    document.documentElement.classList.add('light-theme')
  } else {
    document.documentElement.classList.remove('light-theme')
  }
}, { immediate: true })
</script>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
