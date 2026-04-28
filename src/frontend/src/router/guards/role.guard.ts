/**
 * 角色权限守卫
 * 检查用户是否有访问特定路由的权限
 */
import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/store/auth'

/**
 * 角色守卫 - 检查用户角色权限
 * @param to 目标路由
 * @param _from 来源路由（未使用）
 * @param next 导航函数
 * @returns 是否允许继续导航
 */
export function roleGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext
): boolean {
  const authStore = useAuthStore()

  // 检查是否需要管理员权限
  if (to.meta.adminOnly && authStore.user?.role !== 'admin') {
    console.warn(`Access denied: User role '${authStore.user?.role}' is not admin`)
    // 非管理员访问管理员页面，跳转到首页
    next('/')
    return false
  }

  return true
}
