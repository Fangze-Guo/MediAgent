/**
 * 页面标题守卫
 * 设置页面标题
 */
import type { RouteLocationNormalized } from 'vue-router'

/**
 * 标题守卫 - 设置页面标题
 * @param to 目标路由
 */
export function titleGuard(to: RouteLocationNormalized): void {
  // 设置页面标题
  if (to.meta.title) {
    document.title = to.meta.title as string
  }
}
