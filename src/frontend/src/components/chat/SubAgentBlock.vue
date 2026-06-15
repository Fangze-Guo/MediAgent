<template>
  <div class="sub-agent-block" :class="{ 'is-expanded': isExpanded, 'is-loading': isStreaming }">
    <!-- Header -->
    <div class="sub-agent-header" @click="handleToggle">
      <div class="sub-agent-header-left">
        <span class="sub-agent-icon">🤖</span>
        <div class="sub-agent-meta">
          <span class="sub-agent-badge">Sub-Agent Task</span>
          <span class="sub-agent-prompt" :title="message.content || ''">{{ promptPreview }}</span>
        </div>
      </div>
      <div class="sub-agent-header-right">
        <span v-if="isStreaming" class="sub-agent-status-dot streaming" title="子智能体执行中"></span>
        <span v-else-if="transcriptLoaded && subAgentMessages.length > 0" class="sub-agent-msg-count">
          {{ subAgentMessages.length }} 条
        </span>
        <span class="sub-agent-chevron" :class="{ rotated: isExpanded }">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
            <path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
      </div>
    </div>

    <!-- Transcript panel -->
    <Transition name="sub-agent-slide">
      <div v-if="isExpanded" class="sub-agent-transcript">
        <!-- Loading state -->
        <div v-if="loadingTranscript" class="transcript-loading">
          <span class="transcript-spinner"></span>
          <span>加载子智能体会话中...</span>
        </div>

        <!-- Empty / not found -->
        <div v-else-if="transcriptLoaded && subAgentMessages.length === 0" class="transcript-empty">
          <span class="transcript-empty-icon">🔍</span>
          <span>{{ notFoundReason }}</span>
        </div>

        <!-- Messages -->
        <template v-else>
          <div
            v-for="(msg, idx) in subAgentMessages"
            :key="msg.message_id || idx"
            class="transcript-msg"
            :class="[
              msg.role === 'user' ? 'transcript-user' : '',
              msg.role === 'assistant' ? 'transcript-ai' : '',
              msg.event_type === 'todo' ? 'transcript-todo' : '',
              msg.event_type === 'sub_agent_call' ? 'transcript-nested-agent' : '',
            ]"
          >
            <!-- User / task prompt -->
            <template v-if="msg.role === 'user'">
              <div class="tc-user-bubble">
                <span class="tc-role-tag">👤 用户</span>
                <MarkdownRenderer :content="msg.content || ''" class="tc-md tc-md-user" />
              </div>
            </template>

            <!-- Thinking only -->
            <template v-else-if="msg.role === 'assistant' && msg.thinking && !msg.content">
              <StreamingThinkingRenderer
                :content="msg.thinking"
                :streaming="false"
                :collapsed="true"
                class="tc-thinking-renderer"
              />
            </template>

            <!-- AI text (with optional thinking) -->
            <template v-else-if="msg.role === 'assistant' && msg.content">
              <StreamingThinkingRenderer
                v-if="msg.thinking"
                :content="msg.thinking"
                :streaming="false"
                :collapsed="true"
                class="tc-thinking-renderer"
              />
              <div class="tc-ai-bubble">
                <span class="tc-role-tag">🤖 子智能体</span>
                <MarkdownRenderer :content="msg.content" class="tc-md" />
              </div>
            </template>

            <!-- Todo -->
            <template v-else-if="msg.event_type === 'todo'">
              <div class="tc-todo-badge">
                <span>📋</span>
                <span>Todo 更新 ({{ (msg.todo_list || []).length }} 项)</span>
              </div>
            </template>

            <!-- Nested sub-agent (don't recurse, just show prompt) -->
            <template v-else-if="msg.event_type === 'sub_agent_call'">
              <div class="tc-nested-agent-badge">
                <span>🤖</span>
                <span>嵌套子智能体: {{ (msg.content || '').slice(0, 80) }}{{ (msg.content || '').length > 80 ? '…' : '' }}</span>
              </div>
            </template>
          </div>
        </template>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import type { MessageResponse } from '@/apis/codeAgent'
import { getSubAgentMessages } from '@/apis/codeAgent'
import MarkdownRenderer from '@/components/markdown/MarkdownRenderer.vue'
import StreamingThinkingRenderer from '@/components/markdown/StreamingThinkingRenderer.vue'

const props = defineProps<{
  message: MessageResponse
  conversationId: string
  isStreaming?: boolean
}>()

const isExpanded = ref(false)
const loadingTranscript = ref(false)
const transcriptLoaded = ref(false)
const subAgentMessages = ref<MessageResponse[]>([])
const notFoundReason = ref('暂无子智能体会话记录（可能正在执行或尚未记录）')
const pollTimer = ref<number | null>(null)

const promptPreview = computed(() => {
  const text = props.message.content || ''
  return text.length > 80 ? text.slice(0, 80) + '…' : text
})

const loadTranscript = async (silent = false) => {
  if (!props.message.tool_use_id) {
    notFoundReason.value = '缺少 tool_use_id，无法关联子智能体会话'
    transcriptLoaded.value = true
    return
  }
  if (!silent) {
    loadingTranscript.value = true
  }
  try {
    const res = await getSubAgentMessages(props.conversationId, props.message.tool_use_id)
    if (res.code === 200 && res.data) {
      subAgentMessages.value = res.data.messages || []
      if (!res.data.found) {
        notFoundReason.value = props.isStreaming
          ? '子智能体会话正在生成，等待 ClaudeCode 写入 agent-*.jsonl...'
          : '未找到匹配的子智能体会话文件（agent-*.jsonl）'
      }
    } else {
      notFoundReason.value = '加载子智能体会话失败'
    }
  } catch (e) {
    console.error('[SubAgentBlock] 加载失败:', e)
    notFoundReason.value = '加载子智能体会话出错'
  } finally {
    if (!silent) {
      loadingTranscript.value = false
    }
    transcriptLoaded.value = true
  }
}

const stopPolling = () => {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

const startPolling = () => {
  if (!isExpanded.value || !props.isStreaming || pollTimer.value !== null) return
  pollTimer.value = window.setInterval(() => {
    loadTranscript(true)
  }, 1500)
}

const handleToggle = () => {
  isExpanded.value = !isExpanded.value
  if (isExpanded.value && !transcriptLoaded.value) {
    loadTranscript()
  }
  if (isExpanded.value) {
    startPolling()
  } else {
    stopPolling()
  }
}

// 流式状态结束后自动刷新（若已展开）
watch(() => props.isStreaming, (nowStreaming, wasStreaming) => {
  if (nowStreaming && isExpanded.value) {
    startPolling()
  }
  if (wasStreaming && !nowStreaming && isExpanded.value) {
    stopPolling()
    transcriptLoaded.value = false
    subAgentMessages.value = []
    loadTranscript()
  }
})

watch(isExpanded, expanded => {
  if (expanded) {
    startPolling()
  } else {
    stopPolling()
  }
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
/* ── Block 整体 ─────────────────────────────────────────────── */
.sub-agent-block {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(99, 102, 241, 0.25);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.04) 0%, rgba(168, 85, 247, 0.04) 100%);
  margin: 6px 0;
  transition: box-shadow 0.2s ease;
}
.sub-agent-block:hover {
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.12);
}

/* ── Header ─────────────────────────────────────────────────── */
.sub-agent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.08) 0%, rgba(168, 85, 247, 0.06) 100%);
  border-bottom: 1px solid rgba(99, 102, 241, 0.12);
  transition: background 0.15s ease;
}
.sub-agent-header:hover {
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.14) 0%, rgba(168, 85, 247, 0.1) 100%);
}

.sub-agent-header-left {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.sub-agent-icon {
  font-size: 18px;
  line-height: 1.2;
  flex-shrink: 0;
}

.sub-agent-meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.sub-agent-badge {
  font-size: 11px;
  font-weight: 600;
  color: #6366f1;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}

.sub-agent-prompt {
  font-size: 13px;
  color: var(--text-secondary, #4b5563);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 440px;
}

.sub-agent-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  margin-left: 12px;
}

.sub-agent-msg-count {
  font-size: 11px;
  color: #8b5cf6;
  background: rgba(139, 92, 246, 0.1);
  padding: 2px 7px;
  border-radius: 10px;
  font-weight: 500;
}

.sub-agent-chevron {
  color: #a78bfa;
  transition: transform 0.2s ease;
  display: flex;
  align-items: center;
}
.sub-agent-chevron.rotated {
  transform: rotate(180deg);
}

/* Streaming pulse dot */
.sub-agent-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.sub-agent-status-dot.streaming {
  background: #8b5cf6;
  animation: pulse-dot 1.2s infinite ease-in-out;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 0.4; transform: scale(0.85); }
  50%       { opacity: 1;   transform: scale(1.1); }
}

/* ── Transcript panel ────────────────────────────────────────── */
.sub-agent-transcript {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 420px;
  overflow-y: auto;
  background: rgba(255, 255, 255, 0.6);
}

.transcript-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #8b5cf6;
  font-size: 13px;
  padding: 8px 0;
}
.transcript-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(139, 92, 246, 0.25);
  border-top-color: #8b5cf6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.transcript-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary, #9ca3af);
  font-size: 13px;
  padding: 8px 0;
}
.transcript-empty-icon { font-size: 16px; }

/* ── Individual transcript messages ────────────────────────── */
.transcript-msg {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tc-user-bubble {
  background: rgba(99, 102, 241, 0.08);
  border-radius: 8px;
  padding: 8px 10px;
}

.tc-ai-bubble {
  background: #fff;
  border: 1px solid rgba(99, 102, 241, 0.12);
  border-radius: 8px;
  padding: 8px 10px;
}

.tc-role-tag {
  font-size: 10px;
  font-weight: 600;
  color: #6366f1;
  letter-spacing: 0.3px;
  display: block;
  margin-bottom: 4px;
}

.tc-md {
  font-size: 13px;
  line-height: 1.6;
}
.tc-md :deep(p) {
  margin: 0 0 6px 0;
}
.tc-md :deep(p:last-child) {
  margin-bottom: 0;
}
.tc-md :deep(pre) {
  border-radius: 6px;
  font-size: 12px;
  margin: 6px 0;
}
.tc-md :deep(code:not(pre code)) {
  font-size: 12px;
  padding: 1px 4px;
  border-radius: 3px;
  background: rgba(99, 102, 241, 0.08);
}
.tc-md :deep(ul), .tc-md :deep(ol) {
  margin: 4px 0;
  padding-left: 18px;
}
.tc-md :deep(h1), .tc-md :deep(h2), .tc-md :deep(h3) {
  font-size: 13px;
  font-weight: 600;
  margin: 8px 0 4px;
}
.tc-md :deep(table) {
  font-size: 12px;
  border-collapse: collapse;
  width: 100%;
  margin: 6px 0;
}
.tc-md :deep(th), .tc-md :deep(td) {
  border: 1px solid rgba(99, 102, 241, 0.2);
  padding: 4px 8px;
}
.tc-md-user {
  color: var(--text-primary, #111827);
}
.tc-thinking-renderer {
  margin-bottom: 4px;
}

.tc-thinking-bubble {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid rgba(99, 102, 241, 0.12);
  background: rgba(99, 102, 241, 0.04);
  color: #8b5cf6;
  font-size: 12px;
  user-select: none;
}
.tc-thinking-bubble:hover { background: rgba(99, 102, 241, 0.08); }

.tc-thinking-icon { font-size: 13px; }
.tc-thinking-label { flex: 1; font-weight: 500; }
.tc-thinking-chevron {
  transition: transform 0.18s ease;
  font-size: 16px;
  line-height: 1;
  transform: rotate(90deg);
}
.tc-thinking-chevron.rotated { transform: rotate(270deg); }

.tc-thinking-content {
  background: rgba(99, 102, 241, 0.04);
  border-radius: 6px;
  padding: 8px 10px;
}
.tc-pre {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  line-height: 1.6;
}

.tc-todo-badge,
.tc-nested-agent-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #7c3aed;
  background: rgba(124, 58, 237, 0.08);
  border-radius: 6px;
  padding: 4px 10px;
  border: 1px solid rgba(124, 58, 237, 0.15);
}

/* ── Slide transition ────────────────────────────────────────── */
.sub-agent-slide-enter-active,
.sub-agent-slide-leave-active {
  transition: max-height 0.25s ease, opacity 0.2s ease;
  max-height: 420px;
  overflow: hidden;
}
.sub-agent-slide-enter-from,
.sub-agent-slide-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
