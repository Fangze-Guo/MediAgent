/**
 * 路由配置
 * 定义应用的所有路由规则和页面组件映射
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

/**
 * 路由配置数组
 * 定义所有页面的路由规则
 */
const routes: RouteRecordRaw[] = [
    {
        path: '/',
        name: 'Home',
        component: () => import('@/views/HomeView.vue'),
        meta: {title: 'MediAgent - 首页'}
    },
    {
        path: '/chat/:id',
        name: 'Chat',
        component: () => import('@/views/ChatView.vue'),
        meta: {title: 'MediAgent - 聊天'}
    },
    {
        path: '/files',
        name: 'files',
        component: () => import('@/views/FileManageView.vue'),
        meta: {title: 'MediAgent - 文件'}
    },
    {
        path: '/settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: {
            title: 'MediAgent - 设置'
        }
    },
    {
        path: '/:pathMatch(.*)*',
        name: 'NotFound',
        component: () => import('@/views/NotFoundView.vue'),
        meta: {
            title: 'MediAgent - 页面未找到'
        }
    }
]

/**
 * 创建路由实例
 * 使用HTML5 History模式
 */
const router = createRouter({
    history: createWebHistory(),
    routes
})

/**
 * 全局路由守卫
 * 在每次路由跳转前执行，用于设置页面标题
 * @param to 目标路由
 * @param _from 来源路由（未使用）
 * @param next 路由跳转函数
 */
router.beforeEach((to, _from, next) => {
    // 如果路由meta中有title，则设置为页面标题
    if (to.meta.title) {
        document.title = to.meta.title as string
    }
    next()
})

export default router
