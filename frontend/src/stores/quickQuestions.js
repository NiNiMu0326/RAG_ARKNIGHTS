import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useQuickQuestionsStore = defineStore('quickQuestions', () => {
  // 快速问题按钮
  const quickActions = ref([])

  // 是否已初始化（防止重复初始化）
  const hasInitialized = ref(false)

  // 数据加载状态
  const isLoading = ref(false)

  /**
   * 设置快速问题按钮
   * @param {Array} actions - 问题按钮数组
   */
  function setQuickActions(actions) {
    quickActions.value = actions
  }

  /**
   * 标记为已初始化
   */
  function markAsInitialized() {
    hasInitialized.value = true
  }

  /**
   * 设置加载状态
   * @param {boolean} loading - 加载状态
   */
  function setLoading(loading) {
    isLoading.value = loading
  }

  /**
   * 重置状态（用于测试或特殊需求）
   */
  function reset() {
    quickActions.value = []
    hasInitialized.value = false
    isLoading.value = false
  }

  return {
    // 状态
    quickActions,
    hasInitialized,
    isLoading,

    // 方法
    setQuickActions,
    markAsInitialized,
    setLoading,
    reset
  }
})
