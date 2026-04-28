/**
 * 路由配置
 * 定义应用的所有路由规则和页面组件映射
 */
import { useAuthStore } from '@/store/auth'
import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'
import { authGuard, roleGuard, titleGuard } from './guards'

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
        path: '/code-agent',
        name: 'CodeAgent',
        component: () => import('@/views/clinical_tools/code_agent/CodeAgentView.vue'),
        meta: {
            title: 'MediAgent - Code Agent',
            requiresAuth: true
        }
    },
    {
        path: '/rag-knowledge-base',
        name: 'RagKnowledgeBase',
        component: () => import('@/views/clinical_tools/rag/RagKnowledgeBaseView.vue'),
        meta: {
            title: 'MediAgent - Rag Knowledge Base',
            requiresAuth: true
        }
    },
    {
        path: '/knowledge-base/:id',
        name: 'KnowledgeBaseDetail',
        component: () => import('@/views/clinical_tools/rag/RagKnowledgeBaseDetailView.vue'),
        meta: {
            title: 'MediAgent - Knowledge Base Detail',
            requiresAuth: true
        }
    },
    {
        path: '/knowledge-base/:kbId/document/:docId',
        name: 'DocumentDetail',
        component: () => import('@/views/DocumentDetailView.vue'),
        meta: {
            title: 'MediAgent - Document Detail',
            requiresAuth: true
        }
    },
    {
        path: '/ct-diagnosis',
        name: 'CtDiagnosis',
        component: () => import('@/views/clinical_tools/CtDiagnosisView.vue'),
        meta: {
            title: 'MediAgent - Ct Diagnosis',
            requiresAuth: true
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
 * 在每次路由跳转前执行，用于认证检查、权限验证和设置页面标题
 * @param to 目标路由
 * @param from 来源路由
 * @param next 路由跳转函数
 */
router.beforeEach(async (to, from, next) => {
    // 1. 设置页面标题
    titleGuard(to)

    // 2. 检查是否需要认证
    const requiresAuth = to.meta.requiresAuth !== false // 默认为需要认证
    const authStore = useAuthStore()

    if (requiresAuth) {
        // 需要认证的路由
        // 2.1 执行认证守卫
        const authPassed = await authGuard(to, from, next)
        if (!authPassed) {
            return // 认证失败，已在守卫中处理跳转
        }

        // 2.2 执行角色权限守卫
        const rolePassed = roleGuard(to, from, next)
        if (!rolePassed) {
            return // 权限不足，已在守卫中处理跳转
        }
    } else if (to.name === 'Login' && authStore.isLoggedIn) {
        // 已登录用户访问登录页，跳转到首页
        next('/')
        return
    }

    // 3. 所有检查通过，允许导航
    next()
})

export default router
