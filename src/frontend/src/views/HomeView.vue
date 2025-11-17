<template>
  <div class="home">
    <div class="hero">
      <h1 class="title">{{ t('views_HomeView.welcome') }}</h1>
      <p class="subtitle">{{ t('views_HomeView.subtitle') }}</p>
      <div class="start-box">
        <a-textarea
            v-model:value="draft"
            :auto-size="{ minRows: 2, maxRows: 6 }"
            :placeholder="t('views_HomeView.placeholder')"
            class="start-input"
        />
        <a-button type="primary" class="start-btn" :loading="creating" @click="startConversation">{{ t('views_HomeView.startConversation') }}</a-button>
      </div>
      <!-- 技能按钮区域 -->
      <div class="skills-container">
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">{{ t('views_HomeView.programming') }}</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">{{ t('views_HomeView.writing') }}</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">{{ t('views_HomeView.imageGen') }}</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">{{ t('views_HomeView.musicGen') }}</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">{{ t('views_HomeView.translation') }}</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">{{ t('views_HomeView.ppt') }}</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">{{ t('views_HomeView.uploadFiles') }}</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">{{ t('views_HomeView.more') }}</span>
        </a-button>
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
    
    // 发送初始消息到Agent
    await conversationsStore.sendMessageToAgent(conv.id, text)
    
    // 注意：不需要再次加载会话内容，因为sendMessageToAgent已经处理了消息
    // await conversationsStore.loadConversationMessages(conv.id)

    // 跳转到对话页面
    await router.push(`/conversation/${conv.id}`)
  } catch (error) {
    console.error('创建会话失败:', error)
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.home {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.title {
  margin: 0 0 8px 0;
  font-size: 28px;
  color: #222;
}

.subtitle {
  margin: 0 0 24px 0;
  color: #666;
}

.start-box {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.start-input {
  flex: 1;
}

.start-btn {
  white-space: nowrap;
}

.skills-container {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  margin-top: 40px;
}

.skill-btn {
  padding: 12px 20px;
  border-radius: 24px;
  font-size: 14px;
  border: 1px solid #e0e0e0;
  background-color: white;
  color: #666;
  transition: all 0.2s ease;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
}

.skill-btn:hover {
  background-color: #f5f5f5;
  border-color: #d9d9d9;
}

.skill-icon {
  margin-right: 8px;
  font-size: 16px;
  display: flex;
  align-items: center;
}
</style>


