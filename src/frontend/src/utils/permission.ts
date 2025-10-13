/**
 * 权限判断工具
 * 基于后端返回的role字段进行权限控制
 */

export type UserRole = 'guest' | 'user' | 'admin'

export interface User {
  uid: number
  user_name: string
  role?: string
}

/**
 * 判断用户是否为管理员
 * @param user 用户信息
 * @returns 是否为管理员
 */
export function isAdmin(user: User | null): boolean {
  if (!user) return false
  const role = user.role || 'user'
  return role === 'admin'
}

/**
 * 获取用户角色
 * @param user 用户信息
 * @returns 用户角色
 */
export function getUserRole(user: User | null): UserRole {
  if (!user) return 'guest'
  return (user.role as UserRole) || 'user'
}

/**
 * 检查用户是否有指定权限
 * @param user 用户信息
 * @param requiredRole 需要的角色
 * @returns 是否有权限
 */
export function hasPermission(user: User | null, requiredRole: UserRole): boolean {
  if (!user) return requiredRole === 'guest'
  
  const userRole = getUserRole(user)
  
  // 权限等级：guest < user < admin
  const roleLevel = {
    'guest': 0,
    'user': 1,
    'admin': 2
  }
  
  return roleLevel[userRole] >= roleLevel[requiredRole]
}

/**
 * 权限装饰器 - 用于组件中的权限控制
 * @param requiredRole 需要的角色
 * @returns 权限检查函数
 */
export function requireRole(requiredRole: UserRole) {
  return (user: User | null) => hasPermission(user, requiredRole)
}

// 预定义的权限检查函数
export const requireAdmin = requireRole('admin')
export const requireUser = requireRole('user')

/**
 * 角色显示名称映射
 */
export const ROLE_NAMES: Record<UserRole, string> = {
  'guest': '游客',
  'user': '普通用户',
  'admin': '管理员'
}

/**
 * 获取角色显示名称
 * @param role 角色
 * @returns 显示名称
 */
export function getRoleName(role: UserRole): string {
  return ROLE_NAMES[role] || '未知角色'
}
