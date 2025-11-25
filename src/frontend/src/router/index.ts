/**
 * 路由配置
 * 定义应用的所有路由规则和页面组件映射
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/store/auth'

/**
 * 路由配置数组
 * 定义所有页面的路由规则
 */
const routes: RouteRecordRaw[] = [
    {
        path: '/login',
        name: 'Login',
        component: () => import('@/views/LoginView.vue'),
        meta: { 
            title: 'MediAgent - Login',
            requiresAuth: false 
        }
    },
    {
        path: '/',
        name: 'Home',
        component: () => import('@/views/HomeView.vue'),
        meta: {
            title: 'MediAgent - Home',
            requiresAuth: true
        }
    },
    {
        path: '/conversation/:id',
        name: 'Conversation',
        component: () => import('@/views/ChatView.vue'),
        meta: {
            title: 'MediAgent - Conversation',
            requiresAuth: true
        }
    },
    {
        path: '/files',
        name: 'files',
        component: () => import('@/views/FileManageView.vue'),
        meta: {
            title: 'MediAgent - Files',
            requiresAuth: true
        }
    },
    {
        path: '/tasks',
        name: 'Tasks',
        component: () => import('@/views/TaskManageView.vue'),
        meta: {
            title: 'MediAgent - Tasks',
            requiresAuth: true
        }
    },
    {
        path: '/datasets',
        name: 'Datasets',
        component: () => import('@/views/DatasetManageView.vue'),
        meta: {
            title: 'MediAgent - Datasets',
            requiresAuth: true
        }
    },
    {
        path: '/settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: {
            title: 'MediAgent - Settings',
            requiresAuth: true
        }
    },
    {
        path: '/app-store',
        name: 'AppStore',
        component: () => import('@/views/AppStoreView.vue'),
        meta: {
            title: 'MediAgent - AppStore',
            requiresAuth: true
        }
    },
    {
        path: '/app-store/:id',
        name: 'AppDetail',
        component: () => import('@/views/AppDetailView.vue'),
        meta: {
            title: 'MediAgent - AppDetail',
            requiresAuth: true
        }
    },
    {
        path: '/model-config',
        name: 'ModelConfig',
        component: () => import('@/views/ModelConfigView.vue'),
        meta: {
            title: 'MediAgent - Model Config',
            requiresAuth: true,
            adminOnly: true
        }
    },
    {
        path: '/:pathMatch(.*)*',
        name: 'NotFound',
        component: () => import('@/views/NotFoundView.vue'),
        meta: {
            title: 'MediAgent - NotFound'
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
 * 在每次路由跳转前执行，用于认证检查和设置页面标题
 * @param to 目标路由
 * @param _from 来源路由（未使用）
 * @param next 路由跳转函数
 */
router.beforeEach(async (to, _from, next) => {
    // 设置页面标题
    if (to.meta.title) {
        document.title = to.meta.title as string
    }

    // 检查是否需要认证
    const requiresAuth = to.meta.requiresAuth !== false // 默认为需要认证
    const authStore = useAuthStore()

    if (requiresAuth) {
        // 需要认证的路由
        if (!authStore.isLoggedIn) {
            // 未登录，跳转到登录页
            next('/login')
            return
        }
        // 如果有token但没有用户信息，尝试获取用户信息
        if (authStore.token && !authStore.user) {
            try {
                await authStore.fetchUserInfo()
            } catch (error) {
                console.error('Failed to fetch user info:', error)
                // 如果获取用户信息失败，清除token并跳转到登录页
                authStore.logout()
                next('/login')
                return
            }
        }
        
        // 检查管理员权限
        if (to.meta.adminOnly && authStore.user?.role !== 'admin') {
            // 非管理员访问管理员页面，跳转到首页
            next('/')
            return
        }
    } else if (to.name === 'Login' && authStore.isLoggedIn) {
        // 已登录用户访问登录页，跳转到首页
        next('/')
        return
    }

    next()
})

export default router
