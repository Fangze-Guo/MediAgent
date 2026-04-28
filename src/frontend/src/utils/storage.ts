/**
 * localStorage 工具类
 * 提供类型安全的 localStorage 操作
 */

/**
 * 类型守卫函数
 */
export function isValidUserInfo(obj: any): obj is { uid: number; user_name: string; role?: string; avatar?: string } {
  return (
    obj &&
    typeof obj === 'object' &&
    typeof obj.uid === 'number' &&
    typeof obj.user_name === 'string' &&
    (obj.role === undefined || typeof obj.role === 'string') &&
    (obj.avatar === undefined || typeof obj.avatar === 'string')
  )
}

/**
 * 安全的 localStorage 操作类
 */
export class SafeStorage {
  /**
   * 安全地获取并解析 JSON 数据
   * @param key 存储键
   * @param validator 类型验证函数
   * @returns 解析后的数据或 null
   */
  static getJSON<T>(key: string, validator?: (obj: any) => obj is T): T | null {
    try {
      const item = localStorage.getItem(key)
      if (!item) return null

      const parsed = JSON.parse(item)
      
      // 如果提供了验证函数，使用它验证
      if (validator && !validator(parsed)) {
        console.warn(`Invalid data structure for key: ${key}`)
        localStorage.removeItem(key) // 清除无效数据
        return null
      }

      return parsed as T
    } catch (error) {
      console.error(`Failed to parse localStorage item: ${key}`, error)
      localStorage.removeItem(key) // 清除损坏的数据
      return null
    }
  }

  /**
   * 安全地设置 JSON 数据
   * @param key 存储键
   * @param value 要存储的值
   * @returns 是否成功
   */
  static setJSON<T>(key: string, value: T): boolean {
    try {
      const serialized = JSON.stringify(value)
      localStorage.setItem(key, serialized)
      return true
    } catch (error) {
      console.error(`Failed to set localStorage item: ${key}`, error)
      return false
    }
  }

  /**
   * 安全地获取字符串
   * @param key 存储键
   * @returns 字符串或 null
   */
  static getString(key: string): string | null {
    try {
      return localStorage.getItem(key)
    } catch (error) {
      console.error(`Failed to get localStorage item: ${key}`, error)
      return null
    }
  }

  /**
   * 安全地设置字符串
   * @param key 存储键
   * @param value 要存储的值
   * @returns 是否成功
   */
  static setString(key: string, value: string): boolean {
    try {
      localStorage.setItem(key, value)
      return true
    } catch (error) {
      console.error(`Failed to set localStorage item: ${key}`, error)
      return false
    }
  }

  /**
   * 安全地移除项
   * @param key 存储键
   */
  static remove(key: string): void {
    try {
      localStorage.removeItem(key)
    } catch (error) {
      console.error(`Failed to remove localStorage item: ${key}`, error)
    }
  }

  /**
   * 安全地清空所有项
   */
  static clear(): void {
    try {
      localStorage.clear()
    } catch (error) {
      console.error('Failed to clear localStorage', error)
    }
  }
}

/**
 * 存储键常量
 */
export const StorageKeys = {
  TOKEN: 'mediagent_token',
  USER: 'mediagent_user',
} as const
