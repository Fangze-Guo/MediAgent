<template>
  <div class="chat-bg">
    <div class="chat-fixed">
      <a-layout class="chat-layout">
        <a-layout-content>
          <!-- 聊天内容区域 -->
          <div class="chat-content" ref="messagesEl" @scroll="handleScroll">
            <!-- 消息列表 -->
            <div class="messages-container">
              <!-- 空状态：会话中没有消息时显示 -->
              <div v-if="currentMessages.length === 0 && !sending" class="chat-empty-state">
                <img src="/MedWiser.png" alt="MedWiser" class="empty-logo" />
                <p class="empty-hint">{{ t('views_ChatView.inputPlaceholder') }}</p>
              </div>
              <div v-for="(m, idx) in currentMessages" :key="idx"
                   :class="['message', m.role === 'user' ? 'user' : 'ai']"
                   @mouseleave="copiedIdx = null">
                <!-- 流式期间显示项目图标，完成后不显示 -->
                <div v-if="m.role === 'assistant' && !m.typingComplete" class="streaming-icon">
                  <img src="/MedWiser.png" alt="MedWiser" />
                </div>
                <!-- message-main: 内容 + hover 操作栏 -->
                <div class="message-main">
                <div class="message-content">
                  <!-- 解析并展示思考过程和回复内容 -->
                  <div v-if="m.parsedContent">
                    <!-- 工具调用链路（流式期间与完成后均显示） -->
                    <template v-if="m.role === 'assistant' && m.toolCalls && m.toolCalls.length">
                      <WebSearchBlock
                        v-if="m.toolCalls.some(tc => tc.name === 'web_search')"
                        :items="m.toolCalls.filter(tc => tc.name === 'web_search')"
                      />
                      <KnowledgeSearchBlock
                        v-if="m.toolCalls.some(tc => tc.name === 'search_knowledge_base')"
                        :items="m.toolCalls.filter(tc => tc.name === 'search_knowledge_base')"
                        :sources="m.sources"
                      />
                      <ToolCallBlock
                        v-for="(tc, ti) in m.toolCalls.filter(tc => tc.name !== 'web_search' && tc.name !== 'search_knowledge_base')"
                        :key="ti"
                        :item="tc"
                      />
                    </template>
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
                    <!-- 流式期间正在思考（<think> 未闭合） -->
                    <div v-if="m.parsedContent.isThinking" class="thinking-section thinking-active">
                      <div class="thinking-header">
                        <a-icon type="bulb" />
                        <span>{{ t('views_ChatView.thinkingProcess') }}</span>
                        <span class="thinking-indicator"><span></span><span></span><span></span></span>
                      </div>
                    </div>
                    <!-- 回复内容（统一使用 MarkdownRenderer，streaming 仅控制光标） -->
                    <div v-if="m.parsedContent.response" class="response-content">
                      <MarkdownRenderer :content="m.parsedContent.response" :streaming="!m.typingComplete" />
                    </div>
                  </div>
                  <!-- 原始内容（如果没有解析出思考过程） -->
                  <div v-else>
                    <!-- 工具调用链路（流式期间与完成后均显示） -->
                    <template v-if="m.role === 'assistant' && m.toolCalls && m.toolCalls.length">
                      <WebSearchBlock
                        v-if="m.toolCalls.some(tc => tc.name === 'web_search')"
                        :items="m.toolCalls.filter(tc => tc.name === 'web_search')"
                      />
                      <KnowledgeSearchBlock
                        v-if="m.toolCalls.some(tc => tc.name === 'search_knowledge_base')"
                        :items="m.toolCalls.filter(tc => tc.name === 'search_knowledge_base')"
                        :sources="m.sources"
                      />
                      <ToolCallBlock
                        v-for="(tc, ti) in m.toolCalls.filter(tc => tc.name !== 'web_search' && tc.name !== 'search_knowledge_base')"
                        :key="ti"
                        :item="tc"
                      />
                    </template>
                    <!-- 流式等待中：无内容且无运行中工具调用 → 显示打字动画 -->
                    <div v-if="m.role === 'assistant' && !m.typingComplete && !m.content
                      && !(m.toolCalls && m.toolCalls.some(tc => tc.status === 'running'))" class="typing-indicator">
                      <span></span><span></span><span></span>
                    </div>
                    <!-- 助手消息：统一使用 MarkdownRenderer，streaming 仅控制光标 -->
                    <MarkdownRenderer
                      v-else-if="m.role === 'assistant' && m.content"
                      :content="m.content"
                      :streaming="!m.typingComplete"
                    />
                    <!-- 用户消息直接显示 -->
                    <template v-else>
                      <div v-if="m.images && m.images.length" class="message-images">
                        <img
                          v-for="(img, imgIdx) in m.images"
                          :key="imgIdx"
                          :src="img"
                          class="message-image-thumb"
                          @click="selectedPreviewImage = img"
                        />
                      </div>
                      <MarkdownRenderer v-if="m.content" :content="m.content" />
                    </template>
                  </div>
                  <!-- RAG 来源引用（输出完成后显示） -->
                  <div v-if="m.role === 'assistant' && m.sources && m.sources.length > 0" class="rag-sources">
                    <div class="rag-sources-header">
                      <span class="rag-icon">📚</span>
                      <span>参考来源</span>
                    </div>
                    <div v-for="(src, si) in m.sources" :key="si" class="rag-source-item">
                      <span class="rag-source-index">[{{ si + 1 }}]</span>
                      <span class="rag-source-kb">{{ src.kb_name }}</span>
                      <span v-if="src.file_name" class="rag-source-file">· {{ src.file_name }}</span>
                      <span class="rag-source-score">{{ Math.round((1 - src.score) * 100) }}% 相关</span>
                    </div>
                  </div>
                </div>
                <!-- hover 操作栏：时间 + 复制 -->
                <div v-if="m.typingComplete" class="message-actions">
                  <span v-if="m.timestamp" class="action-time">{{ formatMsgTime(m.timestamp) }}</span>
                  <button class="action-btn" @click="copyMessage(m, idx)" :title="copiedIdx === idx ? '已复制' : '复制'">
                    <CheckOutlined v-if="copiedIdx === idx" class="action-copy-ok" />
                    <CopyOutlined v-else />
                  </button>
                </div>
                </div><!-- end message-main -->
              </div>
              <!-- 加载状态：仅在没有未完成消息时显示（避免与气泡内 typing dots 重复） -->
              <div v-if="sending && !currentMessages.some(m => m.role === 'assistant' && !m.typingComplete)" class="loading-message">
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
            <div
              class="input-container"
              :class="{ 'drag-active': isDragging }"
              @dragover="handleDragOver"
              @dragleave="handleDragLeave"
              @drop="handleDrop"
            >
              <!-- 隐藏的文件选择器 -->
              <input
                ref="fileInputRef"
                type="file"
                accept="image/*,text/plain,text/csv,.md,.txt,.csv"
                multiple
                style="display: none"
                @change="handleFileSelect"
              />
              <!-- 待发送附件预览 -->
              <div v-if="pendingAttachments.length > 0" class="pending-attachments">
                <div v-for="att in pendingAttachments" :key="att.id" class="attachment-item">
                  <template v-if="att.type === 'image'">
                    <img :src="att.dataUrl" class="attachment-thumb" :alt="att.name" />
                    <div v-if="att.uploading" class="attachment-uploading">
                      <span class="upload-spinner" />
                    </div>
                  </template>
                  <template v-else>
                    <div class="attachment-file">
                      <FileTextOutlined class="attachment-file-icon" />
                      <span class="attachment-name">{{ att.name }}</span>
                    </div>
                  </template>
                  <button class="attachment-remove" @click="removeAttachment(att.id)" title="移除">
                    <CloseOutlined />
                  </button>
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
                  @paste="handlePaste"
                  rows="1"
                  ref="textareaRef"
                ></textarea>
              </div>
              <!-- 底部操作栏 -->
              <div class="input-bottom-bar">
                <!-- 左侧：+ 附件按钮 -->
                <button class="bar-plus-btn" @click="handleAttachClick" :title="t('views_ChatView.uploadFile')">
                  <PlusOutlined />
                </button>
                <!-- 右侧：模型选择器 + 功能图标 / 发送停止按钮 -->
                <div class="bar-right">
                  <ModelSelector
                    :value="selectedModel"
                    @update:value="selectedModel = $event"
                    @model-change="handleModelChange"
                  />
                  <!-- 有内容时显示发送/停止，无内容时显示功能图标 -->
                  <template v-if="sending || inputMessage.trim() || pendingAttachments.length">
                    <button
                      class="send-icon-btn"
                      @click="sending ? stopGeneration() : sendMessage()"
                    >
                      <span v-if="sending" class="stop-square" />
                      <ArrowUpOutlined v-else />
                    </button>
                  </template>
                  <template v-else>
                    <button class="bar-action-btn" title="语音输入">
                      <AudioOutlined />
                    </button>
                    <button class="bar-action-btn bar-wave-btn" title="语音">
                      <span class="wave-icon"><span/><span/><span/><span/><span/></span>
                    </button>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </a-layout-footer>
      </a-layout>
    </div>

    <!-- 对话链路图谱面板 -->
    <ConversationGraph
      v-if="showGraph"
      :messages="currentConversation?.messages ?? []"
      @close="showGraph = false"
    />

    <!-- 图谱切换浮动按钮 -->
    <button
      class="graph-toggle-btn"
      :class="{ active: showGraph }"
      :title="showGraph ? '隐藏链路图' : '查看对话链路图'"
      @click="showGraph = !showGraph"
    >🔗</button>

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

    <!-- 图片预览 Lightbox -->
    <div
      v-if="selectedPreviewImage"
      class="image-lightbox"
      @click="selectedPreviewImage = null"
    >
      <img :src="selectedPreviewImage" class="lightbox-img" @click.stop />
      <button class="lightbox-close" @click="selectedPreviewImage = null">
        <CloseOutlined />
      </button>
    </div>
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
import MarkdownRenderer from '@/components/markdown/MarkdownRenderer.vue'
import ToolCallBlock from '@/components/chat/ToolCallBlock.vue'
import WebSearchBlock from '@/components/chat/WebSearchBlock.vue'
import KnowledgeSearchBlock from '@/components/chat/KnowledgeSearchBlock.vue'
import ConversationGraph from '@/components/chat/ConversationGraph.vue'
import ModelSelector from '@/components/model/ModelSelector.vue'
import { type FileInfo, getChatImagePresignUrl, uploadToOss } from '@/apis/files'
import {
  ArrowUpOutlined,
  AudioOutlined,
  CheckOutlined,
  CloseOutlined,
  CopyOutlined,
  DeleteOutlined,
  DownOutlined,
  FileImageOutlined,
  FileOutlined,
  FileTextOutlined,
  PlusOutlined,
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
/** 中止控制器（停止生成用）*/
const abortController = ref<AbortController | null>(null)
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

/** 待发送附件 */
interface PendingAttachment {
  id: string
  name: string
  type: 'image' | 'text'
  /** 本地预览 URL（ObjectURL，仅显示用） */
  dataUrl: string
  /** OSS 永久访问 URL（上传完成后填入） */
  ossUrl?: string
  /** 是否正在上传到 OSS */
  uploading?: boolean
  textContent?: string
  size: number
  mimeType: string
}
const pendingAttachments = ref<PendingAttachment[]>([])
/** 文件选择器 input 引用 */
const fileInputRef = ref<HTMLInputElement | null>(null)
/** 拖拽悬停状态 */
const isDragging = ref(false)
/** 是否显示对话链路图谱面板 */
const showGraph = ref(false)
/** 当前预览大图的 URL */
const selectedPreviewImage = ref<string | null>(null)

const MAX_IMAGE_SIZE = 10 * 1024 * 1024  // 10 MB
const MAX_ATTACHMENTS = 6


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
      response: response || null,
      isThinking: false,
    }
  }
  return null
}

/**
 * 流式期间轻量解析：提取已闭合 <think> 块，检测未闭合的思考状态
 * 不使用缓存（流式期间内容持续变化），但正则足够轻量
 */
const parseStreamingContent = (content: string) => {
  // 提取已闭合的 <think>...</think> 块
  const thinkMatches = content.match(/<think>(.*?)<\/think>/gs)
  const thinkingList = thinkMatches
    ? thinkMatches.map(match => match.replace(/<\/?think>/g, '').trim())
    : []

  // 移除已闭合的 <think> 块
  let remaining = content.replace(/<think>.*?<\/think>/gs, '')

  // 检测是否有未闭合的 <think>（正在思考中）
  const unclosedIdx = remaining.lastIndexOf('<think>')
  const isThinking = unclosedIdx !== -1
  if (isThinking) {
    // 去掉未闭合的 <think> 及其后面的内容（思考中，不展示）
    remaining = remaining.substring(0, unclosedIdx)
  }

  const response = remaining.trim() || null

  // 如果没有任何思考块且不在思考中，返回 null 让 fallback 渲染
  if (thinkingList.length === 0 && !isThinking && !response) {
    return null
  }

  return {
    thinkingList,
    response,
    isThinking,
  }
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
 * 处理附件文件
 * - 图片：立即生成本地预览，异步上传到 OSS 拿到永久 URL
 * - 文本：读取内容到内存
 */
const processFiles = (files: FileList | File[]) => {
  const arr = Array.from(files)
  for (const file of arr) {
    if (pendingAttachments.value.length >= MAX_ATTACHMENTS) {
      message.warning(`最多支持 ${MAX_ATTACHMENTS} 个附件`)
      break
    }
    const isImage = file.type.startsWith('image/')
    const isText = file.type.startsWith('text/') || /\.(txt|csv|md)$/i.test(file.name)
    if (!isImage && !isText) {
      message.warning(`不支持的文件类型: ${file.name}，仅支持图片和文本文件`)
      continue
    }
    if (isImage && file.size > MAX_IMAGE_SIZE) {
      message.warning(`图片 "${file.name}" 超过 10MB 限制`)
      continue
    }

    const id = crypto.randomUUID()

    if (isImage) {
      // 立即生成本地预览（ObjectURL，低内存消耗）
      const localUrl = URL.createObjectURL(file)
      pendingAttachments.value.push({
        id, name: file.name, type: 'image',
        dataUrl: localUrl,
        ossUrl: undefined,
        uploading: true,
        size: file.size, mimeType: file.type,
      })

      // 异步上传到 OSS
      const conversationId = currentConversation.value?.id ?? 'unknown'
      getChatImagePresignUrl(conversationId, file.name, file.type)
        .then(async ({ put_url, signed_headers, access_url }) => {
          await uploadToOss(put_url, file, signed_headers)
          const idx = pendingAttachments.value.findIndex(a => a.id === id)
          if (idx !== -1) {
            pendingAttachments.value[idx] = {
              ...pendingAttachments.value[idx],
              ossUrl: access_url,
              uploading: false,
            }
          }
        })
        .catch(err => {
          console.error('OSS 上传失败:', err)
          message.error(`图片 "${file.name}" 上传失败，请重试`)
          pendingAttachments.value = pendingAttachments.value.filter(a => a.id !== id)
        })
    } else {
      const reader = new FileReader()
      reader.onload = () => {
        pendingAttachments.value.push({
          id, name: file.name, type: 'text',
          dataUrl: '', textContent: reader.result as string,
          size: file.size, mimeType: file.type,
        })
      }
      reader.readAsText(file)
    }
  }
}

/**
 * 处理粘贴事件（捕获剪贴板图片）
 */
const handlePaste = (event: ClipboardEvent) => {
  const items = event.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.kind === 'file' && item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) processFiles([file])
    }
  }
}

/**
 * 拖拽事件
 */
const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = true
}
const handleDragLeave = (event: DragEvent) => {
  const target = event.currentTarget as HTMLElement
  if (!target.contains(event.relatedTarget as Node)) {
    isDragging.value = false
  }
}
const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = false
  const files = event.dataTransfer?.files
  if (files && files.length > 0) processFiles(files)
}

/**
 * 点击附件按钮 → 打开文件选择器
 */
const handleAttachClick = () => {
  fileInputRef.value?.click()
}

/**
 * 文件选择器 change 事件
 */
const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    processFiles(input.files)
    input.value = ''
  }
}

/**
 * 移除待发送附件
 */
const removeAttachment = (id: string) => {
  pendingAttachments.value = pendingAttachments.value.filter(a => a.id !== id)
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


/** parsedContent 缓存：key = `convId-index:content`，避免每次 token 都重跑正则 */
const parsedContentCache = new Map<string, ReturnType<typeof parseMessageContent>>()

// 计算属性
/** 当前活跃的会话对象 */
const currentConversation = computed(() => conversationsStore.getConversation(activeId.value) || null)
/** 当前会话的消息列表，包含解析后的内容 */
const currentMessages = computed(() => {
  const messages = currentConversation.value?.messages || []
  return messages.map((msg, index) => {
    const messageKey = `${activeId.value}-${index}`

    // 显式读取 content，确保流式期间 Vue 也能追踪到该响应式属性
    const msgContent = msg.content
    // 完成后使用缓存解析；流式期间也做轻量解析以剥离 <think> 标签
    let parsedContent = null
    if (msg.typingComplete && msgContent) {
      const cacheKey = `${messageKey}:${msgContent.length}`
      if (!parsedContentCache.has(cacheKey)) {
        parsedContentCache.set(cacheKey, parseMessageContent(msgContent))
      }
      parsedContent = parsedContentCache.get(cacheKey)!
    } else if (!msg.typingComplete && msgContent && msgContent.includes('<think>')) {
      // 流式期间：只提取已闭合的 <think> 块，未闭合的部分隐藏（正在思考中）
      parsedContent = parseStreamingContent(msgContent)
    }

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
      showThinking: thinkingStates.value[messageKey] || false,
      showThinkingList,
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
  if (routeId === 'new') {
    await createNewConversation()
    return
  }
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
 * @param images 图片 base64 列表（可选）
 */
const sendMessageToAI = async (
  messageText: string,
  images?: string[],
  attachments?: { type: string; url: string }[],
) => {
  if (!currentConversation.value || sending.value) return
  const ctrl = new AbortController()
  abortController.value = ctrl
  sending.value = true
  try {
    await conversationsStore.streamMessageToAgent(
      currentConversation.value.id, messageText, images, attachments, ctrl.signal
    )
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      console.error('发送消息失败:', error)
      message.error('发送消息失败，请稍后再试')
    }
  } finally {
    sending.value = false
    abortController.value = null
  }
}

const stopGeneration = () => {
  abortController.value?.abort()
  abortController.value = null
}

/** 当前显示 ✓ 的消息索引 */
const copiedIdx = ref<number | null>(null)

/**
 * 格式化消息时间戳：今天只显示时:分，其余显示完整日期
 */
const formatMsgTime = (ts?: string): string => {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ''
  const now = new Date()
  const isToday = d.getFullYear() === now.getFullYear() &&
                  d.getMonth() === now.getMonth() &&
                  d.getDate() === now.getDate()
  const timeStr = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  if (isToday) return timeStr
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) + ' ' + timeStr
}

/**
 * 复制消息内容，复制成功后按钮变 ✓，离开 hover 后恢复
 */
const copyMessage = async (m: any, idx: number) => {
  const text: string = (m.parsedContent?.response ?? m.content) || ''
  try {
    await navigator.clipboard.writeText(text)
    copiedIdx.value = idx
  } catch {
    message.error('复制失败')
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
 * 处理用户输入的消息（含附件），发送到后端并显示AI回复
 */
const sendMessage = async () => {
  const text = inputMessage.value.trim()
  const hasAttachments = pendingAttachments.value.length > 0

  // 验证输入和状态
  if ((!text && !hasAttachments) || sending.value) return

  // 构造最终文本：文本文件内容前置拼接
  const textFiles = pendingAttachments.value.filter(a => a.type === 'text')
  let finalContent = text
  if (textFiles.length > 0) {
    const fileBlocks = textFiles
      .map(f => `[文件: ${f.name}]\n${f.textContent ?? ''}\n[/文件]`)
      .join('\n\n')
    finalContent = text ? `${fileBlocks}\n\n${text}` : fileBlocks
  }

  // 检查是否有图片还在上传
  const uploading = pendingAttachments.value.some(a => a.uploading)
  if (uploading) {
    message.warning('图片正在上传中，请稍候再发送')
    return
  }

  // 提取图片 OSS URL 和附件元数据
  const imageAttachments = pendingAttachments.value.filter(a => a.type === 'image' && a.ossUrl)
  const images = imageAttachments.map(a => a.ossUrl!)
  const attachments: { type: string; url: string }[] = imageAttachments.map(a => ({
    type: 'image',
    url: a.ossUrl!,
  }))

  // 清空输入框和附件，revoke ObjectURL 释放内存
  inputMessage.value = ''
  // 需在 nextTick 后调用，否则 DOM 未更新 scrollHeight 仍是旧值
  nextTick(() => adjustTextareaHeight())
  const toRevoke = pendingAttachments.value.filter(a => a.dataUrl.startsWith('blob:'))
  pendingAttachments.value = []
  nextTick(() => toRevoke.forEach(a => URL.revokeObjectURL(a.dataUrl)))

  // 确保有当前会话，没有则创建
  if (!currentConversation.value) {
    await createNewConversation()
  }

  // 重置滚动状态，确保新消息能正常滚动
  userScrolled.value = false
  autoScrollEnabled.value = true

  // 滚动到底部显示用户消息
  await scrollToBottom()

  // 发送消息给AI
  await sendMessageToAI(
    finalContent || '请分析这些内容',
    images.length ? images : undefined,
    attachments.length ? attachments : undefined,
  )
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
  position: relative;
  background: var(--bg-primary);
}

/* 图谱切换浮动按钮 */
.graph-toggle-btn {
  position: fixed;
  bottom: 90px;
  right: 20px;
  z-index: 200;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1.5px solid var(--border-color, #e5e7eb);
  background: var(--bg-primary, #fff);
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  transition: all 0.2s;
}
.graph-toggle-btn:hover,
.graph-toggle-btn.active {
  background: var(--text-primary, #111);
  border-color: var(--text-primary, #111);
  filter: invert(1);
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
  background: var(--bg-primary) !important;
  flex-direction: column;
  overflow: hidden;
}

/* 布局内容区域 */
.ant-layout-content {
  position: relative;
  background: var(--bg-primary) !important;
}

/* 聊天内容区域：占据主要空间 */
.chat-content {
  flex: 1;
  overflow-y: auto;
  height: 100%;
  width: 100%;
  position: relative;
}

/* 消息区底部渐变遇雐层 */
.chat-content::after {
  content: '';
  display: block;
  position: sticky;
  bottom: 0;
  height: 48px;
  background: linear-gradient(to bottom, transparent, var(--bg-primary));
  pointer-events: none;
  margin-top: -48px;
}

/* 空状态占位 */
.chat-empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 80px 20px;
  opacity: 0.35;
  user-select: none;
  pointer-events: none;
}
.empty-logo {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: contain;
}
.empty-hint {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
}

/* 消息容器：居中列 */
.messages-container {
  max-width: 860px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0;
  margin: 0 auto;
  padding: 16px 0 24px;
}

/* 单条消息：仅布局，无气泡样式 */
.message {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 6px 0;
}

/* 用户消息：靠右，头像在右侧 */
.message.user {
  flex-direction: row-reverse;
  padding: 4px 0;
}

/* AI 消息：靠左，全宽，无气泡，增加垂直间距 */
.message.ai {
  width: 100%;
  padding: 10px 0 6px;
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

/* message-main：列布局，包裹内容和操作栏 */
.message-main {
  display: flex;
  flex-direction: column;
}

.message.ai .message-main {
  flex: 1;
  min-width: 0;
}

.message.user .message-main {
  align-items: flex-end;
}

/* AI 消息内容 */
.message.ai .message-content {
  min-width: 0;
  line-height: 1.7;
  word-wrap: break-word;
  padding: 4px 0;
  color: var(--text-primary);
}

/* 用户消息内容：气泡样式 */
.message.user .message-content {
  max-width: calc(860px * 0.62);
  background: var(--user-bubble-bg, #e8edf8);
  border: 1px solid rgba(99, 102, 241, 0.12);
  border-radius: 18px 18px 4px 18px;
  padding: 10px 14px;
  line-height: 1.6;
  word-wrap: break-word;
  color: var(--text-primary);
  font-size: 14px;
  box-shadow: 0 1px 4px rgba(99, 102, 241, 0.08);
}

/* hover 操作栏 */
.message-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 2px;
  margin-top: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;
  pointer-events: none;
}

.message:hover .message-actions {
  opacity: 1;
  pointer-events: auto;
}


.action-time {
  font-size: 11px;
  color: var(--text-tertiary);
  user-select: none;
  padding: 0 2px;
}

.action-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  cursor: pointer;
  border-radius: 4px;
  padding: 0;
  transition: background 0.15s, color 0.15s;
}

.action-btn:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.action-copy-ok {
  color: #22c55e;
}

/* 流式期间的项目图标 */
.streaming-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  margin-top: 4px;
}
.streaming-icon img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 50%;
}

/* 底部区域：无边框，背景与页面融合，靠输入框阴影做视觉分隔 */
.ant-layout-footer {
  padding: 0;
  background: var(--bg-primary);
  border: none;
}

/* 输入区域：居中对齐消息列 */
.input-area {
  max-width: 860px;
  margin: 0 auto;
  padding: 10px 16px 14px;
}

/* 当前会话文件显示区域 */
.session-files {
  padding: 12px 16px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
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
  color: var(--text-primary);
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
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  transition: all 0.2s ease;
}

.session-files .file-item:hover {
  border-color: var(--border-color-light);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.session-files .file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.session-files .file-icon {
  color: var(--text-secondary);
  font-size: 16px;
}

.session-files .file-details {
  flex: 1;
  min-width: 0;
}

.session-files .file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-files .file-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* 输入容器：圆角卡片，与消息区背景一致 */
.input-container {
  width: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 18px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
  overflow: hidden;
  background: var(--bg-primary);
}

.input-container:focus-within {
  border-color: rgba(0, 0, 0, 0.18);
  box-shadow: 0 1px 8px rgba(0, 0, 0, 0.08);
}


/* 消息输入框样式 */
.message-input {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: 15px;
  min-height: 52px;
  max-height: 200px;
  width: 100%;
  color: var(--text-primary);
  background: transparent;
  padding: 14px 16px 6px;
  line-height: 1.6;
}

.message-input::placeholder {
  color: var(--text-tertiary);
}

/* 输入操作按钮组 */
.input-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.upload-btn {
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.upload-btn:hover {
  color: var(--link-color);
  border-color: var(--link-color);
}

/* 发送按钮样式 */
.send-btn {
  height: 30px;
  background: var(--text-primary);
  border: none;
  color: var(--bg-primary);
}

.send-btn:hover:not(:disabled) {
  background: var(--text-secondary);
}

.send-btn:disabled {
  background: var(--border-color);
  color: var(--text-tertiary);
  cursor: not-allowed;
}

/* 思考过程样式 */
.thinking-section {
  margin-bottom: 12px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.thinking-header:hover {
  background: var(--hover-bg);
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
  color: var(--text-secondary);
}

.toggle-thinking-btn:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

.thinking-content {
  padding: 16px;
  background: var(--bg-primary);
  white-space: pre-wrap;
  word-wrap: break-word;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-primary);
}

.response-content {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
}

/* 打字等待指示器 */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 2px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-secondary);
  animation: typing-bounce 1.2s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40%           { transform: scale(1);   opacity: 1;   }
}

/* RAG 来源引用 */
.rag-sources {
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--link-color) 6%, var(--bg-primary));
  border: 1px solid color-mix(in srgb, var(--link-color) 20%, transparent);
  font-size: 12px;
}

.rag-sources-header {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.rag-icon { font-size: 13px; }

.rag-source-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  color: var(--text-secondary);
}

.rag-source-index {
  font-weight: 700;
  color: var(--link-color);
  min-width: 20px;
}

.rag-source-kb {
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}

.rag-source-file {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}

.rag-source-score {
  font-size: 11px;
  color: #16a34a;
  background: rgba(22, 163, 74, 0.1);
  padding: 1px 6px;
  border-radius: 10px;
  white-space: nowrap;
}
.rag-file-icon { font-size: 13px; flex-shrink: 0; }

/* 输入框区域 */
.input-field {
  width: 100%;
}

/* 底部操作栏 */
.input-bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px 10px;
}

/* 左侧 + 按钮 */
.bar-plus-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1.5px solid rgba(0, 0, 0, 0.22);
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
  flex-shrink: 0;
}

.bar-plus-btn:hover {
  border-color: var(--text-primary);
  color: var(--text-primary);
}

/* 右侧容器 */
.bar-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 右侧功能图标按钮（mic / wave） */
.bar-action-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  cursor: pointer;
  border-radius: 6px;
  transition: color 0.2s;
  flex-shrink: 0;
}

.bar-action-btn:hover {
  color: var(--text-primary);
}

/* 波形图标（5根竖条） */
.wave-icon {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 14px;
}

.wave-icon span {
  width: 3px;
  border-radius: 2px;
  background: currentColor;
}

.wave-icon span:nth-child(1) { height: 6px; }
.wave-icon span:nth-child(2) { height: 10px; }
.wave-icon span:nth-child(3) { height: 14px; }
.wave-icon span:nth-child(4) { height: 10px; }
.wave-icon span:nth-child(5) { height: 6px; }

/* 圆形发送 / 正方形停止按钮 */
.send-icon-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--text-primary);
  color: var(--bg-primary);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
  transition: opacity 0.2s;
}

.send-icon-btn:hover:not(:disabled) {
  opacity: 0.78;
}

.send-icon-btn:disabled {
  background: var(--border-color);
  cursor: not-allowed;
}

.stop-square {
  width: 11px;
  height: 11px;
  background: var(--bg-primary);
  border-radius: 2px;
  flex-shrink: 0;
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

/* ─── 附件预览区 ─── */
.pending-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.attachment-item {
  position: relative;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-primary);
  flex-shrink: 0;
}

.attachment-thumb {
  display: block;
  width: 72px;
  height: 72px;
  object-fit: cover;
  cursor: pointer;
}

.attachment-file {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  max-width: 160px;
  min-height: 40px;
}

.attachment-file-icon {
  color: var(--link-color);
  font-size: 16px;
  flex-shrink: 0;
}

.attachment-name {
  font-size: 12px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}

.attachment-remove {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  padding: 0;
  line-height: 1;
  transition: background 0.2s;
}

.attachment-remove:hover {
  background: rgba(0, 0, 0, 0.8);
}

.attachment-uploading {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}

.upload-spinner {
  display: block;
  width: 22px;
  height: 22px;
  border: 3px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ─── 拖拽高亮 ─── */
.input-container.drag-active {
  border-color: var(--link-color);
  background: color-mix(in srgb, var(--link-color) 6%, var(--bg-primary));
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--link-color) 20%, transparent);
}

/* ─── 消息内图片展示 ─── */
.message-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.message-image-thumb {
  max-width: 240px;
  max-height: 200px;
  border-radius: 8px;
  object-fit: contain;
  cursor: pointer;
  border: 1px solid var(--border-color);
  transition: opacity 0.2s;
  display: block;
}

.message-image-thumb:hover {
  opacity: 0.85;
}

/* ─── 图片 Lightbox ─── */
.image-lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.82);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
}

.lightbox-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
  cursor: default;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
}

.lightbox-close {
  position: absolute;
  top: 20px;
  right: 24px;
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: #fff;
  font-size: 20px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.lightbox-close:hover {
  background: rgba(255, 255, 255, 0.3);
}

</style>