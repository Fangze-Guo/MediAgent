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
}

/**
 * 流式响应数据接口
 */
export interface StreamResponseData {
  content: string
  full_content: string
  done: boolean
  error?: string
}

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
  role: 'user' | 'assistant'
  content: string
  created_at?: string
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
    const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
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
 */
export async function parseStreamResponse(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onChunk: (data: StreamResponseData) => void,
  onComplete: (fullContent: string) => void,
  onError: (error: string) => void
): Promise<void> {
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // 保留最后一个不完整的行

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const jsonStr = line.slice(6) // 去掉 "data: " 前缀
            const response: BaseResponse<StreamResponseData> = JSON.parse(jsonStr)

            if (response.code === 200 && response.data) {
              if (response.data.done) {
                onComplete(response.data.full_content)
              } else {
                onChunk(response.data)
              }
            } else {
              onError(response.message || '未知错误')
            }
          } catch (e) {
            console.error('解析 SSE 数据失败:', e, line)
          }
        }
      }
    }

    // 处理剩余的 buffer
    if (buffer.trim()) {
      const lines = buffer.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const jsonStr = line.slice(6)
            const response: BaseResponse<StreamResponseData> = JSON.parse(jsonStr)
            if (response.code === 200 && response.data) {
              if (response.data.done) {
                onComplete(response.data.full_content)
              } else {
                onChunk(response.data)
              }
            }
          } catch (e) {
            console.error('解析 SSE 数据失败:', e)
          }
        }
      }
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
 * @returns 会话详情
 */
export async function getConversationDetail(
  conversationId: string
): Promise<BaseResponse<ConversationDetail>> {
  const response = await get<BaseResponse<ConversationDetail>>(
    `/code-agent/conversations/${conversationId}`
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
