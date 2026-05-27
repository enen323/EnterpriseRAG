<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">EnterpriseRAG</h1>
      <p class="login-subtitle">企业级知识库问答系统</p>

      <div class="tabs">
        <button
          :class="['tab', { active: tab === 'login' }]"
          @click="tab = 'login'"
        >
          登录
        </button>
        <button
          :class="['tab', { active: tab === 'register' }]"
          @click="tab = 'register'"
        >
          注册
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="login-form">
        <div class="field">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            required
            minlength="2"
          />
        </div>
        <div class="field">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="请输入密码"
            required
            minlength="8"
          />
        </div>

        <p v-if="error" class="error-msg">{{ error }}</p>
        <p v-if="successMsg" class="success-msg">{{ successMsg }}</p>

        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? '处理中...' : tab === 'login' ? '登录' : '注册' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const tab = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const error = ref('')
const successMsg = ref('')
const loading = ref(false)

async function handleSubmit() {
  error.value = ''
  successMsg.value = ''
  loading.value = true
  try {
    if (tab.value === 'login') {
      await auth.login(username.value, password.value)
      router.push('/chat')
    } else {
      await auth.register(username.value, password.value)
      successMsg.value = '注册成功，请登录'
      tab.value = 'login'
    }
  } catch (e: any) {
    error.value = e.message || '操作失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}

.login-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  width: 400px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.login-title {
  text-align: center;
  font-size: 28px;
  margin: 0 0 4px;
  color: #1a1a2e;
}

.login-subtitle {
  text-align: center;
  color: #666;
  margin: 0 0 32px;
  font-size: 14px;
}

.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 24px;
  border-bottom: 2px solid #eee;
}

.tab {
  flex: 1;
  padding: 10px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 15px;
  color: #666;
  transition: all 0.2s;
}

.tab.active {
  color: #1a73e8;
  border-bottom: 2px solid #1a73e8;
  margin-bottom: -2px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.field input {
  padding: 10px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.field input:focus {
  outline: none;
  border-color: #1a73e8;
  box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.1);
}

.error-msg {
  color: #e53935;
  font-size: 13px;
  margin: 0;
}

.success-msg {
  color: #43a047;
  font-size: 13px;
  margin: 0;
}

.btn-primary {
  padding: 10px;
  background: #1a73e8;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 15px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: #1557b0;
}

.btn-primary:disabled {
  background: #93b8f0;
  cursor: not-allowed;
}
</style>
