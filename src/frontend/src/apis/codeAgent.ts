/**
 * Code智能体API接口
 */
import { get, post, put, del } from '@/utils/request'

/**
 * 聊天消息接口
 */
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/**
 * 聊天请求接口
 */
export interface ChatRequest {
  conversation_id?: string
  message: string
  messages?: ChatMessage[]  // 历史消息列表
}

/**
 * 流式响应数据接口
 */
export interface StreamResponseData {
  content?: string
  full_content?: string
  done?: boolean
  event_type?: string
  error?: string
  type?: 'thinking' | 'thinking_delta' | 'text' | 'done'  // ✅ 新增
  thinking?: string  // ✅ 新增
}

/**
 * Qwen 流式事件基类
 */
export interface QwenStreamEvent {
  type: string
  uuid: string
  session_id: string
  parent_tool_use_id?: string
}

/**
 * 系统初始化事件
 */
export interface SystemEvent extends QwenStreamEvent {
  type: 'system'
  subtype: 'init'
  cwd: string
  tools: string[]
  mcp_servers: any[]
  model: string
  permission_mode: string
  slash_commands: string[]
  qwen_code_version: string
  agents: string[]
}

/**
 * 流式事件
 */
export interface StreamEventData {
  type: string
  [key: string]: any
}

export interface StreamEvent extends QwenStreamEvent {
  type: 'stream_event'
  event: StreamEventData
}

/**
 * 消息开始事件
 */
export interface MessageStartEvent extends StreamEventData {
  type: 'message_start'
  message: {
    id: string
    role: 'assistant'
    model: string
    content: any[]
  }
}

/**
 * 内容块增量事件
 */
export interface ContentBlockDeltaEvent extends StreamEventData {
  type: 'content_block_delta'
  index: number
  delta: {
    type: 'text_delta'
    text: string
  }
}

/**
 * 内容块停止事件
 */
export interface ContentBlockStopEvent extends StreamEventData {
  type: 'content_block_stop'
  index: number
}

/**
 * 消息停止事件
 */
export interface MessageStopEvent extends StreamEventData {
  type: 'message_stop'
}

/**
 * 助手消息事件
 */
export interface AssistantEvent extends QwenStreamEvent {
  type: 'assistant'
  message: {
    id: string
    type: 'message'
    role: 'assistant'
    model: string
    content: any[]
    stop_reason: string | null
    usage: {
      input_tokens: number
      output_tokens: number
      cache_read_input_tokens: number
      total_tokens: number
    }
  }
}

/**
 * 结果事件
 */
export interface ResultEvent extends QwenStreamEvent {
  type: 'result'
  subtype: 'success'
  is_error: boolean
  duration_ms: number
  duration_api_ms: number
  num_turns: number
  result: string
  usage: {
    input_tokens: number
    output_tokens: number
    cache_read_input_tokens: number
    total_tokens: number
  }
  permission_denials: any[]
}

/**
 * 会话创建事件
 */
export interface SessionCreatedEvent extends QwenStreamEvent {
  type: 'session_created'
  sessionId: string
  newSessionId?: string
  isNewSession?: boolean
}

/**
 * 联合类型：所有可能的 Qwen 流式事件
 */
export type QwenEventType =
  | SystemEvent
  | StreamEvent
  | AssistantEvent
  | ResultEvent
  | SessionCreatedEvent

/**
 * 创建会话请求接口
 */
export interface CreateConversationRequest {
  title?: string
}

/**
 * 更新会话请求接口
 */
export interface UpdateConversationRequest {
  title?: string
}

/**
 * 消息响应接口
 */
export interface MessageResponse {
  message_id: string
  conversation_id: string
  role?: 'user' | 'assistant' | null  // null 表示非消息事件（如 skill_call）
  content?: string | null
  thinking?: string  // ✅ 新增：思考内容
  created_at?: string
  loading?: boolean
  // Skill call 字段
  event_type?: 'skill_call' | 'todo' | null
  skill_name?: string | null
  skill_arguments?: string | null
  // Todo 事件字段
  todo_list?: TodoItem[]
}

/**
 * Todo 项目接口
 */
export interface TodoItem {
  content: string
  status: 'pending' | 'in_progress' | 'completed'
  activeForm?: string
}

/**
 * 会话信息接口
 */
export interface ConversationInfo {
  conversation_id: string
  user_id: number
  title?: string
  created_at?: string
  updated_at?: string
  message_count: number
  last_message?: string
}

/**
 * 会话详情接口
 */
export interface ConversationDetail {
  conversation_id: string
  user_id: number
  title?: string
  created_at?: string
  updated_at?: string
  messages: MessageResponse[]
}

/**
 * 基础响应接口
 */
export interface BaseResponse<T = any> {
  code: number
  data?: T
  message: string
}

/**
 * 流式对话接口（SSE）
 * @param request 聊天请求
 * @returns ReadableStream
 */
export async function streamChat(request: ChatRequest): Promise<ReadableStream<Uint8Array> | null> {
  try {
    // 获取 API 基础 URL
    const baseURL = (import.meta as any).env?.VITE_API_BASE || '/api'
    const url = `${baseURL}/code-agent/taking`

    // 获取 token（如果需要认证）
    const token = localStorage.getItem('mediagent_token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(request)
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return response.body
  } catch (error) {
    console.error('流式对话失败:', error)
    return null
  }
}

/**
 * 同步对话接口
 * @param request 聊天请求
 * @returns 响应数据
 */
export async function syncChat(request: ChatRequest): Promise<BaseResponse<string>> {
  const response = await post<BaseResponse<string>>('/code-agent/taking/sync', request)
  return response.data
}

/**
 * 解析 SSE 流式数据
 * @param reader ReadableStreamDefaultReader
 * @param onChunk 接收到 chunk 时的回调
 * @param onComplete 完成时的回调
 * @param onError 错误时的回调
 * @param onEvent 可选的事件回调，用于处理特定的流式事件
 */
export async function parseStreamResponse(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onChunk: (data: { full_content?: string; thinking?: string; content?: string }, type?: string) => void,
  onComplete: (fullContent: string) => void,
  onError: (error: string) => void,
  onEvent?: (event: QwenEventType) => void
): Promise<void> {
  const decoder = new TextDecoder()
  let buffer = ''
  let completeCalled = false
  let fullContent = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const jsonStr = line.slice(6)
            const data = JSON.parse(jsonStr)

            const kind = data.kind
            const done = data.done

            if (kind === 'thinking') {
              onChunk({ thinking: data.content, full_content: fullContent }, 'thinking')
            } else if (kind === 'stream_delta' || kind === 'text') {
              if (data.content) fullContent = data.content
              onChunk({ content: data.content || fullContent, full_content: fullContent }, 'text')
            } else if (kind === 'complete' || done) {
              if (!completeCalled) {
                completeCalled = true
                onComplete(data.content || fullContent)
              }
            } else if (kind === 'error') {
              onError(data.content || 'Unknown error')
            } else if (kind === 'session_created') {
              // 会话创建事件，传递给 onEvent 处理
              if (onEvent) {
                onEvent(data as any)
              }
            } else {
              // 其他事件类型
              if (onEvent && kind) {
                onEvent(data as any)
              }
            }
          } catch (e) {
            console.error('解析 SSE 数据失败:', e, line)
          }
        }
      }
    }

    // 处理剩余 buffer
    if (buffer.trim() && !completeCalled) {
      try {
        const data = JSON.parse(buffer.trim().replace('data: ', ''))
        if (data.done) {
          onComplete(data.content || fullContent)
        }
      } catch {}
    }
  } catch (error) {
    onError(error instanceof Error ? error.message : '流式读取失败')
  } finally {
    reader.releaseLock()
  }
}

/**
 * 创建新会话
 * @param request 创建会话请求
 * @returns 会话信息
 */
export async function createConversation(request: CreateConversationRequest): Promise<BaseResponse<ConversationInfo>> {
  const response = await post<BaseResponse<ConversationInfo>>('/code-agent/conversations', request)
  return response.data
}

/**
 * 获取会话列表
 * @param limit 返回数量限制
 * @param offset 偏移量
 * @returns 会话信息列表
 */
export async function getConversations(
  limit: number = 50,
  offset: number = 0
): Promise<BaseResponse<ConversationInfo[]>> {
  const response = await get<BaseResponse<ConversationInfo[]>>(
    `/code-agent/conversations?limit=${limit}&offset=${offset}`
  )
  return response.data
}

/**
 * 获取会话详情
 * @param conversationId 会话ID
 * @param signal 可选的 AbortSignal，用于取消请求
 * @returns 会话详情
 */
export async function getConversationDetail(
  conversationId: string,
  signal?: AbortSignal
): Promise<BaseResponse<ConversationDetail>> {
  const response = await get<BaseResponse<ConversationDetail>>(
    `/code-agent/conversations/${conversationId}`,
    { signal }
  )
  return response.data
}

/**
 * 更新会话信息
 * @param conversationId 会话ID
 * @param request 更新会话请求
 * @returns 是否更新成功
 */
export async function updateConversation(
  conversationId: string,
  request: UpdateConversationRequest
): Promise<BaseResponse<boolean>> {
  const response = await put<BaseResponse<boolean>>(
    `/code-agent/conversations/${conversationId}`,
    request
  )
  return response.data
}

/**
 * 删除会话
 * @param conversationId 会话ID
 * @returns 是否删除成功
 */
export async function deleteConversation(
  conversationId: string
): Promise<BaseResponse<boolean>> {
  const response = await del<BaseResponse<boolean>>(
    `/code-agent/conversations/${conversationId}`
  )
  return response.data
}
