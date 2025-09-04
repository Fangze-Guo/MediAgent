import { reactive, computed } from 'vue'

export type ChatMessage = { role: 'user' | 'assistant'; content: string }
export type Conversation = { id: string; title: string; messages: ChatMessage[] }

const STORAGE_KEY = 'mediagent_conversations'

function load(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const data = JSON.parse(raw)
    if (Array.isArray(data)) return data
    return []
  } catch {
    return []
  }
}

function save(list: Conversation[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(list)) } catch {}
}

const state = reactive({
  conversations: load() as Conversation[]
})

export const conversations = computed(() => state.conversations)

export function createConversation(initialUserText?: string): Conversation {
  const id = 'web-' + Date.now()
  const title = initialUserText ? (initialUserText.length > 20 ? initialUserText.slice(0, 20) + '…' : initialUserText) : ''
  const conv: Conversation = { id, title, messages: [] }
  if (initialUserText) conv.messages.push({ role: 'user', content: initialUserText })
  state.conversations.unshift(conv)
  save(state.conversations)
  return conv
}

export function getConversation(id: string): Conversation | undefined {
  return state.conversations.find(c => c.id === id)
}

export function appendMessage(id: string, msg: ChatMessage) {
  const c = getConversation(id)
  if (!c) return
  c.messages.push(msg)
  if (!c.title && msg.role === 'user') {
    c.title = msg.content.length > 20 ? msg.content.slice(0, 20) + '…' : msg.content
  }
  save(state.conversations)
}


