import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi, setToken as storeToken, type UserOut } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserOut | null>(null)

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    token.value = res.access_token
    storeToken(res.access_token)
    await loadUser()
  }

  async function register(username: string, password: string) {
    await authApi.register({ username, password })
  }

  async function loadUser() {
    if (!token.value) return
    try {
      user.value = await authApi.me()
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    storeToken(null)
  }

  return { token, user, login, register, loadUser, logout }
})
