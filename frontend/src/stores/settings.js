import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const theme = ref('dark')
  const useCrag = ref(true)
  const useGraphrag = ref(true)
  const useParentDoc = ref(true)

  function loadSettings() {
    const saved = localStorage.getItem('arknights_rag_settings')
    if (saved) {
      const settings = JSON.parse(saved)
      theme.value = settings.theme || 'dark'
      useCrag.value = settings.useCrag !== false
      useGraphrag.value = settings.useGraphrag !== false
      useParentDoc.value = settings.useParentDoc !== false
    }
  }

  function saveSettings() {
    localStorage.setItem('arknights_rag_settings', JSON.stringify({
      theme: theme.value,
      useCrag: useCrag.value,
      useGraphrag: useGraphrag.value,
      useParentDoc: useParentDoc.value
    }))
  }

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    saveSettings()
  }

  function toggleCrag() {
    useCrag.value = !useCrag.value
    saveSettings()
  }

  function toggleGraphrag() {
    useGraphrag.value = !useGraphrag.value
    saveSettings()
  }

  function toggleParentDoc() {
    useParentDoc.value = !useParentDoc.value
    saveSettings()
  }

  function getRAGSettings() {
    return {
      use_crag: useCrag.value,
      use_graphrag: useGraphrag.value,
      use_parent_doc: useParentDoc.value
    }
  }

  loadSettings()

  return {
    theme,
    useCrag,
    useGraphrag,
    useParentDoc,
    toggleTheme,
    toggleCrag,
    toggleGraphrag,
    toggleParentDoc,
    getRAGSettings,
    saveSettings
  }
})