/**
 * 错误处理工具类
 * 提供统一的错误处理机制
 */
import { logger } from './logger'

/**
 * 错误类型
 */
export enum ErrorType {
  NETWORK = 'NETWORK_ERROR',
  VALIDATION = 'VALIDATION_ERROR',
  AUTHENTICATION = 'AUTHENTICATION_ERROR',
  AUTHORIZATION = 'AUTHORIZATION_ERROR',
  NOT_FOUND = 'NOT_FOUND_ERROR',
  SERVER = 'SERVER_ERROR',
  UNKNOWN = 'UNKNOWN_ERROR'
}

/**
 * 标准错误接口
 */
export interface AppError {
  type: ErrorType
  message: string
  code?: number
  details?: any
  timestamp: number
}

/**
 * 错误处理器类
 */
export class ErrorHandler {
  /**
   * 创建标准错误对象
   */
  static createError(
    type: ErrorType,
    message: string,
    code?: number,
    details?: any
  ): AppError {
    return {
      type,
      message,
      code,
      details,
      timestamp: Date.now()
    }
  }

  /**
   * 从 HTTP 错误创建标准错误
   */
  static fromHttpError(error: any): AppError {
    // 网络错误
    if (!error.response) {
      return this.createError(
        ErrorType.NETWORK,
        '网络连接失败，请检查网络',
        0,
        error
      )
    }

    const status = error.response?.status
    const data = error.response?.data

    // 根据状态码分类
    switch (status) {
      case 400:
        return this.createError(
          ErrorType.VALIDATION,
          data?.message || '请求参数错误',
          status,
          data
        )
      case 401:
        return this.createError(
          ErrorType.AUTHENTICATION,
          data?.message || '未授权，请重新登录',
          status,
          data
        )
      case 403:
        return this.createError(
          ErrorType.AUTHORIZATION,
          data?.message || '拒绝访问',
          status,
          data
        )
      case 404:
        return this.createError(
          ErrorType.NOT_FOUND,
          data?.message || '请求的资源不存在',
          status,
          data
        )
      case 500:
      case 502:
      case 503:
        return this.createError(
          ErrorType.SERVER,
          data?.message || '服务器错误，请稍后重试',
          status,
          data
        )
      default:
        return this.createError(
          ErrorType.UNKNOWN,
          data?.message || `请求失败 (${status})`,
          status,
          data
        )
    }
  }

  /**
   * 处理错误并返回用户友好的消息
   */
  static handle(error: any, context?: string): AppError {
    let appError: AppError

    // 如果已经是 AppError
    if (error.type && error.message && error.timestamp) {
      appError = error as AppError
    } 
    // 如果是 HTTP 错误
    else if (error.response || error.request) {
      appError = this.fromHttpError(error)
    }
    // 其他错误
    else {
      appError = this.createError(
        ErrorType.UNKNOWN,
        error.message || '发生未知错误',
        undefined,
        error
      )
    }

    // 记录错误日志
    logger.error(
      `${context ? `[${context}] ` : ''}${appError.type}: ${appError.message}`,
      appError
    )

    return appError
  }

  /**
   * 获取用户友好的错误消息
   */
  static getUserMessage(error: AppError): string {
    return error.message
  }

  /**
   * 判断是否需要重新登录
   */
  static shouldRelogin(error: AppError): boolean {
    return error.type === ErrorType.AUTHENTICATION
  }

  /**
   * 判断是否是网络错误
   */
  static isNetworkError(error: AppError): boolean {
    return error.type === ErrorType.NETWORK
  }
}

/**
 * 异步函数错误包装器
 * 自动捕获并处理错误
 */
export function withErrorHandler<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  context?: string
): T {
  return (async (...args: any[]) => {
    try {
      return await fn(...args)
    } catch (error) {
      const appError = ErrorHandler.handle(error, context)
      throw appError
    }
  }) as T
}
