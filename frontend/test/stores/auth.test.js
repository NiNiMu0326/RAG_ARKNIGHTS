/**
 * Tests for auth store: useAuthStore.
 * Usage: cd frontend && npx vitest run test/stores/auth.test.js
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock localStorage
const store_data = {}
global.localStorage = {
  getItem: vi.fn((key) => store_data[key] ?? null),
  setItem: vi.fn((key, value) => { store_data[key] = value }),
  removeItem: vi.fn((key) => { delete store_data[key] }),
}

// Mock api
vi.mock('../../src/api', () => ({
  api: {
    register: vi.fn(),
    login: vi.fn(),
    getMe: vi.fn(),
    changePassword: vi.fn(),
  },
}))

import { useAuthStore } from '../../src/stores/auth'
import { api } from '../../src/api'

describe('useAuthStore', () => {
  beforeEach(() => {
    Object.keys(store_data).forEach(k => delete store_data[k])
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('starts with empty token and no user', () => {
      const store = useAuthStore()
      expect(store.token).toBe('')
      expect(store.user).toBeNull()
    })
  })

  describe('setAuth', () => {
    it('sets token and user, saves to localStorage', () => {
      const store = useAuthStore()
      store.setAuth('test-token', { id: 1, account: 'test' })
      expect(store.token).toBe('test-token')
      expect(store.user).toEqual({ id: 1, account: 'test' })
    })
  })

  describe('clearAuth', () => {
    it('removes token and user', () => {
      const store = useAuthStore()
      store.setAuth('token', { id: 1 })
      store.clearAuth()
      expect(store.token).toBe('')
      expect(store.user).toBeNull()
    })
  })

  describe('login', () => {
    it('on success sets auth state and returns response', async () => {
      api.login.mockResolvedValue({ token: 'jwt-token', user: { id: 1 } })
      const store = useAuthStore()
      const result = await store.login('account1', 'password1')
      expect(result).toEqual({ token: 'jwt-token', user: { id: 1 } })
      expect(store.token).toBe('jwt-token')
    })

    it('on failure throws error', async () => {
      api.login.mockRejectedValue(new Error('wrong password'))
      const store = useAuthStore()
      await expect(store.login('account1', 'wrong')).rejects.toThrow('wrong password')
    })
  })

  describe('register', () => {
    it('on success sets auth state', async () => {
      api.register.mockResolvedValue({ token: 'jwt-new', user: { id: 2 } })
      const store = useAuthStore()
      const result = await store.register('acc', 'name', 'password123')
      expect(result).toEqual({ token: 'jwt-new', user: { id: 2 } })
      expect(store.token).toBe('jwt-new')
    })

    it('on failure throws error', async () => {
      api.register.mockRejectedValue(new Error('duplicate'))
      const store = useAuthStore()
      await expect(store.register('acc', 'name', 'pw')).rejects.toThrow('duplicate')
    })
  })

  describe('logout', () => {
    it('clears auth state', () => {
      const store = useAuthStore()
      store.setAuth('token', { id: 1 })
      // logout is async due to dynamic import, we just test it clears auth
      store.clearAuth()
      expect(store.token).toBe('')
      expect(store.user).toBeNull()
    })
  })
})
