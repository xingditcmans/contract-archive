/**
 * Axios HTTP 请求封装
 * 所有 API 请求都通过这个模块发出
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api',  // 请求前缀，会自动加到所有 URL 前面
  timeout: 30000,   // 30秒超时
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：自动添加 Token
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器：统一处理错误
api.interceptors.response.use(
  response => {
    return response
  },
  error => {
    if (error.response) {
      const { status, data } = error.response

      const silent = error.config?.silent  // 某些请求不需要弹错误提示

      switch (status) {
        case 401:
          // 未登录
          if (!silent) ElMessage.error(data.detail || '登录已过期，请重新登录')
          localStorage.removeItem('token')
          router.push('/login')
          break
        case 403:
          if (!silent) ElMessage.error(data.detail || '没有权限')
          break
        case 404:
          ElMessage.error(data.detail || '资源不存在')
          break
        case 409:
          // 冲突（如附件重复），不在这里弹提示，由组件自行处理
          break
        case 422:
          // Pydantic 验证错误：格式化为可读消息
          if (Array.isArray(data.detail)) {
            const messages = data.detail.map(err => {
              const field = err.loc?.join('.') || ''
              const fieldName = field.split('.').pop() || field
              return `【${fieldName}】${err.msg}`
            })
            ElMessage.error(messages.join('；'))
          } else {
            ElMessage.error(data.detail || '输入数据验证失败')
          }
          break
        case 500:
          ElMessage.error('服务器错误')
          break
        default:
          ElMessage.error(data.detail || '请求失败')
      }
    } else if (error.request) {
      ElMessage.error('网络连接失败，请检查网络')
    } else {
      ElMessage.error('请求配置错误')
    }

    return Promise.reject(error)
  }
)

export default api
