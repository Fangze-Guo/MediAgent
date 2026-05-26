<template>
  <div class="ksb-wrapper">
    <!-- Header toggle -->
    <div class="ksb-header" @click="expanded = !expanded">
      <span class="ksb-header-text">Searched knowledge base</span>
      <span v-if="items.some(i => i.status === 'running')" class="ksb-running">
        <span></span><span></span><span></span>
      </span>
      <span v-else class="ksb-chevron" :class="{ open: expanded }">›</span>
    </div>

    <!-- Each search group -->
    <div v-if="expanded" class="ksb-body">
      <div v-for="(item, i) in items" :key="i" class="ksb-group">
        <!-- Query row -->
        <div class="ksb-query-row">
          <span class="ksb-icon">📚</span>
          <span class="ksb-query-text">{{ item.query || item.inputSummary }}</span>
          <span v-if="item.found !== undefined" class="ksb-count">{{ item.found }} 个片段</span>
          <span v-else-if="item.status === 'done'" class="ksb-count">完成</span>
        </div>

        <!-- Source snippets (only on last / done item) -->
        <div v-if="item.status === 'done' && sources?.length && i === items.length - 1" class="ksb-results">
          <div v-for="(s, si) in sources" :key="si" class="ksb-source-item">
            <div class="ksb-source-meta">
              <span class="ksb-file-icon">{{ getFileEmoji(s.file_name) }}</span>
              <span class="ksb-source-name">{{ s.file_name || s.kb_name }}</span>
              <span class="ksb-source-kb">{{ s.kb_name }}</span>
            </div>
            <div class="ksb-source-content">{{ s.content }}</div>
          </div>
        </div>
      </div>

      <!-- Done footer -->
      <div class="ksb-done">
        <span class="ksb-done-icon">✓</span>
        <span>Done</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { ToolCallItem } from '@/store/conversations'
import type { RagSource } from '@/apis/conversation'

defineProps<{ items: ToolCallItem[]; sources?: RagSource[] }>()

const expanded = ref(false)

function getFileEmoji(filename?: string): string {
  if (!filename) return '📄'
  const ext = filename.toLowerCase()
  if (ext.endsWith('.pdf')) return '📕'
  if (ext.endsWith('.xlsx') || ext.endsWith('.xls')) return '📗'
  if (ext.endsWith('.docx') || ext.endsWith('.doc')) return '📘'
  return '📄'
}
</script>

<style scoped>
.ksb-wrapper {
  margin-bottom: 10px;
  font-size: 13px;
}

.ksb-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 0;
  cursor: pointer;
  color: var(--text-secondary, #6b7280);
  user-select: none;
}
.ksb-header:hover { color: var(--text-primary, #111827); }
.ksb-header-text { font-size: 14px; color: var(--text-secondary, #6b7280); }
.ksb-chevron {
  font-size: 14px;
  line-height: 1;
  transform: rotate(90deg);
  transition: transform 0.18s ease;
  display: inline-block;
}
.ksb-chevron.open { transform: rotate(270deg); }

.ksb-body {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ksb-group {
  display: flex;
  flex-direction: column;
}

.ksb-query-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ksb-icon { font-size: 14px; flex-shrink: 0; }
.ksb-query-text {
  flex: 1;
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
}
.ksb-count {
  font-size: 11px;
  color: var(--text-tertiary, #9ca3af);
  white-space: nowrap;
}

.ksb-running {
  display: inline-flex;
  gap: 3px;
  align-items: center;
}
.ksb-running span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-tertiary, #9ca3af);
  animation: dot-bounce 1.2s infinite ease-in-out;
}
.ksb-running span:nth-child(2) { animation-delay: 0.2s; }
.ksb-running span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40%           { transform: scale(1);   opacity: 1; }
}

/* Source results */
.ksb-results {
  border-left: 2px solid var(--border-color, #e5e7eb);
  padding-left: 12px;
  margin-top: 6px;
  max-height: 280px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ksb-source-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 6px 6px;
  border-radius: 5px;
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
}
.ksb-source-meta {
  display: flex;
  align-items: center;
  gap: 5px;
}
.ksb-file-icon { font-size: 13px; flex-shrink: 0; }
.ksb-source-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary, #111827);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ksb-source-kb {
  font-size: 11px;
  color: var(--text-tertiary, #9ca3af);
  flex-shrink: 0;
}
.ksb-source-content {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ksb-done {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
}
.ksb-done-icon {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1.5px solid currentColor;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
}
</style>
