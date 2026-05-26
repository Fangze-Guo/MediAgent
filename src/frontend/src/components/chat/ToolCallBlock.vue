<template>
  <div class="tool-call-block" :class="item.status">
    <div class="tool-call-header" @click="toggle">
      <span class="tool-icon">{{ item.icon || toolIcon }}</span>
      <span class="tool-name">{{ item.displayName || displayName }}</span>
      <span v-if="item.status === 'running'" class="dot-wave">
        <span></span><span></span><span></span>
      </span>
      <template v-else-if="item.status === 'error'">
        <span class="status-badge error">✕</span>
      </template>
      <template v-else>
        <span class="status-badge done">✓</span>
        <span class="chevron" :class="{ rotated: localExpanded }">›</span>
      </template>
    </div>
    <div v-if="localExpanded && item.status !== 'running'" class="tool-call-body">
      <div class="tool-call-divider" />
      <div v-if="item.inputSummary || item.query" class="tool-call-row">
        <span class="tc-label">输入</span>
        <span class="tc-value">{{ item.inputSummary || item.query }}</span>
      </div>

      <!-- web_search 结果卡片 -->
      <template v-if="item.name === 'web_search' && item.searchResults?.length">
        <div class="search-results-list">
          <a
            v-for="(r, i) in item.searchResults"
            :key="i"
            :href="r.url"
            target="_blank"
            rel="noopener noreferrer"
            class="search-result-item"
          >
            <img
              :src="`https://www.google.com/s2/favicons?domain=${getDomain(r.url)}&sz=16`"
              class="result-favicon"
              loading="lazy"
              @error="($event.target as HTMLImageElement).style.display='none'"
            />
            <span class="result-title">{{ r.title }}</span>
            <span class="result-domain">{{ getDomain(r.url) }}</span>
          </a>
        </div>
      </template>
      <template v-else>
        <div class="tool-call-row">
          <span class="tc-icon" :class="item.status">✓</span>
          <span class="tc-value">
            <template v-if="item.found !== undefined">找到 {{ item.found }} 个相关片段</template>
            <template v-else-if="item.outputSummary">{{ item.outputSummary }}</template>
            <template v-else-if="item.status === 'error'">执行失败</template>
            <template v-else>执行完成</template>
          </span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCallItem } from '@/store/conversations'

const props = defineProps<{ item: ToolCallItem }>()

const localExpanded = ref(false)

const TOOL_LABEL: Record<string, string> = {
  search_knowledge_base: '知识库检索',
  web_search: '网络搜索',
  read_local_file: '读取文件',
  get_datetime: '获取时间',
}
const TOOL_ICON: Record<string, string> = {
  search_knowledge_base: '📚',
  web_search: '🌐',
  read_local_file: '📄',
  get_datetime: '🕐',
}

const displayName = computed(() => TOOL_LABEL[props.item.name] ?? props.item.name)
const toolIcon = computed(() => TOOL_ICON[props.item.name] ?? '🔧')

function toggle() {
  if (props.item.status === 'done') localExpanded.value = !localExpanded.value
}

function getDomain(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url }
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
.tool-call-block.done:has(.search-results-list) {
  max-width: 480px;
}
.tool-call-block.error {
  border-color: #fca5a5;
  background: #fff5f5;
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
.tc-icon.error {
  color: #ef4444;
  font-size: 13px;
  min-width: 14px;
}

.status-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 4px;
  margin-left: 4px;
}
.status-badge.done {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.1);
}
.status-badge.error {
  color: #dc2626;
  background: rgba(220, 38, 38, 0.1);
}

/* 搜索结果列表 */
.search-results-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
  max-height: 220px;
  overflow-y: auto;
}
.search-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 4px;
  border-radius: 6px;
  text-decoration: none;
  color: inherit;
  transition: background 0.12s;
}
.search-result-item:hover {
  background: var(--hover-bg, #f3f4f6);
}
.result-favicon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  border-radius: 2px;
}
.result-title {
  flex: 1;
  font-size: 12px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.result-domain {
  font-size: 11px;
  color: var(--text-tertiary, #9ca3af);
  flex-shrink: 0;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
