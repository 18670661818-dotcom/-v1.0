import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { message } from 'antd'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 标记是否正在刷新 token
let isRefreshing = false
// 等待 token 刷新的请求队列
let failedQueue: Array<{
  resolve: (value: any) => void
  reject: (reason?: any) => void
}> = []

// 处理队列中的请求
const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// 清除本地存储并跳转登录
const clearAuthAndRedirect = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  // 使用 replace 避免用户回退到需要登录的页面
  window.location.replace('/login')
}

// 请求拦截器
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // 添加请求时间戳，用于调试
    config.metadata = { startTime: new Date() }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    // 可以在这里添加响应时间统计
    return response
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }

    // 处理 401 错误（未授权）
    if (error.response?.status === 401) {
      // 如果是登录接口的 401，直接返回错误
      if (originalRequest.url?.includes('/auth/login')) {
        return Promise.reject(error)
      }

      // 如果已经在重试，直接跳转登录
      if (originalRequest._retry) {
        clearAuthAndRedirect()
        return Promise.reject(error)
      }

      // 标记为重试请求
      originalRequest._retry = true

      // 如果正在刷新 token，将请求加入队列
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then(() => request(originalRequest))
          .catch((err) => Promise.reject(err))
      }

      isRefreshing = true

      // 清除本地存储并跳转登录
      clearAuthAndRedirect()
      processQueue(error, null)
      isRefreshing = false

      return Promise.reject(error)
    }

    // 处理其他错误
    const errorMessage = getErrorMessage(error)

    // 不重复显示错误消息
    if (!(error.config as any)?.hideErrorMessage) {
      message.error(errorMessage)
    }

    return Promise.reject(error)
  },
)

// 获取错误消息
function getErrorMessage(error: AxiosError): string {
  if (error.response) {
    const data = error.response.data as any
    // 优先使用后端返回的错误消息
    if (data?.detail) {
      return typeof data.detail === 'string'
        ? data.detail
        : JSON.stringify(data.detail)
    }
    if (data?.message) {
      return data.message
    }
    // 根据状态码返回默认消息
    switch (error.response.status) {
      case 400:
        return '请求参数错误'
      case 403:
        return '没有权限访问'
      case 404:
        return '请求的资源不存在'
      case 500:
        return '服务器内部错误'
      case 502:
        return '网关错误'
      case 503:
        return '服务不可用'
      default:
        return `请求失败 (${error.response.status})`
    }
  }

  if (error.code === 'ECONNABORTED') {
    return '请求超时，请检查网络连接'
  }

  if (error.message === 'Network Error') {
    return '网络连接失败，请检查网络'
  }

  return error.message || '未知错误'
}

export default request
