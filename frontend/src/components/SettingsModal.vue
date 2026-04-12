<template>
  <div class="modal-overlay" :class="{ active: isOpen }" @click.self="close">
    <div class="modal-content">
      <div class="modal-header">
        <h2>设置</h2>
        <button class="modal-close" @click="close">&times;</button>
      </div>
      <div class="modal-body">
        <div class="settings-section" v-if="authStore.isLoggedIn">
          <h3>账号</h3>
          <div class="user-info-section">
            <div class="user-info-item">
              <span class="user-info-label">用户名</span>
              <span class="user-info-value">{{ authStore.user?.username }}</span>
            </div>
            <div class="user-info-item">
              <span class="user-info-label">账号</span>
              <span class="user-info-value">{{ authStore.user?.account }}</span>
            </div>
          </div>
          <div class="user-actions">
            <button class="btn btn-secondary" @click="showChangePasswordModal = true">修改密码</button>
            <button class="btn btn-danger" @click="handleLogout">退出登录</button>
          </div>
        </div>
        <div class="settings-section" v-else>
          <h3>账号</h3>
          <p class="login-hint">登录后可保存聊天记录</p>
          <div class="user-actions" style="justify-content: center;">
            <button class="btn btn-primary" @click="emit('openAuth', 'login')">登录</button>
            <button class="btn btn-secondary" @click="emit('openAuth', 'register')">注册</button>
          </div>
        </div>

        <div class="settings-section">
          <h3>主题</h3>
          <div class="settings-toggle-item">
            <span>深色模式</span>
            <button class="toggle-btn" :class="{ active: settingsStore.theme !== 'light' }" @click="settingsStore.toggleTheme()">
              {{ settingsStore.theme === 'light' ? '关' : '开' }}
            </button>
          </div>
        </div>

        <div class="settings-section">
          <h3>LLM 模型</h3>
          <div class="model-selector">
            <select class="model-select" v-model="selectedModel" @change="onModelChange">
              <option v-for="model in settingsStore.availableModels" :key="model.id" :value="model.id">
                {{ model.display_name }}
              </option>
            </select>
            <div class="model-select-info" v-if="currentModelInfo">
              <span class="model-provider-badge">{{ currentModelInfo.provider }}</span>
            </div>
            <div v-if="settingsStore.availableModels.length === 0" class="model-loading">
              加载模型列表...
            </div>
          </div>
        </div>

        <div class="settings-section">
          <h3>关于系统</h3>
          <div class="about-info" v-if="stats">
            <div class="about-item"><span>版本</span><span>1.0.0</span></div>
            <div class="about-item"><span>状态</span><span class="status-online">在线</span></div>
            <div class="about-item"><span>当前模型</span><span>{{ currentModelDisplayName }}</span></div>
            <div class="about-item"><span>干员数据</span><span>{{ stats.operators }} 条</span></div>
            <div class="about-item"><span>故事数据</span><span>{{ stats.stories }} 条</span></div>
            <div class="about-item"><span>知识数据</span><span>{{ stats.knowledge }} 条</span></div>
            <div class="about-item"><span>关系数据</span><span>{{ stats.relations }} 条</span></div>
          </div>
          <div class="about-info" v-else>
            <div class="about-item"><span>版本</span><span>1.0.0</span></div>
            <div class="about-item"><span>状态</span><span class="status-offline">离线</span></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 修改密码弹窗 -->
  <div class="modal-overlay" :class="{ active: showChangePasswordModal }" @click.self="showChangePasswordModal = false">
    <div class="modal-content modal-sm">
      <div class="modal-header">
        <h2>修改密码</h2>
        <button class="modal-close" @click="showChangePasswordModal = false">&times;</button>
      </div>
      <div class="modal-body">
        <div class="auth-form">
          <div class="form-group">
            <label>旧密码</label>
            <div class="password-input">
              <input :type="showOldPassword ? 'text' : 'password'" v-model="changePasswordForm.oldPassword" placeholder="输入旧密码">
              <button class="password-toggle" tabindex="-1" @click="showOldPassword = !showOldPassword">
                <svg v-if="!showOldPassword" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
            </div>
          </div>
          <div class="form-group">
            <label>新密码</label>
            <div class="password-input">
              <input :type="showNewPassword ? 'text' : 'password'" v-model="changePasswordForm.newPassword" placeholder="8-16位，支持英文、数字和符号">
              <button class="password-toggle" tabindex="-1" @click="showNewPassword = !showNewPassword">
                <svg v-if="showNewPassword" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
            </div>
          </div>
          <div class="form-group">
            <label>确认新密码</label>
            <div class="password-input">
              <input :type="showConfirmPassword ? 'text' : 'password'" v-model="changePasswordForm.confirmPassword" placeholder="再次输入新密码">
              <button class="password-toggle" tabindex="-1" @click="showConfirmPassword = !showConfirmPassword">
                <svg v-if="!showConfirmPassword" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
            </div>
          </div>
          <div v-if="changePasswordError" class="auth-error">{{ changePasswordError }}</div>
          <button class="btn btn-primary w-full" @click="handleChangePassword" :disabled="changePasswordLoading">
            {{ changePasswordLoading ? '修改中...' : '确认修改' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useAuthStore } from '../stores/auth'
import { api } from '../api'

const emit = defineEmits(['openAuth'])

const settingsStore = useSettingsStore()
const authStore = useAuthStore()
const isOpen = ref(false)
const stats = ref(null)
const selectedModel = ref('')

const currentModelInfo = computed(() => {
  return settingsStore.availableModels.find(m => m.id === selectedModel.value) || null
})

const currentModelDisplayName = computed(() => {
  const model = settingsStore.availableModels.find(m => m.id === settingsStore.currentModel)
  return model?.display_name || settingsStore.currentModel || '未知'
})

function onModelChange() {
  settingsStore.setModel(selectedModel.value)
}

function open() {
  isOpen.value = true
  loadStats()
  settingsStore.loadModels().then(() => {
    selectedModel.value = settingsStore.currentModel
  })
}

function close() {
  isOpen.value = false
}

async function loadStats() {
  try {
    stats.value = await api.getStats()
  } catch (e) {
    stats.value = null
  }
}

function handleOpenSettings() {
  open()
}

// Change password
const showChangePasswordModal = ref(false)
const changePasswordForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const showOldPassword = ref(false)
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)
const changePasswordError = ref('')
const changePasswordLoading = ref(false)

async function handleChangePassword() {
  changePasswordError.value = ''
  const f = changePasswordForm.value
  if (!f.oldPassword || !f.newPassword || !f.confirmPassword) {
    changePasswordError.value = '请填写所有字段'
    return
  }
  if (f.newPassword !== f.confirmPassword) {
    changePasswordError.value = '两次新密码不一致'
    return
  }
  changePasswordLoading.value = true
  try {
    await authStore.changePassword(f.oldPassword, f.newPassword)
    showChangePasswordModal.value = false
    changePasswordForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  } catch (e) {
    changePasswordError.value = e.message
  } finally {
    changePasswordLoading.value = false
  }
}

function handleLogout() {
  authStore.logout()
  window.dispatchEvent(new CustomEvent('auth-changed'))
}

onMounted(() => {
  window.addEventListener('open-settings', handleOpenSettings)
})

onUnmounted(() => {
  window.removeEventListener('open-settings', handleOpenSettings)
})
</script>

<style scoped>
.model-selector {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.model-select {
  width: 100%;
  padding: 10px 14px;
  background: var(--bg-dark, #1a1a2e);
  border: 1px solid var(--border-color, #2a2a3e);
  border-radius: var(--radius-md, 8px);
  color: var(--text-primary, #e0e0e0);
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23888' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}

.model-select:hover {
  border-color: var(--color-primary-dim, rgba(0, 229, 204, 0.3));
}

.model-select:focus {
  outline: none;
  border-color: var(--color-primary, #00e5cc);
  box-shadow: 0 0 0 2px rgba(0, 229, 204, 0.15);
}

.model-select option {
  background: var(--bg-dark, #1a1a2e);
  color: var(--text-primary, #e0e0e0);
  padding: 8px;
}

.model-select-info {
  display: flex;
  align-items: center;
}

.model-provider-badge {
  display: inline-block;
  font-size: 0.7rem;
  color: var(--text-dim, #888);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: var(--bg-panel, #1e1e32);
  padding: 2px 8px;
  border-radius: var(--radius-sm, 4px);
}

.model-loading {
  text-align: center;
  color: var(--text-dim, #888);
  font-size: 0.85rem;
  padding: 12px;
}

/* User info section */
.user-info-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.user-info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.user-info-label {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.user-info-value {
  font-size: 0.85rem;
  color: var(--text-primary);
  font-weight: 500;
}

.user-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.login-hint {
  font-size: 0.85rem;
  color: var(--text-dim);
  margin-bottom: var(--spacing-sm);
}

/* Auth form styles */
.auth-form { display: flex; flex-direction: column; gap: var(--spacing-md); }
.form-group { display: flex; flex-direction: column; gap: var(--spacing-xs); }
.form-group label { font-size: 0.8rem; color: var(--text-secondary); }
.form-group input { width: 100%; padding: var(--spacing-sm) var(--spacing-md); background: var(--bg-dark); border: 1px solid var(--border-color); border-radius: var(--radius-md); color: var(--text-primary); font-size: 0.9rem; }
.form-group input:focus { outline: none; border-color: var(--color-primary); }
.password-input { position: relative; display: flex; align-items: center; }
.password-input input { padding-right: 40px; }
.password-toggle { position: absolute; right: 8px; background: none; border: none; cursor: pointer; padding: 4px; line-height: 1; color: var(--text-dim, #888); display: flex; align-items: center; justify-content: center; transition: color 0.2s; }
.password-toggle:hover { color: var(--text-secondary, #bbb); }
.auth-error { font-size: 0.8rem; color: #ff4444; text-align: center; padding: var(--spacing-xs); }
.w-full { width: 100%; }
</style>
