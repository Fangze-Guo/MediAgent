<template>
  <div class="medical-consultation-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2 class="page-title">
        <CommentOutlined />
        {{ t('views_MedicalConsultationView.title') }}
      </h2>
    </div>

    <!-- 主要内容区域 -->
    <div class="content-grid">
      <!-- 左侧：对话列表 -->
      <div class="conversation-list-section">
        <a-card>
          <template #title>
            <div class="card-title-row">
              <span>{{ t('views_MedicalConsultationView.conversationList') }}</span>
              <a-button type="primary" size="small" @click="handleNewConsultation">
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
              :key="conversation.id"
              class="conversation-item"
              :class="{ active: selectedConversation?.id === conversation.id }"
              @click="selectConversation(conversation)"
            >
              <div class="conversation-header">
                <span class="patient-name">{{ conversation.patientName }}</span>
                <span class="conversation-time">{{ conversation.time }}</span>
              </div>
              <p class="conversation-preview">{{ conversation.preview }}</p>
            </div>
          </div>
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
              {{ selectedConversation.patientName }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_MedicalConsultationView.gender')">
              {{ selectedConversation.gender }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_MedicalConsultationView.age')">
              {{ selectedConversation.age }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_MedicalConsultationView.consultationTime')">
              {{ selectedConversation.time }}
            </a-descriptions-item>
          </a-descriptions>

          <!-- 对话内容区域 -->
          <div class="messages-container">
            <div
              v-for="(message, index) in selectedConversation.messages"
              :key="index"
              class="message-wrapper"
              :class="message.sender === 'patient' ? 'message-right' : 'message-left'"
            >
              <div class="message-header">
                <span class="message-sender">{{ getSenderName(message.sender) }}</span>
                <span class="message-time">{{ message.time }}</span>
              </div>
              <div class="message-bubble" :class="message.sender === 'patient' ? 'bubble-patient' : 'bubble-ai'">
                <p v-if="message.text" class="message-text">{{ message.text }}</p>
                <ul v-if="message.list" class="message-list">
                  <li v-for="(item, idx) in message.list" :key="idx">{{ item }}</li>
                </ul>
                <div v-if="message.tags" class="message-tags">
                  <div
                    v-for="(tag, idx) in message.tags"
                    :key="idx"
                    class="tag-item"
                  >
                    <a-tag color="blue" class="message-tag">
                      {{ tag.label }}
                    </a-tag>
                    <span v-if="tag.description" class="tag-description">
                      {{ tag.description }}
                    </span>
                  </div>
                </div>
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
              />
              <a-button type="primary" @click="handleSendMessage" :loading="sendingMessage">
                <template #icon>
                  <SendOutlined />
                </template>
                {{ t('views_MedicalConsultationView.send') }}
              </a-button>
            </div>
            <div class="input-actions">
              <a-button type="link" size="small" @click="handleUploadImage">
                <template #icon>
                  <UploadOutlined />
                </template>
                {{ t('views_MedicalConsultationView.uploadImage') }}
              </a-button>
              <a-button type="link" size="small" @click="handleUploadReport">
                <template #icon>
                  <FileTextOutlined />
                </template>
                {{ t('views_MedicalConsultationView.uploadReport') }}
              </a-button>
            </div>
          </div>
        </a-card>

        <!-- 空状态 -->
        <a-empty
          v-else
          :description="t('views_MedicalConsultationView.selectConversation')"
          class="empty-state"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  CommentOutlined,
  PlusOutlined,
  SendOutlined,
  UploadOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'
import type { ChatMessage } from '@/apis/medicalConsultation'
import { streamChat, parseStreamResponse } from '@/apis/medicalConsultation'

const { t } = useI18n()

// 搜索关键词
const searchKeyword = ref('')

// 输入消息
const inputMessage = ref('')

// 发送消息加载状态
const sendingMessage = ref(false)

// 对话列表数据
interface Conversation {
  id: number
  patientName: string
  gender: string
  age: string
  time: string
  preview: string
  messages: Array<{
    sender: 'patient' | 'ai'
    time: string
    text?: string
    list?: string[]
    tags?: Array<{ label: string; description?: string }>
  }>
}

const conversations = ref<Conversation[]>([])

// 当前选中的对话
const selectedConversation = ref<Conversation | null>(null)

// 过滤后的对话列表
const filteredConversations = computed(() => {
  if (!searchKeyword.value) {
    return conversations.value
  }
  const keyword = searchKeyword.value.toLowerCase()
  return conversations.value.filter(
    conv =>
      conv.patientName.toLowerCase().includes(keyword) ||
      conv.preview.toLowerCase().includes(keyword)
  )
})

// 选择对话
const selectConversation = (conversation: Conversation) => {
  selectedConversation.value = conversation
}

// 新建咨询
const handleNewConsultation = () => {
  // 静态页面，仅展示
  console.log('新建咨询')
}

// 搜索
const handleSearch = () => {
  // 静态页面，仅展示
  console.log('搜索:', searchKeyword.value)
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
  const userMsg = {
    sender: 'patient' as const,
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    text: userMessage
  }
  selectedConversation.value.messages.push(userMsg)

  // 添加 AI 消息占位符
  const aiMsgIndex = selectedConversation.value.messages.length
  selectedConversation.value.messages.push({
    sender: 'ai' as const,
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    text: ''
  })

  // 准备请求数据：将历史消息转换为 API 格式（排除刚添加的用户消息和空的 AI 占位符）
  const historyMessages: ChatMessage[] = selectedConversation.value.messages
    .slice(0, -2) // 排除刚添加的用户消息和 AI 占位符
    .filter(msg => msg.text) // 只保留有内容的消息
    .map(msg => ({
      role: (msg.sender === 'patient' ? 'user' : 'assistant') as 'user' | 'assistant',
      content: msg.text || ''
    }))

  try {
    // 调用流式接口
    const stream = await streamChat({
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
        if (selectedConversation.value) {
          selectedConversation.value.messages[aiMsgIndex].text = fullContent
        }
      },
      // onComplete: 完成
      (finalContent) => {
        if (selectedConversation.value) {
          selectedConversation.value.messages[aiMsgIndex].text = finalContent
        }
      },
      // onError: 错误处理
      (error) => {
        console.error('流式对话错误:', error)
        if (selectedConversation.value) {
          selectedConversation.value.messages[aiMsgIndex].text = `错误: ${error}`
        }
      }
    )
  } catch (error) {
      console.error('发送消息失败:', error)
      if (selectedConversation.value) {
        selectedConversation.value.messages[aiMsgIndex].text = '发送消息失败，请重试'
      }
    } finally {
      sendingMessage.value = false
    }
  }

// 上传影像
const handleUploadImage = () => {
  // 静态页面，仅展示
  console.log('上传影像')
}

// 上传报告
const handleUploadReport = () => {
  // 静态页面，仅展示
  console.log('上传报告')
}

// 获取发送者名称
const getSenderName = (sender: string) => {
  return sender === 'patient' ? t('views_MedicalConsultationView.patient') : t('views_MedicalConsultationView.aiAssistant')
}
</script>

<style scoped>
.medical-consultation-container {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
}

.page-header {
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
}

.conversation-list-section {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.conversation-detail-section {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.search-input {
  margin-bottom: 16px;
}

.conversation-list {
  max-height: 600px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.conversation-item {
  padding: 12px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
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
}

.patient-name {
  font-weight: 500;
  color: #333;
}

.conversation-time {
  font-size: 12px;
  color: #999;
}

.conversation-preview {
  font-size: 14px;
  color: #666;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.patient-info {
  margin-bottom: 24px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.message-wrapper {
  display: flex;
  flex-direction: column;
  max-width: 70%;
}

.message-left {
  align-self: flex-start;
}

.message-right {
  align-self: flex-end;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
}

.message-left .message-header {
  flex-direction: row;
}

.message-right .message-header {
  flex-direction: row-reverse;
}

.message-sender {
  font-weight: 500;
  color: #666;
}

.message-time {
  color: #999;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 8px;
  word-wrap: break-word;
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
}

.message-list {
  margin: 8px 0 0 0;
  padding-left: 20px;
  color: #333;
  line-height: 1.8;
}

.message-tags {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tag-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.message-tag {
  margin: 0;
}

.tag-description {
  font-size: 12px;
  color: #666;
}

.input-area {
  border-top: 1px solid #d9d9d9;
  padding-top: 16px;
  margin-top: 16px;
}

.input-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.message-input {
  flex: 1;
}

.input-actions {
  display: flex;
  gap: 16px;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

  .message-wrapper {
    max-width: 85%;
  }
}
</style>
