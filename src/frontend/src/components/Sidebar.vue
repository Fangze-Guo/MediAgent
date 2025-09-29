<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <h3>MediAgent</h3>
    </div>

    <div class="sidebar-content">
      <a-menu
          v-model:openKeys="openKeys"
          v-model:selectedKeys="selectedKeys"
          mode="inline"
          :items="items"
          @click="handleMenuClick"
      />
      <hr />
      <div class="history-section">
        <h4>历史对话</h4>
        <a-list class="chat-list" :split="false">
          <a-list-item
              v-for="c in conversations"
              :key="c.id"
              :class="['chat-item', { active: c.id === currentId }]"
              @click="openConversation(c.id)"
          >
            <div class="chat-item-link">
              <!-- 会话头像 -->
              <div 
                class="conversation-avatar" 
                :class="getConversationAvatarClass(c)"
                :style="getConversationAvatarStyle(c)"
              >
                <component :is="getConversationIcon(c)" />
              </div>
              <div class="conversation-content">
                <div class="chat-title">{{ c.title || c.id }}</div>
                <div class="chat-preview">{{ c.messages[c.messages.length - 1]?.content || '...' }}</div>
              </div>
            </div>
            <div class="delete-btn" @click.stop="handleDeleteConversation(c.id)">
              删除
            </div>
          </a-list-item>
        </a-list>
      </div>
    </div>

    <!-- 用户信息区域 - 移到底部 -->
    <div class="user-section">
      <div class="user-info">
        <div class="user-avatar">
          {{ currentUser?.user_name?.charAt(0).toUpperCase() || 'U' }}
        </div>
        <div class="user-details">
          <div class="user-name">{{ currentUser?.user_name || '用户' }}</div>
          <div class="user-uid">UID: {{ currentUser?.uid || '--' }}</div>
        </div>
      </div>
      <a-button 
        type="text" 
        danger 
        size="small" 
        @click="handleLogout"
        class="logout-btn"
      >
        <template #icon>
          <LogoutOutlined />
        </template>
        退出登录
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 侧边栏组件
 * 显示应用标题、新建对话按钮和历史会话列表
 * 提供会话切换功能
 */
import { useConversationsStore } from '@/store/conversations'
import { useAuthStore } from '@/store/auth'
import { useRoute, useRouter } from 'vue-router'
import { computed, h, ref } from 'vue'
import { MenuProps, message, Modal } from 'ant-design-vue'
import { CommentOutlined, FolderOutlined, LogoutOutlined, RobotOutlined, BarChartOutlined, FileTextOutlined, ExperimentOutlined } from '@ant-design/icons-vue'

// 路由相关
const router = useRouter()
const route = useRoute()

// 状态管理
const conversationsStore = useConversationsStore()
const authStore = useAuthStore()

// 计算属性
/** 当前活跃的会话ID，从路由参数获取 */
const currentId = computed(() => String(route.params.id || ''))
/** 会话列表，从store获取 */
const conversations = computed(() => conversationsStore.conversations)
/** 当前用户信息 */
const currentUser = computed(() => authStore.currentUser)

const selectedKeys = ref(['1']);
const openKeys = ref(['sub1']);
const items = ref([
  {
    key: '1',
    icon: () => h(CommentOutlined),
    label: '新建对话',
  },
  {
    key: '3',
    icon: () => h(FolderOutlined),
    label: '文件管理',
  },
  {
    key: '5',
    icon: () => h(ExperimentOutlined),
    label: '沙盒管理',
  },
]);

/**
 * 处理菜单点击事件
 */
const handleMenuClick: MenuProps['onClick'] = ({key}) => {
  if (key === '1') {
    // 跳转到主页（新建对话）
    router.push('/')
  } else if (key === '3') {
    // 跳转到文件管理页面
    router.push('/files')
  } else if (key === '5') {
    // 跳转到沙盒文件管理页面
    router.push('/sandbox-manage')
  }
};

/**
 * 打开指定会话
 * @param id 会话ID
 */
const openConversation = (id: string) => {
  if (id && id !== currentId.value) {
    router.push(`/conversation/${id}`)
  }
}

/**
 * 处理删除会话操作
 * @param id 要删除的会话ID
 */
const handleDeleteConversation = (id: string) => {
  const conversation = conversations.value.find(c => c.id === id)
  if (!conversation) return

  Modal.confirm({
    title: '确认删除',
    content: `确定要删除会话"${conversation.title || '未命名会话'}"吗？此操作不可撤销。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        const deletedTitle = conversation.title || '未命名会话'
        console.log('准备删除会话:', id, deletedTitle)

        // 调用后端API删除会话（同时从本地store删除）
        await conversationsStore.deleteConversation(id)

        console.log('会话删除完成，当前会话列表:', conversationsStore.conversations)
        message.success(`会话"${deletedTitle}"已删除`)

        // 如果删除的是当前激活的会话
        if (id === currentId.value) {
          // 检查是否还有其他会话
          if (conversationsStore.conversations.length > 0) {
            // 如果有其他会话，跳转到第一个会话
            const firstConversation = conversationsStore.conversations[0]
            await router.push(`/conversation/${firstConversation.id}`)
          } else {
            // 如果没有其他会话了，跳转到首页让用户选择
            await router.push('/')
          }
        }
      } catch (error) {
        message.error('删除会话失败，请稍后再试')
        console.error('Delete conversation error:', error)
      }
    }
  })
}

// 处理用户登出
const handleLogout = () => {
  Modal.confirm({
    title: '确认退出',
    content: '确定要退出登录吗？',
    okText: '退出',
    okType: 'danger',
    cancelText: '取消',
    onOk: () => {
      authStore.logout()
      router.push('/login')
      message.success('已退出登录')
    }
  })
}

/**
 * 助手相关方法
 */

/**
 * 获取会话图标
 */
const getConversationIcon = (conversation: any) => {
  // 如果有工具信息，使用工具的图标
  if (conversation.toolInfo?.toolIcon) {
    return conversation.toolInfo.toolIcon
  }
  
  if (conversation.assistantType) {
    switch (conversation.assistantType) {
      case 'data':
        return BarChartOutlined
      case 'document':
        return FileTextOutlined
      default:
        return RobotOutlined
    }
  }
  return RobotOutlined
}


/**
 * 获取会话头像样式类
 */
const getConversationAvatarClass = (conversation: any) => {
  // 如果有工具信息，使用工具特定的样式
  if (conversation.toolInfo?.toolId) {
    return `tool-avatar tool-${conversation.toolInfo.toolId}`
  }
  
  if (conversation.assistantType) {
    switch (conversation.assistantType) {
      case 'data':
        return 'data-avatar'
      case 'document':
        return 'document-avatar'
      default:
        return 'general-avatar'
    }
  }
  return 'general-avatar'
}

/**
 * 获取会话头像样式
 */
const getConversationAvatarStyle = (conversation: any) => {
  // 如果有工具信息，使用工具的渐变背景
  if (conversation.toolInfo?.toolGradient) {
    return {
      background: conversation.toolInfo.toolGradient
    }
  }
  return {}
}
</script>

<style scoped>
/* 侧边栏根容器：固定宽度、白底、右侧分割线 */
.sidebar {
  width: 300px;
  height: 100%;
  background: white;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: relative;
}

/* 菜单项样式调整 */
:deep(.ant-menu-item) {
  height: 48px !important;
  line-height: 48px !important;
  font-size: 16px !important;
  margin-bottom: 4px !important;
}

:deep(.ant-menu-item .anticon) {
  font-size: 18px !important;
}

:deep(.ant-menu-inline) {
  border-right: none !important;
}

/* 顶部标题区：内边距与底部分隔线 */
.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #e0e0e0;
}

/* 标题文本：大小与颜色 */
.sidebar-header h3 {
  margin: 0;
  color: #333;
  font-size: 18px;
}

/* 内容滚动区：撑满剩余高度，允许纵向滚动 */
.sidebar-content {
  flex: 1;
  padding: 20px;
  padding-bottom: 120px; /* 为底部用户信息区域留出空间 */
  overflow-y: auto;
}

/* 新建对话按钮悬停效果：轻微上移与阴影 */
.new-chat-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

/* 历史区域标题：间距、字号与颜色 */
.history-section h4 {
  margin: 0 0 16px 0;
  color: #666;
  font-size: 14px;
  font-weight: 500;
}

/* 对话列表容器：纵向间距 */
.chat-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 单条对话项：圆角、边框、过渡与可点击 */
.chat-item {
  padding: 12px !important;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid #e5e7eb;
  margin-bottom: 10px;
  background: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 对话项悬停：浅灰背景与边框高亮 */
.chat-item:hover {
  background: #f8f9fa;
  border-color: #e9ecef;
}

/* 激活中的对话项：浅蓝背景与主色边框 */
.chat-item.active {
  background: #e3f2fd;
  border-color: #2196f3;
}

/* 对话标题：加粗、字号与颜色 */
.chat-title {
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
  font-size: 14px;
}

/* 对话链接容器：水平布局 */
.chat-item-link {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

/* 对话预览：灰色小号文字，超出省略 */
.chat-preview {
  color: #666;
  font-size: 12px;
  display: block;
  width: 160px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 删除按钮样式 */
.delete-btn {
  color: #ff4d4f;
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 2px;
  transition: opacity 0.2s ease;
}

/* 删除按钮悬停效果 */
.delete-btn:hover {
  background-color: #fff1f0;
}

/* 会话头像样式 */
.conversation-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  margin-right: 12px;
  flex-shrink: 0;
  position: relative;
}


/* 工具头像基础样式 */
.tool-avatar {
  /* 基础样式，渐变背景通过内联样式设置 */
  position: relative;
}


.data-avatar {
  background: linear-gradient(135deg, #fa8c16, #ffa940);
}

.document-avatar {
  background: linear-gradient(135deg, #722ed1, #9254de);
}

.general-avatar {
  background: linear-gradient(135deg, #1890ff, #40a9ff);
}

.conversation-content {
  flex: 1;
  min-width: 0;
}

/* 用户信息区域 - 固定在底部 */
.user-section {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px 20px;
  background: white;
  border-top: 1px solid #f0f0f0;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.06);
}

.user-info {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.user-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 18px;
  margin-right: 12px;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.3);
  transition: all 0.3s ease;
}

.user-avatar:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.4);
}

.user-details {
  flex: 1;
}

.user-name {
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
  font-size: 14px;
}

.user-uid {
  font-size: 12px;
  color: #999;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-block;
}

.logout-btn {
  width: 100%;
  margin-top: 8px;
  height: 32px;
  border-radius: 6px;
  transition: all 0.3s ease;
}

.logout-btn:hover {
  background: #fff2f0;
  border-color: #ff4d4f;
}

/* 滚动条：窄条、圆角、轻度着色 */
.sidebar-content::-webkit-scrollbar {
  width: 6px;
}

/* 滚动条轨道：透明 */
.sidebar-content::-webkit-scrollbar-track {
  background: transparent;
}

/* 滚动条拇指：半透明深色、圆角 */
.sidebar-content::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
}

/* 滚动条拇指悬停：稍深颜色 */
.sidebar-content::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}
</style>
