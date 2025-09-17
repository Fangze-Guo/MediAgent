<template>
  <div class="message-item" :class="message.role">
    <!-- 用户和AI的头像 -->
    <div v-if="message.role !== 'user'" class="avatar ai-avatar" :class="getAssistantAvatarClass(message.assistantType)">
      <component :is="getAssistantIcon(message.assistantType)" />
      <!-- 助手类型标识 -->
      <div v-if="message.assistantType && message.assistantType !== 'general'" class="assistant-badge">
        {{ getAssistantLabel(message.assistantType) }}
      </div>
    </div>
    
    <div class="message-content">
      <!-- 解析并展示思考过程和回复内容 -->
      <div v-if="message.parsedContent">
        <!-- 多个思考过程 -->
        <div v-if="message.parsedContent.thinkingList && message.parsedContent.thinkingList.length > 0">
          <div v-for="(thinking, thinkingIdx) in message.parsedContent.thinkingList" :key="thinkingIdx"
               class="thinking-section">
            <div class="thinking-header">
              <a-icon type="bulb" />
              <span>思考过程 {{ message.parsedContent.thinkingList.length > 1 ? thinkingIdx + 1 : '' }}</span>
              <a-button type="text" size="small" @click="toggleThinking(thinkingIdx)"
                        class="toggle-thinking-btn">
                {{ message.showThinkingList && message.showThinkingList[thinkingIdx] ? '收起' : '展开' }}
              </a-button>
            </div>
            <!-- 思考内容 -->
            <div v-show="message.showThinkingList && message.showThinkingList[thinkingIdx]" class="thinking-content">
              {{ thinking }}
            </div>
          </div>
        </div>
        <!-- 回复内容 -->
        <div v-if="message.parsedContent.response" class="response-content">
          <MarkdownRenderer :content="message.parsedContent.response" />
        </div>
      </div>
      <!-- 原始内容（如果没有解析出思考过程） -->
      <div v-else>
        <MarkdownRenderer :content="message.content" />
      </div>
      
      <!-- 消息时间 -->
      <div v-if="message.timestamp" class="message-time">
        {{ formatTime(message.timestamp) }}
      </div>
    </div>
    
    <div v-if="message.role === 'user'" class="avatar user-avatar">
      <UserOutlined />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UserOutlined, RobotOutlined, MedicineBoxOutlined, BarChartOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import MarkdownRenderer from './MarkdownRenderer.vue'

// 定义消息类型
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: Date
  assistantType?: 'general' | 'medical' | 'data' | 'document'
  parsedContent?: {
    thinkingList?: string[]
    response?: string
  }
  showThinkingList?: boolean[]
}

// Props
const props = defineProps<{
  message: ChatMessage
}>()

// 思考过程展开状态
const showThinkingList = ref<boolean[]>([])

// 初始化思考过程展开状态
if (props.message.parsedContent?.thinkingList) {
  showThinkingList.value = new Array(props.message.parsedContent.thinkingList.length).fill(false)
}

/**
 * 获取助手图标
 */
const getAssistantIcon = (assistantType?: string) => {
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
 * 获取助手标签
 */
const getAssistantLabel = (assistantType?: string) => {
  switch (assistantType) {
    case 'medical':
      return '医学助手'
    case 'data':
      return '数据分析'
    case 'document':
      return '文档处理'
    default:
      return '通用助手'
  }
}

/**
 * 获取助手头像样式类
 */
const getAssistantAvatarClass = (assistantType?: string) => {
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
 * 切换思考过程显示
 */
const toggleThinking = (index: number) => {
  if (!showThinkingList.value[index]) {
    showThinkingList.value[index] = true
  } else {
    showThinkingList.value[index] = false
  }
}

/**
 * 格式化时间
 */
const formatTime = (timestamp: Date) => {
  return timestamp.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.message-item {
  display: flex;
  margin-bottom: 16px;
  align-items: flex-start;
  gap: 12px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-content {
  flex: 1;
  max-width: calc(100% - 60px);
}

.message-time {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

/* 头像样式 */
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
  flex-shrink: 0;
}

.user-avatar {
  background: #1890ff;
}

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

/* 思考过程样式 */
.thinking-section {
  margin-bottom: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: #f5f5f5;
  border-bottom: 1px solid #e8e8e8;
  font-size: 14px;
  font-weight: 500;
}

.thinking-header .anticon {
  margin-right: 6px;
  color: #1890ff;
}

.toggle-thinking-btn {
  margin-left: auto;
  padding: 0;
  height: auto;
  font-size: 12px;
}

.thinking-content {
  padding: 12px;
  background: white;
  font-size: 13px;
  line-height: 1.6;
  color: #666;
  white-space: pre-wrap;
}

.response-content {
  margin-top: 8px;
}
</style>