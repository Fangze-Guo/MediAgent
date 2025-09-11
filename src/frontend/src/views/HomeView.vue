<template>
  <div class="home">
    <div class="hero">
      <h1 class="title">欢迎使用 MediAgent</h1>
      <p class="subtitle">输入你的问题，开始与您的助手对话</p>
      <div class="start-box">
        <a-textarea
            v-model:value="draft"
            :auto-size="{ minRows: 2, maxRows: 6 }"
            placeholder="发消息或选择技能"
            class="start-input"
        />
        <a-button type="primary" class="start-btn" :loading="creating" @click="startConversation">开始对话</a-button>
      </div>
      <!-- 技能按钮区域 -->
      <div class="skills-container">
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">💻 编程</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">✍️ 帮我写作</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">🖼️ 图像生成</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">🎵 音乐生成</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">🔄 翻译</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">📊 PPT</span>
        </a-button>
        <a-button type="default" class="skill-btn">
          <span class="skill-icon">➕</span> 更多
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

// 路由相关
const router = useRouter()

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
    // 创建新会话，使用用户输入作为初始消息
    const conv = conversationsStore.createConversation(text)

    // 跳转到聊天页面
    await router.push(`/chat/${conv.id}`)
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


