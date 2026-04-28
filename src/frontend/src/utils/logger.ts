/**
 * 日志工具类
 * 根据环境变量控制日志输出
 */

/**
 * 日志级别
 */
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4
}

/**
 * 日志配置
 */
interface LogConfig {
  level: LogLevel
  enableConsole: boolean
  enableTimestamp: boolean
}

/**
 * 日志工具类
 */
class Logger {
  private config: LogConfig

  constructor() {
    // 根据环境变量设置日志级别
    const isDev = import.meta.env.DEV
    const isTest = import.meta.env.MODE === 'test'

    this.config = {
      level: isDev ? LogLevel.DEBUG : LogLevel.WARN,
      enableConsole: !isTest,
      enableTimestamp: isDev
    }
  }

  /**
   * 设置日志级别
   */
  setLevel(level: LogLevel): void {
    this.config.level = level
  }

  /**
   * 格式化日志消息
   */
  private format(level: string, message: string, ...args: any[]): string {
    const timestamp = this.config.enableTimestamp 
      ? `[${new Date().toISOString()}]` 
      : ''
    return `${timestamp}[${level}] ${message}`
  }

  /**
   * 检查是否应该输出日志
   */
  private shouldLog(level: LogLevel): boolean {
    return this.config.enableConsole && level >= this.config.level
  }

  /**
   * DEBUG 级别日志
   */
  debug(message: string, ...args: any[]): void {
    if (this.shouldLog(LogLevel.DEBUG)) {
      console.debug(this.format('DEBUG', message), ...args)
    }
  }

  /**
   * INFO 级别日志
   */
  info(message: string, ...args: any[]): void {
    if (this.shouldLog(LogLevel.INFO)) {
      console.info(this.format('INFO', message), ...args)
    }
  }

  /**
   * WARN 级别日志
   */
  warn(message: string, ...args: any[]): void {
    if (this.shouldLog(LogLevel.WARN)) {
      console.warn(this.format('WARN', message), ...args)
    }
  }

  /**
   * ERROR 级别日志
   */
  error(message: string, ...args: any[]): void {
    if (this.shouldLog(LogLevel.ERROR)) {
      console.error(this.format('ERROR', message), ...args)
    }
  }

  /**
   * 记录 HTTP 请求
   */
  logRequest(method: string, url: string, data?: any): void {
    if (this.shouldLog(LogLevel.DEBUG)) {
      console.group(`🔵 ${method} ${url}`)
      if (data) {
        console.log('Request Data:', data)
      }
      console.groupEnd()
    }
  }

  /**
   * 记录 HTTP 响应
   */
  logResponse(method: string, url: string, status: number, data?: any): void {
    if (this.shouldLog(LogLevel.DEBUG)) {
      const emoji = status >= 200 && status < 300 ? '✅' : '❌'
      console.group(`${emoji} ${method} ${url} - ${status}`)
      if (data) {
        console.log('Response Data:', data)
      }
      console.groupEnd()
    }
  }

  /**
   * 记录 HTTP 错误
   */
  logError(method: string, url: string, error: any): void {
    if (this.shouldLog(LogLevel.ERROR)) {
      console.group(`❌ ${method} ${url} - Error`)
      console.error('Error:', error)
      if (error.response) {
        console.error('Response:', error.response)
      }
      console.groupEnd()
    }
  }
}

// 导出单例
export const logger = new Logger()

// 导出类型
export type { LogConfig }
