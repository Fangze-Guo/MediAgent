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
        component: () => import('@/views/auth/LoginView.vue'),
        meta: {
            title: 'MedWiser - Login',
            requiresAuth: false
        }
    },
    {
        path: '/',
        name: 'Home',
        component: () => import('@/views/home/HomeView.vue'),
        meta: {
            title: 'MedWiser - Home',
            requiresAuth: true
        }
    },
    {
        path: '/conversation/:id',
        name: 'Conversation',
        component: () => import('@/views/chat/ChatView.vue'),
        meta: {
            title: 'MedWiser - Conversation',
            requiresAuth: true
        }
    },
    {
        path: '/files',
        name: 'files',
        component: () => import('@/views/file/FileManageView.vue'),
        meta: {
            title: 'MedWiser - Files',
            requiresAuth: true
        }
    },
    {
        path: '/patients',
        name: 'Patients',
        component: () => import('@/views/patient/PatientManageView.vue'),
        meta: {
            title: 'MedWiser - Patients',
            requiresAuth: true
        }
    },
    {
        path: '/patients/:patientId',
        name: 'PatientDetail',
        component: () => import('@/views/patient/PatientDetailView.vue'),
        meta: {
            title: 'MedWiser - Patient Detail',
            requiresAuth: true
        }
    },
    {
        path: '/skill-repository',
        name: 'SkillStore',
        component: () => import('@/views/skill-store/SkillStoreView.vue'),
        meta: {
            title: 'MedWiser - Skill Repository',
            requiresAuth: true
        }
    },
    {
        path: '/skill-repository/:id',
        name: 'SkillDetail',
        component: () => import('@/views/skill-store/SkillDetailView.vue'),
        meta: {
            title: 'MedWiser - Skill Detail',
            requiresAuth: true
        }
    },
    {
        path: '/skill-store',
        redirect: '/skill-repository'
    },
    {
        path: '/skill-store/:id',
        redirect: to => `/skill-repository/${to.params.id}`
    },
    {
        path: '/model-config',
        name: 'ModelConfig',
        component: () => import('@/views/model/ModelConfigView.vue'),
        meta: {
            title: 'MedWiser - Model Config',
            requiresAuth: true,
            adminOnly: true
        }
    },
    {
        path: '/clinical-tools',
        name: 'ClinicalTools',
        component: () => import('@/views/clinical-tools/ClinicalToolsView.vue'),
        meta: {
            title: 'MedWiser - Clinical Tools',
            requiresAuth: true
        }
    },
    {
        path: '/nice-bcx-agent',
        name: 'NiceBcxAgent',
        component: () => import('@/views/clinical-tools/code_agent/CodeAgentView.vue'),
        meta: {
            title: 'MedWiser - NICE-BCX Agent',
            requiresAuth: true
        }
    },
    {
        path: '/clinical-agent/:agentId',
        name: 'ClinicalAgent',
        component: () => import('@/views/clinical-tools/code_agent/CodeAgentView.vue'),
        meta: {
            title: 'MedWiser - Clinical Agent',
            requiresAuth: true
        }
    },
    {
        path: '/clinical-agent/:agentId/skills',
        name: 'ClinicalAgentSkills',
        component: () => import('@/views/clinical-tools/ClinicalAgentSkillsView.vue'),
        meta: {
            title: 'MedWiser - Agent Skills',
            requiresAuth: true
        }
    },
    {
        path: '/knowledge-base',
        name: 'KnowledgeBase',
        component: () => import('@/views/clinical-tools/rag/RagKnowledgeBaseView.vue'),
        meta: {
            title: 'MedWiser - Knowledge Base',
            requiresAuth: true
        }
    },
    {
        path: '/nice-bcx-knowledge-base',
        redirect: '/knowledge-base'
    },
    {
        path: '/knowledge-base/:id',
        name: 'KnowledgeBaseDetail',
        component: () => import('@/views/clinical-tools/rag/RagKnowledgeBaseDetailView.vue'),
        meta: {
            title: 'MedWiser - Knowledge Base Detail',
            requiresAuth: true
        }
    },
    {
        path: '/knowledge-base/:kbId/document/:docId',
        name: 'DocumentDetail',
        component: () => import('@/views/dataset/DocumentDetailView.vue'),
        meta: {
            title: 'MedWiser - Document Detail',
            requiresAuth: true
        }
    },
    {
        path: '/:pathMatch(.*)*',
        name: 'NotFound',
        component: () => import('@/views/NotFoundView.vue'),
        meta: {
            title: 'MedWiser - NotFound'
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
