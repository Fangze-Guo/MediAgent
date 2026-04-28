/**
 * HTTP请求工具类 - 基于axios封装
 * 提供统一的请求配置、拦截器和错误处理
 */
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { logger } from './logger'
import { ErrorHandler } from './errorHandler'
import { SafeStorage, StorageKeys } from './storage'

/**
 * API基础配置接口
 */
interface ApiConfig {
  /** API基础URL */
  baseURL: string
  /** 默认请求头 */
  headers: Record<string, string>
}

/**
 * 响应数据接口
 */
interface ApiResponse<T = any> {
  /** 响应数据 */
  data: T
  /** 响应状态码 */
  status: number
  /** 响应状态文本 */
  statusText: string
  /** 响应头 */
  headers: any
}

/**
 * 错误信息接口
 */
interface ApiError {
  /** 错误消息 */
  message: string
  /** 错误状态码 */
  status?: number
  /** 原始错误对象 */
  originalError?: any
}

/**
 * 获取API基础URL
 * 优先使用环境变量，否则使用默认值
 */
const getBaseURL = (): string => {
  return '/api'
}

/**
 * 默认API配置
 */
const defaultConfig: ApiConfig = {
  baseURL: getBaseURL(),
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
}

/**
 * 创建axios实例
 */
const createAxiosInstance = (): AxiosInstance => {
  const instance = axios.create(defaultConfig)

  // 请求拦截器
  instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      // 添加认证token
      const token = SafeStorage.getString(StorageKeys.TOKEN)
      if (token) {
        config.headers.set('Authorization', `Bearer ${token}`)
      }

      // 如果是 FormData，删除默认的 Content-Type，让浏览器自动设置（包含 boundary）
      if (config.data instanceof FormData) {
        config.headers.delete('Content-Type')
      }

      // 记录请求日志
      logger.logRequest(
        config.method?.toUpperCase() || 'GET',
        config.url || '',
        config.data
      )

      return config
    },
    (error: AxiosError) => {
      logger.error('请求拦截器错误:', error)
      return Promise.reject(error)
    }
  )

  // 响应拦截器
  instance.interceptors.response.use(
    (response: AxiosResponse) => {
      // 记录响应日志
      logger.logResponse(
        response.config.method?.toUpperCase() || 'GET',
        response.config.url || '',
        response.status,
        response.data
      )
      return response
    },
    (error: AxiosError) => {
      // 记录错误日志
      logger.logError(
        error.config?.method?.toUpperCase() || 'GET',
        error.config?.url || '',
        error
      )

      // 使用统一错误处理
      const appError = ErrorHandler.fromHttpError(error)

      // 401 错误特殊处理
      if (appError.code === 401) {
        // 清除过期的token
        SafeStorage.remove(StorageKeys.TOKEN)
        SafeStorage.remove(StorageKeys.USER)

        // 如果当前不在登录页，跳转到登录页
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }

      return Promise.reject(appError)
    }
  )

  return instance
}

// 创建axios实例
const api = createAxiosInstance()

/**
 * 通用HTTP请求方法
 * @param config axios请求配置
 * @returns Promise<ApiResponse<T>>
 */
export const request = async <T = any>(config: AxiosRequestConfig): Promise<ApiResponse<T>> => {
  try {
    const response = await api.request<T>(config)
    return {
      data: response.data,
      status: response.status,
      statusText: response.statusText,
      headers: response.headers
    }
  } catch (error) {
    throw error
  }
}

/**
 * GET请求
 * @param url 请求URL
 * @param config 请求配置
 * @returns Promise<ApiResponse<T>>
 */
export const get = async <T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> => {
  return request<T>({ ...config, method: 'GET', url })
}

/**
 * POST请求
 * @param url 请求URL
 * @param data 请求数据
 * @param config 请求配置
 * @returns Promise<ApiResponse<T>>
 */
export const post = async <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> => {
  return request<T>({ ...config, method: 'POST', url, data })
}

/**
 * PUT请求
 * @param url 请求URL
 * @param data 请求数据
 * @param config 请求配置
 * @returns Promise<ApiResponse<T>>
 */
export const put = async <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> => {
  return request<T>({ ...config, method: 'PUT', url, data })
}

/**
 * DELETE请求
 * @param url 请求URL
 * @param config 请求配置
 * @returns Promise<ApiResponse<T>>
 */
export const del = async <T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> => {
  return request<T>({ ...config, method: 'DELETE', url })
}

/**
 * 发送JSON数据的POST请求
 * @param url 请求URL
 * @param data 请求数据
 * @param signal 取消信号
 * @returns Promise<T>
 */
export const postJson = async <T = any, B = any>(
  url: string, 
  data: B, 
  signal?: AbortSignal
): Promise<T> => {
  const response = await post<T>(url, data, { 
    headers: { 'Content-Type': 'application/json' },
    signal 
  })
  return response.data
}

/**
 * 发送JSON数据的PUT请求
 * @param url 请求URL
 * @param data 请求数据
 * @param signal 取消信号
 * @returns Promise<T>
 */
export const putJson = async <T = any, B = any>(
  url: string, 
  data: B, 
  signal?: AbortSignal
): Promise<T> => {
  const response = await put<T>(url, data, { 
    headers: { 'Content-Type': 'application/json' },
    signal 
  })
  return response.data
}

/**
 * 导出axios实例，供特殊需求使用
 */
export { api }

/**
 * 导出类型定义
 */
export type { ApiResponse, ApiError, ApiConfig }

/**
 * Authenticated fetch - 用于 SSE 等需要原生 fetch 的场景
 * 与参考项目 claudecodeui 的 authenticatedFetch 保持一致
 */
export const authenticatedFetch = (url: string, options: RequestInit = {}): Promise<Response> => {
  const token = SafeStorage.getString(StorageKeys.TOKEN)

  const defaultHeaders: Record<string, string> = {}

  // Only set Content-Type for non-FormData requests
  if (!(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json'
  }

  if (token) {
    defaultHeaders['Authorization'] = `Bearer ${token}`
  }

  return fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  })
}
