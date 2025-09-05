<template>
  <div class="chat-bg">
    <div class="chat-fixed">
      <a-layout class="chat-layout">
        <a-layout-header class="chat-header">
          <div class="header-left">
            <h2 class="chat-title">{{ currentConversation?.title || '新对话' }}</h2>
          </div>
          <div class="header-right">
            <a-button 
              v-if="currentConversation" 
              type="text" 
              danger 
              @click="handleDeleteConversation"
              :loading="deleting"
            >
              <template #icon>
                <a-icon type="delete" />
              </template>
              删除会话
            </a-button>
          </div>
        </a-layout-header>
        <a-layout-content class="chat-messages" ref="messagesEl">
          <div 
            v-for="(m, idx) in currentMessages" 
            :key="idx"
            :class="['message', m.role === 'user' ? 'user' : 'ai']"
          >
            <div v-if="m.role !== 'user'" class="avatar ai-avatar">
              <a-icon type="robot" />
            </div>
            <div class="message-content">{{ m.content }}</div>
            <div v-if="m.role === 'user'" class="avatar user-avatar">
              <a-icon type="user" />
            </div>
          </div>
        </a-layout-content>
        <a-layout-footer class="chat-input">
          <a-textarea 
            v-model:value="inputMessage"
            class="message-input"
            placeholder="输入消息，按 Enter 换行"
            :auto-size="{ minRows: 1, maxRows: 6 }"
          />
          <a-button 
            type="primary" 
            class="send-btn"
            :loading="sending"
            @click="sendMessage"
          >
            发送
          </a-button>
        </a-layout-footer>
      </a-layout>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 聊天视图组件
 * 提供完整的聊天界面，包括消息显示、输入、发送和会话管理功能
 */
import { ref, nextTick, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Modal, message } from 'ant-design-vue'
import { chat as chatApi } from '@/apis/chat'
import { useConversationsStore } from '@/store/conversations'

// 路由相关
const route = useRoute()
const router = useRouter()

// 状态管理
const conversationsStore = useConversationsStore()

// 响应式数据
/** 用户输入的消息内容 */
const inputMessage = ref('')
/** 是否正在发送消息 */
const sending = ref(false)
/** 是否正在删除会话 */
const deleting = ref(false)
/** 当前活跃的会话ID */
const activeId = ref<string>('')
/** 消息容器的DOM引用，用于滚动到底部 */
const messagesEl = ref<HTMLElement | null>(null)

/**
 * 滚动消息容器到底部
 * 在发送消息后自动滚动到最新消息
 */
const scrollToBottom = async () => {
  await nextTick()
  const el = messagesEl.value
  if (el) el.scrollTop = el.scrollHeight
}

// 计算属性
/** 当前活跃的会话对象 */
const currentConversation = computed(() => conversationsStore.getConversation(activeId.value) || null)
/** 当前会话的消息列表 */
const currentMessages = computed(() => currentConversation.value?.messages || [])

/**
 * 创建新会话
 * 生成新的会话ID并跳转到聊天页面
 */
const createNewConversation = () => {
  const conv = conversationsStore.createConversation()
  activeId.value = conv.id
  router.replace({ name: 'Chat', params: { id: conv.id } })
}

// 初始化：根据路由参数加载或创建会话
const routeId = (route.params.id as string | undefined) || ''
if (routeId && conversationsStore.getConversation(routeId)) {
  // 如果路由ID存在且对应会话存在，则加载该会话
  activeId.value = routeId
} else {
  // 否则创建新会话
  createNewConversation()
}

// 监听路由变化，切换会话
watch(() => route.params.id, (val) => {
  const id = String(val || '')
  if (id && id !== activeId.value) {
    activeId.value = id
  }
})

// 监听当前会话变化，检查是否需要自动发送消息
watch(currentConversation, (newConv) => {
  if (newConv && newConv.messages.length > 0) {
    // 检查最后一条消息是否是用户消息且没有对应的AI回复
    const lastMessage = newConv.messages[newConv.messages.length - 1]
    if (lastMessage.role === 'user') {
      // 检查是否有对应的AI回复（下一条消息应该是assistant）
      const nextMessage = newConv.messages[newConv.messages.length]
      if (!nextMessage || nextMessage.role !== 'assistant') {
        // 自动发送消息获取AI回复
        console.log('检测到未回复的用户消息，自动发送给AI')
        setTimeout(() => {
          sendMessageToAI(lastMessage.content)
        }, 100)
      }
    }
  }
}, { immediate: true })

/**
 * 发送消息给AI（内部函数）
 * @param messageText 要发送的消息内容
 */
const sendMessageToAI = async (messageText: string) => {
  if (!currentConversation.value || sending.value) return
  
  sending.value = true
  
  try {
    // 调用聊天API
    const data = await chatApi({
      conversation_id: currentConversation.value.id,
      message: messageText,
      history: currentMessages.value.map(m => ({ 
        role: m.role, 
        content: m.content 
      }))
    })
    
    // 添加AI回复到会话
    conversationsStore.appendMessage(currentConversation.value.id, { 
      role: 'assistant', 
      content: data.answer ?? '' 
    })
  } catch (error) {
    // 处理错误，显示错误消息
    console.error('发送消息失败:', error)
    conversationsStore.appendMessage(currentConversation.value.id, { 
      role: 'assistant', 
      content: '抱歉，请求失败，请稍后再试。' 
    })
  } finally {
    // 重置发送状态并滚动到底部
    sending.value = false
    await scrollToBottom()
  }
}

/**
 * 发送消息
 * 处理用户输入的消息，发送到后端并显示AI回复
 */
const sendMessage = async () => {
  const text = inputMessage.value.trim()
  
  // 验证输入和状态
  if (!text || sending.value) return
  
  // 清空输入框
  inputMessage.value = ''
  
  // 确保有当前会话，没有则创建
  if (!currentConversation.value) {
    createNewConversation()
  }
  
  // 添加用户消息到会话
  conversationsStore.appendMessage(currentConversation.value!.id, { 
    role: 'user', 
    content: text 
  })
  
  // 滚动到底部显示用户消息
  await scrollToBottom()
  
  // 发送消息给AI
  await sendMessageToAI(text)
}

/**
 * 处理删除会话操作
 * 显示确认对话框，确认后删除当前会话并创建新会话
 */
const handleDeleteConversation = () => {
  if (!currentConversation.value) return
  
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除会话"${currentConversation.value.title || '未命名会话'}"吗？此操作不可撤销。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      deleting.value = true
      try {
        const deletedId = currentConversation.value!.id
        const deletedTitle = currentConversation.value!.title || '未命名会话'
        console.log('准备删除会话:', deletedId, deletedTitle)
        
        // 从本地store删除会话（纯本地实现，不调用后端API）
        conversationsStore.deleteConversation(deletedId)
        
        console.log('会话删除完成，当前会话列表:', conversationsStore.conversations)
        message.success(`会话"${deletedTitle}"已删除`)
        
        // 检查是否还有其他会话
        if (conversationsStore.conversations.length > 0) {
          // 如果有其他会话，跳转到第一个会话
          const firstConversation = conversationsStore.conversations[0]
          router.push(`/chat/${firstConversation.id}`)
        } else {
          // 如果没有其他会话了，跳转到首页让用户选择
          router.push('/')
        }
      } catch (error) {
        message.error('删除会话失败，请稍后再试')
        console.error('Delete conversation error:', error)
      } finally {
        deleting.value = false
      }
    }
  })
}
</script>

<style scoped>
/* 背景容器：铺满内容区，负责居中内部固定宽度聊天卡片 */
.chat-bg {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: stretch;
  justify-content: center;
}

/* 居中容器：提供内边距与水平居中承载聊天布局 */
.chat-fixed {
  flex: 1;
  display: flex;
  align-items: stretch;
  justify-content: center;
  padding: 24px;
}

/* 聊天主卡片：目标宽度约 60%（含最小/最大宽度），高度跟随内容区 100% */
.chat-layout {
  width: min(60%, 980px);
  min-width: 640px;
  max-width: 980px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
}

/* 小屏策略：当空间不足时允许卡片压缩到更小宽度 */
@media (max-width: 720px) {
  .chat-layout {
    width: 100%;
    min-width: 360px;
  }
}

/* 顶部栏：固定 56px 高度，白色背景与底部分隔线 */
.chat-header {
  background: white;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  padding: 0 16px;
  height: 56px;
}

/* 顶部标题：字号/颜色/加粗 */
.chat-title {
  margin: 0;
  color: #333;
  font-size: 18px;
  font-weight: 600;
}

.header-left { flex: 1; min-width: 0; }
.header-right { 
  display: flex; 
  gap: 8px; 
  align-items: center;
}

.history-bar {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
}
.history-item {
  padding: 6px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  font-size: 12px;
  color: #555;
  cursor: pointer;
}
.history-item.active { background: #e3f2fd; border-color: #2196f3; color: #1a1a1a; }

/* 消息列表：可滚动区域，撑满除头尾外的剩余高度 */
.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background-color: #f9f9f9;
}

/* 单条消息容器：最大宽度、圆角、内边距与布局 */
.message {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 18px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

/* 用户消息：靠右显示，头像在右侧 */
.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

/* AI 消息：靠左显示 */
.message.ai {
  align-self: flex-start;
}

/* 头像：尺寸、圆形、居中对齐与顶部微调 */
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 4px;
}

/* AI 头像：紫色渐变背景与白色图标 */
.ai-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

/* 用户头像：浅蓝背景与主色图标 */
.user-avatar {
  background: #e0efff;
  color: #165dff;
}

/* 消息文本：行高与换行策略 */
.message-content {
  line-height: 1.6;
  word-wrap: break-word;
  padding: 8px 0;
}

/* AI 气泡：白底轻阴影 */
.message.ai {
  background: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

/* 用户气泡：紫色渐变与白色文字 */
.message.user {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
}

/* 输入区：底部工具栏容器 */
.chat-input {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  padding: 16px 24px;
  background: white;
  border-top: 1px solid #f0f0f0;
}

/* 文本域：占满剩余空间，支持自适应高度 */
.message-input {
  flex: 1;
}

/* 发送按钮：避免换行 */
.send-btn {
  white-space: nowrap;
}
</style>