/**
 * Session Store - 对齐参考项目 claudecodeui (Vue 版本)
 *
 * 使用内存 Map 存储每个 sessionId 的消息
 * 通过 API 拉取历史消息，不再直接存储消息内容
 */
import { ref, computed, watch } from 'vue'
import { authenticatedFetch } from '@/utils/request'

// ─── NormalizedMessage 类型（与后端 MessageKind 一致）─────────────────────────

export type MessageKind =
  | 'text'
  | 'tool_use'
  | 'tool_result'
  | 'thinking'
  | 'stream_delta'
  | 'stream_end'
  | 'error'
  | 'complete'
  | 'status'
  | 'permission_request'
  | 'permission_cancelled'
  | 'session_created'

export interface NormalizedMessage {
  id: string
  sessionId: string
  timestamp: string
  provider: 'claude' | 'qwen' | 'gemini' | 'codex'
  kind: MessageKind
  role?: 'user' | 'assistant'
  content?: string
  toolName?: string
  toolInput?: unknown
  toolId?: string
  toolResult?: { content: string; isError: boolean } | null
  isError?: boolean
  text?: string
  newSessionId?: string
  exitCode?: number
}

// ─── Per-session slot ────────────────────────────────────────────────────────

export type SessionStatus = 'idle' | 'loading' | 'streaming' | 'error'

export interface SessionSlot {
  serverMessages: NormalizedMessage[]
  realtimeMessages: NormalizedMessage[]
  merged: NormalizedMessage[]
  status: SessionStatus
  fetchedAt: number
  total: number
  hasMore: boolean
  offset: number
  tokenUsage: unknown
}

const EMPTY: NormalizedMessage[] = []

function createEmptySlot(): SessionSlot {
  return {
    serverMessages: EMPTY,
    realtimeMessages: EMPTY,
    merged: EMPTY,
    status: 'idle',
    fetchedAt: 0,
    total: 0,
    hasMore: false,
    offset: 0,
    tokenUsage: null,
  }
}

function computeMerged(server: NormalizedMessage[], realtime: NormalizedMessage[]): NormalizedMessage[] {
  if (realtime.length === 0) return server
  if (server.length === 0) return realtime
  const serverIds = new Set(server.map(m => m.id))
  const extra = realtime.filter(m => !serverIds.has(m.id))
  if (extra.length === 0) return server
  return [...server, ...extra]
}

// ─── Stale threshold ─────────────────────────────────────────────────────────

const STALE_THRESHOLD_MS = 30_000
const MAX_REALTIME_MESSAGES = 500

// ─── Store ────────────────────────────────────────────────────────────────────

const store = new Map<string, SessionSlot>()
const activeSessionId = ref<string | null>(null)

// Force re-render
const tick = ref(0)
const notify = (sessionId: string) => {
  if (sessionId === activeSessionId.value) {
    tick.value++
  }
}

export function setActiveSession(sessionId: string | null) {
  activeSessionId.value = sessionId
}

function getSlot(sessionId: string): SessionSlot {
  if (!store.has(sessionId)) {
    store.set(sessionId, createEmptySlot())
  }
  return store.get(sessionId)!
}

export function hasSession(sessionId: string): boolean {
  return store.has(sessionId)
}

export async function fetchFromServer(
  sessionId: string,
  opts: {
    provider?: 'claude' | 'qwen' | 'gemini' | 'codex'
    limit?: number | null
    offset?: number
  } = {}
) {
  const slot = getSlot(sessionId)
  slot.status = 'loading'
  notify(sessionId)

  try {
    const params = new URLSearchParams()
    if (opts.provider) params.append('provider', opts.provider)
    if (opts.limit !== null && opts.limit !== undefined) {
      params.append('limit', String(opts.limit))
      params.append('offset', String(opts.offset ?? 0))
    }

    const qs = params.toString()
    const url = `/code-agent/sessions/${encodeURIComponent(sessionId)}/messages${qs ? `?${qs}` : ''}`
    const response = await authenticatedFetch(url)

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const data = await response.json()
    const messages: NormalizedMessage[] = data.messages || []

    slot.serverMessages = messages
    slot.total = data.total ?? messages.length
    slot.hasMore = Boolean(data.hasMore)
    slot.offset = (opts.offset ?? 0) + messages.length
    slot.fetchedAt = Date.now()
    slot.status = 'idle'
    slot.merged = computeMerged(slot.serverMessages, slot.realtimeMessages)

    if (data.tokenUsage) {
      slot.tokenUsage = data.tokenUsage
    }

    notify(sessionId)
    return slot
  } catch (error) {
    console.error(`[SessionStore] fetch failed for ${sessionId}:`, error)
    slot.status = 'error'
    notify(sessionId)
    return slot
  }
}

export async function fetchMore(
  sessionId: string,
  opts: {
    provider?: 'claude' | 'qwen' | 'gemini' | 'codex'
    limit?: number
  } = {}
) {
  const slot = getSlot(sessionId)
  if (!slot.hasMore) return slot

  const params = new URLSearchParams()
  if (opts.provider) params.append('provider', opts.provider)
  const limit = opts.limit ?? 20
  params.append('limit', String(limit))
  params.append('offset', String(slot.offset))

  const qs = params.toString()
  const url = `/code-agent/sessions/${encodeURIComponent(sessionId)}/messages${qs ? `?${qs}` : ''}`

  try {
    const response = await authenticatedFetch(url)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()
    const olderMessages: NormalizedMessage[] = data.messages || []

    slot.serverMessages = [...olderMessages, ...slot.serverMessages]
    slot.hasMore = Boolean(data.hasMore)
    slot.offset = slot.offset + olderMessages.length
    slot.merged = computeMerged(slot.serverMessages, slot.realtimeMessages)
    notify(sessionId)
    return slot
  } catch (error) {
    console.error(`[SessionStore] fetchMore failed for ${sessionId}:`, error)
    return slot
  }
}

export function appendRealtime(sessionId: string, msg: NormalizedMessage) {
  const slot = getSlot(sessionId)
  let updated = [...slot.realtimeMessages, msg]
  if (updated.length > MAX_REALTIME_MESSAGES) {
    updated = updated.slice(-MAX_REALTIME_MESSAGES)
  }
  slot.realtimeMessages = updated
  slot.merged = computeMerged(slot.serverMessages, slot.realtimeMessages)
  notify(sessionId)
}

export function appendRealtimeBatch(sessionId: string, msgs: NormalizedMessage[]) {
  if (msgs.length === 0) return
  const slot = getSlot(sessionId)
  let updated = [...slot.realtimeMessages, ...msgs]
  if (updated.length > MAX_REALTIME_MESSAGES) {
    updated = updated.slice(-MAX_REALTIME_MESSAGES)
  }
  slot.realtimeMessages = updated
  slot.merged = computeMerged(slot.serverMessages, slot.realtimeMessages)
  notify(sessionId)
}

export async function refreshFromServer(
  sessionId: string,
  opts: { provider?: 'claude' | 'qwen' | 'gemini' | 'codex' } = {}
) {
  const slot = getSlot(sessionId)
  try {
    const params = new URLSearchParams()
    if (opts.provider) params.append('provider', opts.provider)

    const qs = params.toString()
    const url = `/code-agent/sessions/${encodeURIComponent(sessionId)}/messages${qs ? `?${qs}` : ''}`
    const response = await authenticatedFetch(url)

    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()

    slot.serverMessages = data.messages || []
    slot.total = data.total ?? slot.serverMessages.length
    slot.hasMore = Boolean(data.hasMore)
    slot.fetchedAt = Date.now()
    slot.realtimeMessages = []
    slot.merged = computeMerged(slot.serverMessages, slot.realtimeMessages)
    notify(sessionId)
  } catch (error) {
    console.error(`[SessionStore] refresh failed for ${sessionId}:`, error)
  }
}

export function setStatus(sessionId: string, status: SessionStatus) {
  const slot = getSlot(sessionId)
  slot.status = status
  notify(sessionId)
}

export function isStale(sessionId: string): boolean {
  const slot = store.get(sessionId)
  if (!slot) return true
  return Date.now() - slot.fetchedAt > STALE_THRESHOLD_MS
}

export function updateStreaming(sessionId: string, accumulatedText: string, msgProvider: 'claude' | 'qwen' | 'gemini' | 'codex') {
  const slot = getSlot(sessionId)
  const streamId = `__streaming_${sessionId}`
  const msg: NormalizedMessage = {
    id: streamId,
    sessionId,
    timestamp: new Date().toISOString(),
    provider: msgProvider,
    kind: 'stream_delta',
    content: accumulatedText,
  }
  const idx = slot.realtimeMessages.findIndex(m => m.id === streamId)
  if (idx >= 0) {
    slot.realtimeMessages = [...slot.realtimeMessages]
    slot.realtimeMessages[idx] = msg
  } else {
    slot.realtimeMessages = [...slot.realtimeMessages, msg]
  }
  slot.merged = computeMerged(slot.serverMessages, slot.realtimeMessages)
  notify(sessionId)
}

export function finalizeStreaming(sessionId: string) {
  const slot = store.get(sessionId)
  if (!slot) return
  const streamId = `__streaming_${sessionId}`
  const idx = slot.realtimeMessages.findIndex(m => m.id === streamId)
  if (idx >= 0) {
    const stream = slot.realtimeMessages[idx]
    slot.realtimeMessages = [...slot.realtimeMessages]
    slot.realtimeMessages[idx] = {
      ...stream,
      id: `text_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      kind: 'text',
      role: 'assistant',
    }
    slot.merged = computeMerged(slot.serverMessages, slot.realtimeMessages)
    notify(sessionId)
  }
}

export function clearRealtime(sessionId: string) {
  const slot = store.get(sessionId)
  if (slot) {
    slot.realtimeMessages = []
    slot.merged = computeMerged(slot.serverMessages, slot.realtimeMessages)
    notify(sessionId)
  }
}

export function getMessages(sessionId: string): NormalizedMessage[] {
  return store.get(sessionId)?.merged ?? []
}

export function getSessionSlot(sessionId: string): SessionSlot | undefined {
  return store.get(sessionId)
}

// 导出 tick 用于响应式更新
export function useSessionStore() {
  return {
    tick,
    activeSessionId,
    setActiveSession,
    getSlot,
    hasSession,
    fetchFromServer,
    fetchMore,
    appendRealtime,
    appendRealtimeBatch,
    refreshFromServer,
    setStatus,
    isStale,
    updateStreaming,
    finalizeStreaming,
    clearRealtime,
    getMessages,
    getSessionSlot,
  }
}

export type SessionStore = ReturnType<typeof useSessionStore>