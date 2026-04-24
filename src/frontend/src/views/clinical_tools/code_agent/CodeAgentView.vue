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
                </div>
                <!-- 时间戳 -->
                <div class="message-time">{{ formatTime(message.created_at) }}</div>
              </template>

              <!-- 用户消息：蓝色气泡 -->
              <template v-else>
                <div class="message-bubble bubble-user">
                  <p class="message-text">{{ message.content }}</p>
                </div>
                <div class="message-time">{{ formatTime(message.created_at) }}</div>
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
                 @keydown.enter.prevent="handleSendMessage"
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

        <!-- 新建会话时显示输入区域（无会话详情） -->
        <a-card v-else class="detail-card">
          <div class="new-session-container">
            <div class="new-session-header">
              <PlusOutlined style="font-size: 48px; color: #1890ff; margin-bottom: 16px;" />
              <h3>{{ t('views_CodeAgentView.newSession') }}</h3>
              <p style="color: #888; margin-bottom: 24px;">{{ t('views_CodeAgentView.startNewSessionHint') || '输入消息开始新对话' }}</p>
            </div>
            <!-- 输入区域 -->
            <div class="input-area">
              <div class="input-row">
                <a-input
                  v-model:value="inputMessage"
                  :placeholder="t('views_CodeAgentView.inputPlaceholder')"
                  allow-clear
                  class="message-input"
                   @keydown.enter.prevent="handleSendMessage"
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
  InfoCircleOutlined
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
  updateConversation
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
      currentEventType.value = event.type

      switch (event.type) {
        case 'session_created':
          // 会话创建事件
          if (!capturedSessionId) {
            capturedSessionId = (event as any).sessionId || (event as any).newSessionId
            console.log('[DEBUG] session_created event, sdk session_id:', capturedSessionId)
          }
          break
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
        const idx = getCurrentStepIndex()
        if (idx >= 0) {
          messages.value[idx].content = finalContent
          messages.value[idx].loading = false
        }
        if (selectedConversation.value) {
          selectedConversation.value.last_message = finalContent
        }
        // 重置 Plan 状态
        isPlanConfirmed.value = false
        hasPlanShown.value = false
        sendingMessage.value = false  // 兜底关闭 loading
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
  padding: 40px;
  min-height: 0;
}

.new-session-header {
  text-align: center;
  margin-bottom: 32px;
}

.new-session-header h3 {
  margin: 0 0 8px 0;
  font-size: 20px;
  color: #333;
}

.new-session-container .input-area {
  width: 100%;
  max-width: 600px;
  padding: 16px;
  border-top: 1px solid #e8e8e8;
}

.new-session-container .input-row {
  display: flex;
  gap: 12px;
}

.new-session-container .message-input {
  flex: 1;
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
  background: linear-gradient(135deg, #1890ff 0%, #0050b3 100%);
  color: #fff;
  border: none;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
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

.todo-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-user .message-text {
  word-break: break-word;
}

.bubble-user .message-text {
  margin: 0;
  color: #fff;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message-time {
  color: #b8b8b8;
  font-size: 11px;
  line-height: 1;
}

/* AI消息时间戳左对齐 */
.message-ai .message-time {
  margin-left: 6px;
  margin-top: 2px;
}

/* 用户消息时间戳右对齐 */
.message-user .message-time {
  margin-right: 6px;
  margin-top: 2px;
  text-align: right;
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
