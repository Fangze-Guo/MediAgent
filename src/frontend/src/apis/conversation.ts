/**
 * 对话相关API接口
 * 提供与后端对话服务的交互功能
 */
import { get, post, postJson, del } from '@/utils/request'

/**
 * 对话信息接口
 */
export interface ConversationInfo {
  /** 对话唯一标识符 */
  conversation_uid: string
  /** 对话所有者ID */
  owner_uid: string
}

/**
 * 对话消息接口
 * 与后端main_chat.json中的消息结构保持一致
 */
export interface ConversationMessage {
  /** 消息角色 */
  role: 'user' | 'assistant'
  /** 消息内容 */
  content: string
  /** 消息时间戳（可选，后端可能不提供） */
  timestamp?: string
  /** 附件列表（图片 OSS URL 等） */
  attachments?: { type: string; url: string }[]
}

/**
 * 创建对话请求参数
 */
export interface CreateConversationRequest {
  /** 用户ID */
  user_id: string
}

/**
 * 添加消息请求参数
 */
export interface AddMessageRequest {
  /** 对话ID */
  conversation_id: string
  /** 消息内容 */
  content: string
}

/**
 * 添加流消息请求参数
 */
export interface AddStreamMessageRequest {
  /** 对话ID */
  conversation_id: string
  /** 目标流 */
  target: string
  /** 消息内容 */
  content: string
}

/**
 * 后端BaseResponse结构
 */
interface BaseResponse<T> {
  code: number
  data: T
  message: string
}

/**
 * RAG 来源引用
 */
export interface RagSource {
  kb_name: string
  content: string
  score: number
  doc_id?: number
}

/** 知识库开始检索事件 */
export interface SearchStartEvent {
  kb: string
  kb_id: number
}

/** 知识库检索完成事件 */
export interface SearchResultEvent {
  kb: string
  kb_id: number
  found: number
}

/**
 * Agent 消息响应
 */
export interface AgentMessageResult {
  reply: string
  sources: RagSource[]
}

/**
 * 创建新对话
 * @param user_id 用户ID
 * @returns Promise<ConversationInfo> 返回创建的对话信息
 */
export async function createConversation(user_id: string): Promise<ConversationInfo> {
  try {
    const response = await post<BaseResponse<ConversationInfo>>(`/conversation/create?user_id=${user_id}`)
    return response.data.data
  } catch (error) {
    console.error('创建对话失败:', error)
    throw new Error('创建对话失败，请稍后再试')
  }
}

/**
 * 向Agent添加消息并获取响应
 * @param conversation_id 对话ID
 * @param content 消息内容
 * @returns Promise<AgentMessageResult> 返回回复内容和来源引用
 */
export async function addMessageToAgent(conversation_id: string, content: string, images?: string[]): Promise<AgentMessageResult> {
  try {
    const response = await post<BaseResponse<AgentMessageResult>>('/conversation/add', {
      conversation_id, content, images: images ?? []
    })
    return response.data.data
  } catch (error) {
    console.error('发送消息失败:', error)
    throw new Error('发送消息失败，请稍后再试')
  }
}

/**
 * 获取对话消息列表
 * @param conversation_id 对话ID
 * @param target 目标消息流，默认为'main_chat'
 * @returns Promise<ConversationMessage[]> 返回消息列表
 */
export async function getMessages(conversation_id: string, target: string = 'main_chat'): Promise<ConversationMessage[]> {
  try {
    const response = await get<BaseResponse<ConversationMessage[]>>(`/conversation?conversation_id=${conversation_id}&target=${target}`)
    return response.data.data
  } catch (error) {
    console.error('获取消息失败:', error)
    throw new Error('获取消息失败，请稍后再试')
  }
}

/**
 * 根据用户ID获取其所有会话ID
 * @param user_id 用户ID
 * @returns Promise<string[]> 返回会话ID列表
 */
export async function getUserConversations(user_id: string): Promise<string[]> {
  try {
    const response = await get<BaseResponse<string[]>>(`/conversation/user/${user_id}`)
    return response.data.data
  } catch (error) {
    console.error('获取用户会话列表失败:', error)
    throw new Error('获取用户会话列表失败，请稍后再试')
  }
}

/**
 * 删除会话
 * @param conversation_id 会话ID
 * @returns Promise<boolean> 返回删除是否成功
 */
export async function deleteConversation(conversation_id: string): Promise<boolean> {
  try {
    const response = await del<BaseResponse<boolean>>(`/conversation/${conversation_id}`)
    return response.data.data
  } catch (error) {
    console.error('删除会话失败:', error)
    throw new Error('删除会话失败，请稍后再试')
  }
}

/**
 * 流式发送消息（SSE），逐 token 回调，结束时触发 onSources / onDone
 */
export async function streamMessageToAgent(
  conversation_id: string,
  content: string,
  callbacks: {
    onToken: (token: string) => void
    onSearchStart?: (data: SearchStartEvent) => void
    onSearchResult?: (data: SearchResultEvent) => void
    onSources: (sources: RagSource[]) => void
    onDone: () => void
    onError?: (err: Error) => void
  },
  signal?: AbortSignal,
  images?: string[],
  attachments?: { type: string; url: string }[]
): Promise<void> {
  const url = `/api/conversation/stream`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id, content, images: images ?? [], attachments: attachments ?? [] }),
    signal,
  })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (data === '[DONE]') { callbacks.onDone(); return }
        if (data.startsWith('[SOURCES]')) {
          try { callbacks.onSources(JSON.parse(data.slice(9))) } catch { /* ignore */ }
          continue
        }
        if (data.startsWith('[SEARCH_START]')) {
          try { callbacks.onSearchStart?.(JSON.parse(data.slice(14))) } catch { /* ignore */ }
          continue
        }
        if (data.startsWith('[SEARCH_RESULT]')) {
          try { callbacks.onSearchResult?.(JSON.parse(data.slice(15))) } catch { /* ignore */ }
          continue
        }
        if (data) callbacks.onToken(data)
      }
    }
  } finally {
    reader.releaseLock()
  }
  callbacks.onDone()
}

/**
 * 添加流消息
 * @param conversation_id 对话ID
 * @param target 目标流
 * @param content 消息内容
 * @returns Promise<void>
 */
export async function addStreamMessage(
  conversation_id: string, 
  target: string, 
  content: string
): Promise<void> {
  try {
    await postJson<void, AddStreamMessageRequest>('/conversation/add_stream', {
      conversation_id,
      target,
      content
    })
  } catch (error) {
    console.error('添加流消息失败:', error)
    throw new Error('添加流消息失败，请稍后再试')
  }
}
