<template>
  <div class="modal-overlay" :class="{ active: isOpen }" @click.self="close">
    <div class="modal-content modal-sm auth-modal">
      <div class="modal-header">
        <h2>{{ isLogin ? '登录' : '注册' }}</h2>
        <button class="modal-close" @click="close">&times;</button>
      </div>
      <div class="modal-body">
        <!-- Login Form -->
        <div v-if="isLogin" class="auth-form">
          <div class="form-group">
            <label>账号</label>
            <input type="text" v-model="loginForm.account" placeholder="输入账号" @keydown.enter="handleLogin">
          </div>
          <div class="form-group">
            <label>密码</label>
            <div class="password-input">
              <input :type="showLoginPassword ? 'text' : 'password'" v-model="loginForm.password" placeholder="输入密码" @keydown.enter="handleLogin">
              <button class="password-toggle" tabindex="-1" @click="showLoginPassword = !showLoginPassword">
                <svg v-if="showLoginPassword" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
            </div>
          </div>
          <div v-if="loginError" class="auth-error">{{ loginError }}</div>
          <button class="btn btn-primary w-full" @click="handleLogin" :disabled="loginLoading">
            {{ loginLoading ? '登录中...' : '登录' }}
          </button>
        </div>

        <!-- Register Form -->
        <div v-else class="auth-form">
          <div class="form-group">
            <label>用户名</label>
            <input type="text" v-model="registerForm.username" placeholder="1-16个字符，支持中文" @keydown.enter="handleRegister">
          </div>
          <div class="form-group">
            <label>账号</label>
            <input type="text" v-model="registerForm.account" placeholder="英文、数字、下划线，1-16位" @keydown.enter="handleRegister">
          </div>
          <div class="form-group">
            <label>密码</label>
            <div class="password-input">
              <input :type="showRegisterPassword ? 'text' : 'password'" v-model="registerForm.password" placeholder="8-16位，支持英文、数字和符号" @keydown.enter="handleRegister">
              <button class="password-toggle" tabindex="-1" @click="showRegisterPassword = !showRegisterPassword">
                <svg v-if="showRegisterPassword" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
            </div>
          </div>
          <div class="form-group">
            <label>确认密码</label>
            <div class="password-input">
              <input :type="showRegisterConfirm ? 'text' : 'password'" v-model="registerForm.confirmPassword" placeholder="再次输入密码" @keydown.enter="handleRegister">
              <button class="password-toggle" tabindex="-1" @click="showRegisterConfirm = !showRegisterConfirm">
                <svg v-if="showRegisterConfirm" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
            </div>
          </div>
          <div v-if="registerError" class="auth-error">{{ registerError }}</div>
          <button class="btn btn-primary w-full" @click="handleRegister" :disabled="registerLoading">
            {{ registerLoading ? '注册中...' : '注册' }}
          </button>
        </div>

        <div class="auth-switch">
          <span v-if="isLogin">还没有账号？<span class="auth-link" @click="switchMode">去注册</span></span>
          <span v-else>已有账号？<span class="auth-link" @click="switchMode">去登录</span></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const isOpen = ref(false)
const isLogin = ref(true)

const showLoginPassword = ref(false)
const showRegisterPassword = ref(false)
const showRegisterConfirm = ref(false)

const loginForm = ref({ account: '', password: '' })
const registerForm = ref({ account: '', username: '', password: '', confirmPassword: '' })

const loginError = ref('')
const registerError = ref('')
const loginLoading = ref(false)
const registerLoading = ref(false)

function open(mode = 'login') {
  isOpen.value = true
  isLogin.value = mode === 'login'
  loginError.value = ''
  registerError.value = ''
  loginForm.value = { account: '', password: '' }
  registerForm.value = { account: '', username: '', password: '', confirmPassword: '' }
}

function close() {
  isOpen.value = false
}

function switchMode() {
  isLogin.value = !isLogin.value
  loginError.value = ''
  registerError.value = ''
}

async function handleLogin() {
  loginError.value = ''
  if (!loginForm.value.account || !loginForm.value.password) {
    loginError.value = '请填写账号和密码'
    return
  }
  loginLoading.value = true
  try {
    await authStore.login(loginForm.value.account, loginForm.value.password)
    close()
    window.dispatchEvent(new CustomEvent('auth-changed'))
  } catch (e) {
    loginError.value = e.message
  } finally {
    loginLoading.value = false
  }
}

async function handleRegister() {
  registerError.value = ''
  const f = registerForm.value
  if (!f.username || !f.account || !f.password) {
    registerError.value = '请填写所有字段'
    return
  }
  if (f.password !== f.confirmPassword) {
    registerError.value = '两次密码不一致'
    return
  }
  registerLoading.value = true
  try {
    await authStore.register(f.account, f.username, f.password)
    close()
    window.dispatchEvent(new CustomEvent('auth-changed'))
  } catch (e) {
    registerError.value = e.message
  } finally {
    registerLoading.value = false
  }
}

defineExpose({ open, close })
</script>

<style scoped>
.auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-group label {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.form-group input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.form-group input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.password-input {
  position: relative;
  display: flex;
  align-items: center;
}

.password-input input {
  padding-right: 40px;
}

.password-toggle {
  position: absolute;
  right: 8px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  line-height: 1;
  color: var(--text-dim, #888);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
}

.password-toggle:hover {
  color: var(--text-secondary, #bbb);
}

.auth-error {
  font-size: 0.8rem;
  color: #ff4444;
  text-align: center;
  padding: var(--spacing-xs);
}

.auth-switch {
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-top: var(--spacing-sm);
}

.auth-link {
  color: var(--color-primary);
  cursor: pointer;
  text-decoration: underline;
}

.auth-link:hover {
  opacity: 0.8;
}

.w-full {
  width: 100%;
}
</style>
