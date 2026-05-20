<template>
  <div v-if="items.length" class="rag-progress">
    <div class="rag-progress-header">
      <span class="rag-progress-icon">🔍</span>
      <span class="rag-progress-title">检索知识库</span>
    </div>
    <div v-for="item in items" :key="item.kb_id" class="rag-progress-item">
      <span class="rag-progress-kb">{{ item.kb }}</span>
      <span v-if="item.status === 'searching'" class="rag-progress-status searching">
        <span class="dot-wave"><span></span><span></span><span></span></span>
        搜索中
      </span>
      <span v-else-if="item.found! > 0" class="rag-progress-status found">
        ✓ {{ item.found }} 篇
      </span>
      <span v-else class="rag-progress-status empty">
        — 无相关
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SearchProgressItem } from '@/store/conversations'

defineProps<{
  items: SearchProgressItem[]
}>()
</script>

<style scoped>
.rag-progress {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  margin-bottom: 8px;
  background: color-mix(in srgb, var(--link-color, #1890ff) 6%, var(--bg-primary, #fff));
  border: 1px solid color-mix(in srgb, var(--link-color, #1890ff) 18%, transparent);
  border-radius: 8px;
  font-size: 12px;
}

.rag-progress-header {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: 600;
  color: var(--text-secondary, #666);
  margin-bottom: 2px;
}

.rag-progress-icon { font-size: 13px; }

.rag-progress-title { font-size: 12px; }

.rag-progress-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 0 2px 18px;
  color: var(--text-primary, #333);
}

.rag-progress-kb {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 8px;
}

.rag-progress-status {
  white-space: nowrap;
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 3px;
}

.rag-progress-status.searching {
  color: var(--link-color, #1890ff);
}

.rag-progress-status.found {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.1);
  padding: 1px 6px;
  border-radius: 10px;
}

.rag-progress-status.empty {
  color: var(--text-secondary, #999);
}

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
