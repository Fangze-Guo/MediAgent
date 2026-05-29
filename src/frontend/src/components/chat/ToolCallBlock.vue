<template>
  <div class="chain-step" :class="{ last: index === total - 1, nested }">
    <div class="step-rail">
      <div class="step-dot-wrap">
        <div class="step-dot" :class="item.status">{{ index + 1 }}</div>
      </div>
      <div class="step-line" />
    </div>
    <div
      class="tool-call-block"
      :class="[
        item.status,
        {
          'no-card': TOOL_NO_ICON.has(item.name),
          'report-tool-card': item.name === 'generate_medical_report'
        }
      ]"
    >
      <div class="tool-call-header" @click="toggle">
          <span v-if="!TOOL_NO_ICON.has(item.name)" class="tool-icon">{{ item.icon || toolIcon }}</span>
          <div class="tool-heading">
            <span class="tool-name">{{ displayName }}</span>
          <span class="tool-kind">{{ itemKind }}</span>
        </div>
        <span v-if="item.status === 'running'" class="status-spinner" aria-label="运行中"></span>
        <template v-else-if="item.status === 'error'">
          <span v-if="!TOOL_NO_ICON.has(item.name)" class="status-badge error">✕</span>
        </template>
        <template v-else>
          <span v-if="!TOOL_NO_ICON.has(item.name)" class="status-badge done">✓</span>
          <span class="chevron" :class="{ rotated: localExpanded }">›</span>
        </template>
      </div>
    <!-- no-card 模式展开内容：时间结果 + ✓ Done，和 WebSearchBlock 一致 -->
    <div v-if="localExpanded && item.status !== 'running' && TOOL_NO_ICON.has(item.name)" class="nc-body">
      <div v-if="item.outputSummary" class="nc-result-row">
        <span class="nc-result-text">{{ item.outputSummary }}</span>
      </div>
      <div class="nc-done">
        <span class="nc-done-icon">✓</span>
        <span>Done</span>
      </div>
    </div>
    <!-- 普通卡片展开内容 -->
    <div v-if="localExpanded && item.status !== 'running' && !TOOL_NO_ICON.has(item.name)" class="tool-call-body">
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
        <div v-if="item.name === 'generate_medical_report' && item.reportResult" class="report-result">
          <div class="report-cover">
            <div class="report-cover-mark">CT</div>
            <div class="report-cover-copy">
              <div class="report-title">{{ item.reportResult.title || '医学报告' }}</div>
              <div class="report-meta">{{ item.reportResult.image_count || 0 }} 个影像文件</div>
            </div>
          </div>
          <div v-if="item.reportResult.summary" class="report-summary">{{ item.reportResult.summary }}</div>
          <div class="report-path">{{ item.reportResult.output_dir }}</div>
          <div class="report-actions">
            <a
              v-if="item.reportResult.preview_url"
              class="report-link primary"
              :href="withApiBase(item.reportResult.preview_url)"
              target="_blank"
              rel="noopener noreferrer"
            >
              打开报告
            </a>
            <a
              v-if="item.reportResult.report_json"
              class="report-link"
              :href="withApiBase(`/files/serve/${item.reportResult.report_json}`)"
              target="_blank"
              rel="noopener noreferrer"
            >
              查看 JSON
            </a>
          </div>
        </div>
        <div class="tool-call-row">
          <span class="tc-icon" :class="item.status">✓</span>
          <span class="tc-value">
            <template v-if="item.found !== undefined">找到 {{ item.found }} 个相关片段</template>
            <template v-else-if="item.outputSummary">{{ item.outputSummary }}</template>
            <template v-else-if="item.status === 'error'">执行失败</template>
            <template v-else>执行完成</template>
          </span>
        </div>
        <div
          v-if="item.name === 'search_knowledge_base' && sources?.length"
          class="rag-snippets"
        >
          <div
            v-for="(source, si) in sources"
            :key="`${source.doc_id || source.kb_name}-${si}`"
            class="rag-snippet"
          >
            <div class="rag-snippet-meta">
              <span class="rag-file-icon">{{ getFileEmoji(source.file_name) }}</span>
              <span class="rag-file-name">{{ source.file_name || source.kb_name }}</span>
              <span class="rag-kb-name">{{ source.kb_name }}</span>
            </div>
            <div class="rag-snippet-content">{{ source.content }}</div>
          </div>
        </div>
        <div v-if="item.childCalls?.length" class="child-chain">
          <ToolCallBlock
            v-for="(child, ci) in item.childCalls"
            :key="`${child.name}-${ci}`"
            :item="child"
            :index="ci"
            :total="item.childCalls.length"
            nested
          />
        </div>
      </template>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCallItem } from '@/store/conversations'
import type { RagSource } from '@/apis/conversation'

defineOptions({ name: 'ToolCallBlock' })

const props = withDefaults(defineProps<{
  item: ToolCallItem
  index?: number
  total?: number
  nested?: boolean
  sources?: RagSource[]
}>(), {
  index: 0,
  total: 1,
  nested: false,
})

const localExpanded = ref(props.item.name === 'generate_medical_report')
const TOOL_LABEL: Record<string, string> = {
  search_knowledge_base: 'Knowledge Search',
  web_search: 'Web Search',
  read_local_file: 'Read Local File',
  list_dataset_files: 'Dataset Browser',
  read_dataset_text_file: 'Read Dataset File',
  get_dataset_file_metadata: 'Dataset Metadata',
  generate_medical_report: 'Medical Report Generation',
  MedicalImageReportAgent: 'Medical Image Report Agent',
  render_medical_report: 'Report Renderer',
  get_datetime: 'Date Time',
}
const TOOL_NO_ICON = new Set<string>()
const TOOL_ICON: Record<string, string> = {
  search_knowledge_base: '📚',
  web_search: '🌐',
  read_local_file: '📄',
  list_dataset_files: '📁',
  read_dataset_text_file: '📄',
  get_dataset_file_metadata: 'ℹ️',
  generate_medical_report: '📝',
  MedicalImageReportAgent: '🧠',
  render_medical_report: '📄',
  get_datetime: '🕐',
}

// 已知工具始终用前端英文标签，忽略后端存的旧中文 display_name
const displayName = computed(() => TOOL_LABEL[props.item.name] ?? props.item.displayName ?? props.item.name)
const toolIcon = computed(() => TOOL_ICON[props.item.name] ?? '🔧')
const itemKind = computed(() => props.item.name.includes('Agent') ? 'Agent' : 'Tool')

function toggle() {
  if (props.item.status === 'done') localExpanded.value = !localExpanded.value
}

function getDomain(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url }
}

function getFileEmoji(filename?: string): string {
  if (!filename) return '📄'
  const ext = filename.toLowerCase()
  if (ext.endsWith('.pdf')) return '📕'
  if (ext.endsWith('.xlsx') || ext.endsWith('.xls')) return '📗'
  if (ext.endsWith('.docx') || ext.endsWith('.doc')) return '📘'
  return '📄'
}

function withApiBase(url: string): string {
  if (!url || /^https?:\/\//.test(url)) return url
  const baseURL = (import.meta as any).env?.VITE_API_BASE || '/api'
  return `${baseURL}${url.startsWith('/') ? url : `/${url}`}`
}
</script>

<style scoped>
.tool-call-block {
  display: flex;
  flex-direction: column;
  margin-bottom: 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-secondary, #f9fafb);
  font-size: 13px;
  overflow: hidden;
  width: 100%;
  max-width: 100%;
}

.chain-step {
  --tool-header-height: 2.5rem;
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 10px;
}

.step-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.step-dot-wrap {
  min-height: var(--tool-header-height);
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.step-dot.done {
  border-color: #16a34a;
  background: #ecfdf3;
  color: #15803d;
}

.step-dot.running {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
}

.step-dot.error {
  border-color: #ef4444;
  background: #fef2f2;
  color: #dc2626;
}

.step-line {
  width: 2px;
  flex: 1;
  min-height: 18px;
  background: #dbe2ea;
}

.chain-step.last .step-line {
  display: none;
}

.chain-step.nested {
  --tool-header-height: 2.25rem;
  grid-template-columns: 22px minmax(0, 1fr);
  gap: 8px;
}

.chain-step.nested .step-dot {
  width: 20px;
  height: 20px;
  font-size: 10px;
}

.chain-step.nested .step-line {
  min-height: 14px;
}

.chain-step.nested .tool-call-block {
  width: 100%;
  max-width: 100%;
  margin-bottom: 6px;
}

.tool-call-block.report-tool-card {
  max-width: 100%;
  width: 100%;
  border-radius: 10px;
  background: var(--bg-primary, #fff);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.tool-call-block.report-tool-card.running {
  border: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-primary, #fff);
  border-radius: 10px;
  max-width: 100%;
}

.tool-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.tool-kind {
  font-size: 10px;
  font-weight: 700;
  color: var(--text-tertiary, #94a3b8);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 999px;
  padding: 1px 6px;
  text-transform: uppercase;
  flex-shrink: 0;
}
.tool-call-block.running {
  max-width: 100%;
}
/* no-card 模式：所有状态都无卡片，和 WebSearchBlock 完全一致 */
.tool-call-block.no-card {
  border: none;
  background: transparent;
  border-radius: 0;
  max-width: none;
}
.tool-call-block.no-card .tool-call-header {
  padding: 2px 0;
}
.tool-call-block.no-card .tool-call-header:hover {
  background: transparent;
}
.tool-call-block.no-card {
  overflow: visible;
}
.tool-call-block.no-card .chevron {
  margin-left: 4px;
}
.tool-call-block.no-card .tool-name {
  font-weight: normal;
  color: var(--text-secondary, #6b7280);
}

.report-result {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 10px;
  padding: 12px;
  border-radius: 8px;
  background: linear-gradient(180deg, #f8fbff 0%, var(--bg-primary, #fff) 100%);
  border: 1px solid color-mix(in srgb, var(--link-color, #2563eb) 18%, var(--border-color, #e5e7eb));
}

.report-cover {
  display: flex;
  align-items: center;
  gap: 12px;
}

.report-cover-mark {
  width: 46px;
  height: 58px;
  border: 1px solid #c8d2e3;
  border-radius: 4px;
  background: #fff;
  color: #1f3b73;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 -8px 0 #eef4ff;
  flex-shrink: 0;
}

.report-cover-copy {
  min-width: 0;
}

.report-title {
  font-weight: 600;
  color: var(--text-primary, #111827);
  font-size: 14px;
}

.report-meta {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  word-break: break-all;
  margin-top: 3px;
}

.report-summary {
  color: var(--text-secondary, #6b7280);
  font-size: 12px;
  line-height: 1.6;
}

.report-path {
  padding: 7px 9px;
  border-radius: 6px;
  background: var(--bg-secondary, #f9fafb);
  color: var(--text-tertiary, #6b7280);
  font-size: 11px;
  word-break: break-all;
}

.report-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #e5e7eb);
  font-size: 12px;
  color: var(--link-color, #2563eb);
  text-decoration: none;
}

.report-link.primary {
  border-color: var(--link-color, #2563eb);
  background: var(--link-color, #2563eb);
  color: #fff;
}

.report-link:hover {
  opacity: 0.86;
}

.child-chain {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-top: 10px;
  padding: 10px 0 0 2px;
  border-radius: 8px;
  background: transparent;
}

.rag-snippets {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 280px;
  overflow-y: auto;
  margin-top: 10px;
  padding-left: 10px;
  border-left: 2px solid var(--border-color, #e5e7eb);
}

.rag-snippet {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 6px;
  background: var(--bg-primary, #fff);
}

.rag-snippet-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.rag-file-icon {
  font-size: 13px;
  flex-shrink: 0;
}

.rag-file-name {
  flex: 1;
  min-width: 0;
  color: var(--text-primary, #111827);
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rag-kb-name {
  color: var(--text-tertiary, #94a3b8);
  font-size: 11px;
  flex-shrink: 0;
}

.rag-snippet-content {
  color: var(--text-secondary, #64748b);
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* no-card 展开 body */
.nc-body {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
}
.nc-result-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.nc-result-text {
  color: var(--text-secondary, #6b7280);
  font-size: 13px;
}
.nc-done {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
}
.nc-done-icon {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1.5px solid currentColor;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
}
.tool-call-block.done:has(.search-results-list) {
  max-width: 100%;
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
  min-height: var(--tool-header-height);
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

.status-spinner {
  width: 16px;
  height: 16px;
  margin-left: 4px;
  border-radius: 50%;
  border: 2px dashed var(--link-color, #2563eb);
  border-left-color: transparent;
  animation: status-spin 0.9s linear infinite;
  flex-shrink: 0;
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

@keyframes status-spin {
  to { transform: rotate(360deg); }
}
</style>
