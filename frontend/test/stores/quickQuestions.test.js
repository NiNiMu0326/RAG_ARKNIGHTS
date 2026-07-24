/**
 * Tests for quickQuestions store: useQuickQuestionsStore.
 * Usage: cd frontend && npx vitest run test/stores/quickQuestions.test.js
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

import { useQuickQuestionsStore } from '../../src/stores/quickQuestions'

describe('useQuickQuestionsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('starts with empty quickActions array', () => {
      const store = useQuickQuestionsStore()
      expect(store.quickActions).toEqual([])
    })

    it('starts with hasInitialized = false', () => {
      const store = useQuickQuestionsStore()
      expect(store.hasInitialized).toBe(false)
    })

    it('starts with isLoading = false', () => {
      const store = useQuickQuestionsStore()
      expect(store.isLoading).toBe(false)
    })
  })

  describe('setQuickActions', () => {
    it('sets quickActions to the given array', () => {
      const store = useQuickQuestionsStore()
      const actions = [
        { id: 1, text: '银灰的攻击力是多少？' },
        { id: 2, text: '阿米娅是谁？' },
      ]
      store.setQuickActions(actions)
      expect(store.quickActions).toEqual(actions)
    })

    it('overwrites existing actions', () => {
      const store = useQuickQuestionsStore()
      store.setQuickActions([{ id: 1, text: 'old' }])
      store.setQuickActions([{ id: 2, text: 'new' }])
      expect(store.quickActions.length).toBe(1)
      expect(store.quickActions[0].text).toBe('new')
    })

    it('handles empty array', () => {
      const store = useQuickQuestionsStore()
      store.setQuickActions([{ id: 1, text: 'test' }])
      store.setQuickActions([])
      expect(store.quickActions).toEqual([])
    })
  })

  describe('markAsInitialized', () => {
    it('sets hasInitialized to true', () => {
      const store = useQuickQuestionsStore()
      expect(store.hasInitialized).toBe(false)
      store.markAsInitialized()
      expect(store.hasInitialized).toBe(true)
    })

    it('is idempotent', () => {
      const store = useQuickQuestionsStore()
      store.markAsInitialized()
      store.markAsInitialized()
      expect(store.hasInitialized).toBe(true)
    })
  })

  describe('setLoading', () => {
    it('sets isLoading to true', () => {
      const store = useQuickQuestionsStore()
      store.setLoading(true)
      expect(store.isLoading).toBe(true)
    })

    it('sets isLoading to false', () => {
      const store = useQuickQuestionsStore()
      store.setLoading(true)
      store.setLoading(false)
      expect(store.isLoading).toBe(false)
    })
  })

  describe('reset', () => {
    it('clears all state back to initial values', () => {
      const store = useQuickQuestionsStore()
      store.setQuickActions([{ id: 1, text: 'test' }])
      store.markAsInitialized()
      store.setLoading(true)

      store.reset()

      expect(store.quickActions).toEqual([])
      expect(store.hasInitialized).toBe(false)
      expect(store.isLoading).toBe(false)
    })

    it('reset on clean state is a no-op', () => {
      const store = useQuickQuestionsStore()
      store.reset()
      expect(store.quickActions).toEqual([])
      expect(store.hasInitialized).toBe(false)
      expect(store.isLoading).toBe(false)
    })
  })
})
