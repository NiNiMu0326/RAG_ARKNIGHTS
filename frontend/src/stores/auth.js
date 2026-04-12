import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('arknights_rag_token') || '')
  const user = ref(null)

  const isLoggedIn = computed(() => !!token.value && !!user.value)

  function loadUser() {
    const saved = localStorage.getItem('arknights_rag_user')
    if (saved) {
      try { user.value = JSON.parse(saved) } catch { user.value = null }
    }
  }

  function setAuth(newToken, newUser) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('arknights_rag_token', newToken)
    localStorage.setItem('arknights_rag_user', JSON.stringify(newUser))
  }

  function clearAuth() {
    token.value = ''
    user.value = null
    localStorage.removeItem('arknights_rag_token')
    localStorage.removeItem('arknights_rag_user')
  }

  async function register(account, username, password) {
    const res = await api.register(account, username, password)
    setAuth(res.token, res.user)
    return res
  }

  async function login(account, password) {
    const res = await api.login(account, password)
    setAuth(res.token, res.user)
    return res
  }

  async function logout() {
    clearAuth()
  }

  async function changePassword(oldPassword, newPassword) {
    const res = await api.changePassword(oldPassword, newPassword)
    token.value = res.token
    localStorage.setItem('arknights_rag_token', res.token)
    return res
  }

  async function checkAuth() {
    if (!token.value) return false
    try {
      const res = await api.getMe()
      user.value = res.user
      localStorage.setItem('arknights_rag_user', JSON.stringify(res.user))
      return true
    } catch {
      clearAuth()
      return false
    }
  }

  // Load on init
  loadUser()

  return {
    token, user, isLoggedIn,
    register, login, logout, changePassword, checkAuth, setAuth, clearAuth
  }
})
