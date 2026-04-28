<template>
  <div class="code-agent-container">
    <!-- 主要内容区域 -->
    <div class="content-grid">
      <!-- 左侧：对话列表 -->
      <div class="conversation-list-section">
        <a-card :loading="loadingConversations" class="list-card">
          <template #title>
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
              <span>{{ t('views_CodeAgentView.conversationList') }}</span>
              <a-button type="primary" size="small" @click="startNewConversation">
                <PlusOutlined />
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
                <div class="header-actions">
                  <span class="conversation-time">{{ formatTime(conversation.updated_at) }}</span>
                  <a-button
                    type="text"
                    size="small"
                    danger
                    class="delete-btn"
                    @click.stop="showDeleteConfirm($event, conversation.conversation_id)"
                  >
                    <DeleteOutlined />
                  </a-button>
                </div>
              </div>
              <p v-if="conversation.last_message" class="conversation-preview">{{ conversation.last_message }}</p>
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
        <!-- 有选中会话时显示完整卡片 -->
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
              class="message-item"
              :class="message.event_type === 'todo' ? 'message-todo' : (message.event_type === 'skill_call' ? 'message-skill' : (message.role === 'user' ? 'message-user' : 'message-ai'))"
            >
              <!-- Skill Call 事件：橙色气泡 -->
              <template v-if="message.event_type === 'skill_call'">
                <div class="message-bubble bubble-skill">
                  <span class="skill-icon">🔧</span>
                  <span class="skill-name">{{ message.skill_name }}</span>
                  <span class="skill-label">skill call</span>
                </div>
                <div class="message-time">{{ formatTime(message.created_at) }}</div>
              </template>

              <!-- Todo 事件：紫色气泡，内嵌折叠任务列表 -->
              <template v-else-if="message.event_type === 'todo'">
                <div class="todo-bubble">
                  <div class="todo-header" @click="toggleTodoCollapse(message.message_id)">
                    <span class="todo-header-icon">{{ todoCollapsedStates[message.message_id] ? '+' : '-' }}</span>
                    <span class="todo-header-title">Update Todos</span>
                  </div>
                  <div v-if="!todoCollapsedStates[message.message_id]" class="todo-list">
                    <div
                      v-for="(todo, idx) in message.todo_list"
                      :key="idx"
                      class="todo-item"
                      :class="{ 'todo-done': todo.status === 'completed' }"
                    >
                      <span class="todo-checkbox">
                        {{ todo.status === 'completed' ? '✓' : '' }}
                      </span>
                      <span class="todo-text">{{ todo.activeForm || todo.content }}</span>
                    </div>
                  </div>
                </div>
                <div class="message-time">{{ formatTime(message.created_at) }}</div>
              </template>

              <!-- AI消息 -->
              <template v-else-if="message.role === 'assistant'">
                <!-- 思考内容块 -->
                <StreamingThinkingRenderer
                  v-if="message.thinking"
                  :content="message.thinking"
                  :streaming="message.loading"
                  :collapsed="true"
                  class="message-thinking"
                />
                <!-- 加载状态（无思考且无内容时显示） -->
                <div v-if="message.loading && !message.content && !message.thinking" class="loading-wrapper">
                  <div class="loading-dots">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                  </div>
                  <span class="loading-text">{{ t('views_CodeAgentView.loading') }}</span>
                </div>
                <!-- AI 消息内容：有内容时才显示白块 -->
                <div v-if="message.content" class="message-content">
                  <StreamingMarkdownRenderer
                    :content="message.content"
                    :streaming="message.loading"
                    :streaming-speed="15"
                    class="message-markdown"
                  />
                  <div v-if="!message.loading" class="message-time-inline">{{ formatTime(message.created_at) }}</div>
                </div>
              </template>

              <!-- 用户消息：蓝色气泡 -->
              <template v-else>
                <div class="message-bubble bubble-user">
                  <p class="message-text">{{ message.content }}</p>
                  <div class="message-time-inline">{{ formatTime(message.created_at) }}</div>
                </div>
              </template>
            </div>

            <!-- Plan 确认卡片 -->
            <div v-if="pendingPlan" class="plan-card">
              <div class="plan-content">{{ pendingPlan.content }}</div>
              <div class="plan-actions">
                <a-button
                  type="primary"
                  @click="confirmPlan"
                  :disabled="isPlanConfirmed || sendingMessage"
                >
                  {{ sendingMessage ? '执行中...' : (isPlanConfirmed ? '已确认' : '✅ 确认执行') }}
                </a-button>
                <a-button @click="cancelPlan">❌ 取消</a-button>
              </div>
            </div>

            <!-- 权限确认卡片 -->
            <div v-if="pendingPermission" class="permission-card">
              <div class="permission-header">
                <span class="permission-icon">🔐</span>
                <span class="permission-title">工具调用权限请求</span>
              </div>
              <div class="permission-content">
                <div class="permission-tool">
                  <span class="label">工具名称：</span>
                  <span class="value">{{ pendingPermission.toolName }}</span>
                </div>
                <div v-if="pendingPermission.input && Object.keys(pendingPermission.input).length > 0" class="permission-input">
                  <span class="label">参数：</span>
                  <pre class="input-json">{{ JSON.stringify(pendingPermission.input, null, 2) }}</pre>
                </div>
              </div>
              <div class="permission-actions">
                <a-button
                  type="primary"
                  @click="handleConfirmPermission"
                  :loading="confirmingPermission"
                >
                  ✅ 允许执行
                </a-button>
                <a-button
                  danger
                  @click="handleCancelPermission"
                  :disabled="confirmingPermission"
                >
                  ❌ 拒绝
                </a-button>
              </div>
            </div>
            <!-- 滚动锚点 -->
            <div ref="messagesEndRef" style="height: 1px;" />
          </div>

          <!-- 输入区域 -->
          <div class="input-area">
            <div class="input-container">
              <!-- 顶部工具栏 -->
              <div class="input-toolbar">
                <div class="toolbar-left">
                  <a-button type="text" size="small" class="toolbar-btn" :title="t('views_CodeAgentView.attachFile') || '附加文件'">
                    <PaperClipOutlined />
                  </a-button>
                  <a-button type="text" size="small" class="toolbar-btn" :title="t('views_CodeAgentView.insertCode') || '插入代码'">
                    <CodeOutlined />
                  </a-button>
                  <a-button type="text" size="small" class="toolbar-btn" :title="t('views_CodeAgentView.voiceInput') || '语音输入'">
                    <AudioOutlined />
                  </a-button>
                </div>
                <div class="toolbar-right">
                  <a-button type="text" size="small" class="toolbar-btn" @click="inputMessage = ''" :title="t('views_CodeAgentView.clearInput') || '清空输入'">
                    <DeleteOutlined />
                  </a-button>
                </div>
              </div>

              <!-- 输入框 -->
              <div class="input-field">
                <textarea
                  v-model="inputMessage"
                  class="message-textarea"
                  :placeholder="t('views_CodeAgentView.inputPlaceholder')"
                  @keydown="handleKeyDown"
                  @input="adjustTextareaHeight"
                  rows="1"
                  ref="textareaRef"
                  :disabled="sendingMessage"
                ></textarea>
              </div>

              <!-- 底部操作栏 -->
              <div class="input-bottom">
                <div class="input-hint">
                  <span class="hint-text">{{ t('views_CodeAgentView.inputHint') || 'Enter 发送，Shift+Enter 换行' }}</span>
                </div>
                <a-button
                  v-if="!sendingMessage"
                  type="primary"
                  @click="handleSendMessage"
                  :disabled="!inputMessage.trim()"
                  class="send-btn"
                >
                  <template #icon>
                    <SendOutlined />
                  </template>
                  {{ t('views_CodeAgentView.send') }}
                </a-button>
                <a-button
                  v-else
                  danger
                  @click="handleInterrupt"
                  class="send-btn"
                >
                  <template #icon>
                    <StopOutlined />
                  </template>
                  终止
                </a-button>
              </div>
            </div>
          </div>
        </a-card>

        <!-- 新建会话时显示输入区域（无会话详情） -->
        <a-card v-else class="detail-card">
          <div class="new-session-container">
            <div class="new-session-welcome">
              <div class="welcome-icon">
                <CodeOutlined />
              </div>
              <h2 class="welcome-title">{{ t('views_CodeAgentView.welcomeTitle') || 'Code 智能体' }}</h2>
              <p class="welcome-subtitle">{{ t('views_CodeAgentView.welcomeSubtitle') || '强大的代码助手，帮助您高效完成开发任务' }}</p>

              <div class="feature-cards">
                <div class="feature-card" @click="startNewConversation">
                  <div class="feature-icon">🩺</div>
                  <div class="feature-title">{{ t('views_CodeAgentView.featureMedical') || '医学咨询' }}</div>
                  <div class="feature-desc">{{ t('views_CodeAgentView.featureMedicalDesc') || '专业医学问题解答' }}</div>
                </div>
                <div class="feature-card" @click="startNewConversation">
                  <div class="feature-icon">📊</div>
                  <div class="feature-title">{{ t('views_CodeAgentView.featureData') || '数据导入' }}</div>
                  <div class="feature-desc">{{ t('views_CodeAgentView.featureDataDesc') || '导入并分析医学数据' }}</div>
                </div>
                <div class="feature-card" @click="startNewConversation">
                  <div class="feature-icon">🔬</div>
                  <div class="feature-title">{{ t('views_CodeAgentView.featureSkill') || '医学技能' }}</div>
                  <div class="feature-desc">{{ t('views_CodeAgentView.featureSkillDesc') || '调用专业医学工具' }}</div>
                </div>
              </div>
            </div>
          </div>
        </a-card>
      </div>

      <!-- 删除确认气泡框 -->
      <Teleport to="body">
        <div
          v-if="deleteConfirmVisible"
          class="delete-confirm-popover"
          :style="{
            position: 'fixed',
            left: deleteConfirmPosition.x + 'px',
            top: deleteConfirmPosition.y + 'px',
            transform: 'translate(-50%, -100%)'
          }"
          @click.stop
        >
          <div class="delete-confirm-content">
            <span class="delete-confirm-text">确定删除此会话？</span>
            <div class="delete-confirm-actions">
              <a-button size="small" @click="cancelDelete">取消</a-button>
              <a-button size="small" type="primary" danger @click="confirmDelete">删除</a-button>
            </div>
          </div>
          <div class="delete-confirm-arrow"></div>
        </div>
        <!-- 点击空白处关闭 -->
        <div
          v-if="deleteConfirmVisible"
          class="delete-confirm-overlay"
          @click="cancelDelete"
        ></div>
      </Teleport>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  SendOutlined,
  DeleteOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined,
  PaperClipOutlined,
  CodeOutlined,
  AudioOutlined,
  StopOutlined
} from '@ant-design/icons-vue'
import StreamingMarkdownRenderer from '@/components/markdown-renderer/StreamingMarkdownRenderer.vue'
import StreamingThinkingRenderer from '@/components/markdown-renderer/StreamingThinkingRenderer.vue'
import { useSessionStore } from '@/store/codeAgentSession'
import type {
  ChatMessage,
  ConversationInfo,
  MessageResponse,
  StreamResponseData,
  CodeEventType
} from '@/apis/codeAgent'
import {
  streamChat,
  parseStreamResponse,
  getConversations,
  getConversationDetail,
  createConversation,
  deleteConversation,
  updateConversation,
  confirmPermission,
  cancelPermission,
  interruptSession
} from '@/apis/codeAgent'

const { t } = useI18n()

// Session store for message management
const sessionStore = useSessionStore()

// 搜索关键词
const searchKeyword = ref('')

// 删除确认气泡框
const deleteConfirmVisible = ref(false)
const deleteConfirmConvId = ref<string | null>(null)
const deleteConfirmPosition = ref({ x: 0, y: 0 })

// 显示删除确认气泡框
const showDeleteConfirm = (event: MouseEvent, conversationId: string) => {
  event.stopPropagation()
  deleteConfirmConvId.value = conversationId
  deleteConfirmPosition.value = { x: event.clientX, y: event.clientY }
  deleteConfirmVisible.value = true
}

// 取消删除
const cancelDelete = () => {
  deleteConfirmVisible.value = false
  deleteConfirmConvId.value = null
}

// 确认删除
const confirmDelete = async () => {
  if (deleteConfirmConvId.value) {
    await handleDeleteConversation(deleteConfirmConvId.value)
  }
  cancelDelete()
}

// 输入消息
const inputMessage = ref('')

// textarea ref
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// 发送消息加载状态
const sendingMessage = ref(false)

// 对话列表加载状态
const loadingConversations = ref(false)

// 对话列表数据
const conversations = ref<ConversationInfo[]>([])

// 当前选中的会话ID
const selectedConversationId = ref<string | null>(null)

// 当前选中的会话信息
const selectedConversation = ref<ConversationInfo | null>(null)

// 会话消息列表
const messages = ref<MessageResponse[]>([])

// 当前活动的 session_id（用于中断）
const currentSessionId = ref<string | null>(null)

// Todo 折叠状态
const todoCollapsedStates = ref<Record<string, boolean>>({})

// 切换 Todo 折叠状态
const toggleTodoCollapse = (messageId: string) => {
  todoCollapsedStates.value[messageId] = !todoCollapsedStates.value[messageId]
}

// 默认在底部
const isAtBottom = ref(true)

// Plan 状态管理
const isPlanConfirmed = ref(false)  // 是否已确认
const hasPlanShown = ref(false)      // 是否已显示过 Plan（防抖）

// 权限确认状态管理
const pendingPermission = ref<{
  sessionId: string
  toolName: string
  input: Record<string, any>
  requestId: string
} | null>(null)
const confirmingPermission = ref(false)

const confirmPlan = () => {
  if (isPlanConfirmed.value) return  // 执行锁
  isPlanConfirmed.value = true

  if (pendingPlan.value) {
    inputMessage.value = '确认'
    pendingPlan.value = null
    handleSendMessage()
  }
}

const cancelPlan = () => {
  pendingPlan.value = null
  isPlanConfirmed.value = false
  hasPlanShown.value = false
}

// 权限确认处理方法
const handleConfirmPermission = async () => {
  if (!pendingPermission.value) return

  confirmingPermission.value = true
  try {
    const response = await confirmPermission({
      session_id: pendingPermission.value.sessionId,
      request_id: pendingPermission.value.requestId
    })

    if (response.code === 200) {
      message.success('已允许工具执行')
      pendingPermission.value = null
    } else {
      message.error(response.message || '确认失败')
    }
  } catch (error) {
    console.error('确认权限失败:', error)
    message.error('确认权限失败')
  } finally {
    confirmingPermission.value = false
  }
}

const handleCancelPermission = async () => {
  if (!pendingPermission.value) return

  try {
    const response = await cancelPermission({
      session_id: pendingPermission.value.sessionId,
      request_id: pendingPermission.value.requestId
    })

    if (response.code === 200) {
      message.info('已拒绝工具执行')
      pendingPermission.value = null
    } else {
      message.error(response.message || '取消失败')
    }
  } catch (error) {
    console.error('取消权限失败:', error)
    message.error('取消权限失败')
  }
}

// 中断对话
const handleInterrupt = async () => {
  if (!currentSessionId.value) {
    message.warning('没有正在进行的对话')
    return
  }

  try {
    const response = await interruptSession(currentSessionId.value)
    if (response.code === 200) {
      message.success('已中断对话')
      sendingMessage.value = false
      currentSessionId.value = null
    } else {
      message.error(response.message || '中断失败')
    }
  } catch (error) {
    console.error('中断对话失败:', error)
    message.error('中断对话失败')
  }
}

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

// Plan 确认状态
const pendingPlan = ref<{ sessionId: string; content: string } | null>(null)

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
      setupResizeObserver()
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

// 搜索
const handleSearch = () => {
  // 搜索由computed自动处理
}

// 开始新对话 - 调用 API 创建会话
const startNewConversation = async () => {
  try {
    const response = await createConversation({})
    if (response.code === 200 && response.data) {
      // 选中新创建的会话
      await selectConversation(response.data)
      // 新建对话后立即刷新列表
      await loadConversations()
      message.success('创建会话成功')
    } else {
      message.error(response.message || '创建会话失败')
    }
  } catch (error) {
    console.error('创建会话失败:', error)
    message.error('创建会话失败')
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
  if (!inputMessage.value.trim() || sendingMessage.value) {
    return
  }

  // 检查是否是新建会话（没有选中会话）
  const isNewConversation = !selectedConversation.value

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''

  // 重置 textarea 高度
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
  }

  await nextTick()
  sendingMessage.value = true

  // 重置事件显示
  eventDisplay.value = null
  currentEventType.value = ''

  // 如果没有选中会话，先创建新会话
  if (isNewConversation) {
    try {
      const resp = await createConversation({})
      if (resp.code === 200 && resp.data) {
        await selectConversation(resp.data)
        await loadConversations()
      } else {
        message.error(resp.message || '创建会话失败')
        sendingMessage.value = false
        return
      }
    } catch (error) {
      console.error('创建会话失败:', error)
      message.error('创建会话失败')
      sendingMessage.value = false
      return
    }
  }

  // 添加用户消息
  const userMsg: MessageResponse = {
    message_id: '',
    conversation_id: selectedConversation.value!.conversation_id,
    role: 'user',
    content: userMessage,
    created_at: new Date().toISOString()
  }
  messages.value.push(userMsg)
  isAtBottom.value = true 
  scrollToBottom()

  // 新消息时重置 Plan 状态
  isPlanConfirmed.value = false
  hasPlanShown.value = false

  // 准备请求数据
  const historyMessages: ChatMessage[] = messages.value
    .slice(0, -1)
    .filter(msg => msg.content && msg.role)
    .map(msg => ({
      role: msg.role as 'user' | 'assistant',
      content: msg.content || ''
    }))

  // 在 streamChat 之前，先插入 AI 占位消息
  messages.value.push({
    message_id: '',
    conversation_id: selectedConversation.value!.conversation_id,
    role: 'assistant',
    content: '',
    thinking: '',
    created_at: new Date().toISOString(),
    loading: true
  })
  scrollToBottom()

  try {
    const stream = await streamChat({
      conversation_id: selectedConversation.value?.conversation_id,
      messages: historyMessages,
      message: userMessage
    })

    if (!stream) {
      throw new Error('无法建立流式连接')
    }

    const reader = stream.getReader()

    // 用于捕获 session_id
    let capturedSessionId: string | null = null

    // 步骤流状态机：追踪当前步骤类型，每次切换类型时新建步骤
    let activeStep: 'thinking' | 'text' | null = null

    // 获取当前 loading 的 assistant 步骤索引
    const getCurrentStepIndex = (): number => {
      for (let i = messages.value.length - 1; i >= 0; i--) {
        if (messages.value[i].role === 'assistant' && messages.value[i].loading) {
          return i
        }
      }
      return -1
    }

    // 关闭当前步骤并新建下一步
    const switchStep = (newType: 'thinking' | 'text') => {
      const idx = getCurrentStepIndex()
      if (idx >= 0) {
        messages.value[idx].loading = false
      }
      messages.value.push({
        message_id: '',
        conversation_id: selectedConversation.value!.conversation_id,
        role: 'assistant',
        content: '',
        thinking: '',
        created_at: new Date().toISOString(),
        loading: true
      })
      activeStep = newType
      scrollToBottom()
    }

    // 定义事件处理器
    const handleEvent = (event: CodeEventType) => {
      const eventKind = (event as any).kind || (event as any).type

      switch (eventKind) {
        case 'session_created':
          // 会话创建事件
          if (!capturedSessionId) {
            capturedSessionId = (event as any).sessionId || (event as any).newSessionId
            currentSessionId.value = capturedSessionId
            console.log('[DEBUG] session_created event, sdk session_id:', capturedSessionId)
          }
          break
        case 'system':
          // 系统初始化事件
          const systemEvent = event as any
          eventDisplay.value = {
            message: `系统已初始化 - 模型: ${systemEvent.model || 'unknown'}, 版本: ${systemEvent.qwen_code_version || 'unknown'}`,
            type: 'info'
          }
          break
        case 'permission_request':
          // 权限请求事件
          const permEvent = event as any
          console.log('[DEBUG] permission_request event:', permEvent)
          pendingPermission.value = {
            sessionId: permEvent.sessionId,
            toolName: permEvent.toolName,
            input: permEvent.input || {},
            requestId: permEvent.requestId
          }
          // 滚动到底部显示权限卡片
          nextTick(() => scrollToBottom())
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
      // onChunk: 步骤流模式，按 thinking/text 切换创建独立步骤
    async (data: { full_content?: string; thinking?: string; content?: string }, type?: string) => {
        // 检查是否还在当前的对话中
        const convId = selectedConversation.value?.conversation_id
        if (!convId && !capturedSessionId) return

        const isThinking = type === 'thinking' || type === 'thinking_delta'
        const newStepType = isThinking ? 'thinking' : 'text'

        // thinking 每次都是完整块，每次都新建步骤；text 增量合并到当前步骤
        if (isThinking) {
            switchStep(newStepType)
            // 等两帧让 loading 动画能先渲染出来，再填内容
            await nextTick()
            await nextTick()
        } else if (activeStep !== newStepType || getCurrentStepIndex() < 0) {
          switchStep(newStepType)
        }

        // 更新当前步骤
        const stepIdx = getCurrentStepIndex()
        if (stepIdx < 0) return

        if (isThinking) {
          if (data.thinking) {
            messages.value[stepIdx].thinking = data.thinking
          }
        } else if (data.content !== undefined) {
          messages.value[stepIdx].content = data.content
          // 检测到"请先确认"提示，设置 pendingPlan（防抖）
          if (data.content.includes('请先确认任务') && capturedSessionId && !hasPlanShown.value) {
            hasPlanShown.value = true
            pendingPlan.value = {
              sessionId: capturedSessionId,
              content: data.content
            }
            // 关闭当前加载状态
            messages.value[stepIdx].loading = false
          }
        } else if (data.full_content !== undefined) {
          messages.value[stepIdx].content = data.full_content
          // 检测到"请先确认"提示，设置 pendingPlan（防抖）
          if (data.full_content.includes('请先确认任务') && capturedSessionId && !hasPlanShown.value) {
            hasPlanShown.value = true
            pendingPlan.value = {
              sessionId: capturedSessionId,
              content: data.full_content
            }
            // 关闭当前加载状态
            messages.value[stepIdx].loading = false
          }
        }
      },
      // onComplete: 关闭最后一个 loading 步骤
      (finalContent) => {
        // 找最后一个 assistant 消息，不管 loading 状态
        for (let i = messages.value.length - 1; i >= 0; i--) {
          if (messages.value[i].role === 'assistant') {
            messages.value[i].content = finalContent
            messages.value[i].loading = false
            break
          }
        }
        if (selectedConversation.value) {
          selectedConversation.value.last_message = finalContent
        }
        // 重置 Plan 状态
        isPlanConfirmed.value = false
        hasPlanShown.value = false
        sendingMessage.value = false
        currentSessionId.value = null
        setTimeout(() => {
          eventDisplay.value = null
          currentEventType.value = ''
        }, 3000)
        nextTick(() => scrollToBottom())
      },
      // onError: 标记最后一个 loading 步骤为错误
      (error) => {
        console.error('流式对话错误:', error)
        const idx = getCurrentStepIndex()
        if (idx >= 0) {
          messages.value[idx].content = `错误: ${error}`
          messages.value[idx].loading = false
        }
        // 重置 Plan 状态
        isPlanConfirmed.value = false
        hasPlanShown.value = false
        sendingMessage.value = false  // 兜底关闭 loading
        currentSessionId.value = null  // 清除 session_id
        eventDisplay.value = {
          message: `错误: ${error}`,
          type: 'info'
        }
      },
      // onEvent: 事件处理
      handleEvent
    )

    // 流式响应完成后，如果会话还没有标题，用用户的第一条消息作为标题
    if (!selectedConversation.value?.title && messages.value.length >= 2) {
      const firstUserMsg = messages.value.find(m => m.role === 'user')
      if (firstUserMsg && firstUserMsg.content) {
        const title = firstUserMsg.content.length > 50
          ? firstUserMsg.content.slice(0, 50) + '...'
          : firstUserMsg.content
        try {
          await updateConversation(selectedConversation.value!.conversation_id, { title })
          selectedConversation.value!.title = title
          // 更新标题后刷新列表
          await loadConversations()
        } catch (e) {
          console.error('更新会话标题失败:', e)
        }
      }
    }
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
    currentSessionId.value = null
  }
}

// 滚动到底部
let resizeObserver: ResizeObserver | null = null
const scrollToBottom = async () => {
  await nextTick()
  if (!messagesEndRef.value || !messagesContainer.value) return
  messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
}

// 设置 ResizeObserver 监听容器高度变化
const setupResizeObserver = () => {
  if (!messagesContainer.value) return
  if (resizeObserver) {
    resizeObserver.disconnect()
  }

  resizeObserver = new ResizeObserver(() => {
    if (isAtBottom.value && messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
  resizeObserver.observe(messagesContainer.value)
}

// 监听用户手动滚动
const handleScroll = () => {
  if (!messagesContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
  // 距离底部 80px 以内认为是"在底部"
  isAtBottom.value = scrollHeight - scrollTop - clientHeight < 80
}

// 格式化时间（精确到秒）
const formatTime = (time: string | undefined) => {
  if (!time) return ''
  const date = new Date(time)
  return date.toLocaleString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    month: '2-digit',
    day: '2-digit'
  })
}

// 自动调整 textarea 高度
const adjustTextareaHeight = () => {
  if (!textareaRef.value) return
  textareaRef.value.style.height = 'auto'
  textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 200)}px`
}

// 处理键盘事件
const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSendMessage()
  }
}

// 组件挂载时加载对话列表
onMounted(() => {
  loadConversations()
  messagesContainer.value?.addEventListener('scroll', handleScroll, { passive: true })
  setupResizeObserver()
})

onUnmounted(() => {
  messagesContainer.value?.removeEventListener('scroll', handleScroll)
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})

// 监听消息变化，自动滚动到底部
watch(messages, async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}, { deep: true })

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

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
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
  width: 80%;
  max-width: 80%;
  line-height: 1.4;
  min-height: 28px;
}

.delete-btn {
  opacity: 0;
  transition: opacity 0.3s;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
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

.new-session-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 60px 40px;
  min-height: 0;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
}

.new-session-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  max-width: 900px;
  margin: 0 auto;
}

.welcome-icon {
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: linear-gradient(135deg, #1890ff 0%, #0050b3 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  color: #fff;
  margin-bottom: 24px;
  box-shadow: 0 8px 24px rgba(24, 144, 255, 0.3);
}

.welcome-title {
  font-size: 32px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 12px 0;
  letter-spacing: -0.5px;
}

.welcome-subtitle {
  font-size: 16px;
  color: #666;
  margin: 0 0 48px 0;
  line-height: 1.6;
}

.feature-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  width: 100%;
}

.feature-card {
  background: #fff;
  border-radius: 12px;
  padding: 32px 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
  border: 1px solid #f0f0f0;
  cursor: pointer;
  user-select: none;
}

.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  border-color: #1890ff;
}

.feature-card:active {
  transform: translateY(-2px);
}

.feature-icon {
  font-size: 40px;
  margin-bottom: 16px;
}

.feature-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 8px;
}

.feature-desc {
  font-size: 14px;
  color: #888;
  line-height: 1.5;
}

.patient-info {
  display: none;
}

/* ==========================================
   4. 右侧：消息区（气泡简洁布局）
========================================== */
/* 消息容器 */
.messages-container {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  background: #fafafa;
  padding: 16px;
  margin-top: 16px;
  min-height: 0;
  scrollbar-gutter: stable;
  overflow-anchor: none;
  will-change: scroll-position;
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

/* 消息项 */
.message-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-width: 80%;
  flex-shrink: 0;
}

/* AI消息左对齐 */
.message-ai {
  align-self: flex-start;
  width: 100%; /* 直接撑满，避免流式输出时宽度动态扩展 */
}

/* 用户消息右对齐 */
.message-user {
  align-self: flex-end;
}

/* Todo 消息左对齐 */
.message-todo {
  align-self: flex-start;
  width: 100%;
}

/* AI消息内容白块 */
.message-content {
  padding: 12px 16px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;
  width: 100%; /* 撑满父级(.message-ai) */
  box-sizing: border-box; /* 防止 padding 撑宽容器 */
}

/* 思考块宽度固定 */
:deep(.thinking-block) {
  width: 100%;
  box-sizing: border-box;
}

/* 用户消息蓝色气泡 */
.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;
  max-width: 100%;
}

.bubble-user {
  background: #e3f2fd;
  color: #1a1a1a;
  border: 1px solid #90caf9;
  box-shadow: 0 2px 8px rgba(66, 165, 245, 0.2);
}

/* Skill Call 橙色气泡 */
.bubble-skill {
  background: linear-gradient(135deg, #fff7e6 0%, #ffe7ba 100%);
  color: #d4380d;
  border: 1px solid #ffbb6b;
  box-shadow: 0 2px 8px rgba(255, 122, 69, 0.15);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 8px;
}

.skill-icon {
  font-size: 14px;
}

.skill-name {
  font-weight: 600;
  font-size: 13px;
  color: #d4380d;
}

.skill-label {
  font-size: 12px;
  color: #ff7a45;
  font-weight: 500;
}

/* Todo 紫色气泡 */
.todo-bubble {
  background: linear-gradient(135deg, #faf5ff 0%, #ede9fe 100%);
  border: 1px solid #c4b5fd;
  border-radius: 8px;
  padding: 8px 14px;
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0;
  box-shadow: 0 2px 8px rgba(139, 92, 246, 0.15);
}

.todo-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0 8px 0;
  cursor: pointer;
  user-select: none;
}

.todo-header-icon {
  font-size: 12px;
  font-weight: 600;
  color: #7c3aed;
  width: 16px;
  text-align: center;
}

.todo-header-title {
  font-size: 13px;
  font-weight: 600;
  color: #7c3aed;
}

.todo-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 4px;
  border-top: 1px solid #e9d5ff;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #5b21b6;
  line-height: 1.5;
}

.todo-done .todo-text {
  color: #a78bfa;
  text-decoration: line-through;
}

.todo-checkbox {
  width: 16px;
  height: 16px;
  border: 1px solid #a78bfa;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #7c3aed;
  flex-shrink: 0;
}

.todo-done .todo-checkbox {
  background: #7c3aed;
  color: #fff;
}

.todo-done .todo-checkbox {
  background: #7c3aed;
  color: #fff;
}

/* Plan 确认卡片 */
.plan-card {
  background: linear-gradient(135deg, #fff7e6 0%, #ffe7ba 100%);
  border: 1px solid #ffbb6b;
  border-radius: 8px;
  padding: 16px;
  margin: 16px 0;
  max-width: 80%;
  align-self: flex-start;
  box-shadow: 0 2px 8px rgba(255, 122, 69, 0.15);
}

.plan-content {
  margin-bottom: 12px;
  color: #d4380d;
  font-size: 14px;
  line-height: 1.5;
}

.plan-actions {
  display: flex;
  gap: 12px;
}

/* 权限确认卡片 */
.permission-card {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border: 2px solid #38bdf8;
  border-radius: 12px;
  padding: 20px;
  margin: 16px 0;
  max-width: 80%;
  align-self: flex-start;
  box-shadow: 0 4px 16px rgba(56, 189, 248, 0.2);
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.permission-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #bae6fd;
}

.permission-icon {
  font-size: 24px;
}

.permission-title {
  font-size: 16px;
  font-weight: 600;
  color: #0c4a6e;
}

.permission-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.permission-tool {
  display: flex;
  align-items: center;
  gap: 8px;
}

.permission-tool .label {
  font-weight: 600;
  color: #0369a1;
  font-size: 14px;
}

.permission-tool .value {
  color: #0c4a6e;
  font-size: 14px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  background: #fff;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #bae6fd;
}

.permission-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.permission-input .label {
  font-weight: 600;
  color: #0369a1;
  font-size: 14px;
}

.input-json {
  background: #fff;
  border: 1px solid #bae6fd;
  border-radius: 6px;
  padding: 12px;
  margin: 0;
  font-size: 13px;
  color: #0c4a6e;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  line-height: 1.5;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.permission-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.todo-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-user .message-text {
  word-break: break-word;
}

.bubble-user .message-text {
  margin: 0;
  color: inherit;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message-time {
  color: #b8b8b8;
  font-size: 11px;
  line-height: 1;
}

.message-time-inline {
  color: #999;
  font-size: 11px;
  margin-top: 8px;
  opacity: 0.7;
  text-align: right;
}

/* AI消息时间戳左对齐 */
.message-ai .message-time {
  margin-left: 6px;
  margin-top: 2px;
}

.message-ai .message-time-inline {
  text-align: left;
}

/* 用户消息时间戳右对齐 */
.message-user .message-time {
  margin-right: 6px;
  margin-top: 2px;
  text-align: right;
}

.message-user .message-time-inline {
  color: rgba(0, 0, 0, 0.5);
}

/* 思考块样式 */
.thinking-block {
  background: #f0f4f8;
  border: 1px solid #d0dce8;
  border-left: 4px solid #1890ff;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #333;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-weight: 600;
  color: #1890ff;
}

.thinking-label {
  white-space: nowrap;
}

.thinking-length {
  color: #999;
  font-size: 12px;
  font-weight: normal;
}

.thinking-content {
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.5;
  color: #666;
  max-height: 200px;
  overflow-y: auto;
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
  padding: 0;
  margin-top: 16px;
}

.input-container {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}

.input-container:focus-within {
  border-color: #1890ff;
  box-shadow: 0 2px 12px rgba(24, 144, 255, 0.15);
}

.input-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 4px;
}

.toolbar-btn {
  color: #666;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  color: #1890ff;
  background: rgba(24, 144, 255, 0.08);
}

.input-field {
  padding: 12px 16px;
}

.message-textarea {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  color: #333;
  background: transparent;
  min-height: 24px;
  max-height: 200px;
  overflow-y: auto;
}

.message-textarea::placeholder {
  color: #bbb;
}

.message-textarea:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.input-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-top: 1px solid #f0f0f0;
  background: #fafafa;
}

.input-hint {
  flex: 1;
}

.hint-text {
  font-size: 12px;
  color: #999;
}

.send-btn {
  border-radius: 8px;
  height: 36px;
  padding: 0 20px;
  font-weight: 500;
  box-shadow: 0 2px 4px rgba(24, 144, 255, 0.2);
  transition: all 0.3s ease;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(24, 144, 255, 0.3);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
  .message-item { max-width: 85%; }
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
  .message-item { max-width: 95%; }
  .message-content { padding: 12px 16px; }
}

@media (max-width: 480px) {
  .code-agent-container { padding: 8px; }
  .page-title { font-size: 18px; }
  .content-grid { gap: 8px; }
  .search-input { margin-bottom: 12px; }
  .card-title-row .ant-btn { padding: 4px 8px; font-size: 12px; }
  .message-item { max-width: 100%; }
  .message-content { padding: 8px 12px; }
  .input-row { gap: 6px; }
.input-actions { gap: 8px; }
}

/* 删除确认气泡框 */
.delete-confirm-popover {
  z-index: 9999;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  padding: 12px;
  min-width: 180px;
}

.delete-confirm-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.delete-confirm-text {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.delete-confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.delete-confirm-arrow {
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid #fff;
}

.delete-confirm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9998;
}
</style>
