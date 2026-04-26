import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])

  function show(message, type = 'info') {
    const id = Date.now()
    toasts.value.push({ id, message, type })
    setTimeout(() => remove(id), 3000)
  }

  function remove(id) {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index > -1) toasts.value.splice(index, 1)
  }

  return { toasts, show, remove }
})