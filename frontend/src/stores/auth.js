/**
 * Pinia 状态管理：认证模块
 * 存储登录状态和用户信息
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'

export const useAuthStore = defineStore('auth', () => {
  // 状态
  // 使用 localStorage：跨标签页共享（预览/下载打开新标签页时需要）
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(null)

  // 计算属性
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userInfo.value?.role === 'admin')

  // 登录
  async function login(username, password) {
    const response = await api.post('/auth/login', {
      username,
      password
    })

    token.value = response.data.access_token
    localStorage.setItem('token', token.value)

    // 获取用户信息
    await fetchUserInfo()

    return response.data
  }

  // 获取当前用户信息
  async function fetchUserInfo() {
    try {
      const response = await api.get('/auth/me')
      userInfo.value = response.data
    } catch (error) {
      logout()
      throw error
    }
  }

  // 登出
  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  // 初始化：检查是否已登录
  async function init() {
    if (token.value) {
      try {
        await fetchUserInfo()
      } catch (error) {
        logout()
      }
    }
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    isAdmin,
    login,
    fetchUserInfo,
    logout,
    init
  }
})
