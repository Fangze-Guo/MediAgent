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
            <div class="message-content">
              <!-- 解析并展示思考过程和回复内容 -->
              <div v-if="m.parsedContent">
                <!-- 多个思考过程 -->
                <div v-if="m.parsedContent.thinkingList && m.parsedContent.thinkingList.length > 0">
                  <div 
                    v-for="(thinking, thinkingIdx) in m.parsedContent.thinkingList" 
                    :key="thinkingIdx"
                    class="thinking-section"
                  >
                    <div class="thinking-header">
                      <a-icon type="bulb" />
                      <span>思考过程 {{ m.parsedContent.thinkingList.length > 1 ? thinkingIdx + 1 : '' }}</span>
                      <a-button 
                        type="text" 
                        size="small" 
                        @click="toggleThinking(idx, thinkingIdx)"
                        class="toggle-thinking-btn"
                      >
                        {{ m.showThinkingList && m.showThinkingList[thinkingIdx] ? '收起' : '展开' }}
                      </a-button>
                    </div>
                    <div v-show="m.showThinkingList && m.showThinkingList[thinkingIdx]" class="thinking-content">
                      {{ thinking }}
                    </div>
                  </div>
                </div>
                <!-- 回复内容 -->
                <div v-if="m.parsedContent.response" class="response-content">
                  {{ m.parsedContent.response }}
                </div>
              </div>
              <!-- 原始内容（如果没有解析出思考过程） -->
              <div v-else>{{ m.content }}</div>
            </div>
            <div v-if="m.role === 'user'" class="avatar user-avatar">
              <a-icon type="user" />
            </div>
          </div>
        </a-layout-content>
        <a-layout-footer class="chat-input">
          <!-- 文件上传区域 -->
          <div v-if="showFileUpload" class="file-upload-section">
            <a-button 
              type="text" 
              size="small"
              @click="showFileUpload = false"
              class="close-upload-btn"
            >
              <CloseOutlined />
            </a-button>
            <FileUpload 
              @upload-success="handleFileUploadSuccess"
              @upload-error="handleFileUploadError"
              @use-file="handleUseFile"
            />

          </div>
          
          <!-- 输入区域 -->
          <div class="input-section">
            <a-textarea 
              v-model:value="inputMessage"
              class="message-input"
              placeholder="输入消息，按 Enter 换行"
              :auto-size="{ minRows: 1, maxRows: 6 }"
            />
            <div class="input-actions">
              <a-button 
                type="text" 
                class="upload-btn"
                @click="showFileUpload = !showFileUpload"
                :title="showFileUpload ? '隐藏文件上传' : '上传文件'"
              >
                <PlusOutlined v-if="!showFileUpload" />
                <CloseOutlined v-else />
              </a-button>
              <a-button 
                type="primary" 
                class="send-btn"
                :loading="sending"
                @click="sendMessage"
              >
                发送
              </a-button>
            </div>
          </div>
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
import { chatStream } from '@/apis/chat'
import { useConversationsStore } from '@/store/conversations'
import FileUpload from '@/components/FileUpload.vue'
import { type FileUploadResponse } from '@/apis/files'
import { PlusOutlined, CloseOutlined } from '@ant-design/icons-vue'

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
/** 是否显示文件上传区域 */
const showFileUpload = ref(false)
/** 已上传的文件列表 */
const uploadedFiles = ref<FileUploadResponse['file'][]>([])
/** 当前会话关联的文件信息 */
const currentSessionFiles = ref<FileUploadResponse['file'][]>([])

/**
 * 解析消息内容，提取思考过程和回复内容
 * @param content 原始消息内容
 * @returns 解析后的内容对象
 */
const parseMessageContent = (content: string) => {
  // 匹配所有<think>标签
  const thinkMatches = content.match(/<think>(.*?)<\/think>/gs)
  if (thinkMatches && thinkMatches.length > 0) {
    const thinkingList = thinkMatches.map(match => {
      const thinkContent = match.replace(/<\/?think>/g, '').trim()
      return thinkContent
    })
    
    // 移除所有<think>标签，获取回复内容
    const response = content.replace(/<think>.*?<\/think>/gs, '').trim()
    
    return {
      thinkingList, // 改为数组，支持多个思考过程
      response: response || null
    }
  }
  return null
}

/**
 * 切换思考过程的显示/隐藏
 * @param messageIndex 消息索引
 * @param thinkingIndex 思考过程索引（可选，用于多个思考过程）
 */
const toggleThinking = (messageIndex: number, thinkingIndex?: number) => {
  const messageKey = `${activeId.value}-${messageIndex}`
  if (thinkingIndex !== undefined) {
    // 多个思考过程的情况
    const thinkingKey = `${messageKey}-${thinkingIndex}`
    thinkingStates.value[thinkingKey] = !thinkingStates.value[thinkingKey]
  } else {
    // 单个思考过程的情况（向后兼容）
    thinkingStates.value[messageKey] = !thinkingStates.value[messageKey]
  }
}


/**
 * 滚动消息容器到底部
 * 在发送消息后自动滚动到最新消息
 */
const scrollToBottom = async () => {
  await nextTick()
  const el = messagesEl.value
  if (el) el.scrollTop = el.scrollHeight
}

/**
 * 处理文件上传成功
 * @param file 上传成功的文件信息
 */
const handleFileUploadSuccess = (file: FileUploadResponse['file']) => {
  uploadedFiles.value.push(file)
  console.log('文件上传成功:', file)
}

/**
 * 处理文件上传失败
 * @param error 错误信息
 */
const handleFileUploadError = (error: string) => {
  console.error('文件上传失败:', error)
}

/**
 * 使用文件
 * @param file 要使用的文件
 */
const handleUseFile = (file: FileUploadResponse['file']) => {
  // 将文件添加到当前会话的文件列表中
  currentSessionFiles.value.push(file)
  
  // 根据文件类型生成不同的提示信息
  let message = ''
  if (file.type.startsWith('image/')) {
    message = `我已经上传了图片文件 "${file.originalName}"，文件路径是：${file.path}。帮我调整图片大小，"将图片调整为800x600像素"，输出路径为./output/${file.originalName}。`
  } else if (file.type.includes('csv')) {
    message = `我已经上传了CSV文件 "${file.originalName}"，文件路径是：${file.path}。帮我分析这个文件，"生成这个CSV文件的摘要"，输出路径为./output/${file.originalName}。。`
  } else {
    message = `无法处理该文件`
  }
  
  // 将文件信息添加到输入消息中
  inputMessage.value = message
  showFileUpload.value = false
}


// 响应式数据
/** 思考过程显示状态 */
const thinkingStates = ref<Record<string, boolean>>({})

// 计算属性
/** 当前活跃的会话对象 */
const currentConversation = computed(() => conversationsStore.getConversation(activeId.value) || null)
/** 当前会话的消息列表，包含解析后的内容 */
const currentMessages = computed(() => {
  const messages = currentConversation.value?.messages || []
  return messages.map((msg, index) => {
    const messageKey = `${activeId.value}-${index}`
    const parsedContent = parseMessageContent(msg.content)
    
    // 为多个思考过程生成显示状态
    let showThinkingList = null
    if (parsedContent && parsedContent.thinkingList) {
      showThinkingList = parsedContent.thinkingList.map((_, thinkingIdx) => {
        const thinkingKey = `${messageKey}-${thinkingIdx}`
        return thinkingStates.value[thinkingKey] || false
      })
    }
    
    return {
      ...msg,
      parsedContent,
      showThinking: thinkingStates.value[messageKey] || false, // 保持向后兼容
      showThinkingList, // 新增：多个思考过程的显示状态
    }
  })
})

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
    // 切换会话时清空当前会话的文件列表
    currentSessionFiles.value = []
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
  
  // 创建AI消息占位符
  const aiMessage = { 
    role: 'assistant' as const, 
    content: '',
  }
  conversationsStore.appendMessage(currentConversation.value.id, aiMessage)
  
  try {
    // 使用流式聊天API，包含文件信息
    await chatStream({
      conversation_id: currentConversation.value.id,
      message: messageText,
      history: currentMessages.value.map(m => ({ 
        role: m.role, 
        content: m.content 
      })),
      files: currentSessionFiles.value // 添加文件信息
    }, {
      onStart: (conversationId) => {
        console.log('开始流式对话:', conversationId)
      },
      onContent: (content) => {
        // 逐步更新AI消息内容
        const conversation = conversationsStore.getConversation(currentConversation.value!.id)
        if (conversation && conversation.messages.length > 0) {
          const lastMessage = conversation.messages[conversation.messages.length - 1]
          if (lastMessage.role === 'assistant') {
            lastMessage.content += content
            // 实时滚动到底部
            scrollToBottom()
          }
        }
      },
      onToolCall: (tool) => {
        console.log('调用工具:', tool)
        // 可以在这里显示工具调用状态
      },
      onComplete: (toolCalls) => {
        console.log('对话完成，工具调用:', toolCalls)
        // 对话完成，移除打字机效果
        const conversation = conversationsStore.getConversation(currentConversation.value!.id)
        if (conversation && conversation.messages.length > 0) {
          const lastMessage = conversation.messages[conversation.messages.length - 1]
          if (lastMessage.role === 'assistant') {
          }
        }
        // 确保滚动到底部
        scrollToBottom()
      },
      onError: (error) => {
        console.error('流式聊天错误:', error)
        // 更新最后一条消息为错误信息
        const conversation = conversationsStore.getConversation(currentConversation.value!.id)
        if (conversation && conversation.messages.length > 0) {
          const lastMessage = conversation.messages[conversation.messages.length - 1]
          if (lastMessage.role === 'assistant') {
            lastMessage.content = `抱歉，请求失败：${error}`
          }
        }
        scrollToBottom()
      }
    })
  } catch (error) {
    // 处理错误，显示错误消息
    console.error('发送消息失败:', error)
    const conversation = conversationsStore.getConversation(currentConversation.value!.id)
    if (conversation && conversation.messages.length > 0) {
      const lastMessage = conversation.messages[conversation.messages.length - 1]
      if (lastMessage.role === 'assistant') {
        lastMessage.content = '抱歉，请求失败，请稍后再试。'
      }
    }
    await scrollToBottom()
  } finally {
    // 重置发送状态
    sending.value = false
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
  flex-direction: column;
  gap: 12px;
  padding: 16px 24px;
  background: white;
  border-top: 1px solid #f0f0f0;
}

/* 文件上传区域 */
.file-upload-section {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 16px;
  position: relative;
  max-height: 300px;
  overflow-y: auto;
  margin-bottom: 12px;
}

.close-upload-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.9);
  border: none;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transition: all 0.3s ease;
  color: #666;
}

.close-upload-btn:hover {
  background: rgba(255, 77, 79, 0.1);
  color: #ff4d4f;
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(255, 77, 79, 0.2);
}

/* 输入区域 */
.input-section {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

/* 输入操作按钮组 */
.input-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.upload-btn {
  color: #666;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-btn:hover {
  color: #1890ff;
  border-color: #1890ff;
}

/* 文本域：占满剩余空间，支持自适应高度 */
.message-input {
  flex: 1;
}

/* 发送按钮：避免换行 */
.send-btn {
  white-space: nowrap;
}

/* 思考过程样式 */
.thinking-section {
  margin-bottom: 12px;
  border: 1px solid #e8f4fd;
  border-radius: 8px;
  background: #f8fcff;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #e3f2fd;
  border-radius: 8px 8px 0 0;
  font-size: 12px;
  color: #1976d2;
  font-weight: 500;
}

.thinking-header .anticon {
  color: #ff9800;
}

.toggle-thinking-btn {
  margin-left: auto;
  font-size: 11px;
  padding: 2px 6px;
  height: auto;
  line-height: 1.2;
}

.thinking-content {
  padding: 12px;
  font-size: 13px;
  line-height: 1.5;
  color: #666;
  background: #fafafa;
  border-radius: 0 0 8px 8px;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.response-content {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
}


</style>