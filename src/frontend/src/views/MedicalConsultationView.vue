<template>
  <div class="medical-consultation-container">
    <!-- 主要内容区域 -->
    <div class="content-grid">
      <!-- 左侧：对话列表 -->
      <div class="conversation-list-section">
        <a-card :loading="loadingConversations" class="list-card">
          <template #title>
            <div class="card-title-row">
              <span>{{ t('views_MedicalConsultationView.conversationList') }}</span>
              <a-button type="primary" size="small" @click="showNewConversationModal">
                <template #icon>
                  <PlusOutlined />
                </template>
                {{ t('views_MedicalConsultationView.newConsultation') }}
              </a-button>
            </div>
          </template>

          <!-- 搜索框 -->
          <a-input-search
            v-model:value="searchKeyword"
            :placeholder="t('views_MedicalConsultationView.searchPlaceholder')"
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
                  {{ conversation.title || conversation.patient_name || '未命名会话' }}
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
            :description="t('views_MedicalConsultationView.noConversations')"
            class="empty-state"
          />
        </a-card>
      </div>

      <!-- 右侧：对话详情 -->
      <div class="conversation-detail-section">
        <a-card v-if="selectedConversation" class="detail-card">
          <!-- 患者信息卡片 -->
          <a-descriptions
            :title="t('views_MedicalConsultationView.patientInfo')"
            bordered
            :column="2"
            size="small"
            class="patient-info"
          >
            <a-descriptions-item :label="t('views_MedicalConsultationView.patientName')">
              {{ selectedConversation.patient_name || '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_MedicalConsultationView.gender')">
              {{ selectedConversation.gender || '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_MedicalConsultationView.age')">
              {{ selectedConversation.age || '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_MedicalConsultationView.consultationTime')">
              {{ formatTime(selectedConversation.created_at) }}
            </a-descriptions-item>
          </a-descriptions>

          <!-- 对话内容区域 -->
          <div class="messages-container" ref="messagesContainer">
            <div
              v-for="(message, index) in messages"
              :key="index"
              class="message-wrapper"
              :class="message.role === 'user' ? 'message-right' : 'message-left'"
            >
              <div class="message-header">
                <span class="message-sender">
                  {{ message.role === 'user' ? t('views_MedicalConsultationView.patient') : t('views_MedicalConsultationView.aiAssistant') }}
                </span>
                <span class="message-time">{{ formatTime(message.created_at) }}</span>
              </div>
              <div class="message-bubble" :class="message.role === 'user' ? 'bubble-patient' : 'bubble-ai'">
                <p class="message-text">{{ message.content }}</p>
              </div>
            </div>
          </div>

          <!-- 输入区域 -->
          <div class="input-area">
            <div class="input-row">
              <a-input
                v-model:value="inputMessage"
                :placeholder="t('views_MedicalConsultationView.inputPlaceholder')"
                allow-clear
                class="message-input"
                @press-enter="handleSendMessage"
                :disabled="sendingMessage"
              />
              <a-button type="primary" @click="handleSendMessage" :loading="sendingMessage">
                <template #icon>
                  <SendOutlined />
                </template>
                {{ t('views_MedicalConsultationView.send') }}
              </a-button>
            </div>
          </div>
        </a-card>

        <!-- 空状态 -->
        <a-empty
          v-else-if="!loadingConversations"
          :description="t('views_MedicalConsultationView.selectConversation')"
          class="empty-state"
        />
      </div>
    </div>

    <!-- 新建会话模态框 -->
    <a-modal
      v-model:open="newConversationModalVisible"
      :title="t('views_MedicalConsultationView.newConsultation')"
      @ok="handleCreateConversation"
      :confirm-loading="creatingConversation"
    >
      <a-form :model="newConversationForm" layout="vertical">
        <a-form-item :label="t('views_MedicalConsultationView.title')">
          <a-input v-model:value="newConversationForm.title" />
        </a-form-item>
        <a-form-item :label="t('views_MedicalConsultationView.patientName')">
          <a-input v-model:value="newConversationForm.patient_name" />
        </a-form-item>
        <a-form-item :label="t('views_MedicalConsultationView.gender')">
          <a-select v-model:value="newConversationForm.gender" allow-clear>
            <a-select-option value="男">{{ t('views_MedicalConsultationView.male') }}</a-select-option>
            <a-select-option value="女">{{ t('views_MedicalConsultationView.female') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('views_MedicalConsultationView.age')">
          <a-input v-model:value="newConversationForm.age" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  CommentOutlined,
  PlusOutlined,
  SendOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import type {
  ChatMessage,
  ConversationInfo,
  ConversationDetail,
  MessageResponse,
  CreateConversationRequest
} from '@/apis/medicalConsultation'
import {
  streamChat,
  parseStreamResponse,
  getConversations,
  getConversationDetail,
  createConversation,
  deleteConversation
} from '@/apis/medicalConsultation'

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

// 消息容器引用
const messagesContainer = ref<HTMLElement | null>(null)

// 新建会话模态框显示状态
const newConversationModalVisible = ref(false)

// 新建会话表单
const newConversationForm = ref<CreateConversationRequest>({
  title: '',
  patient_name: '',
  gender: '',
  age: ''
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
      (conv.patient_name && conv.patient_name.toLowerCase().includes(keyword)) ||
      (conv.last_message && conv.last_message.toLowerCase().includes(keyword))
  )
})

// 加载对话列表
const loadConversations = async () => {
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
  selectedConversationId.value = conversation.conversation_id
  selectedConversation.value = conversation

  // 加载会话详情和消息
  loadingConversations.value = true
  try {
    const response = await getConversationDetail(conversation.conversation_id)
    if (response.code === 200 && response.data) {
      messages.value = response.data.messages || []
      scrollToBottom()
    } else {
      message.error(response.message || '加载会话详情失败')
    }
  } catch (error) {
    console.error('加载会话详情失败:', error)
    message.error('加载会话详情失败')
  } finally {
    loadingConversations.value = false
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
    title: '',
    patient_name: '',
    gender: '',
    age: ''
  }
}

// 创建新会话
const handleCreateConversation = async () => {
  if (!newConversationForm.value.title && !newConversationForm.value.patient_name) {
    message.warning('请填写会话标题或患者姓名')
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
    // 添加 AI 消息占位符
    const aiMsgIndex = messages.value.length
    messages.value.push({
      message_id: '',
      conversation_id: selectedConversation.value!.conversation_id,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    })

    // 调用流式接口
    const stream = await streamChat({
      conversation_id: selectedConversation.value!.conversation_id,
      messages: historyMessages,
      message: userMessage
    })

    if (!stream) {
      throw new Error('无法建立流式连接')
    }

    const reader = stream.getReader()
    let fullContent = ''

    await parseStreamResponse(
      reader,
      // onChunk: 接收到每个 chunk
      (data) => {
        fullContent = data.full_content
        // 更新 AI 消息内容
        if (messages.value[aiMsgIndex]) {
          messages.value[aiMsgIndex].content = fullContent
          scrollToBottom()
        }
      },
      // onComplete: 完成
      (finalContent) => {
        if (messages.value[aiMsgIndex]) {
          messages.value[aiMsgIndex].content = finalContent
        }
        // 更新会话的最后消息
        if (selectedConversation.value) {
          selectedConversation.value.last_message = finalContent
        }
        scrollToBottom()
      },
      // onError: 错误处理
      (error) => {
        console.error('流式对话错误:', error)
        if (messages.value[aiMsgIndex]) {
          messages.value[aiMsgIndex].content = `错误: ${error}`
        }
      }
    )
  } catch (error) {
    console.error('发送消息失败:', error)
    message.error('发送消息失败，请重试')
    // 移除失败的AI消息
    messages.value.pop()
  } finally {
    sendingMessage.value = false
  }
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
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
</script>

<style scoped>
/* ==========================================
   1. 整体页面布局
========================================== */
.medical-consultation-container {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
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
  grid-template-columns: 1fr 2fr;
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
}

.list-card {
  height: 100%;
  display: flex;
  flex-direction: column;
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
}

.conversation-item {
  padding: 12px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
  flex-shrink: 0;
  min-width: 0;
}

.conversation-item:hover {
  background-color: #f5f5f5;
  border-color: #40a9ff;
}

.conversation-item.active {
  background-color: #e6f7ff;
  border-color: #1890ff;
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
}

.detail-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
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
  flex-shrink: 0;
  margin: 16px 16px 0 16px;
  padding-bottom: 16px;
  max-height: 200px;
  overflow-y: auto;
  border-bottom: 1px solid #e8e8e8;
}

/* ==========================================
   4. 右侧：聊天气泡与消息区
========================================== */
.messages-container {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: #fafafa;
  padding: 16px;
  scroll-behavior: smooth;
  min-height: 0;
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

.message-sender { font-weight: 500; color: #666; }
.message-time { color: #999; flex-shrink: 0; }

.message-bubble {
  padding: 12px 16px;
  border-radius: 8px;
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;
  max-width: 100%;
}

.bubble-patient {
  background-color: #e6f7ff;
  border: 1px solid #91d5ff;
}

.bubble-ai {
  background-color: #fff;
  border: 1px solid #d9d9d9;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.message-text {
  margin: 0;
  color: #333;
  line-height: 1.6;
  white-space: pre-wrap;
}

/* ==========================================
   5. 右侧：输入框与通用状态
========================================== */
.input-area {
  flex-shrink: 0;
  border-top: 1px solid #d9d9d9;
  padding: 16px;
  background: #fff;
  margin-top: 16px;
}

.input-row {
  display: flex;
  gap: 8px;
}

.message-input { flex: 1; }
.input-actions { display: flex; gap: 16px; }

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
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
  .medical-consultation-container { padding: 20px; }
  .content-grid { gap: 20px; }
}

@media (max-width: 1200px) {
  .medical-consultation-container { padding: 16px; }
  .content-grid { gap: 16px; }
  .message-wrapper { max-width: 85%; }
}

@media (max-width: 768px) {
  .medical-consultation-container { padding: 12px; }
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
  .medical-consultation-container { padding: 8px; }
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
