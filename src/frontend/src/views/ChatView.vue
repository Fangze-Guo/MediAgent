<template>
  <div class="chat-bg">
    <div class="chat-fixed">
      <a-layout class="chat-layout">
        <a-layout-content>
          <!-- 聊天内容区域 -->
          <div class="chat-content" ref="messagesEl" @scroll="handleScroll">
            <!-- 消息列表 -->
            <div class="messages-container">
              <div v-for="(m, idx) in currentMessages" :key="idx"
                   :class="['message', m.role === 'user' ? 'user' : 'ai']">
                <!-- 用户和AI的头像 -->
                <div 
                  v-if="m.role !== 'user'" 
                  class="avatar ai-avatar" 
                  :class="getAssistantAvatarClass(m.assistantType)"
                  :style="getAssistantAvatarStyle()"
                >
                  <component :is="getAssistantIcon(m.assistantType, m)" />
                </div>
                <div class="message-content">
                  <!-- 解析并展示思考过程和回复内容 -->
                  <div v-if="m.parsedContent">
                    <!-- 多个思考过程 -->
                    <div v-if="m.parsedContent.thinkingList && m.parsedContent.thinkingList.length > 0">
                      <div v-for="(thinking, thinkingIdx) in m.parsedContent.thinkingList" :key="thinkingIdx"
                           class="thinking-section">
                        <div class="thinking-header">
                          <a-icon type="bulb" />
                          <span>{{ t('views_ChatView.thinkingProcess') }} {{ m.parsedContent.thinkingList.length > 1 ? thinkingIdx + 1 : '' }}</span>
                          <a-button type="text" size="small" @click="toggleThinking(idx, thinkingIdx)"
                                    class="toggle-thinking-btn">
                            {{ m.showThinkingList && m.showThinkingList[thinkingIdx] ? t('views_ChatView.collapse') : t('views_ChatView.expand') }}
                          </a-button>
                        </div>
                        <!-- 思考内容 -->
                        <div v-show="m.showThinkingList && m.showThinkingList[thinkingIdx]" class="thinking-content">
                          {{ thinking }}
                        </div>
                      </div>
                    </div>
                    <!-- 回复内容 -->
                    <div v-if="m.parsedContent.response" class="response-content">
                      <MarkdownRenderer :content="m.parsedContent.response" />
                    </div>
                  </div>
                  <!-- 原始内容（如果没有解析出思考过程） -->
                  <div v-else>
                    <MarkdownRenderer :content="m.content" />
                  </div>
                </div>
                <div v-if="m.role === 'user'" class="avatar user-avatar">
                  <UserOutlined />
                </div>
              </div>
              <!-- 加载状态 -->
              <div v-if="sending" class="loading-message">
                <div class="message-content">
                  <a-spin size="small" />
                  <span style="margin-left: 8px;">{{ t('views_ChatView.aiThinking') }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 回到底部按钮 -->
          <div v-if="userScrolled" class="scroll-to-bottom-btn" @click="scrollToBottom">
            <a-button type="primary" shape="circle" size="small">
              <template #icon>
                <DownOutlined />
              </template>
            </a-button>
          </div>
        </a-layout-content>
        <a-layout-footer>
          <!-- 输入区域 -->
          <div class="input-area">
            <!-- 当前会话文件显示区域 -->
            <div v-if="currentSessionFiles.length > 0" class="session-files">
              <div class="files-header">
                <span class="files-title">
                  <FileOutlined />
                  {{ t('views_ChatView.currentSessionFiles') }} ({{ currentSessionFiles.length }})
                </span>
              </div>
              <div class="files-list">
                <div 
                  v-for="file in currentSessionFiles" 
                  :key="file.id"
                  class="file-item"
                >
                  <div class="file-info">
                    <div class="file-icon">
                      <FileImageOutlined v-if="file.type.startsWith('image/')" />
                      <FileTextOutlined v-else-if="file.type.includes('csv')" />
                      <FileOutlined v-else />
                    </div>
                    <div class="file-details">
                      <div class="file-name">{{ file.name }}</div>
                      <div class="file-meta">
                        {{ formatFileSize(file.size) }} • {{ formatTime(file.modifiedTime) }}
                      </div>
                    </div>
                  </div>
                  <a-button 
                    type="text" 
                    size="small" 
                    danger
                    @click="removeSessionFile(file.id)"
                  >
                    <DeleteOutlined />
                  </a-button>
                </div>
              </div>
            </div>
            
            <!-- 输入容器 -->
            <div class="input-container">
              <!-- 顶部工具栏 -->
              <div class="input-toolbar">
                <div class="toolbar-left">
                  <!-- 模型选择器 -->
                  <ModelSelector 
                    :value="selectedModel"
                    @update:value="selectedModel = $event"
                    @model-change="handleModelChange"
                  />
                  <!-- 功能图标 -->
                  <div class="toolbar-icons">
                    <a-button type="text" class="toolbar-icon" @click="handleUploadClick"
                              :title="t('views_ChatView.uploadFile')">
                      <PaperClipOutlined />
                    </a-button>
                    <a-button type="text" class="toolbar-icon" :title="t('views_ChatView.documentManagement')">
                      <FileTextOutlined />
                    </a-button>
                    <a-button type="text" class="toolbar-icon" :title="t('views_ChatView.settings')">
                      <SettingOutlined />
                    </a-button>
                    <a-button type="text" class="toolbar-icon" :title="t('views_ChatView.voiceInput')">
                      <AudioOutlined />
                    </a-button>
                    <a-button type="text" class="toolbar-icon" :title="t('views_ChatView.tools')">
                      <AppstoreOutlined />
                    </a-button>
                  </div>
                </div>
                <div class="toolbar-right">
                  <a-button type="text" class="toolbar-icon" :title="t('views_ChatView.clearInput')">
                    <DeleteOutlined />
                  </a-button>
                  <a-button type="text" class="toolbar-icon" :title="t('views_ChatView.expandInput')">
                    <ExpandOutlined />
                  </a-button>
                </div>
              </div>
              <!-- 输入框 -->
              <div class="input-field">
                <textarea 
                  v-model="inputMessage" 
                  class="message-input" 
                  :placeholder="t('views_ChatView.inputPlaceholder')" 
                  @keydown="handleKeyDown"
                  @input="adjustTextareaHeight"
                  rows="1"
                  ref="textareaRef"
                ></textarea>
              </div>
              <!-- 底部工具栏 -->
              <div class="input-bottom">
                <div class="input-hint">
                  <span class="hint-text">{{ t('views_ChatView.inputHint') }}</span>
                </div>
                <div class="send-group">
                  <a-button type="primary" class="send-btn" :loading="sending" @click="sendMessage"
                            :disabled="!inputMessage.trim()">
                    {{ t('views_ChatView.send') }}
                  </a-button>
                </div>
              </div>
            </div>
          </div>
        </a-layout-footer>
      </a-layout>
    </div>

    <!-- 文件上传模态框 -->
    <a-modal
        v-model:open="showFileUpload"
        :title="t('views_ChatView.uploadFileTitle')"
        width="600px"
        :footer="null"
        @cancel="showFileUpload = false"
    >
      <FileUpload
          upload-mode="dataset"
          @upload-success="handleFileUploadSuccess"
          @upload-error="handleFileUploadError"
          @use-file="handleUseFile"
          @batch-use-complete="handleBatchUseComplete"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/**
 * 聊天视图组件
 * 提供完整的聊天界面，包括消息显示、输入、发送和会话管理功能
 */
import { computed, nextTick, ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useConversationsStore } from '@/store/conversations'
import FileUpload from '@/components/file/FileUpload.vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import ModelSelector from '@/components/model/ModelSelector.vue'
import { type FileInfo } from '@/apis/files'
import {
  AppstoreOutlined,
  AudioOutlined,
  BarChartOutlined,
  DeleteOutlined,
  DownOutlined,
  ExpandOutlined,
  FileTextOutlined,
  MedicineBoxOutlined,
  PaperClipOutlined,
  RobotOutlined,
  SettingOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'

// 路由相关
const route = useRoute()
const router = useRouter()

// 国际化
const { t } = useI18n()

// 状态管理
const conversationsStore = useConversationsStore()

// 响应式数据
/** 用户输入的消息内容 */
const inputMessage = ref('')
/** 是否正在发送消息 */
const sending = ref(false)
/** 当前活跃的会话ID */
const activeId = ref<string>('')
/** 消息容器的DOM引用，用于滚动到底部 */
const messagesEl = ref<HTMLElement | null>(null)
/** 输入框的DOM引用，用于自动调整高度 */
const textareaRef = ref<HTMLTextAreaElement | null>(null)
/** 是否显示文件上传区域 */
const showFileUpload = ref(false)
/** 当前会话关联的文件信息 */
const currentSessionFiles = ref<FileInfo[]>([])
/** 当前选择的模型 */
const selectedModel = ref('QWen-Plus')
/** 用户是否手动滚动了页面 */
const userScrolled = ref(false)
/** 自动滚动是否启用 */
const autoScrollEnabled = ref(true)


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
      return match.replace(/<\/?think>/g, '').trim()
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
  if (el) {
    // 使用平滑滚动，确保滚动到底部
    el.scrollTo({
      top: el.scrollHeight,
      behavior: 'smooth'
    })
  }
}


/**
 * 检查是否在底部附近
 */
const isNearBottom = () => {
  const el = messagesEl.value
  if (!el) return false

  const threshold = 50 // 距离底部50px内认为是在底部，更敏感
  return el.scrollTop + el.clientHeight >= el.scrollHeight - threshold
}

/**
 * 处理滚动事件
 */
const handleScroll = () => {
  const el = messagesEl.value
  if (!el) return

  // 检查用户是否手动滚动
  if (isNearBottom()) {
    userScrolled.value = false
    autoScrollEnabled.value = true
  } else {
    userScrolled.value = true
    autoScrollEnabled.value = false
  }
}


/**
 * 处理文件上传成功
 * @param _file
 */
const handleFileUploadSuccess = (_file: FileInfo) => {
  // 文件上传成功处理
}

/**
 * 处理文件上传失败
 * @param error 错误信息
 */
const handleFileUploadError = (error: string) => {
  console.error('文件上传失败:', error)
}

/**
 * 处理上传按钮点击
 */
const handleUploadClick = () => {
  showFileUpload.value = true
}

/**
 * 使用文件
 * @param file 要使用的文件
 */
const handleUseFile = (file: FileInfo) => {
  // 检查文件是否已经存在
  const existingFile = currentSessionFiles.value.find(f => f.id === file.id)
  if (existingFile) {
    message.warning(`文件 "${file.name}" 已经在当前会话中`)
    return
  }
  
  // 将文件添加到当前会话的文件列表中
  currentSessionFiles.value.push(file)
  
  // 显示成功提示
  message.success(`文件 "${file.name}" 已添加到当前会话`)
}

/**
 * 从当前会话中移除文件
 * @param fileId 文件ID
 */
const removeSessionFile = (fileId: string) => {
  const fileIndex = currentSessionFiles.value.findIndex((f: FileInfo) => f.id === fileId)
  if (fileIndex > -1) {
    const fileName = currentSessionFiles.value[fileIndex].name
    currentSessionFiles.value.splice(fileIndex, 1)
    message.success(`文件 "${fileName}" 已从当前会话中移除`)
  }
}

/**
 * 处理批量使用完成事件
 */
const handleBatchUseComplete = () => {
  // 关闭文件上传模态框
  showFileUpload.value = false
}

/**
 * 处理模型变化
 */
const handleModelChange = (model: any) => {
  // ModelSelector 组件已经调用了 API，这里只需要更新本地状态
  selectedModel.value = model.id
}


/**
 * 格式化文件大小
 * @param bytes 文件大小（字节）
 * @returns 格式化后的文件大小
 */
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * 格式化时间
 * @param timeString 时间字符串
 * @returns 格式化后的时间
 */
const formatTime = (timeString: string): string => {
  try {
    const date = new Date(timeString)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return timeString
  }
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
 * 生成新的会话ID并跳转到对话页面
 */
const createNewConversation = async () => {
  try {
    const conv = await conversationsStore.createConversation()
    activeId.value = conv.id
    conversationsStore.setCurrentConversation(conv.id)
    await router.replace({name: 'Conversation', params: {id: conv.id}})
  } catch (error) {
    console.error('创建会话失败:', error)
    message.error('创建会话失败，请稍后再试')
  }
}

// 初始化：根据路由参数加载或创建会话
const routeId = (route.params.id as string | undefined) || ''

// 异步初始化函数
const initializeConversation = async () => {
  if (routeId) {
    // 如果路由ID存在，尝试加载该会话
    activeId.value = routeId
    conversationsStore.setCurrentConversation(routeId)
    
    // 检查会话是否已存在，如果不存在则从后端加载
    const existingConversation = conversationsStore.getConversation(routeId)
    
    if (!existingConversation) {
      try {
        // 从后端加载会话消息
        await conversationsStore.loadConversationMessages(routeId)
      } catch (error) {
        console.error('ChatView: 加载会话失败:', error)
        // 如果加载失败，创建新会话
        await createNewConversation()
      }
    } else {
      // 如果会话已存在，检查是否需要刷新消息
      // 只有在消息为空时才从后端加载
      if (existingConversation.messages.length === 0) {
        try {
          await conversationsStore.loadConversationMessages(routeId)
        } catch (error) {
          console.warn('ChatView: 刷新会话消息失败:', error)
        }
      }
    }
  } else {
    // 否则创建新会话
    await createNewConversation()
  }
}

// 在组件挂载时执行初始化
onMounted(() => {
  // 使用nextTick确保DOM已渲染
  nextTick(() => {
    initializeConversation()
    
    // 初始化滚动到底部
    try {
      scrollToBottom()
    } catch (error) {
      console.warn('初始化滚动失败:', error)
    }
  })
})

// 监听路由变化，切换会话
watch(() => route.params.id, async (val) => {
  const id = String(val || '')
  if (id && id !== activeId.value) {
    activeId.value = id
    conversationsStore.setCurrentConversation(id)
    
    // 切换会话时清空当前会话的文件列表
    currentSessionFiles.value = []
    
    // 尝试从后端加载会话消息
    try {
      await conversationsStore.loadConversationMessages(id)
    } catch (error) {
      console.error('加载会话消息失败:', error)
    }
  }
})

// 监听当前会话变化
watch(currentConversation, (newConv) => {
  if (newConv) {
    // 会话切换时，确保滚动到底部
    nextTick(() => {
      try {
        scrollToBottom()
      } catch (error) {
        console.warn('滚动到底部失败:', error)
      }
    })
  }
}, {immediate: true})

// 监听消息变化，自动滚动到底部
watch(currentMessages, async () => {
  if (autoScrollEnabled.value) {
    try {
      await nextTick()
      const el = messagesEl.value
      if (el) {
        el.scrollTop = el.scrollHeight
      }
    } catch (error) {
      console.warn('自动滚动失败:', error)
    }
  }
}, {deep: true})

// 监听发送状态变化，在开始发送时重置滚动状态
watch(sending, (newSending) => {
  if (newSending) {
    // 开始发送消息时，重置滚动状态，确保能自动滚动
    userScrolled.value = false
    autoScrollEnabled.value = true
  }
})

// 组件销毁时清理
onUnmounted(() => {
  // 清理定时器等资源
  // 注意：这里可以添加其他需要清理的资源
})

/**
 * 发送消息给AI（内部函数）
 * @param messageText 要发送的消息内容
 */
const sendMessageToAI = async (messageText: string) => {
  if (!currentConversation.value || sending.value) return

  sending.value = true

  try {
    // 使用新的conversation API发送消息
    await conversationsStore.sendMessageToAgent(currentConversation.value.id, messageText)
  } catch (error) {
    console.error('发送消息失败:', error)
    message.error('发送消息失败，请稍后再试')
  } finally {
    sending.value = false
  }
}

/**
 * 自动调整textarea高度
 * 根据内容自动调整输入框高度，提供更好的用户体验
 */
const adjustTextareaHeight = () => {
  const textarea = textareaRef.value
  if (!textarea) return
  
  // 重置高度以获取正确的scrollHeight
  textarea.style.height = 'auto'
  
  // 设置新高度，但不超过最大高度
  const maxHeight = 150 // 对应CSS中的max-height
  const newHeight = Math.min(textarea.scrollHeight, maxHeight)
  textarea.style.height = newHeight + 'px'
}

/**
 * 处理键盘事件
 * Enter: 发送消息
 * Ctrl+Enter / Cmd+Enter / Shift+Enter: 换行
 * @param event 键盘事件
 */
const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Enter') {
    if (event.ctrlKey || event.metaKey || event.shiftKey) {
      // Ctrl+Enter、Cmd+Enter 或 Shift+Enter：换行
      // 插入换行符到当前光标位置
      const textarea = event.target as HTMLTextAreaElement
      const start = textarea.selectionStart
      const end = textarea.selectionEnd
      const value = textarea.value

      // 在光标位置插入换行符
      inputMessage.value = value.substring(0, start) + '\n' + value.substring(end)

      // 设置光标位置到换行符后，并调整高度
      nextTick(() => {
        textarea.selectionStart = textarea.selectionEnd = start + 1
        textarea.focus()
        // 调整高度以显示换行效果
        adjustTextareaHeight()
      })

      event.preventDefault()
    } else {
      // Enter：发送消息
      event.preventDefault()
      sendMessage()
    }
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

  // 清空输入框并重置高度
  inputMessage.value = ''
  adjustTextareaHeight()

  // 确保有当前会话，没有则创建
  if (!currentConversation.value) {
    createNewConversation()
  }

  // 重置滚动状态，确保新消息能正常滚动
  userScrolled.value = false
  autoScrollEnabled.value = true

  // 滚动到底部显示用户消息
  await scrollToBottom()

  // 发送消息给AI（sendMessageToAgent内部会处理用户消息的添加）
  await sendMessageToAI(text)
}

/**
 * 助手相关方法
 */

/**
 * 获取助手图标
 */
const getAssistantIcon = (assistantType?: string, message?: any) => {
  // 如果有消息且消息来自医学助手会话，尝试使用工具图标
  if (message && currentConversation.value?.toolInfo?.toolIcon) {
    return currentConversation.value.toolInfo.toolIcon
  }
  
  switch (assistantType) {
    case 'medical':
      return MedicineBoxOutlined
    case 'data':
      return BarChartOutlined
    case 'document':
      return FileTextOutlined
    default:
      return RobotOutlined
  }
}

/**
 * 获取助手头像样式类
 */
const getAssistantAvatarClass = (assistantType?: string) => {
  // 如果有工具信息，使用工具特定的样式
  if (currentConversation.value?.toolInfo?.toolId) {
    return `tool-avatar tool-${currentConversation.value.toolInfo.toolId}`
  }
  
  switch (assistantType) {
    case 'medical':
      return 'medical-avatar'
    case 'data':
      return 'data-avatar'
    case 'document':
      return 'document-avatar'
    default:
      return 'general-avatar'
  }
}

/**
 * 获取助手头像样式
 */
const getAssistantAvatarStyle = () => {
  // 如果有工具信息，使用工具的渐变背景
  if (currentConversation.value?.toolInfo?.toolGradient) {
    return {
      background: currentConversation.value.toolInfo.toolGradient
    }
  }
  return {}
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
}

/* 聊天主卡片：全屏布局，内容区占据主要空间 */
.chat-layout {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 布局内容区域 */
.ant-layout-content {
  position: relative;
}

/* 聊天内容区域：占据主要空间 */
.chat-content {
  flex: 1;
  overflow-y: auto;
  height: 100%;
  width: 100%;
  position: relative;
}

/* 消息容器 */
.messages-container {
  max-width: 80%;
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin: 10px auto 10px;
}


/* 单条消息容器：最大宽度、圆角、内边距与布局 */
.message {
  padding: 16px 20px;
  border-radius: 16px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

/* 用户消息：靠右显示，头像在右侧 */
.message.user {
  max-width: 50%;
  align-self: flex-end;
  flex-direction: row-reverse;
}

/* AI 消息：靠左显示 */
.message.ai {
  max-width: 80%;
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
  margin-top: 8px;
}

/* AI 头像：现代渐变背景与白色图标 */
.ai-avatar {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.2);
}

/* 用户头像：浅蓝背景与主色图标 */
.user-avatar {
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(6, 182, 212, 0.2);
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
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  border: 1px solid #f0f0f0;
}

/* 用户气泡：白底与白色文字 */
.message.user {
  background: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

/* 底部区域 */
.ant-layout-footer {
  padding: 0;
  background: #ffffff;
  min-height: auto; /* 移除固定高度，让内容自适应 */
  border: 1px solid #e5e7eb;
}

/* 输入区域：固定在底部 */
.input-area {
  height: auto; /* 改为自适应高度 */
  width: 100%;
}

/* 当前会话文件显示区域 */
.session-files {
  padding: 12px 16px;
  background: #f8f9fa;
  border-bottom: 1px solid #e5e7eb;
}

.session-files .files-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.session-files .files-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.session-files .files-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.session-files .file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.session-files .file-item:hover {
  border-color: #d1d5db;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.session-files .file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.session-files .file-icon {
  color: #6b7280;
  font-size: 16px;
}

.session-files .file-details {
  flex: 1;
  min-width: 0;
}

.session-files .file-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-files .file-meta {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}

/* 输入容器 */
.input-container {
  height: auto; /* 改为自适应高度 */
  width: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

.input-container:focus-within {
  border-color: #4f46e5;
}


/* 消息输入框样式 */
.message-input {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: 16px;
  min-height: 60px; /* 增加最小高度 */
  max-height: 150px; /* 增加最大高度 */
  width: 100%;
  color: #374151;
  padding: 12px 16px; /* 增加内边距 */
  line-height: 1.6; /* 增加行高，让换行更明显 */
}

.message-input::placeholder {
  color: #9ca3af;
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
  transition: all 0.2s;
}

.upload-btn:hover {
  color: #1890ff;
  border-color: #1890ff;
}

/* 发送按钮样式 */
.send-btn {
  height: 30px;
  background: #374151;
  border: none;
  color: white;
}

.send-btn:hover:not(:disabled) {
  background: #1f2937;
}

.send-btn:disabled {
  background: #d1d5db;
  color: #9ca3af;
  cursor: not-allowed;
}

/* 思考过程样式 */
.thinking-section {
  margin-bottom: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #f9fafb;
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f3f4f6;
  cursor: pointer;
  transition: all 0.2s ease;
  border-bottom: 1px solid #e5e7eb;
  font-size: 13px;
  color: #374151;
  font-weight: 500;
}

.thinking-header:hover {
  background: #e5e7eb;
}

.thinking-header .anticon {
  color: #f59e0b;
}

.toggle-thinking-btn {
  margin-left: auto;
  font-size: 11px;
  padding: 4px 8px;
  height: auto;
  line-height: 1.2;
  border-radius: 6px;
  transition: all 0.2s ease;
  color: #6b7280;
}

.toggle-thinking-btn:hover {
  background: #d1d5db;
  color: #374151;
}

.thinking-content {
  padding: 16px;
  background: #ffffff;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-size: 14px;
  line-height: 1.5;
  color: #374151;
}

.response-content {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
}

/* 顶部工具栏 */
.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px; /* 增加内边距 */
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  height: auto; /* 改为自适应高度 */
  min-height: 60px; /* 增加最小高度 */
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 模型选择器 */
.model-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #4f46e5;
  border-radius: 20px;
  color: white;
  font-size: 14px;
  font-weight: 500;
}

.model-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.model-name {
  font-size: 13px;
}

/* 工具栏图标 */
.toolbar-icons {
  display: flex;
  align-items: center;
  gap: 4px;
}

.toolbar-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: #6b7280;
  transition: all 0.2s ease;
}

.toolbar-icon:hover {
  background: #e5e7eb;
  color: #374151;
}

/* 输入框区域 */
.input-field {
  height: auto; /* 改为自适应高度 */
  width: 100%;
  min-height: 80px; /* 增加最小高度 */
}

/* 底部工具栏 */
.input-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between; /* 改为两端对齐 */
  padding: 12px 16px; /* 增加内边距 */
  height: auto; /* 改为自适应高度 */
  min-height: 60px; /* 增加最小高度 */
}

/* 输入提示 */
.input-hint {
  display: flex;
  align-items: center;
}

.hint-text {
  font-size: 12px;
  color: #9ca3af;
  user-select: none;
  transition: color 0.2s ease;
}

.input-container:focus-within .hint-text {
  color: #6b7280;
}

/* 发送按钮组 */
.send-group {
  display: flex;
  align-items: center;
  border-radius: 8px;
  overflow: hidden;
}

/* 回到底部按钮 */
.scroll-to-bottom-btn {
  position: absolute;
  bottom: 40px;
  right: 80px;
  z-index: 1000;
  opacity: 0.6;
  transition: all 0.3s ease;
  pointer-events: auto;
}

.scroll-to-bottom-btn:hover {
  opacity: 1;
  transform: translateY(-2px);
}

.scroll-to-bottom-btn .ant-btn {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  width: 40px;
  height: 40px;
}

/* 助手头像样式 */
.ai-avatar {
  position: relative;
}

.assistant-badge {
  position: absolute;
  top: -8px;
  right: -8px;
  background: #ff4d4f;
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 500;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* 工具头像基础样式 */
.tool-avatar {
  /* 基础样式，渐变背景通过内联样式设置 */
  position: relative;
}

/* 不同助手类型的头像样式 */
.medical-avatar {
  background: linear-gradient(135deg, #52c41a, #73d13d);
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

</style>