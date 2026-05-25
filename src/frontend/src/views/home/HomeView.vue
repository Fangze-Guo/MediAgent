<template>
  <div class="home-wrap">
      <div class="home-content">
            <div class="welcome">
              <img src="/MedWiser.png" alt="MedWiser" class="welcome-logo" />
              <h1 class="welcome-title">{{ t('views_HomeView.welcome') }}</h1>
              <p class="welcome-sub">{{ t('views_HomeView.subtitle') }}</p>
              <p class="welcome-desc">{{ t('views_HomeView.description') }}</p>
            </div>
      </div>
      <div class="home-footer">
          <div class="input-area">
            <div class="input-container">
              <div class="input-field">
                <textarea
                  v-model="draft"
                  class="message-input"
                  :placeholder="t('views_ChatView.inputPlaceholder')"
                  @keydown="handleKeyDown"
                  @input="adjustTextareaHeight"
                  rows="1"
                  ref="textareaRef"
                ></textarea>
              </div>
              <div class="input-bottom-bar">
                <button class="bar-plus-btn" title="附件">
                  <PlusOutlined />
                </button>
                <div class="bar-right">
                  <ModelSelector
                    :value="selectedModel"
                    @update:value="selectedModel = $event"
                  />
                  <button
                    v-if="draft.trim()"
                    class="send-icon-btn"
                    @click="startConversation"
                    :disabled="creating"
                  >
                    <ArrowUpOutlined />
                  </button>
                  <template v-else>
                    <button class="bar-action-btn" title="语音输入">
                      <AudioOutlined />
                    </button>
                    <button class="bar-action-btn" title="语音">
                      <span class="wave-icon"><span/><span/><span/><span/><span/></span>
                    </button>
                  </template>
                </div>
              </div>
            </div>
          </div>
      </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 首页组件
 * 提供应用介绍和快速开始对话的功能
 * 用户可以在首页输入初始消息直接开始聊天
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useConversationsStore } from '@/store/conversations'
import { useI18n } from 'vue-i18n'
import ModelSelector from '@/components/model/ModelSelector.vue'
import { ArrowUpOutlined, AudioOutlined, PlusOutlined } from '@ant-design/icons-vue'

// 路由相关
const router = useRouter()

// 国际化
const { t } = useI18n()

// 状态管理
const conversationsStore = useConversationsStore()

// 响应式数据
/** 用户输入的初始消息草稿 */
const draft = ref('')
/** 是否正在创建会话 */
const creating = ref(false)
/** 当前选择的模型 */
const selectedModel = ref('')
/** textarea 元素引用 */
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const adjustTextareaHeight = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

/**
 * 处理键盘快捷键
 * Enter: 发送消息
 * Ctrl+Enter / Shift+Enter: 换行
 */
const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Enter') {
    // Ctrl+Enter 或 Shift+Enter: 换行
    if (event.ctrlKey || event.shiftKey) {
      // 允许默认行为（换行）
      return
    }
    
    // 单独按 Enter: 发送消息
    event.preventDefault()
    startConversation()
  }
}

/**
 * 开始新对话
 * 根据用户输入创建新会话并跳转到聊天页面
 */
const startConversation = async () => {
  const text = draft.value.trim()

  // 验证输入和状态
  if (!text || creating.value) return

  creating.value = true
  try {
    // 创建新会话（调用后端API）
    const conv = await conversationsStore.createConversation()

    // 先启动流式发送：同步部分（appendMessage）立刻把消息写入 store
    // ChatView 加载后会看到 messages.length > 0，不会触发后端重载
    const streamPromise = conversationsStore.streamMessageToAgent(conv.id, text)

    // 立即跳转到对话页面，不等流式结束
    await router.push(`/conversation/${conv.id}`)

    // 流式输出继续在后台运行，ChatView 响应式展示 token
    streamPromise.catch(err => console.error('流式发送失败:', err))
  } catch (error) {
    console.error('创建会话失败:', error)
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
/* 外层容器：铺满整个内容区，背景与页面一致 */
.home-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
}

/* 内容区：垂直居中欢迎信息 */
.home-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.welcome {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.welcome-logo {
  width: 52px;
  height: 52px;
  object-fit: contain;
  border-radius: 50%;
  margin-bottom: 4px;
}

.welcome-title {
  margin: 0;
  font-size: 32px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.welcome-sub {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 14px;
}

.welcome-desc {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
  max-width: 680px;
}

/* 底部区域：背景与页面一致，无白底 */
.home-footer {
  background: var(--bg-secondary);
  padding: 0;
  flex-shrink: 0;
}

.input-area {
  max-width: 860px;
  margin: 0 auto;
  padding: 10px 16px 14px;
}

.input-container {
  width: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 18px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  background: var(--input-surface, #f5f5f5);
}

.input-container:focus-within {
  border-color: rgba(0, 0, 0, 0.18);
  box-shadow: 0 1px 8px rgba(0, 0, 0, 0.08);
}

.input-field {
  width: 100%;
}

.message-input {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-size: 15px;
  min-height: 52px;
  max-height: 200px;
  color: var(--text-primary);
  background: transparent;
  padding: 14px 16px 6px;
  line-height: 1.6;
}

.message-input::placeholder {
  color: var(--text-tertiary);
}

.input-bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px 10px;
}

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

.bar-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

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


</style>


