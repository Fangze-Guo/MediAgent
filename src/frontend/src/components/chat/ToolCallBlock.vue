<template>
  <div class="tool-call-block">
    <div class="tool-call-header" @click="toggle">
      <span class="tool-icon">🔍</span>
      <span class="tool-name">{{ displayName }}</span>
      <span v-if="item.status === 'running'" class="dot-wave">
        <span></span><span></span><span></span>
      </span>
      <template v-else>
        <span class="chevron" :class="{ rotated: localExpanded }">›</span>
      </template>
    </div>
    <div v-if="localExpanded && item.status === 'done'" class="tool-call-body">
      <div class="tool-call-divider" />
      <div v-if="item.query" class="tool-call-row">
        <span class="tc-label">查询</span>
        <span class="tc-value">{{ item.query }}</span>
      </div>
      <div class="tool-call-row">
        <span class="tc-icon done">✓</span>
        <span class="tc-value">{{ item.found ? `找到 ${item.found} 个相关片段` : '未找到相关内容' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCallItem } from '@/store/conversations'

const props = defineProps<{ item: ToolCallItem }>()

const localExpanded = ref(false)

const displayName = computed(() => {
  const nameMap: Record<string, string> = {
    search_knowledge_base: '搜索知识库',
  }
  return nameMap[props.item.name] ?? props.item.name
})

function toggle() {
  if (props.item.status === 'done') localExpanded.value = !localExpanded.value
}
</script>

<style scoped>
.tool-call-block {
  display: inline-flex;
  flex-direction: column;
  margin-bottom: 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-secondary, #f9fafb);
  font-size: 13px;
  overflow: hidden;
  max-width: 360px;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  cursor: pointer;
  user-select: none;
  color: var(--text-secondary, #6b7280);
}

.tool-call-header:hover {
  background: var(--hover-bg, #f3f4f6);
}

.tool-icon { font-size: 13px; }

.tool-name {
  font-weight: 500;
  color: var(--text-primary, #111827);
}

.chevron {
  margin-left: auto;
  font-size: 16px;
  line-height: 1;
  transform: rotate(90deg);
  transition: transform 0.18s ease;
  color: var(--text-tertiary, #9ca3af);
}
.chevron.rotated { transform: rotate(270deg); }

.tool-call-body {
  padding: 0 12px 10px;
}

.tool-call-divider {
  height: 1px;
  background: var(--border-color, #e5e7eb);
  margin: 0 0 8px;
}

.tool-call-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 4px;
}

.tc-label {
  font-size: 11px;
  color: var(--text-tertiary, #9ca3af);
  min-width: 28px;
  padding-top: 1px;
}

.tc-value {
  color: var(--text-secondary, #4b5563);
  line-height: 1.5;
  word-break: break-all;
}

.tc-icon.done {
  color: #22c55e;
  font-size: 13px;
  min-width: 14px;
}

/* 运行中三点动画 */
.dot-wave {
  display: inline-flex;
  gap: 3px;
  align-items: center;
  margin-left: 4px;
}
.dot-wave span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-tertiary, #9ca3af);
  animation: dot-bounce 1.2s infinite ease-in-out;
}
.dot-wave span:nth-child(2) { animation-delay: 0.2s; }
.dot-wave span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40%           { transform: scale(1);   opacity: 1; }
}
</style>
