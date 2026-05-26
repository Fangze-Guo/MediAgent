<template>
  <div class="wsb-wrapper">
    <!-- Header toggle -->
    <div class="wsb-header" @click="expanded = !expanded">
      <span class="wsb-header-text">Searched the web</span>
      <span class="wsb-chevron" :class="{ open: expanded }">›</span>
    </div>

    <!-- Each search group -->
    <div v-if="expanded" class="wsb-body">
      <div v-for="(item, i) in items" :key="i" class="wsb-group">
        <!-- Query row -->
        <div class="wsb-query-row">
          <span class="wsb-globe">🌐</span>
          <span class="wsb-query-text">{{ item.query || item.inputSummary }}</span>
          <template v-if="item.status === 'running'">
            <span class="wsb-running">
              <span></span><span></span><span></span>
            </span>
          </template>
          <span v-else-if="item.searchResults?.length" class="wsb-count">
            {{ item.searchResults.length }} results
          </span>
        </div>

        <!-- Results list -->
        <div v-if="item.searchResults?.length" class="wsb-results">
          <a
            v-for="(r, ri) in item.searchResults"
            :key="ri"
            :href="r.url"
            target="_blank"
            rel="noopener noreferrer"
            class="wsb-result-item"
          >
            <img
              :src="`https://www.google.com/s2/favicons?domain=${getDomain(r.url)}&sz=16`"
              class="wsb-favicon"
              loading="lazy"
              @error="($event.target as HTMLImageElement).style.display='none'"
            />
            <span class="wsb-result-title">{{ r.title }}</span>
            <span class="wsb-result-domain">{{ getDomain(r.url) }}</span>
          </a>
        </div>
      </div>

      <!-- Done footer -->
      <div class="wsb-done">
        <span class="wsb-done-icon">✓</span>
        <span>Done</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { ToolCallItem } from '@/store/conversations'

defineProps<{ items: ToolCallItem[] }>()

const expanded = ref(false)

function getDomain(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url }
}
</script>

<style scoped>
.wsb-wrapper {
  margin-bottom: 10px;
  font-size: 13px;
}

/* Header */
.wsb-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 0;
  cursor: pointer;
  color: var(--text-secondary, #6b7280);
  user-select: none;
}
.wsb-header:hover { color: var(--text-primary, #111827); }
.wsb-header-text { font-size: 14px; color: var(--text-secondary, #6b7280); }
.wsb-chevron {
  font-size: 14px;
  line-height: 1;
  transform: rotate(90deg);
  transition: transform 0.18s ease;
  display: inline-block;
}
.wsb-chevron.open { transform: rotate(270deg); }

/* Body */
.wsb-body {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Each search group */
.wsb-group {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* Query row */
.wsb-query-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.wsb-globe { font-size: 14px; flex-shrink: 0; }
.wsb-query-text {
  flex: 1;
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
}
.wsb-count {
  font-size: 11px;
  color: var(--text-tertiary, #9ca3af);
  white-space: nowrap;
}

/* Running dots */
.wsb-running {
  display: inline-flex;
  gap: 3px;
  align-items: center;
}
.wsb-running span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-tertiary, #9ca3af);
  animation: dot-bounce 1.2s infinite ease-in-out;
}
.wsb-running span:nth-child(2) { animation-delay: 0.2s; }
.wsb-running span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40%           { transform: scale(1);   opacity: 1; }
}

/* Results list */
.wsb-results {
  border-left: 2px solid var(--border-color, #e5e7eb);
  padding-left: 12px;
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.wsb-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 4px;
  border-radius: 5px;
  text-decoration: none;
  color: inherit;
  transition: background 0.12s;
}
.wsb-result-item:hover { background: var(--hover-bg, #f3f4f6); }
.wsb-favicon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  border-radius: 2px;
}
.wsb-result-title {
  flex: 1;
  font-size: 12px;
  color: var(--text-primary, #111827);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wsb-result-domain {
  font-size: 11px;
  color: var(--text-tertiary, #9ca3af);
  flex-shrink: 0;
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Done */
.wsb-done {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  margin-top: 2px;
}
.wsb-done-icon {
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
