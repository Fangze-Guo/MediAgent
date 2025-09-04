<template>
  <div class="home">
    <div class="hero">
      <h1 class="title">欢迎使用 MediAgent</h1>
      <p class="subtitle">输入你的问题，开始与你的健康助手对话</p>
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
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createConversation } from '@/store/conversations'

const router = useRouter()
const draft = ref('')
const creating = ref(false)

const startConversation = async () => {
  const text = draft.value.trim()
  if (!text || creating.value) return
  creating.value = true
  try {
    const conv = createConversation(text)
    await router.push(`/chat/${conv.id}`)
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


