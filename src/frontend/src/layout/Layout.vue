<template>
  <a-layout class="root-layout">
    <a-layout-sider 
        :collapsed="collapsed" 
        :collapsible="true" 
        :trigger="null" 
        :width="300" 
        :collapsedWidth="0"
        theme="light" 
        class="app-sider">
      <Sidebar />
    </a-layout-sider>
    <a-layout class="site-layout">
      <a-layout-header style="background: #fff; padding: 0">
        <menu-unfold-outlined v-if="collapsed" class="trigger" @click="toggle()" />
        <menu-fold-outlined v-else class="trigger" @click="toggle()" />
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
import Sidebar from '@/components/Sidebar.vue'
import { MenuUnfoldOutlined, MenuFoldOutlined } from '@ant-design/icons-vue'
import { useConversationsStore } from '@/store/conversations'
import { useAuthStore } from '@/store/auth'

const collapsed = ref(false)
const toggle = () => (collapsed.value = !collapsed.value)

// 状态管理
const conversationsStore = useConversationsStore()
const authStore = useAuthStore()

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
  background: #ffffff;
  border-right: 1px solid #e5e7eb;
}

.site-layout {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  min-width: 0;
}

.trigger {
  font-size: 18px;
  cursor: pointer;
}

.app-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: #f5f5f5;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #666;
}

.loading-container p {
  margin-top: 16px;
  margin-bottom: 0;
}
</style>
  