<template>
  <div v-if="isSearching" class="rag-progress">
    <span class="rag-progress-icon">🔍</span>
    <span class="rag-progress-title">正在检索知识库</span>
    <span class="dot-wave"><span></span><span></span><span></span></span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  items: { status: string }[]
}>()

const isSearching = computed(() => props.items.some(i => i.status === 'searching'))
</script>

<style scoped>
.rag-progress {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  margin-bottom: 8px;
  background: color-mix(in srgb, var(--link-color, #1890ff) 6%, var(--bg-primary, #fff));
  border: 1px solid color-mix(in srgb, var(--link-color, #1890ff) 18%, transparent);
  border-radius: 16px;
  font-size: 12px;
  color: var(--link-color, #1890ff);
}

.rag-progress-icon { font-size: 12px; }
.rag-progress-title { font-weight: 500; }

/* 三点波动动画 */
.dot-wave {
  display: inline-flex;
  gap: 2px;
  align-items: center;
}

.dot-wave span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
  animation: dot-bounce 1.2s infinite ease-in-out;
}

.dot-wave span:nth-child(2) { animation-delay: 0.2s; }
.dot-wave span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40%           { transform: scale(1);   opacity: 1; }
}
</style>
