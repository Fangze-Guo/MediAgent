<template>
  <a-layout class="root-layout">
    <a-layout-sider
        :collapsed="collapsed"
        :collapsible="true"
        :trigger="null"
        :width="300"
        :collapsedWidth="0"
        :theme="themeStore.isDark ? 'dark' : 'light'"
        class="app-sider">
      <Sidebar />
    </a-layout-sider>
    <a-layout class="site-layout">
      <a-layout-header class="app-header">
        <div class="header-left">
          <menu-unfold-outlined v-if="collapsed" class="trigger" @click="toggle()" />
          <menu-fold-outlined v-else class="trigger" @click="toggle()" />
          <Breadcrumb />
        </div>
        <div class="header-right">
          <a-button type="text" @click="themeStore.toggleTheme()" class="theme-toggle">
            <template #icon>
              <svg v-if="themeStore.isDark" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <line x1="12" y1="21" x2="12" y2="23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <line x1="1" y1="12" x2="3" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <line x1="21" y1="12" x2="23" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </template>
          </a-button>
          <LanguageSwitcher />
        </div>
      </a-layout-header>
      <a-layout-content class="app-content">
        <Suspense>
          <router-view />
          <template #fallback>
            <div class="loading-container">
              <a-spin size="large" />
              <p>加载中...</p>
            </div>
          </template>
        </Suspense>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch } from 'vue'
import Sidebar from '@/components/common/Sidebar.vue'
import LanguageSwitcher from '@/components/common/LanguageSwitcher.vue'
import Breadcrumb from '@/components/common/Breadcrumb.vue'
import { MenuUnfoldOutlined, MenuFoldOutlined } from '@ant-design/icons-vue'
import { useConversationsStore } from '@/store/conversations'
import { useAuthStore } from '@/store/auth'
import { useThemeStore } from '@/store/theme'

const collapsed = ref(false)
const toggle = () => (collapsed.value = !collapsed.value)

// 状态管理
const conversationsStore = useConversationsStore()
const authStore = useAuthStore()
const themeStore = useThemeStore()

// 加载用户会话的函数
const loadConversations = async () => {
  try {
    // 只有在用户已登录时才加载会话
    if (authStore.user && conversationsStore.conversations.length === 0) {
      console.log('准备加载用户会话列表')
      await conversationsStore.loadUserConversationsDetails()
    }
  } catch (error) {
    console.error('加载会话列表失败:', error)
  }
}

// 页面初始化时检查并加载用户会话
onMounted(async () => {
  await loadConversations()
})

// 监听用户状态变化，当用户登录成功后自动加载会话
watch(
  () => authStore.user,
  async (newUser, oldUser) => {
    // 如果用户从null变为有值（登录成功），则加载会话
    if (newUser && !oldUser) {
      console.log('检测到用户登录，开始加载会话列表')
      await loadConversations()
    }
    // 如果用户从有值变为null（登出），则清空会话列表
    else if (!newUser && oldUser) {
      console.log('检测到用户登出，清空会话列表')
      conversationsStore.clearAllConversations()
    }
  },
  { immediate: false }
)
</script>

<style>
.root-layout {
  width: 100%;
  height: 100vh;
  display: flex;
}

.app-sider {
  border-right: 1px solid var(--border-color);
}

.site-layout {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  min-width: 0;
}

.app-header {
  padding: 0 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color-light);
  background: var(--bg-primary) !important;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.trigger {
  font-size: 18px;
  cursor: pointer;
  color: var(--text-primary);
}

.theme-toggle {
  font-size: 18px;
  color: var(--text-primary);
}

.app-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: var(--bg-secondary) !important;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-secondary);
}

.loading-container p {
  margin-top: 16px;
  margin-bottom: 0;
}
</style>
  