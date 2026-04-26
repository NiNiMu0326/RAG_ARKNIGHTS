<template>
  <div class="app-container" :class="{ 'light-theme': isLightTheme }">
    <div class="mobile-overlay" :class="{ active: sidebarOpen }" @click="sidebarOpen = false"></div>
    <AppSidebar :class="{ 'mobile-open': sidebarOpen }" />
    <main class="main-content">
      <AppHeader @toggle-sidebar="sidebarOpen = !sidebarOpen" />
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
    <SettingsModal @openAuth="openAuthModal" />
    <AuthModal ref="authModal" />
    <Toast />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useSettingsStore } from './stores/settings'
import { useAuthStore } from './stores/auth'
import AppSidebar from './components/AppSidebar.vue'
import AppHeader from './components/AppHeader.vue'
import SettingsModal from './components/SettingsModal.vue'
import AuthModal from './components/AuthModal.vue'
import Toast from './components/Toast.vue'

const settingsStore = useSettingsStore()
const authStore = useAuthStore()
const isLightTheme = computed(() => settingsStore.theme === 'light')
const sidebarOpen = ref(false)
const authModal = ref(null)

// Apply theme class to documentElement for CSS :root selector
watch(isLightTheme, (isLight) => {
  if (isLight) {
    document.documentElement.classList.add('light-theme')
  } else {
    document.documentElement.classList.remove('light-theme')
  }
}, { immediate: true })

function openAuthModal(mode = 'login') {
  authModal.value?.open(mode)
}

// Auto-login check on mount
onMounted(async () => {
  if (authStore.token) {
    const ok = await authStore.checkAuth()
    if (ok) {
      window.dispatchEvent(new CustomEvent('auth-changed'))
    }
  }
})
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
