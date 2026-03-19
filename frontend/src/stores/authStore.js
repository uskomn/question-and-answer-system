import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import authApi from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref(localStorage.getItem('liteqa_token') || null)
  const user = ref(JSON.parse(localStorage.getItem('liteqa_user') || 'null'))
  const isLoading = ref(false)
  const error = ref(null)

  // Getters
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const username = computed(() => user.value?.username || '')
  const userEmail = computed(() => user.value?.email || '')

  // Actions
  async function login(username, password) {
  isLoading.value = true
  error.value = null

  try {
    const response = await authApi.login(username, password)


    token.value = response.access_token

    user.value = {
      id: response.user_id,
      username: response.username
    }

    localStorage.setItem('liteqa_token', response.access_token)
    localStorage.setItem('liteqa_user', JSON.stringify(user.value))

    return response

  } catch (err) {
    const message = err.response?.data?.message || err.message || 'Login failed'
    error.value = message
    throw new Error(message)
  } finally {
    isLoading.value = false
  }
}

  async function register(username, email, password) {
    isLoading.value = true
    error.value = null

    try {
      const response = await authApi.register(username, email, password)
      
      // Auto login after registration - save token and user
      token.value = response.access_token
      user.value = response.user
      
      // Persist to localStorage
      localStorage.setItem('liteqa_token', response.access_token)
      localStorage.setItem('liteqa_user', JSON.stringify(response.user))
      
      return response
    } catch (err) {
      const message = err.response?.data?.message || err.message || 'Registration failed'
      error.value = message
      throw new Error(message)
    } finally {
      isLoading.value = false
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('liteqa_token')
    localStorage.removeItem('liteqa_user')
  }

  async function checkAuth() {
  return !!token.value
}

  return {
    // State
    token,
    user,
    isLoading,
    error,
    // Getters
    isAuthenticated,
    username,
    userEmail,
    // Actions
    login,
    register,
    logout,
    checkAuth
  }
})
