<template>
  <div class="home">
    <div class="hero">
      <h1 class="title">欢迎使用 MediAgent</h1>
      <p class="subtitle">输入你的问题，开始与您的助手对话</p>
      <div class="start-box">
        <a-textarea
          v-model:value="draft"
          :auto-size="{ minRows: 2, maxRows: 6 }"
          placeholder="例如：最近总是睡不着，怎么办？"
          class="start-input"
        />
        <a-button type="primary" class="start-btn" :loading="creating" @click="startConversation">开始对话</a-button>
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
.home { display: flex; width: 100%; height: 100%; align-items: center; justify-content: center; }
.hero { max-width: 720px; width: min(70%, 720px); text-align: center; }
.title { margin: 0 0 8px 0; font-size: 28px; color: #222; }
.subtitle { margin: 0 0 24px 0; color: #666; }
.start-box { display: flex; gap: 12px; align-items: flex-end; }
.start-input { flex: 1; }
.start-btn { white-space: nowrap; }
</style>


