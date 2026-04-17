<template>
  <div class="code-agent-container">
    <!-- 主要内容区域 -->
    <div class="content-grid">
      <!-- 左侧：对话列表 -->
      <div class="conversation-list-section">
        <a-card :loading="loadingConversations" class="list-card">
          <template #title>
            <div class="card-title-row">
              <span>{{ t('views_CodeAgentView.conversationList') }}</span>
              <a-button type="primary" size="small" @click="showNewConversationModal">
                <template #icon>
                  <PlusOutlined />
                </template>
                {{ t('views_CodeAgentView.newSession') }}
              </a-button>
            </div>
          </template>

          <!-- 搜索框 -->
          <a-input-search
            v-model:value="searchKeyword"
            :placeholder="t('views_CodeAgentView.searchPlaceholder')"
            allow-clear
            class="search-input"
            @search="handleSearch"
          />

          <!-- 对话列表 -->
          <div class="conversation-list">
            <div
              v-for="conversation in filteredConversations"
              :key="conversation.conversation_id"
              class="conversation-item"
              :class="{ active: selectedConversationId === conversation.conversation_id }"
              @click="selectConversation(conversation)"
            >
              <div class="conversation-header">
                <span class="patient-name">
                  {{ conversation.title || '未命名会话' }}
                </span>
                <span class="conversation-time">{{ formatTime(conversation.updated_at) }}</span>
              </div>
              <p class="conversation-preview">{{ conversation.last_message || '暂无消息' }}</p>
              <a-button
                type="text"
                size="small"
                danger
                class="delete-btn"
                @click.stop="handleDeleteConversation(conversation.conversation_id)"
              >
                <DeleteOutlined />
              </a-button>
            </div>
          </div>

          <!-- 空状态 -->
          <a-empty
            v-if="filteredConversations.length === 0 && !loadingConversations"
            :description="t('views_CodeAgentView.noConversations')"
            class="empty-state"
          />
        </a-card>
      </div>

      <!-- 右侧：对话详情 -->
      <div class="conversation-detail-section">
        <a-card v-if="selectedConversation" class="detail-card">


          <!-- 对话内容区域 -->
          <div class="messages-container" ref="messagesContainer">
            <!-- 事件显示区域 -->
            <div v-if="eventDisplay" class="event-display" :class="`event-${eventDisplay.type}`">
              <LoadingOutlined v-if="eventDisplay.type === 'loading'" class="event-icon" />
              <CheckCircleOutlined v-else-if="eventDisplay.type === 'success'" class="event-icon" />
              <InfoCircleOutlined v-else class="event-icon" />
              <span class="event-message">{{ eventDisplay.message }}</span>
            </div>

            <div
              v-for="message in messages"
              :key="message.message_id"
              class="message-wrapper"
              :class="message.role === 'user' ? 'message-right' : 'message-left'"
            >
              <div class="message-header">
                <span class="message-sender">
                  {{ message.role === 'user' ? t('views_CodeAgentView.patient') : t('views_CodeAgentView.aiAssistant') }}
                </span>
                <span class="message-time">{{ formatTime(message.created_at) }}</span>
              </div>
              <div class="message-bubble" :class="message.role === 'user' ? 'bubble-patient' : 'bubble-ai'">
                <!-- 加载状态：仅在内容为空且loading=true时显示 -->
                <div v-if="message.loading && !message.content" class="loading-wrapper">
                  <div class="loading-dots">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                  </div>
                  <span class="loading-text">{{ t('views_CodeAgentView.loading') }}</span>
                </div>
                <!-- AI 消息：使用流式渲染，内容不为空时显示 -->
                <StreamingMarkdownRenderer v-else-if="message.role === 'assistant' && message.content" :content="message.content" :streaming="message.loading" :streaming-speed="15" class="message-markdown" />
                <!-- 用户消息和其他文本消息 -->
                <p v-else class="message-text">{{ message.content }}</p>
              </div>
            </div>
            <!-- 滚动锚点 -->
            <div ref="messagesEndRef" style="height: 1px;" />
          </div>

          <!-- 输入区域 -->
          <div class="input-area">
            <div class="input-row">
              <a-input
                v-model:value="inputMessage"
                :placeholder="t('views_CodeAgentView.inputPlaceholder')"
                allow-clear
                class="message-input"
                @press-enter="handleSendMessage"
                :disabled="sendingMessage"
              />
              <a-button type="primary" @click="handleSendMessage" :loading="sendingMessage">
                <template #icon>
                  <SendOutlined />
                </template>
                {{ t('views_CodeAgentView.send') }}
              </a-button>
            </div>
          </div>
        </a-card>

        <!-- 空状态 -->
        <a-empty
          v-else-if="!loadingConversations"
          :description="t('views_CodeAgentView.selectConversation')"
          class="empty-state"
        />
      </div>
    </div>

    <!-- 新建会话模态框 -->
    <a-modal
      v-model:open="newConversationModalVisible"
      :title="t('views_CodeAgentView.newSession')"
      @ok="handleCreateConversation"
      :confirm-loading="creatingConversation"
    >
      <a-form :model="newConversationForm" layout="vertical">
        <a-form-item :label="t('views_CodeAgentView.sessionTitle')">
          <a-input
            v-model:value="newConversationForm.title"
            :placeholder="t('views_CodeAgentView.sessionTitlePlaceholder')"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  SendOutlined,
  DeleteOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined
} from '@ant-design/icons-vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import StreamingMarkdownRenderer from '@/components/StreamingMarkdownRenderer.vue'
import type {
  ChatMessage,
  ConversationInfo,
  MessageResponse,
  CreateConversationRequest,
  StreamResponseData,
  QwenEventType
} from '@/apis/codeAgent'
import {
  streamChat,
  parseStreamResponse,
  getConversations,
  getConversationDetail,
  createConversation,
  deleteConversation
} from '@/apis/codeAgent'

const { t } = useI18n()

// 搜索关键词
const searchKeyword = ref('')

// 输入消息
const inputMessage = ref('')

// 发送消息加载状态
const sendingMessage = ref(false)

// 对话列表加载状态
const loadingConversations = ref(false)

// 创建会话加载状态
const creatingConversation = ref(false)

// 对话列表数据
const conversations = ref<ConversationInfo[]>([])

// 当前选中的会话ID
const selectedConversationId = ref<string | null>(null)

// 当前选中的会话信息
const selectedConversation = ref<ConversationInfo | null>(null)

// 会话消息列表
const messages = ref<MessageResponse[]>([])

// 加载会话详情状态（防止重复调用）
const loadingConversationDetail = ref(false)

// 用于取消上次请求的 AbortController
let currentAbortController: AbortController | null = null

// 消息容器引用
const messagesContainer = ref<HTMLElement | null>(null)
const messagesEndRef = ref<HTMLElement | null>(null)

// 当前流式事件状态
const currentEventType = ref<string>('')
const eventDisplay = ref<{ message: string; type: 'info' | 'success' | 'loading' } | null>(null)

// 新建会话模态框显示状态
const newConversationModalVisible = ref(false)

// 新建会话表单
const newConversationForm = ref<CreateConversationRequest>({
  title: undefined
})

// 过滤后的对话列表
const filteredConversations = computed(() => {
  if (!searchKeyword.value) {
    return conversations.value
  }
  const keyword = searchKeyword.value.toLowerCase()
  return conversations.value.filter(
    conv =>
      (conv.title && conv.title.toLowerCase().includes(keyword)) ||
      (conv.last_message && conv.last_message.toLowerCase().includes(keyword))
  )
})

// 加载对话列表
const loadConversations = async () => {
  // 防止重复调用
  if (loadingConversations.value) {
    console.log('对话列表正在加载中，跳过此次调用')
    return
  }
  loadingConversations.value = true
  try {
    const response = await getConversations()
    if (response.code === 200 && response.data) {
      conversations.value = response.data
    } else {
      message.error(response.message || '加载对话列表失败')
    }
  } catch (error) {
    console.error('加载对话列表失败:', error)
    message.error('加载对话列表失败')
  } finally {
    loadingConversations.value = false
  }
}

// 选择对话
const selectConversation = async (conversation: ConversationInfo) => {
  // 取消之前的请求
  if (currentAbortController) {
    currentAbortController.abort()
    currentAbortController = null
  }

  // 如果点击的是当前已选中的会话，不重复加载
  if (selectedConversationId.value === conversation.conversation_id) {
    return
  }

  // 立即清理 ResizeObserver，避免它在清空消息时触发滚动
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  // 创建新的 AbortController
  currentAbortController = new AbortController()

  selectedConversationId.value = conversation.conversation_id
  selectedConversation.value = conversation

  // 先清空消息列表
  messages.value = []
  await nextTick()
  // 立即重置滚动位置到顶部，避免旧滚动位置的影响
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = 0
  }

  loadingConversationDetail.value = true

  // 加载会话详情和消息
  try {
    const response = await getConversationDetail(conversation.conversation_id, currentAbortController.signal)
    if (response.code === 200 && response.data) {
      messages.value = response.data.messages || []
      // 等待消息渲染完成后再滚动到底部
      await nextTick()
      scrollToBottom()
    } else {
      message.error(response.message || '加载会话详情失败')
    }
  } catch (error: any) {
    // 忽略被取消的请求错误
    if (error.name === 'AbortError' || error.name === 'CanceledError') {
      console.log('会话详情请求被取消')
      return
    }
    console.error('加载会话详情失败:', error)
    message.error('加载会话详情失败')
  } finally {
    loadingConversationDetail.value = false
    currentAbortController = null
  }
}

// 滚动到顶部
const scrollToTop = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = 0
  }
}

// 搜索
const handleSearch = () => {
  // 搜索由computed自动处理
}

// 显示新建会话模态框
const showNewConversationModal = () => {
  newConversationModalVisible.value = true
  // 重置表单
  newConversationForm.value = {
    title: undefined
  }
}

// 创建新会话
const handleCreateConversation = async () => {
  if (!newConversationForm.value.title || !newConversationForm.value.title.trim()) {
    message.warning('请填写会话标题')
    return
  }

  creatingConversation.value = true
  try {
    const response = await createConversation(newConversationForm.value)
    if (response.code === 200 && response.data) {
      message.success('创建会话成功')
      newConversationModalVisible.value = false
      // 重新加载对话列表
      await loadConversations()
      // 自动选中新创建的会话
      await selectConversation(response.data)
    } else {
      message.error(response.message || '创建会话失败')
    }
  } catch (error) {
    console.error('创建会话失败:', error)
    message.error('创建会话失败')
  } finally {
    creatingConversation.value = false
  }
}

// 删除会话
const handleDeleteConversation = async (conversationId: string) => {
  try {
    const response = await deleteConversation(conversationId)
    if (response.code === 200 && response.data) {
      message.success('删除会话成功')
      // 如果删除的是当前选中的会话，清空选中状态
      if (selectedConversationId.value === conversationId) {
        selectedConversationId.value = null
        selectedConversation.value = null
        messages.value = []
      }
      // 重新加载对话列表
      await loadConversations()
    } else {
      message.error(response.message || '删除会话失败')
    }
  } catch (error) {
    console.error('删除会话失败:', error)
    message.error('删除会话失败')
  }
}

// 发送消息
const handleSendMessage = async () => {
  if (!inputMessage.value.trim() || !selectedConversation.value || sendingMessage.value) {
    return
  }

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  sendingMessage.value = true

  // 重置事件显示
  eventDisplay.value = null
  currentEventType.value = ''

  // 添加用户消息到对话中
  const userMsg: MessageResponse = {
    message_id: '',
    conversation_id: selectedConversation.value!.conversation_id,
    role: 'user',
    content: userMessage,
    created_at: new Date().toISOString()
  }
  messages.value.push(userMsg)
  scrollToBottom()

  // 准备请求数据：将历史消息转换为 API 格式（排除刚添加的用户消息）
  const historyMessages: ChatMessage[] = messages.value
    .slice(0, -1) // 排除刚添加的用户消息
    .filter(msg => msg.content) // 只保留有内容的消息
    .map(msg => ({
      role: msg.role,
      content: msg.content || ''
    }))

  try {
    // 添加 AI 消息占位符，标记为加载中
    const aiMsgIndex = messages.value.length
    const currentConversationId = selectedConversation.value!.conversation_id
    messages.value.push({
      message_id: '',
      conversation_id: currentConversationId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      loading: true
    })
    scrollToBottom()

    // 调用流式接口
    const stream = await streamChat({
      conversation_id: currentConversationId,
      messages: historyMessages,
      message: userMessage
    })

    if (!stream) {
      throw new Error('无法建立流式连接')
    }

    const reader = stream.getReader()

    // 定义事件处理器
    const handleEvent = (event: QwenEventType) => {
      currentEventType.value = event.type

      switch (event.type) {
        case 'system':
          // 系统初始化事件
          eventDisplay.value = {
            message: `系统已初始化 - 模型: ${event.model}, 版本: ${event.qwen_code_version}`,
            type: 'info'
          }
          break
        case 'stream_event':
          // 流式事件
          const streamEvent = event as any
          if (streamEvent.event) {
            const innerEvent = streamEvent.event
            if (innerEvent.type === 'message_start') {
              eventDisplay.value = {
                message: '开始生成回复...',
                type: 'loading'
              }
            } else if (innerEvent.type === 'message_stop') {
              eventDisplay.value = {
                message: '回复生成完成',
                type: 'success'
              }
            }
          }
          break
        case 'assistant':
          // 助手消息完成
          eventDisplay.value = {
            message: '助手消息已接收',
            type: 'success'
          }
          break
        case 'result':
          // 最终结果
          const resultEvent = event as any
          if (resultEvent.subtype === 'success') {
            eventDisplay.value = {
              message: `处理完成 - 耗时: ${resultEvent.duration_ms}ms, 使用: ${resultEvent.usage.total_tokens} tokens`,
              type: 'success'
            }
          }
          break
      }
    }

    await parseStreamResponse(
      reader,
      // onChunk: 接收到每个 chunk
      (data) => {
        // 检查是否还在当前的对话中
        if (messages.value[aiMsgIndex] && messages.value[aiMsgIndex].conversation_id === currentConversationId) {
          // 关键：每次更新内容和 loading 状态
          messages.value[aiMsgIndex].content = data.full_content
          messages.value[aiMsgIndex].loading = true
          // 使用 nextTick 确保 DOM 更新完成后再滚动
          nextTick(() => {
            scrollToBottom()
          })
        }
      },
      // onComplete: 完成
      (finalContent) => {
        // 检查是否还在当前的对话中
        if (messages.value[aiMsgIndex] && messages.value[aiMsgIndex].conversation_id === currentConversationId) {
          messages.value[aiMsgIndex].content = finalContent
          messages.value[aiMsgIndex].loading = false  // ✅ 标记流式输出结束
        }
        // 更新会话的最后消息
        if (selectedConversation.value && selectedConversation.value.conversation_id === currentConversationId) {
          selectedConversation.value.last_message = finalContent
        }
        // 清除事件显示
        setTimeout(() => {
          eventDisplay.value = null
          currentEventType.value = ''
        }, 3000)
        nextTick(() => {
          scrollToBottom()
        })
      },
      // onError: 错误处理
      (error) => {
        console.error('流式对话错误:', error)
        // 检查是否还在当前的对话中
        if (messages.value[aiMsgIndex] && messages.value[aiMsgIndex].conversation_id === currentConversationId) {
          messages.value[aiMsgIndex].content = `错误: ${error}`
          messages.value[aiMsgIndex].loading = false
        }
        eventDisplay.value = {
          message: `错误: ${error}`,
          type: 'info'
        }
      },
      // onEvent: 事件处理
      handleEvent
    )
  } catch (error) {
    console.error('发送消息失败', error)
    message.error('发送消息失败，请重试')
    // 移除失败的AI消息
    const aiMsgIndex = messages.value.length - 1
    if (messages.value[aiMsgIndex]) {
      messages.value[aiMsgIndex].loading = false
    }
  } finally {
    sendingMessage.value = false
  }
}

// 滚动到底部
let resizeObserver: ResizeObserver | null = null
const scrollToBottom = async () => {
  await nextTick()
  if (!messagesEndRef.value || !messagesContainer.value) return

  // 直接滚动到底部，不使用 ResizeObserver 以避免抖动
  messagesEndRef.value?.scrollIntoView({ behavior: 'instant', block: 'end' })
}

// 格式化时间
const formatTime = (time: string | undefined) => {
  if (!time) return ''
  const date = new Date(time)
  return date.toLocaleString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    month: '2-digit',
    day: '2-digit'
  })
}

// 组件挂载时加载对话列表
onMounted(() => {
  loadConversations()
})

// 组件卸载时清理资源
onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})
</script>

<style scoped>
/* ==========================================
   1. 整体页面布局
========================================== */
.code-agent-container {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  box-sizing: border-box;
  overflow: hidden;
}

.page-header {
  flex-shrink: 0;
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.content-grid {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 24px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  align-items: stretch;
}

/* ==========================================
   2. 左侧：对话列表区域
========================================== */
.conversation-list-section {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  contain: layout;
}

.list-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

/* 穿透 Ant Design Card 内部，打通 Flex 布局 */
:deep(.list-card > .ant-card-head) {
  border-bottom: 1px solid #e8e8e8;
  background: #fafbfc;
  border-radius: 8px 8px 0 0;
}

/* 穿透 Ant Design Card 内部，打通 Flex 布局 */
:deep(.list-card > .ant-card-body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 16px;
}

.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.search-input {
  margin-bottom: 16px;
  width: 100%;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
  padding: 4px;
  scrollbar-gutter: stable;
}

.conversation-item {
  padding: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  flex-shrink: 0;
  min-width: 0;
  background: #fff;
}

.conversation-item:hover {
  background-color: #f9f9f9;
  border-color: #40a9ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.15);
}

.conversation-item.active {
  background: linear-gradient(135deg, #e6f7ff 0%, #f0f5ff 100%);
  border-color: #1890ff;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.25);
}

.conversation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
  gap: 8px;
  min-width: 0;
  width: 100%;
}

.patient-name {
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
  flex: 1;
  min-width: 0;
}

.conversation-time {
  font-size: 12px;
  color: #999;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 80px;
}

.conversation-preview {
  font-size: 14px;
  color: #666;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-clamp: 2;
  padding-right: 30px;
  width: 80%;
  max-width: 80%;
  line-height: 1.4;
  min-height: 28px;
}

.delete-btn {
  position: absolute;
  top: 50%;
  right: 8px;
  transform: translateY(-50%);
  opacity: 0;
  transition: opacity 0.3s;
}

.conversation-item:hover .delete-btn {
  opacity: 1;
}

/* ==========================================
   3. 右侧：对话详情区域
========================================== */
.conversation-detail-section {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  contain: layout;
}

.detail-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  contain: layout;
}

:deep(.detail-card > .ant-card-body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

.patient-info {
  display: none;
}

/* ==========================================
   4. 右侧：聊天气泡与消息区
========================================== */
/* 消息容器 - 优化滚动和更新性能 */
.messages-container {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: #f9f9fb;
  padding: 16px;
  margin-top: 16px;
  min-height: 0;
  scrollbar-gutter: stable;
  overflow-anchor: none;
  /* 优化流式输出的性能和流畅性 */
  contain: layout;
  will-change: scroll-position;
  scroll-behavior: smooth;
}

.event-display {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  animation: fadeIn 0.3s ease-in;
  max-width: 80%;
}

.event-info {
  background: #e6f7ff;
  border: 1px solid #91d5ff;
  color: #0050b3;
}

.event-success {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  color: #389e0d;
}

.event-loading {
  background: #fffbe6;
  border: 1px solid #ffe58f;
  color: #d48806;
}

.event-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.event-message {
  word-break: break-word;
  line-height: 1.5;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-wrapper {
  display: flex;
  flex-direction: column;
  max-width: 70%;
  flex-shrink: 0;
  margin-bottom: 4px;
}

.message-left { align-self: flex-start; }
.message-right { align-self: flex-end; }

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
}
.message-left .message-header { flex-direction: row; }
.message-right .message-header { flex-direction: row-reverse; }

.message-sender { 
  font-weight: 600; 
  color: #1890ff;
  font-size: 13px;
}
.message-right .message-sender {
  color: #0050b3;
}
.message-time { color: #999; flex-shrink: 0; }

.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;
  max-width: 100%;
  transition: all 0.2s ease;
  min-height: 24px;
}

.bubble-patient {
  background: linear-gradient(135deg, #1890ff 0%, #0050b3 100%);
  color: #fff;
  border: none;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
}

.bubble-ai {
  background-color: #fff;
  border: 1px solid #e8e8e8;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.message-text {
  margin: 0;
  color: #333;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message-right .message-text {
  color: #fff;
}

/* Markdown 渲染样式 */
.message-markdown {
  line-height: 1.6;
}

.message-markdown :deep(h1),
.message-markdown :deep(h2),
.message-markdown :deep(h3),
.message-markdown :deep(h4),
.message-markdown :deep(h5),
.message-markdown :deep(h6) {
  margin: 12px 0 6px 0;
  font-weight: 600;
  color: #1a1a1a;
}

.message-markdown :deep(h1) { font-size: 1.3em; }
.message-markdown :deep(h2) { font-size: 1.2em; }
.message-markdown :deep(h3) { font-size: 1.1em; }

.message-markdown :deep(p) {
  margin: 6px 0;
}

.message-markdown :deep(ul),
.message-markdown :deep(ol) {
  margin: 6px 0;
  padding-left: 20px;
}

.message-markdown :deep(li) {
  margin: 3px 0;
}

.message-markdown :deep(pre) {
  background: #f6f8fa;
  border: 1px solid #e1e4e8;
  border-radius: 4px;
  padding: 10px 12px;
  margin: 8px 0;
  overflow-x: auto;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.45;
}

.message-markdown :deep(code) {
  background: #f6f8fa;
  border-radius: 3px;
  padding: 1px 4px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
}

.message-markdown :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
}

.message-markdown :deep(blockquote) {
  border-left: 3px solid #dfe2e5;
  padding-left: 12px;
  margin: 8px 0;
  color: #6a737d;
  font-style: italic;
}

.message-markdown :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
  font-size: 13px;
}

.message-markdown :deep(th),
.message-markdown :deep(td) {
  border: 1px solid #dfe2e5;
  padding: 6px 10px;
  text-align: left;
}

.message-markdown :deep(th) {
  background: #f6f8fa;
  font-weight: 600;
}

.message-markdown :deep(a) {
  color: #0366d6;
  text-decoration: none;
}

.message-markdown :deep(a:hover) {
  text-decoration: underline;
}

.message-markdown :deep(strong) {
  font-weight: 600;
}

.message-markdown :deep(em) {
  font-style: italic;
}

@keyframes dot-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.7;
  }
  30% {
    transform: translateY(-8px);
    opacity: 1;
  }
}

.loading-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 24px;
  padding: 4px 0;
}

.loading-dots {
  display: flex;
  gap: 4px;
  align-items: center;
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1890ff 0%, #0050b3 100%);
  animation: dot-bounce 1.4s infinite;
}

.dot:nth-child(1) {
  animation-delay: 0s;
}

.dot:nth-child(2) {
  animation-delay: 0.2s;
}

.dot:nth-child(3) {
  animation-delay: 0.4s;
}

.loading-text {
  color: #666;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

/* ==========================================
   5. 右侧：输入框与通用状态
========================================== */
.input-area {
  flex-shrink: 0;
  border-top: 1px solid #e8e8e8;
  padding: 16px;
  background: linear-gradient(to bottom, #fafbfc, #fff);
  margin-top: 16px;
}

.input-row {
  display: flex;
  gap: 12px;
}

.message-input { 
  flex: 1;
}

:deep(.message-input .ant-input:focus) {
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.15) !important;
}
.input-actions { display: flex; gap: 16px; }

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  contain: layout;
}

/* ==========================================
   6. 滚动条美化
========================================== */
.messages-container::-webkit-scrollbar,
.conversation-list::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.messages-container::-webkit-scrollbar-track,
.conversation-list::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}
.messages-container::-webkit-scrollbar-thumb,
.conversation-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}
.messages-container::-webkit-scrollbar-thumb:hover,
.conversation-list::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
.messages-container,
.conversation-list {
  scrollbar-width: thin;
  scrollbar-color: #c1c1c1 #f1f1f1;
}

/* ==========================================
   7. 响应式适配
========================================== */
@media (max-width: 1400px) {
  .code-agent-container { padding: 20px; }
  .content-grid { gap: 20px; }
}

@media (max-width: 1200px) {
  .code-agent-container { padding: 16px; }
  .content-grid { gap: 16px; }
  .message-wrapper { max-width: 85%; }
}

@media (max-width: 768px) {
  .code-agent-container { padding: 12px; }
  .page-header { margin-bottom: 12px; }
  .page-title { font-size: 20px; }
  .content-grid {
    gap: 12px;
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }
  .conversation-item { padding: 10px; }
  .message-wrapper { max-width: 95%; }
  .message-bubble { padding: 12px 16px; }
}

@media (max-width: 480px) {
  .code-agent-container { padding: 8px; }
  .page-title { font-size: 18px; }
  .content-grid { gap: 8px; }
  .search-input { margin-bottom: 12px; }
  .card-title-row .ant-btn { padding: 4px 8px; font-size: 12px; }
  .message-wrapper { max-width: 100%; }
  .message-bubble { padding: 8px 12px; }
  .input-row { gap: 6px; }
  .input-actions { gap: 8px; }
}
</style>
