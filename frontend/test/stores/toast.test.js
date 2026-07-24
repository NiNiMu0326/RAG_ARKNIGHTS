/**
 * Tests for toast store: useToastStore.
 * Usage: cd frontend && npx vitest run test/stores/toast.test.js
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

import { useToastStore } from '../../src/stores/toast'

describe('useToastStore', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('initial state', () => {
    it('starts with empty toasts array', () => {
      const store = useToastStore()
      expect(store.toasts).toEqual([])
    })
  })

  describe('show', () => {
    it('adds a toast with default type info', () => {
      const store = useToastStore()
      store.show('hello world')
      expect(store.toasts.length).toBe(1)
      expect(store.toasts[0].message).toBe('hello world')
      expect(store.toasts[0].type).toBe('info')
      expect(store.toasts[0].id).toBeGreaterThan(0)
    })

    it('adds a toast with custom type', () => {
      const store = useToastStore()
      store.show('error message', 'error')
      expect(store.toasts[0].type).toBe('error')
    })

    it('adds a toast with success type', () => {
      const store = useToastStore()
      store.show('success!', 'success')
      expect(store.toasts[0].type).toBe('success')
    })

    it('each toast has unique id', () => {
      const store = useToastStore()
      store.show('first')
      // Advance timer slightly so Date.now() returns different values
      vi.advanceTimersByTime(1)
      store.show('second')
      expect(store.toasts.length).toBe(2)
      expect(store.toasts[0].id).not.toBe(store.toasts[1].id)
    })

    it('auto-removes toast after 3000ms', () => {
      const store = useToastStore()
      store.show('ephemeral message')
      expect(store.toasts.length).toBe(1)

      vi.advanceTimersByTime(3000)
      expect(store.toasts.length).toBe(0)
    })

    it('does not remove toast before 3000ms', () => {
      const store = useToastStore()
      store.show('message')
      vi.advanceTimersByTime(2999)
      expect(store.toasts.length).toBe(1)
    })
  })

  describe('remove', () => {
    it('removes a specific toast by id', () => {
      const store = useToastStore()
      store.show('message 1')
      const id2 = store.toasts[0].id
      store.show('message 2')

      store.remove(id2)
      expect(store.toasts.length).toBe(1)
      expect(store.toasts[0].message).toBe('message 2')
    })

    it('removing non-existent id does nothing', () => {
      const store = useToastStore()
      store.show('message')
      expect(() => store.remove(99999)).not.toThrow()
      expect(store.toasts.length).toBe(1)
    })

    it('removing the only toast results in empty array', () => {
      const store = useToastStore()
      store.show('only one')
      store.remove(store.toasts[0].id)
      expect(store.toasts).toEqual([])
    })
  })
})
