<template>
  <div class="code-agent-container">
    <!-- 主要内容区域 -->
    <div class="content-grid">
      <!-- 左侧面板：对话列表 + Work Flow -->
      <div class="left-panel">
        <!-- 对话列表 -->
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
                  {{ conversation.title || t('views_CodeAgentView.unnamedConversation') }}
                </span>
                <div class="header-actions">
                  <a-popover
                    trigger="click"
                    placement="bottomRight"
                    @click.stop
                  >
                    <template #content>
                      <div class="export-format-menu">
                        <div class="export-format-item" @click.stop="handleExport(conversation.conversation_id, 'markdown')">
                          Markdown (.md)
                        </div>
                        <div class="export-format-item" @click.stop="handleExport(conversation.conversation_id, 'json')">
                          JSON (.json)
                        </div>
                        <div class="export-format-item" @click.stop="handleExport(conversation.conversation_id, 'html')">
                          HTML (.html)
                        </div>
                      </div>
                    </template>
                    <a-button
                      type="text"
                      size="small"
                      class="export-btn"
                      @click.stop
                    >
                      <ExportOutlined />
                    </a-button>
                  </a-popover>
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
              <span class="conversation-time">{{ formatTime(conversation.updated_at) }}</span>
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

      <!-- Work Flow 面板 -->
      <div class="workflow-section">
        <div class="workflow-header">
          <span class="workflow-title">
            <span class="workflow-title-icon">⚡</span>
            {{ t('views_CodeAgentView.taskManager.title') }}
          </span>
          <div class="workflow-header-actions">
            <span v-if="runningTaskCount > 0" class="workflow-running-badge">{{ runningTaskCount }}</span>
            <a-popconfirm
              v-if="filteredSkillTasks.length > 0"
              :title="t('views_CodeAgentView.taskManager.clearConfirm')"
              :ok-text="t('views_CodeAgentView.taskManager.clear')"
              :cancel-text="t('common.cancel')"
              @confirm="handleClearFinishedTasks"
            >
              <button class="workflow-clear-btn" :disabled="finishedTaskCount === 0" :title="finishedTaskCount === 0 ? t('views_CodeAgentView.taskManager.clearDisabledTitle') : t('views_CodeAgentView.taskManager.clearTitle')">
                {{ t('views_CodeAgentView.taskManager.clear') }}
              </button>
            </a-popconfirm>
          </div>
        </div>

        <div v-if="filteredSkillTasks.length === 0" class="workflow-empty">
          <span class="workflow-empty-icon">🗂️</span>
          <span>{{ t('views_CodeAgentView.taskManager.empty') }}</span>
        </div>

        <div v-else class="workflow-task-list">
          <div
            v-for="task in filteredSkillTasks"
            :key="task.task_id"
            class="workflow-task-item"
            :class="[`workflow-task-${task.status}`, { 'workflow-task-active': task.conversation_id === selectedConversationId }]"
          >
            <!-- 任务头部 -->
            <div class="workflow-task-header">
              <span class="workflow-task-status-icon">
                <span v-if="task.status === 'running'" class="workflow-spin">⟳</span>
                <span v-else-if="task.status === 'success'">✓</span>
                <span v-else-if="task.status === 'failed'">✕</span>
              </span>
              <span class="workflow-task-name" :title="task.skill_name">{{ task.skill_name }}</span>
              <span class="workflow-task-status-text">
                <span v-if="task.status === 'running'">{{ t('views_CodeAgentView.taskManager.statusRunning') }}</span>
                <span v-else-if="task.status === 'success'">{{ t('views_CodeAgentView.taskManager.statusSuccess') }}</span>
                <span v-else-if="task.status === 'failed'">{{ t('views_CodeAgentView.taskManager.statusFailed') }}</span>
              </span>
              <!-- 操作按钮 -->
              <div class="workflow-task-actions">
                <button
                  class="workflow-task-action-btn workflow-task-delete-btn"
                  :title="t('views_CodeAgentView.taskManager.deleteTask')"
                  @click="handleDeleteTask(task.task_id)"
                >×</button>
              </div>
            </div>

            <!-- 底部元信息 -->
            <div class="workflow-task-meta">
              <span
                class="workflow-task-conv"
                :class="{ 'workflow-task-conv-clickable': canJumpToConv(task.conversation_id) }"
                :title="canJumpToConv(task.conversation_id) ? t('views_CodeAgentView.taskManager.jumpToConv') : t('views_CodeAgentView.taskManager.convNotInList')"
                @click="jumpToConversation(task.conversation_id)"
              >💬 {{ getConvTitle(task.conversation_id) }}</span>
              <span v-if="taskLiveElapsed(task)" class="workflow-task-elapsed" :class="{ 'workflow-task-elapsed-live': task.status === 'running' }">
                {{ taskLiveElapsed(task) }}
              </span>
              <span v-else-if="task.status === 'failed'" class="workflow-task-error-hint" :title="task.skill_error || ''">
                {{ task.skill_error || t('views_CodeAgentView.taskManager.viewError') }}
              </span>
              <span v-else class="workflow-task-time">{{ formatTime(task.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>
      <!-- /Work Flow 面板 -->
      </div>
      <!-- /left-panel -->

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

            <template
              v-for="message in messages"
              :key="message.message_id"
            >
              <!-- skill_submitted 消息不渲染任何气泡 -->
              <template v-if="message.event_type === 'skill_submitted'" />

              <!-- 其他消息正常渲染 -->
              <div
                v-else
                class="message-item"
                :class="message.event_type === 'todo' ? 'message-todo' : (message.event_type === 'skill_call' ? 'message-skill' : (message.role === 'user' ? 'message-user' : 'message-ai'))"
              >
              <!-- Skill Call 事件：橙色气泡（历史记录中的旧格式） -->
              <template v-if="message.event_type === 'skill_call'">
                <div class="message-bubble bubble-skill">
                  <span class="skill-icon">🔧</span>
                  <span class="skill-name">{{ message.skill_name }}</span>
                  <span class="skill-label">skill call</span>
                  <span class="skill-time">{{ formatTime(message.created_at) }}</span>
                </div>
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
                  <div class="message-time-inline">{{ formatTime(message.created_at) }}</div>
                </div>
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
            </template>

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
                  <a-button type="text" size="small" class="toolbar-btn" :title="t('views_CodeAgentView.attachFile')">
                    <PaperClipOutlined />
                  </a-button>
                  <a-button type="text" size="small" class="toolbar-btn" :title="t('views_CodeAgentView.insertCode')">
                    <CodeOutlined />
                  </a-button>
                  <a-button type="text" size="small" class="toolbar-btn" :title="t('views_CodeAgentView.voiceInput')">
                    <AudioOutlined />
                  </a-button>
                </div>
                <div class="toolbar-right">
                  <a-button type="text" size="small" class="toolbar-btn" @click="inputMessage = ''" :title="t('views_CodeAgentView.clearInput')">
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
                  <span class="hint-text">{{ t('views_CodeAgentView.inputHint') }}</span>
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
              <h2 class="welcome-title">{{ projectDisplayName }}</h2>
              <p class="welcome-subtitle" v-if="currentProjectId === 'gl-nict'">{{ t('views_CodeAgentView.welcomeSubtitleGlNict') }}</p>
              <p class="welcome-subtitle" v-else>{{ t('views_CodeAgentView.welcomeSubtitle') }}</p>

              <div class="feature-cards">
                <div class="feature-card" @click="startNewConversation">
                  <div class="feature-icon">🩺</div>
                  <div class="feature-title">{{ t('views_CodeAgentView.featureMedical') }}</div>
                  <div class="feature-desc">{{ t('views_CodeAgentView.featureMedicalDesc') }}</div>
                </div>
                <div class="feature-card" @click="startNewConversation">
                  <div class="feature-icon">📊</div>
                  <div class="feature-title">{{ t('views_CodeAgentView.featureData') }}</div>
                  <div class="feature-desc">{{ t('views_CodeAgentView.featureDataDesc') }}</div>
                </div>
                <div class="feature-card" @click="goToSkillStore">
                  <div class="feature-icon">🔬</div>
                  <div class="feature-title">{{ t('views_CodeAgentView.featureSkill') }}</div>
                  <div class="feature-desc">{{ t('views_CodeAgentView.featureSkillDesc') }}</div>
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
import { useRoute, useRouter } from 'vue-router'
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
  StopOutlined,
  ExportOutlined
} from '@ant-design/icons-vue'
import StreamingMarkdownRenderer from '@/components/markdown/StreamingMarkdownRenderer.vue'
import StreamingThinkingRenderer from '@/components/markdown/StreamingThinkingRenderer.vue'
import type {
  ChatMessage,
  ConversationInfo,
  MessageResponse,
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
  interruptSession,
  getSkillTask,
  listSkillTasks,
  deleteSkillTask,
  exportConversation
} from '@/apis/codeAgent'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

// 根据当前路由判断项目标识
const currentProjectId = computed(() => {
  if (route.name === 'GlNictAgent') return 'gl-nict'
  return undefined
})

// 项目显示名称
const projectDisplayName = computed(() => {
  if (currentProjectId.value === 'gl-nict') return t('views_CodeAgentView.titleGlNict')
  return t('views_CodeAgentView.title')
})

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

// 导出会话
const handleExport = async (conversationId: string, format: 'markdown' | 'json' | 'html') => {
  try {
    await exportConversation(conversationId, format)
    message.success(t('views_CodeAgentView.messages.exportSuccess'))
  } catch (error: any) {
    console.error('导出会话失败:', error)
    message.error(t('views_CodeAgentView.messages.exportFailed'))
  }
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
      message.success(t('views_CodeAgentView.messages.toolAllowed'))
      pendingPermission.value = null
    } else {
      message.error(response.message || t('views_CodeAgentView.messages.confirmFailed'))
    }
  } catch (error) {
    console.error('确认权限失败:', error)
    message.error(t('views_CodeAgentView.messages.confirmPermFailed'))
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
      message.info(t('views_CodeAgentView.messages.toolRejected'))
      pendingPermission.value = null
    } else {
      message.error(response.message || t('views_CodeAgentView.messages.cancelFailed'))
    }
  } catch (error) {
    console.error('取消权限失败:', error)
    message.error(t('views_CodeAgentView.messages.cancelPermFailed'))
  }
}

// 中断对话
const handleInterrupt = async () => {
  if (!currentSessionId.value) {
    message.warning(t('views_CodeAgentView.messages.interruptNoSession'))
    return
  }

  try {
    const response = await interruptSession(currentSessionId.value)
    if (response.code === 200) {
      message.success(t('views_CodeAgentView.messages.interruptedConv'))
      sendingMessage.value = false
      currentSessionId.value = null
    } else {
      message.error(response.message || t('views_CodeAgentView.messages.interruptFailed'))
    }
  } catch (error) {
    console.error('中断对话失败:', error)
    message.error(t('views_CodeAgentView.messages.interruptConvFailed'))
  }
}

// 加载会话详情状态（防止重复调用）
const loadingConversationDetail = ref(false)

// 用于取消上次请求的 AbortController
let currentAbortController: AbortController | null = null

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
const switchStep = () => {
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
  scrollToBottom()
}

// 处理流式响应的 chunk 更新
const handleStreamChunk = async (
  data: { full_content?: string; thinking?: string; content?: string },
  type: string | undefined,
  activeStep: { value: 'thinking' | 'text' | null },
  capturedSessionId: string | null
) => {
  const convId = selectedConversation.value?.conversation_id
  if (!convId && !capturedSessionId) return

  const isThinking = type === 'thinking' || type === 'thinking_delta'
  const newStepType = isThinking ? 'thinking' : 'text'

  // 判断是否需要切换步骤（即前一条消息即将结束）
  const needSwitch = isThinking || activeStep.value !== newStepType || getCurrentStepIndex() < 0

  if (needSwitch && activeStep.value !== null && pendingToolEvents.value.length > 0) {
    // 前一条消息完成，插入暂存的 tool 事件
    const idx = getCurrentStepIndex()
    if (idx >= 0) {
      messages.value[idx].loading = false
    }
    pendingToolEvents.value.forEach(event => {
      if (event.type === 'todo') {
        messages.value.push({
          message_id: `todo_${Date.now()}`,
          conversation_id: selectedConversation.value!.conversation_id,
          role: 'assistant',
          content: '',
          event_type: 'todo',
          todo_list: event.data.todos,
          created_at: new Date().toISOString(),
          loading: false
        })
      } else {
        messages.value.push({
          message_id: `skill_${Date.now()}`,
          conversation_id: selectedConversation.value!.conversation_id,
          role: 'assistant',
          content: '',
          event_type: 'skill_call',
          skill_name: event.data.toolName || 'Unknown Tool',
          created_at: new Date().toISOString(),
          loading: false
        })
      }
    })
    pendingToolEvents.value = []
  }

  if (isThinking) {
    switchStep()
    await nextTick()
    await nextTick()
  } else if (activeStep.value !== newStepType || getCurrentStepIndex() < 0) {
    switchStep()
  }

  const stepIdx = getCurrentStepIndex()
  if (stepIdx < 0) return

  if (isThinking) {
    if (data.thinking) {
      messages.value[stepIdx].thinking = data.thinking
    }
  } else if (data.content !== undefined) {
    messages.value[stepIdx].content = data.content
    if (data.content.includes('请先确认任务') && capturedSessionId && !hasPlanShown.value) {
      hasPlanShown.value = true
      pendingPlan.value = { sessionId: capturedSessionId, content: data.content }
      messages.value[stepIdx].loading = false
    }
  } else if (data.full_content !== undefined) {
    messages.value[stepIdx].content = data.full_content
    if (data.full_content.includes('请先确认任务') && capturedSessionId && !hasPlanShown.value) {
      hasPlanShown.value = true
      pendingPlan.value = { sessionId: capturedSessionId, content: data.full_content }
      messages.value[stepIdx].loading = false
    }
  }

  activeStep.value = newStepType
}

// 处理流式响应完成
const handleStreamComplete = (finalContent: string) => {
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
  isPlanConfirmed.value = false
  hasPlanShown.value = false
  sendingMessage.value = false
  currentSessionId.value = null
  setTimeout(() => {
    eventDisplay.value = null
    currentEventType.value = ''
  }, 3000)
  nextTick(() => scrollToBottom())
}

// 处理流式响应错误
const handleStreamError = (error: string) => {
  console.error('流式对话错误:', error)
  const idx = getCurrentStepIndex()
  if (idx >= 0) {
    messages.value[idx].content = `错误: ${error}`
    messages.value[idx].loading = false
  }
  isPlanConfirmed.value = false
  hasPlanShown.value = false
  sendingMessage.value = false
  currentSessionId.value = null
  eventDisplay.value = { message: `错误: ${error}`, type: 'info' }
}

// 暂存待插入的 skill_call 和 todo 事件
const pendingToolEvents = ref<Array<{
  type: 'skill_call' | 'todo'
  data: any
}>>([])

// Skill 后台任务轮询 timers：task_id -> timer id
const skillTaskPollers: Record<string, ReturnType<typeof setInterval>> = {}

// 全局所有 skill 任务列表（用于 Work Flow 面板）
const allSkillTasks = ref<Array<{
  task_id: string
  skill_name: string
  conversation_id: string
  status: 'running' | 'success' | 'failed'
  skill_elapsed_seconds: number | null
  skill_started_at: string | null
  skill_error: string | null
  created_at: string
}>>([])

// 实时时钟，每秒更新一次，用于 running 任务的动态计时
const now = ref(Date.now())
setInterval(() => { now.value = Date.now() }, 1000)

// 返回任务的展示时长字符串：running 时实时计时，success 时显示实际耗时
const taskLiveElapsed = (task: typeof allSkillTasks.value[0]): string => {
  if (task.status === 'success' && task.skill_elapsed_seconds != null) {
    return `${task.skill_elapsed_seconds.toFixed(1)}s`
  }
  if (task.status === 'running' && task.skill_started_at) {
    const secs = Math.floor((now.value - new Date(task.skill_started_at).getTime()) / 1000)
    return `${secs}s`
  }
  return ''
}

// 已见过的任务 id（含初次加载），防止刷新后对历史 success 任务重复弹通知
const seenTaskIds = new Set<string>()

// 监听任务列表：
//   - 已见过(seenTaskIds)的任务 → 说明是本次会话新建，状态变为 success 时弹通知
//   - 未见过的任务(初次加载/刷新恢复) → 静默删除 success，不弹通知
watch(allSkillTasks, (tasks) => {
  for (const task of tasks) {
    if (!seenTaskIds.has(task.task_id)) {
      seenTaskIds.add(task.task_id)
      // 初次加载时已是 success：静默删除，不弹通知
      if (task.status === 'success') {
        setTimeout(() => handleDeleteTask(task.task_id), 0)
      }
      continue
    }
    // 本次会话内状态变为 success：弹通知后删除
    if (task.status === 'success') {
      message.success(t('views_CodeAgentView.taskManager.taskSuccess', { name: task.skill_name }))
      setTimeout(() => handleDeleteTask(task.task_id), 1000)
    }
  }
}, { deep: true })

// 当前项目下的会话 ID 集合（用于按项目过滤 Work Flow）
// 仅展示当前会话的任务，按创建时间倒序
const filteredSkillTasks = computed(() => {
  if (!selectedConversationId.value) return []
  return allSkillTasks.value
    .filter(t => t.conversation_id === selectedConversationId.value)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
})

// 正在运行的任务数量（仅当前项目）
const runningTaskCount = computed(() =>
  filteredSkillTasks.value.filter(t => t.status === 'running').length
)

// 已完成 / 失败的任务数量（仅当前项目）
const finishedTaskCount = computed(() =>
  filteredSkillTasks.value.filter(t => t.status === 'success' || t.status === 'failed').length
)

// 根据 conversation_id 获取会话标题
const getConvTitle = (conversationId: string): string => {
  const conv = conversations.value.find(c => c.conversation_id === conversationId)
  return conv?.title || t('views_CodeAgentView.unnamedConversation')
}

// 是否可以跳转到该会话
const canJumpToConv = (conversationId: string): boolean => {
  return conversations.value.some(c => c.conversation_id === conversationId)
}

// 跳转到任务对应的会话
const jumpToConversation = (conversationId: string) => {
  if (!canJumpToConv(conversationId)) return
  const conv = conversations.value.find(c => c.conversation_id === conversationId)
  if (conv) {
    selectConversation(conv)
  }
}

// 删除单个任务
const handleDeleteTask = async (taskId: string) => {
  try {
    const res = await deleteSkillTask(taskId)
    if (res.code === 200) {
      // 停止轮询
      if (skillTaskPollers[taskId]) {
        clearInterval(skillTaskPollers[taskId])
        delete skillTaskPollers[taskId]
      }
      // 从前端列表移除
      const idx = allSkillTasks.value.findIndex(t => t.task_id === taskId)
      if (idx >= 0) allSkillTasks.value.splice(idx, 1)
    } else {
      message.error(t('views_CodeAgentView.messages.deleteTaskFailed'))
    }
  } catch (e) {
    console.error('[handleDeleteTask] 失败:', e)
    message.error(t('views_CodeAgentView.messages.deleteTaskFailed'))
  }
}

// 清空已完成 / 失败的任务（仅当前项目）
const handleClearFinishedTasks = async () => {
  try {
    // 先收集需要清理的任务 id（仅当前项目下、已完成/失败）
    const toRemove = filteredSkillTasks.value
      .filter(t => t.status === 'success' || t.status === 'failed')
      .map(t => t.task_id)
    if (toRemove.length === 0) return

    // 后端只支持按 conversation_id 或全局清理，这里逐个删除以保证仅清理当前项目
    await Promise.all(toRemove.map(id => deleteSkillTask(id).catch(() => null)))

    // 同步清理本地状态
    for (const id of toRemove) {
      if (skillTaskPollers[id]) {
        clearInterval(skillTaskPollers[id])
        delete skillTaskPollers[id]
      }
    }
    allSkillTasks.value = allSkillTasks.value.filter(t => !toRemove.includes(t.task_id))
    message.success(t('views_CodeAgentView.messages.clearTasksSuccess', { count: toRemove.length }))
  } catch (e) {
    console.error('[handleClearFinishedTasks] 失败:', e)
    message.error(t('views_CodeAgentView.messages.clearTasksFailed'))
  }
}

// 加载全部 Skill 任务（用于刷新页面后恢复 Work Flow 面板）
const loadAllSkillTasks = async () => {
  try {
    const res = await listSkillTasks()
    if (res.code !== 200 || !res.data) return
    for (const task of res.data) {
      upsertGlobalTask(task.task_id, {
        task_id: task.task_id,
        skill_name: task.skill_name,
        conversation_id: task.conversation_id,
        status: task.status,
        skill_elapsed_seconds: task.elapsed_seconds,
        skill_started_at: task.started_at ?? null,
        skill_error: task.error ?? null,
        created_at: task.created_at,
      })
      // 对未结束的任务恢复轮询
      if (task.status === 'running') {
        startSkillTaskPoller(task.task_id)
      }
    }
  } catch (e) {
    console.error('[loadAllSkillTasks] 加载任务列表失败:', e)
  }
}

// 向全局任务列表插入或更新任务
const upsertGlobalTask = (taskId: string, patch: Partial<typeof allSkillTasks.value[0]>) => {
  const idx = allSkillTasks.value.findIndex(t => t.task_id === taskId)
  if (idx >= 0) {
    Object.assign(allSkillTasks.value[idx], patch)
  } else if (patch.task_id) {
    allSkillTasks.value.unshift(patch as typeof allSkillTasks.value[0])
  }
}

// 启动轮询，直到任务进入终态（success / failed）
const startSkillTaskPoller = (taskId: string) => {
  if (skillTaskPollers[taskId]) return  // 防止重复启动
  skillTaskPollers[taskId] = setInterval(async () => {
    try {
      const res = await getSkillTask(taskId)
      if (res.code !== 200 || !res.data) return
      const task = res.data
      // 更新消息气泡
      const msg = messages.value.find(m => m.skill_task_id === taskId)
      if (msg) {
        msg.skill_status = task.status
        msg.skill_started_at = task.started_at
        msg.skill_finished_at = task.finished_at
        msg.skill_elapsed_seconds = task.elapsed_seconds
        msg.skill_error = task.error ?? null
      }
      // 更新 Work Flow 面板
      upsertGlobalTask(taskId, {
        status: task.status,
        skill_elapsed_seconds: task.elapsed_seconds,
        skill_started_at: task.started_at ?? null,
        skill_error: task.error ?? null,
      })
      // 终态：停止轮询
      if (task.status === 'success' || task.status === 'failed') {
        clearInterval(skillTaskPollers[taskId])
        delete skillTaskPollers[taskId]
      }
    } catch (e) {
      console.error('[SkillPoller] 轮询失败:', e)
    }
  }, 3000)
}

// 进入会话时恢复该会话的 skill 后台任务气泡
const restoreSkillTasks = async (conversationId: string) => {
  try {
    const res = await listSkillTasks(conversationId)
    if (res.code !== 200 || !res.data) return

    for (const task of res.data) {
      // 同步到全局 Work Flow 面板
      upsertGlobalTask(task.task_id, {
        task_id: task.task_id,
        skill_name: task.skill_name,
        conversation_id: conversationId,
        status: task.status,
        skill_elapsed_seconds: task.elapsed_seconds,
        skill_started_at: task.started_at ?? null,
        skill_error: task.error ?? null,
        created_at: task.created_at,
      })

      // 已经在消息列表里的不重复插入
      if (messages.value.find(m => m.skill_task_id === task.task_id)) continue

      messages.value.push({
        message_id: `skill_submitted_${task.task_id}`,
        conversation_id: conversationId,
        role: null,
        content: null,
        event_type: 'skill_submitted',
        skill_name: task.skill_name,
        skill_task_id: task.task_id,
        skill_status: task.status,
        skill_started_at: task.started_at,
        skill_finished_at: task.finished_at,
        skill_elapsed_seconds: task.elapsed_seconds,
        skill_error: task.error ?? null,
        created_at: task.created_at,
        loading: false
      })

      // 未完成的任务恢复轮询
      if (task.status === 'running') {
        startSkillTaskPoller(task.task_id)
      }
    }
  } catch (e) {
    console.error('[restoreSkillTasks] 恢复任务失败:', e)
  }
}

// 处理流式事件
const handleStreamEvent = (event: CodeEventType, capturedSessionId: string | null) => {
  const eventKind = (event as any).kind || (event as any).type
  console.log('[DEBUG] 收到事件:', eventKind, event)

  switch (eventKind) {
    case 'session_created':
      if (!capturedSessionId) {
        const sessionId = (event as any).sessionId || (event as any).newSessionId
        currentSessionId.value = sessionId
        console.log('[DEBUG] session_created event, sdk session_id:', sessionId)
        return sessionId
      }
      break
    case 'tool_use':
      const toolEvent = event as any
      const toolName = toolEvent.toolName || toolEvent.tool_name
      console.log('[DEBUG] tool_use event, toolName:', toolName, 'full event:', toolEvent)

      // 暂存事件，等 thinking 结束后插入
      if (toolName === 'TodoWrite') {
        const todos = toolEvent.input?.todos || toolEvent.toolInput?.todos || []
        pendingToolEvents.value.push({
          type: 'todo',
          data: { todos }
        })
      } else {
        // 如果 toolName 是 "Skill"，从 input.skill 取具体技能名
        const displayName = (toolName === 'Skill' && toolEvent.input?.skill)
          ? toolEvent.input.skill
          : toolName
        pendingToolEvents.value.push({
          type: 'skill_call',
          data: { toolName: displayName }
        })
      }
      break
    case 'skill_submitted': {
      const submittedEvent = event as any
      const taskId = submittedEvent.taskId
      const skillName = submittedEvent.skillName || 'Unknown Skill'
      const convId = selectedConversation.value!.conversation_id
      const now = new Date().toISOString()
      messages.value.push({
        message_id: `skill_submitted_${taskId}`,
        conversation_id: convId,
        role: null,
        content: null,
        event_type: 'skill_submitted',
        skill_name: skillName,
        skill_task_id: taskId,
        skill_status: 'running',
        created_at: now,
        loading: false
      })
      // 同步到全局 Work Flow 面板
      upsertGlobalTask(taskId, {
        task_id: taskId,
        skill_name: skillName,
        conversation_id: convId,
        status: 'running',
        skill_elapsed_seconds: null,
        skill_started_at: null,
        skill_error: null,
        created_at: now,
      })
      nextTick(() => scrollToBottom())
      startSkillTaskPoller(taskId)
      break
    }
    case 'skill_call':
      const skillEvent = event as any
      messages.value.push({
        message_id: `skill_${Date.now()}`,
        conversation_id: selectedConversation.value!.conversation_id,
        role: 'assistant',
        content: '',
        event_type: 'skill_call',
        skill_name: skillEvent.skillName || skillEvent.skill_name || 'Unknown Skill',
        created_at: new Date().toISOString(),
        loading: false
      })
      nextTick(() => scrollToBottom())
      break
    case 'todo':
      const todoEvent = event as any
      messages.value.push({
        message_id: `todo_${Date.now()}`,
        conversation_id: selectedConversation.value!.conversation_id,
        role: 'assistant',
        content: '',
        event_type: 'todo',
        todo_list: todoEvent.todos || todoEvent.todo_list || [],
        created_at: new Date().toISOString(),
        loading: false
      })
      nextTick(() => scrollToBottom())
      break
    case 'system':
      const systemEvent = event as any
      eventDisplay.value = {
        message: `系统已初始化 - 模型: ${systemEvent.model || 'unknown'}, 版本: ${systemEvent.qwen_code_version || 'unknown'}`,
        type: 'info'
      }
      break
    case 'permission_request':
      const permEvent = event as any
      console.log('[DEBUG] permission_request event:', permEvent)
      pendingPermission.value = {
        sessionId: permEvent.sessionId,
        toolName: permEvent.toolName,
        input: permEvent.input || {},
        requestId: permEvent.requestId
      }
      nextTick(() => scrollToBottom())
      break
    case 'stream_event':
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
      eventDisplay.value = {
        message: '助手消息已接收',
        type: 'success'
      }
      break
    case 'result':
      const resultEvent = event as any
      if (resultEvent.subtype === 'success') {
        eventDisplay.value = {
          message: `处理完成 - 耗时: ${resultEvent.duration_ms}ms, 使用: ${resultEvent.usage.total_tokens} tokens`,
          type: 'success'
        }
      }
      break
  }
  return capturedSessionId
}

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
    const response = await getConversations(50, 0, currentProjectId.value)
    if (response.code === 200 && response.data) {
      conversations.value = response.data
      // 会话列表加载完后再加载 Work Flow，确保 filteredSkillTasks 过滤正确
      await loadAllSkillTasks()
    } else {
      message.error(t('views_CodeAgentView.messages.loadConvsFailed'))
    }
  } catch (error) {
    console.error('加载对话列表失败:', error)
    message.error(t('views_CodeAgentView.messages.loadConvsFailed'))
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

      // 恢复该会话的 skill 后台任务气泡（切换页面后重新进入时）
      await restoreSkillTasks(conversation.conversation_id)

      // 等待消息渲染完成后再滚动到底部
      await nextTick()
      scrollToBottom()
      setupResizeObserver()
    } else {
      message.error(t('views_CodeAgentView.messages.loadDetailFailed'))
    }
  } catch (error: any) {
    // 忽略被取消的请求错误
    if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') {
      console.log('会话详情请求被取消')
      return
    }
    console.error('加载会话详情失败:', error)
    message.error(t('views_CodeAgentView.messages.loadDetailFailed'))
  } finally {
    loadingConversationDetail.value = false
    currentAbortController = null
  }
}

// 搜索
const handleSearch = () => {
  // 搜索由computed自动处理
}

// 跳转到技能仓库（携带 project_id）
const goToSkillStore = () => {
  const query = currentProjectId.value ? { project_id: currentProjectId.value } : {}
  router.push({ path: '/skill-store', query })
}

// 开始新对话 - 调用 API 创建会话
const startNewConversation = async () => {
  try {
    const response = await createConversation({ project_id: currentProjectId.value })
    if (response.code === 200 && response.data) {
      // 先刷新列表（含 loadAllSkillTasks），再选中新会话，避免并发竞争
      await loadConversations()
      await selectConversation(response.data)
      message.success(t('views_CodeAgentView.messages.createSuccess'))
    } else {
      message.error(t('views_CodeAgentView.messages.createFailed'))
    }
  } catch (error) {
    console.error('创建会话失败:', error)
    message.error(t('views_CodeAgentView.messages.createFailed'))
  }
}

// 删除会话
const handleDeleteConversation = async (conversationId: string) => {
  try {
    const response = await deleteConversation(conversationId)
    if (response.code === 200 && response.data) {
      message.success(t('views_CodeAgentView.messages.deleteConvSuccess'))
      // 如果删除的是当前选中的会话，清空选中状态
      if (selectedConversationId.value === conversationId) {
        selectedConversationId.value = null
        selectedConversation.value = null
        messages.value = []
      }
      // 清理该会话的 Work Flow 任务和轮询
      const taskIds = allSkillTasks.value
        .filter(t => t.conversation_id === conversationId)
        .map(t => t.task_id)
      for (const tid of taskIds) {
        if (skillTaskPollers[tid]) {
          clearInterval(skillTaskPollers[tid])
          delete skillTaskPollers[tid]
        }
      }
      allSkillTasks.value = allSkillTasks.value.filter(t => t.conversation_id !== conversationId)
      // 重新加载对话列表
      await loadConversations()
    } else {
      message.error(t('views_CodeAgentView.messages.deleteConvFailed'))
    }
  } catch (error) {
    console.error('删除会话失败:', error)
    message.error(t('views_CodeAgentView.messages.deleteConvFailed'))
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
      const resp = await createConversation({ project_id: currentProjectId.value })
      if (resp.code === 200 && resp.data) {
        await selectConversation(resp.data)
        await loadConversations()
      } else {
        message.error(resp.message || t('views_CodeAgentView.messages.createFailed'))
        sendingMessage.value = false
        return
      }
    } catch (error) {
      console.error('创建会话失败:', error)
      message.error(t('views_CodeAgentView.messages.createFailed'))
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

  // 发送时锁定当前会话 ID，防止流式响应期间切换会话导致消息串入其他会话
  const streamingConversationId = selectedConversation.value!.conversation_id

  try {
    const stream = await streamChat({
      conversation_id: streamingConversationId,
      messages: historyMessages,
      message: userMessage,
      project_id: currentProjectId.value
    })

    if (!stream) {
      throw new Error('无法建立流式连接')
    }

    const reader = stream.getReader()

    // 用于捕获 session_id
    let capturedSessionId: string | null = null
    const activeStepRef = { value: null as 'thinking' | 'text' | null }

    // 定义事件处理器
    const handleEvent = (event: CodeEventType) => {
      // 如果用户已切换到其他会话，丢弃该事件
      if (selectedConversationId.value !== streamingConversationId) return
      const newSessionId = handleStreamEvent(event, capturedSessionId)
      if (newSessionId && !capturedSessionId) {
        capturedSessionId = newSessionId
      }
    }

    await parseStreamResponse(
      reader,
      async (data, type) => {
        // 如果用户已切换到其他会话，丢弃 chunk
        if (selectedConversationId.value !== streamingConversationId) return
        handleStreamChunk(data, type, activeStepRef, capturedSessionId)
      },
      (finalContent) => {
        // 如果用户已切换到其他会话，丢弃 complete 回调
        if (selectedConversationId.value !== streamingConversationId) return
        handleStreamComplete(finalContent)
      },
      handleStreamError,
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
    message.error(t('views_CodeAgentView.messages.sendFailed'))
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
  loadConversations()  // loadAllSkillTasks 在 loadConversations 完成后自动调用
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

// 监听路由变化，切换项目时重新加载会话列表
watch(() => route.name, (newRouteName, oldRouteName) => {
  // 只在 BC 和 Spine 页面之间切换时重新加载
  const projectRoutes = ['GlNictAgent']
  if (projectRoutes.includes(newRouteName as string) &&
      projectRoutes.includes(oldRouteName as string) &&
      newRouteName !== oldRouteName) {
    // 清空当前选中的会话
    selectedConversationId.value = null
    selectedConversation.value = null
    messages.value = []
    // 重新加载会话列表
    loadConversations()
  }
})

// 监听消息数量变化，自动滚动到底部
watch(() => messages.value.length, async () => {
  if (isAtBottom.value) {
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  }
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
  background: var(--bg-secondary);
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
  color: var(--text-primary);
}

.content-grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 24px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  align-items: stretch;
}

/* 左侧面板：对话列表 + Work Flow 上下排列 */
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.conversation-list-section {
  flex: 0 0 60%;
  min-height: 0;
  overflow: hidden;
}

/* ==========================================
   Work Flow 面板
========================================== */
.workflow-section {
  flex: 0 0 calc(40% - 16px);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 12px 14px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  overflow-y: auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.workflow-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.workflow-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.3px;
}

.workflow-title-icon {
  font-size: 14px;
}

.workflow-running-badge {
  background: #3b82f6;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  border-radius: 10px;
  padding: 1px 7px;
  min-width: 20px;
  text-align: center;
  animation: pulse-badge 1.5s ease-in-out infinite;
}

@keyframes pulse-badge {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.workflow-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  opacity: 0.6;
  text-align: center;
}

.workflow-empty-icon {
  font-size: 22px;
}

.workflow-task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.workflow-task-item {
  border-radius: 8px;
  padding: 9px 11px;
  border: 1px solid transparent;
  transition: background 0.2s;
}

.workflow-task-pending {
  background: rgba(251, 191, 36, 0.08);
  border-color: rgba(251, 191, 36, 0.3);
}

.workflow-task-running {
  background: rgba(59, 130, 246, 0.08);
  border-color: rgba(59, 130, 246, 0.35);
}

.workflow-task-success {
  background: rgba(16, 185, 129, 0.07);
  border-color: rgba(16, 185, 129, 0.3);
}

.workflow-task-failed {
  background: rgba(239, 68, 68, 0.07);
  border-color: rgba(239, 68, 68, 0.3);
}

.workflow-task-header {
  display: flex;
  align-items: center;
  gap: 7px;
}

.workflow-task-status-icon {
  font-size: 14px;
  line-height: 1.4;
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.workflow-task-pending .workflow-task-status-icon { color: #fbbf24; }
.workflow-task-running .workflow-task-status-icon { color: #3b82f6; }
.workflow-task-success .workflow-task-status-icon { color: #10b981; }
.workflow-task-failed  .workflow-task-status-icon { color: #ef4444; }

.workflow-task-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.5;
  padding-bottom: 1px;
}

.workflow-task-status-text {
  font-size: 11px;
  font-weight: 500;
  flex-shrink: 0;
}

.workflow-task-pending .workflow-task-status-text { color: #fbbf24; }
.workflow-task-running .workflow-task-status-text { color: #3b82f6; }
.workflow-task-success .workflow-task-status-text { color: #10b981; }
.workflow-task-failed  .workflow-task-status-text { color: #ef4444; }

.workflow-spin {
  display: inline-block;
  animation: workflow-spin 1s linear infinite;
  font-style: normal;
}

@keyframes workflow-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

.workflow-task-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 5px;
}

.workflow-task-conv {
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}

.workflow-task-elapsed {
  font-size: 11px;
  color: #10b981;
  font-weight: 500;
}

.workflow-task-elapsed-live {
  color: #f59e0b;
  animation: elapsed-blink 1.5s ease-in-out infinite;
}

@keyframes elapsed-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.workflow-task-time {
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.6;
}

.workflow-task-error-hint {
  font-size: 11px;
  color: #ef4444;
  cursor: pointer;
  text-decoration: underline dotted;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workflow-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.workflow-clear-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.18s;
}

.workflow-clear-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.08);
  border-color: #ef4444;
  color: #ef4444;
}

.workflow-clear-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.workflow-task-active {
  outline: 1.5px solid rgba(59, 130, 246, 0.5);
  outline-offset: -1px;
}

.workflow-task-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
  align-items: center;
}

.workflow-task-action-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1;
  padding: 2px 6px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}


.workflow-task-delete-btn {
  font-size: 14px;
  padding: 0 6px;
  height: 18px;
  line-height: 16px;
}

.workflow-task-delete-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: #ef4444;
  color: #ef4444;
}

.workflow-task-conv-clickable {
  cursor: pointer;
  text-decoration: underline dotted transparent;
  transition: color 0.15s, text-decoration-color 0.15s;
}

.workflow-task-conv-clickable:hover {
  color: #3b82f6;
  text-decoration-color: #3b82f6;
  opacity: 1;
}

.list-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

/* 穿透 Ant Design Card 内部，打通 Flex 布局 */
:deep(.list-card > .ant-card-head) {
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
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
  background: var(--bg-primary);
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
  padding: 14px 12px;
  border: 1px solid var(--border-color-light);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  flex-shrink: 0;
  min-width: 0;
  background: var(--bg-primary);
}

.conversation-item:hover {
  background-color: var(--hover-bg);
  border-color: #40a9ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.15);
}

.conversation-item.active {
  background: var(--bg-secondary);
  border-color: #1890ff;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.25);
}

.conversation-item.active .patient-name {
  color: #1890ff;
  font-weight: 600;
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
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
  flex: 1;
  min-width: 0;
}

.conversation-time {
  font-size: 12px;
  color: var(--text-tertiary);
  display: block;
  margin-top: 2px;
  margin-bottom: 2px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.conversation-preview {
  font-size: 14px;
  color: var(--text-secondary);
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

.export-btn {
  opacity: 0;
  transition: opacity 0.3s;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.conversation-item:hover .delete-btn,
.conversation-item:hover .export-btn {
  opacity: 1;
}

.export-format-menu {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-width: 140px;
}

.export-format-item {
  padding: 6px 12px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 13px;
  color: #333;
  transition: background 0.2s;
}

.export-format-item:hover {
  background: #f0f0f0;
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
  border: 1px solid var(--border-color);
  border-radius: 0 !important;
  background: var(--bg-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  contain: layout;
}

:deep(.detail-card.ant-card) {
  border-radius: 0 !important;
}

:deep(.detail-card > .ant-card-body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 0;
  background: var(--bg-primary);
  border-radius: 0 !important;
}

/* Ant Design Table 暗色模式适配 */
:deep(.ant-table) {
  background: var(--bg-primary);
  color: var(--text-primary);
}

:deep(.ant-table-thead > tr > th) {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-color);
}

:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
  color: var(--text-primary);
}

:deep(.ant-table-tbody > tr:hover > td) {
  background: var(--hover-bg);
}

:deep(.ant-table-wrapper) {
  background: var(--bg-primary);
}

.new-session-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 60px 40px;
  min-height: 0;
  background: var(--bg-primary);
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
  color: var(--text-primary);
  margin: 0 0 12px 0;
  letter-spacing: -0.5px;
}

.welcome-subtitle {
  font-size: 16px;
  color: var(--text-secondary);
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
  background: var(--bg-primary);
  border-radius: 12px;
  padding: 32px 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
  border: 1px solid var(--border-color-light);
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
  color: var(--text-primary);
  margin-bottom: 8px;
}

.feature-desc {
  font-size: 14px;
  color: var(--text-secondary);
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
  background: var(--bg-secondary);
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
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
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
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.2);
}

/* Skill Call 橙色气泡 */
.bubble-skill {
  background: var(--bg-secondary);
  color: #fa8c16;
  border: 1px solid #fa8c16;
  box-shadow: 0 2px 8px rgba(255, 122, 69, 0.15);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 8px;
}

.skill-time {
  margin-left: auto;
  font-size: 11px;
  color: #fa8c16;
  opacity: 0.8;
}

.skill-icon {
  font-size: 14px;
  line-height: 1;
  display: flex;
  align-items: center;
}

.skill-name {
  font-weight: 600;
  font-size: 13px;
  color: #fa8c16;
  line-height: 1;
}

.skill-label {
  font-size: 12px;
  color: #fa8c16;
  font-weight: 500;
  margin-left: 10px;
  line-height: 1;
}

/* Todo 紫色气泡 */
.todo-bubble {
  background: var(--bg-secondary);
  border: 1px solid #7c3aed;
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
  background: var(--bg-secondary);
  border: 1px solid #fa8c16;
  border-radius: 8px;
  padding: 16px;
  margin: 16px 0;
  max-width: 80%;
  align-self: flex-start;
  box-shadow: 0 2px 8px rgba(255, 122, 69, 0.15);
}

.plan-content {
  margin-bottom: 12px;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
}

.plan-actions {
  display: flex;
  gap: 12px;
}

/* 权限确认卡片 */
.permission-card {
  background: var(--bg-secondary);
  border: 2px solid #1890ff;
  border-radius: 12px;
  padding: 20px;
  margin: 16px 0;
  max-width: 80%;
  align-self: flex-start;
  box-shadow: 0 4px 16px rgba(24, 144, 255, 0.2);
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
  color: var(--text-primary);
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
  color: var(--text-primary);
  font-size: 14px;
}

.permission-tool .value {
  color: var(--text-primary);
  font-size: 14px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  background: var(--bg-primary);
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
}

.permission-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.permission-input .label {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
}

.input-json {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 12px;
  margin: 0;
  font-size: 13px;
  color: var(--text-primary);
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
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1;
}

.message-time-inline {
  color: var(--text-secondary);
  font-size: 11px;
  margin-top: 8px;
  opacity: 1;
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
  color: var(--text-secondary);
}

/* 思考块样式 */
.thinking-block {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-left: 4px solid #1890ff;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--text-primary);
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
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: normal;
}

.thinking-content {
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.5;
  color: var(--text-secondary);
  max-height: 200px;
  overflow-y: auto;
}

/* Markdown 渲染样式 */
.message-markdown {
  line-height: 1.6;
  color: var(--text-primary);
}

.message-markdown :deep(h1),
.message-markdown :deep(h2),
.message-markdown :deep(h3),
.message-markdown :deep(h4),
.message-markdown :deep(h5),
.message-markdown :deep(h6) {
  margin: 12px 0 6px 0;
  font-weight: 600;
  color: var(--text-primary);
}

.message-markdown :deep(h1) { font-size: 1.3em; }
.message-markdown :deep(h2) { font-size: 1.2em; }
.message-markdown :deep(h3) { font-size: 1.1em; }

.message-markdown :deep(p) {
  margin: 6px 0;
  color: var(--text-primary);
}

.message-markdown :deep(ul),
.message-markdown :deep(ol) {
  margin: 6px 0;
  padding-left: 20px;
  color: var(--text-primary);
}

.message-markdown :deep(li) {
  margin: 3px 0;
  color: var(--text-primary);
}

.message-markdown :deep(pre) {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 10px 12px;
  margin: 8px 0;
  overflow-x: auto;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.45;
  color: var(--text-primary);
}

.message-markdown :deep(code) {
  background: var(--bg-secondary);
  border-radius: 3px;
  padding: 1px 4px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
  color: var(--text-primary);
}

.message-markdown :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
}

.message-markdown :deep(blockquote) {
  border-left: 3px solid var(--border-color);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--text-secondary);
  font-style: italic;
}

.message-markdown :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
  font-size: 13px;
  background: var(--bg-primary);
}

.message-markdown :deep(th),
.message-markdown :deep(td) {
  border: 1px solid var(--border-color);
  padding: 6px 10px;
  text-align: left;
  background: var(--bg-primary);
  color: var(--text-primary);
}

.message-markdown :deep(th) {
  background: var(--bg-secondary);
  font-weight: 600;
  color: var(--text-primary);
}

.message-markdown :deep(tbody tr:hover td) {
  background: var(--hover-bg);
}

.message-markdown :deep(a) {
  color: #0366d6;
  text-decoration: none;
}

.message-markdown :deep(a:hover) {
  text-decoration: underline;
}

.message-markdown :deep(strong) {
  font-weight: 700;
  color: var(--text-primary);
}

[data-theme='dark'] .message-markdown :deep(strong) {
  font-weight: 800;
  color: #ffffff;
}

.message-markdown :deep(em) {
  font-style: italic;
  color: var(--text-primary);
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
  color: var(--text-secondary);
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
}

.input-container {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 0;
  overflow: hidden;
  transition: all 0.3s ease;
}

.input-container:focus-within {
  border-color: #1890ff;
}

.input-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color-light);
  background: var(--bg-secondary);
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 4px;
}

.toolbar-btn {
  color: var(--text-secondary);
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
  color: var(--text-primary);
  background: transparent;
  min-height: 24px;
  max-height: 200px;
  overflow-y: auto;
}

.message-textarea::placeholder {
  color: var(--text-tertiary);
}

.message-textarea:disabled {
  background: var(--bg-secondary);
  cursor: not-allowed;
}

.input-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-top: 1px solid var(--border-color-light);
  background: var(--bg-secondary);
  border-radius: 0 !important;
}

.input-hint {
  flex: 1;
}

.hint-text {
  font-size: 12px;
  color: var(--text-tertiary);
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
  background: var(--bg-secondary);
  border-radius: 4px;
}
.messages-container::-webkit-scrollbar-thumb,
.conversation-list::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 4px;
}
.messages-container::-webkit-scrollbar-thumb:hover,
.conversation-list::-webkit-scrollbar-thumb:hover {
  background: var(--text-tertiary);
}
.messages-container,
.conversation-list {
  scrollbar-width: thin;
  scrollbar-color: var(--border-color) var(--bg-secondary);
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
  background: var(--bg-primary);
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
  color: var(--text-primary);
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
  border-top: 6px solid var(--bg-primary);
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
