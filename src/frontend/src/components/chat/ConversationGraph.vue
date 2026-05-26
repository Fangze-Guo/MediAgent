<template>
  <div class="conv-graph">
    <!-- Header -->
    <div class="graph-header">
      <div class="graph-title-row">
        <span class="graph-icon">🔗</span>
        <span class="graph-title">对话链路图</span>
        <span class="graph-count">{{ turns.length }} 轮</span>
      </div>
      <button class="graph-close" @click="$emit('close')">✕</button>
    </div>

    <!-- Empty state -->
    <div v-if="turns.length === 0" class="graph-empty">
      <span class="empty-icon">💬</span>
      <p>暂无对话记录</p>
    </div>

    <!-- Turn list -->
    <div v-else class="graph-body">
      <div v-for="(turn, ti) in turns" :key="ti" class="graph-turn">
        <!-- Turn index label -->
        <div class="turn-label">第 {{ ti + 1 }} 轮</div>

        <!-- User node -->
        <div class="graph-node user-node">
          <div class="node-avatar user-avatar">👤</div>
          <div class="node-body">
            <div class="node-role">用户</div>
            <div class="node-text">{{ truncate(turn.user.content, 72) }}</div>
          </div>
        </div>

        <!-- Tool chain -->
        <template v-if="turn.assistant?.toolCalls?.length">
          <div v-for="(tc, tci) in turn.assistant.toolCalls" :key="tci" class="tool-chain-item">
            <div class="chain-connector">
              <div class="connector-line" />
              <div class="connector-arrow">▼</div>
            </div>
            <div class="graph-node tool-node" :class="tc.status">
              <div class="node-avatar tool-avatar">{{ tc.icon || toolIcon(tc.name) }}</div>
              <div class="node-body">
                <div class="node-role">{{ tc.displayName || toolLabel(tc.name) }}</div>
                <div class="node-text">{{ truncate(tc.inputSummary || tc.query, 60) }}</div>
                <div class="node-meta" v-if="tc.status !== 'running'">
                  <span v-if="tc.status === 'error'" class="meta-error">✕ 执行失败</span>
                  <span v-else-if="tc.found !== undefined" class="meta-ok">✓ 找到 {{ tc.found }} 个片段</span>
                  <span v-else-if="tc.outputSummary" class="meta-ok">✓ {{ truncate(tc.outputSummary, 48) }}</span>
                  <span v-else class="meta-ok">✓ 完成</span>
                </div>
                <div class="node-meta" v-else>
                  <span class="meta-running">
                    <span class="dot-pulse" /><span class="dot-pulse" /><span class="dot-pulse" />
                    运行中
                  </span>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- Connector to assistant -->
        <div class="chain-connector">
          <div class="connector-line" />
          <div class="connector-arrow">▼</div>
        </div>

        <!-- Assistant node -->
        <div class="graph-node assistant-node" :class="{ streaming: turn.assistant && !turn.assistant.typingComplete }">
          <div class="node-avatar ai-avatar">🤖</div>
          <div class="node-body">
            <div class="node-role">AI 助手</div>
            <div v-if="!turn.assistant" class="node-text muted">等待响应…</div>
            <div v-else-if="!turn.assistant.typingComplete && !turn.assistant.content" class="node-text muted">
              <span class="dot-pulse" /><span class="dot-pulse" /><span class="dot-pulse" />
            </div>
            <div v-else class="node-text">{{ truncate(turn.assistant.content, 72) }}</div>
            <!-- sources badge -->
            <div v-if="turn.assistant?.sources?.length" class="node-sources">
              <span class="sources-badge">📚 {{ turn.assistant.sources.length }} 个来源</span>
            </div>
          </div>
        </div>

        <!-- Turn separator -->
        <div v-if="ti < turns.length - 1" class="turn-sep" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/store/conversations'

const props = defineProps<{ messages: ChatMessage[] }>()
defineEmits<{ close: [] }>()

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

const toolLabel = (name: string) => TOOL_LABEL[name] ?? name
const toolIcon = (name: string) => TOOL_ICON[name] ?? '🔧'

const truncate = (text: string, max: number) => {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '…' : text
}

const turns = computed(() => {
  const result: { user: ChatMessage; assistant: ChatMessage | null }[] = []
  const msgs = props.messages
  for (let i = 0; i < msgs.length; i++) {
    if (msgs[i].role === 'user') {
      const assistant = msgs[i + 1]?.role === 'assistant' ? msgs[i + 1] : null
      result.push({ user: msgs[i], assistant })
    }
  }
  return result
})
</script>

<style scoped>
.conv-graph {
  width: 320px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary, #fff);
  border-left: 1px solid var(--border-color, #e5e7eb);
  overflow: hidden;
  flex-shrink: 0;
}

/* ───── Header ───── */
.graph-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-secondary, #f9fafb);
  flex-shrink: 0;
}
.graph-title-row {
  display: flex;
  align-items: center;
  gap: 7px;
}
.graph-icon { font-size: 15px; }
.graph-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #111);
}
.graph-count {
  font-size: 11px;
  background: var(--border-color, #e5e7eb);
  color: var(--text-secondary, #6b7280);
  padding: 2px 7px;
  border-radius: 10px;
}
.graph-close {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-tertiary, #9ca3af);
  cursor: pointer;
  border-radius: 4px;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.graph-close:hover {
  background: var(--hover-bg, #f3f4f6);
  color: var(--text-primary, #111);
}

/* ───── Empty ───── */
.graph-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-tertiary, #9ca3af);
}
.empty-icon { font-size: 36px; }
.graph-empty p { font-size: 13px; margin: 0; }

/* ───── Body ───── */
.graph-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ───── Turn ───── */
.graph-turn {
  display: flex;
  flex-direction: column;
}
.turn-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary, #9ca3af);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}
.turn-sep {
  height: 20px;
  border-left: 2px dashed var(--border-color, #e5e7eb);
  margin-left: 18px;
  margin-top: 4px;
  margin-bottom: 4px;
}

/* ───── Nodes ───── */
.graph-node {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-primary, #fff);
  position: relative;
  transition: box-shadow 0.15s;
}
.graph-node:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }

.user-node { border-color: rgba(99,102,241,0.3); background: rgba(99,102,241,0.03); }
.assistant-node { border-color: rgba(16,185,129,0.3); background: rgba(16,185,129,0.03); }
.tool-node { border-color: rgba(245,158,11,0.3); background: rgba(245,158,11,0.03); }
.tool-node.error { border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.03); }
.tool-node.running { border-color: rgba(59,130,246,0.3); background: rgba(59,130,246,0.03); }
.assistant-node.streaming { border-color: rgba(16,185,129,0.5); }

.node-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
  background: var(--bg-secondary, #f3f4f6);
}
.user-avatar { background: rgba(99,102,241,0.12); }
.ai-avatar   { background: rgba(16,185,129,0.12); }
.tool-avatar { background: rgba(245,158,11,0.12); }

.node-body { flex: 1; min-width: 0; }
.node-role {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary, #9ca3af);
  margin-bottom: 2px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.node-text {
  font-size: 13px;
  color: var(--text-primary, #111);
  line-height: 1.5;
  word-break: break-word;
}
.node-text.muted { color: var(--text-tertiary, #9ca3af); }

.node-meta { margin-top: 5px; font-size: 11px; }
.meta-ok   { color: #16a34a; }
.meta-error{ color: #dc2626; }
.meta-running {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #3b82f6;
}

.node-sources { margin-top: 5px; }
.sources-badge {
  font-size: 11px;
  color: #6366f1;
  background: rgba(99,102,241,0.1);
  padding: 2px 7px;
  border-radius: 8px;
}

/* ───── Connectors ───── */
.tool-chain-item {
  display: flex;
  flex-direction: column;
}
.chain-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  margin-left: 12px;
  padding: 2px 0;
}
.connector-line {
  width: 2px;
  height: 12px;
  background: var(--border-color, #e5e7eb);
}
.connector-arrow {
  font-size: 9px;
  color: var(--text-tertiary, #9ca3af);
  line-height: 1;
}

/* ───── Dot pulse animation ───── */
.dot-pulse {
  display: inline-block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 1.2s infinite ease-in-out;
  margin: 0 1px;
}
.dot-pulse:nth-child(2) { animation-delay: 0.2s; }
.dot-pulse:nth-child(3) { animation-delay: 0.4s; }

@keyframes pulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40%           { transform: scale(1);   opacity: 1; }
}
</style>
