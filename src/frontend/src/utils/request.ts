/**
 * HTTP请求工具类 - 基于axios封装
 * 提供统一的请求配置、拦截器和错误处理
 */
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios'

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
  return (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
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
      // 可以在这里添加认证token等
      // const token = localStorage.getItem('token')
      // if (token) {
      //   config.headers = {
      //     ...config.headers,
      //     Authorization: `Bearer ${token}`
      //   }
      // }
      
      console.log('发送请求:', config.method?.toUpperCase(), config.url)
      return config
    },
    (error: AxiosError) => {
      console.error('请求拦截器错误:', error)
      return Promise.reject(error)
    }
  )

  // 响应拦截器
  instance.interceptors.response.use(
    (response: AxiosResponse) => {
      console.log('收到响应:', response.status, response.config.url)
      return response
    },
    (error: AxiosError) => {
      console.error('响应拦截器错误:', error)
      
      // 统一错误处理
      const apiError: ApiError = {
        message: error.message || '请求失败',
        status: error.response?.status,
        originalError: error
      }

      // 根据状态码处理不同错误
      if (error.response) {
        // 服务器响应了错误状态码
        const status = error.response.status
        switch (status) {
          case 400:
            apiError.message = '请求参数错误'
            break
          case 401:
            apiError.message = '未授权，请重新登录'
            break
          case 403:
            apiError.message = '拒绝访问'
            break
          case 404:
            apiError.message = '请求的资源不存在'
            break
          case 500:
            apiError.message = '服务器内部错误'
            break
          default:
            apiError.message = `请求失败 (${status})`
        }
      } else if (error.request) {
        // 请求已发出但没有收到响应
        apiError.message = '网络连接失败，请检查网络'
      }

      return Promise.reject(apiError)
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
 * 导出axios实例，供特殊需求使用
 */
export { api }

/**
 * 导出类型定义
 */
export type { ApiResponse, ApiError, ApiConfig }
