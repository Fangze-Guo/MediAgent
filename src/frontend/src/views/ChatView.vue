<template>
  <div class="chat-bg">
    <div class="chat-fixed">
      <a-layout class="chat-layout">
        <a-layout-header class="chat-header">
          <div class="header-left">
            <h2 class="chat-title">{{ currentConversation?.title || '新对话' }}</h2>
          </div>
          <div class="header-right">
            <a-button size="small" @click="createNewConversation" :loading="sending">新建对话</a-button>
          </div>
        </a-layout-header>
        <div class="history-bar" v-if="conversations.length > 0">
          <div
            v-for="c in conversations"
            :key="c.id"
            :class="['history-item', { active: c.id === activeId }]"
            @click="activeId = c.id"
          >
            {{ c.title || c.id }}
          </div>
        </div>
        <a-layout-content class="chat-messages" ref="messagesEl">
          <div 
            v-for="(m, idx) in currentMessages" 
            :key="idx"
            :class="['message', m.role === 'user' ? 'user' : 'ai']"
          >
            <div v-if="m.role !== 'user'" class="avatar ai-avatar">
              <a-icon type="robot" />
            </div>
            <div class="message-content">{{ m.content }}</div>
            <div v-if="m.role === 'user'" class="avatar user-avatar">
              <a-icon type="user" />
            </div>
          </div>
        </a-layout-content>
        <a-layout-footer class="chat-input">
          <a-textarea 
            v-model:value="inputMessage"
            class="message-input"
            placeholder="输入消息，按 Enter 换行"
            :auto-size="{ minRows: 1, maxRows: 6 }"
          />
          <a-button 
            type="primary" 
            class="send-btn"
            :loading="sending"
            @click="sendMessage"
          >
            发送
          </a-button>
        </a-layout-footer>
      </a-layout>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, computed, watch } from 'vue'
import { chat as chatApi } from '@/apis/chat'

type ChatMessage = { role: 'user' | 'assistant'; content: string }
type Conversation = { id: string; title: string; messages: ChatMessage[] }

import { useRoute, useRouter } from 'vue-router'
import { conversations as convList, getConversation, createConversation, appendMessage } from '@/store/conversations'

const route = useRoute()
const router = useRouter()
const inputMessage = ref('')
const sending = ref(false)
const activeId = ref<string>('')
const messagesEl = ref<HTMLElement | null>(null)
const conversations = convList

const scrollToBottom = async () => {
  await nextTick()
  const el = messagesEl.value
  if (el) el.scrollTop = el.scrollHeight
}

const currentConversation = computed(() => getConversation(activeId.value) || null)
const currentMessages = computed<ChatMessage[]>(() => currentConversation.value?.messages || [])

const createNewConversation = () => {
  const conv = createConversation()
  activeId.value = conv.id
  router.replace({ name: 'Chat', params: { id: conv.id } })
}

// 根据路由参数加载/创建会话
const routeId = (route.params.id as string | undefined) || ''
if (routeId && getConversation(routeId)) {
  activeId.value = routeId
} else {
  createNewConversation()
}

watch(() => route.params.id, (val) => {
  const id = String(val || '')
  if (id && id !== activeId.value) {
    activeId.value = id
  }
})

const sendMessage = async () => {
  const text = inputMessage.value.trim()
  if (!text || sending.value) return
  inputMessage.value = ''
  if (!currentConversation.value) createNewConversation()
  appendMessage(currentConversation.value!.id, { role: 'user', content: text })
  await scrollToBottom()
  sending.value = true
  try {
    const data = await chatApi({
      conversation_id: currentConversation.value!.id,
      message: text,
      history: currentMessages.value.map(m => ({ role: m.role, content: m.content }))
    })
    appendMessage(currentConversation.value!.id, { role: 'assistant', content: data.answer ?? '' })
  } catch (e) {
    appendMessage(currentConversation.value!.id, { role: 'assistant', content: '抱歉，请求失败，请稍后再试。' })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
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
.header-right { display: flex; gap: 8px; }

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
  gap: 12px;
  align-items: flex-end;
  padding: 16px 24px;
  background: white;
  border-top: 1px solid #f0f0f0;
}

/* 文本域：占满剩余空间，支持自适应高度 */
.message-input {
  flex: 1;
}

/* 发送按钮：避免换行 */
.send-btn {
  white-space: nowrap;
}
</style>