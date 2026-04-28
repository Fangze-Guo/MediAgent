/**
 * 认证守卫
 * 检查用户是否已登录
 */
import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/store/auth'

/**
 * 认证守卫 - 检查用户登录状态
 * @param _to 目标路由（未使用）
 * @param _from 来源路由（未使用）
 * @param next 导航函数
 * @returns 是否允许继续导航
 */
export async function authGuard(
  _to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext
): Promise<boolean> {
  const authStore = useAuthStore()

  // 如果未登录，跳转到登录页
  if (!authStore.isLoggedIn) {
    next('/login')
    return false
  }

  // 如果有 token 但没有用户信息，尝试获取用户信息
  if (authStore.token && !authStore.user) {
    try {
      await authStore.fetchUserInfo()
    } catch (error) {
      console.error('Failed to fetch user info:', error)
      // 如果获取用户信息失败，清除 token 并跳转到登录页
      authStore.logout()
      next('/login')
      return false
    }
  }

  return true
}
