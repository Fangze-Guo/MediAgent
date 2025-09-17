/**
 * 聊天相关API接口
 * 提供与后端聊天服务的交互功能
 */
import { postJson } from '@/utils/request'

/**
 * 聊天消息数据传输对象
 * 用于前后端消息格式统一
 */
export interface ChatMessageDto {
  /** 消息角色：用户或助手 */
  role: 'user' | 'assistant'
  /** 消息内容 */
  content: string
}

/**
 * 文件信息接口
 */
export interface FileInfo {
  /** 文件ID */
  id: string
  /** 原始文件名 */
  originalName: string
  /** 文件大小（字节） */
  size: number
  /** 文件类型 */
  type: string
  /** 文件路径 */
  path: string
  /** 上传时间 */
  uploadTime: string
}

/**
 * 聊天请求数据传输对象
 * 发送给后端的聊天请求参数
 */
export interface ChatReqDto {
  /** 会话ID，用于标识当前对话 */
  conversation_id: string
  /** 用户输入的消息内容 */
  message: string
  /** 历史消息列表，用于上下文理解 */
  history: ChatMessageDto[]
  /** 当前会话关联的文件信息 */
  files?: FileInfo[]
  /** 助手类型：用于指定AI助手的专业领域 */
  assistant_type?: 'general' | 'medical' | 'data' | 'document'
}

/**
 * 聊天响应数据传输对象
 * 后端返回的聊天响应数据
 */
export interface ChatRespDto {
  /** 会话ID，与请求中的conversation_id一致 */
  conversation_id: string
  /** AI助手的回复内容 */
  answer: string
  /** 工具调用列表（预留字段，用于未来扩展） */
  tool_calls: unknown[]
}

/**
 * 发送聊天消息到后端
 * @param req 聊天请求参数
 * @param signal 可选的取消信号，用于中断请求
 * @returns Promise<ChatRespDto> 返回AI助手的回复
 * @throws {Error} 当请求失败时抛出错误
 * 
 * @example
 * ```typescript
 * const response = await chat({
 *   conversation_id: 'web-1234567890',
 *   message: '你好，我想咨询健康问题',
 *   history: [
 *     { role: 'user', content: '你好' },
 *     { role: 'assistant', content: '您好！我是您的健康助手' }
 *   ]
 * })
 * console.log(response.answer) // AI的回复
 * ```
 */
export async function chat(req: ChatReqDto, signal?: AbortSignal): Promise<ChatRespDto> {
  try {
    const response = await postJson<ChatRespDto, ChatReqDto>('/chat', req, signal)
    return response
  } catch (error) {
    console.error('聊天请求失败:', error)
    throw new Error('发送消息失败，请稍后再试')
  }
}

/**
 * 流式聊天接口类型定义
 */
export interface StreamChunk {
  type: 'start' | 'content' | 'tool_call' | 'complete' | 'error'
  content?: string
  tool?: string
  tool_calls?: unknown[]
  error?: string
  conversation_id?: string
}

/**
 * 流式聊天回调函数类型
 */
export interface StreamCallbacks {
  onStart?: (conversationId: string) => void
  onContent?: (content: string) => void
  onToolCall?: (tool: string) => void
  onComplete?: (toolCalls: unknown[]) => void
  onError?: (error: string) => void
}

/**
 * 流式发送聊天消息到后端
 * @param req 聊天请求参数
 * @param callbacks 流式回调函数
 * @param signal 可选的取消信号，用于中断请求
 * @returns Promise<void>
 * 
 * @example
 * ```typescript
 * await chatStream({
 *   conversation_id: 'web-1234567890',
 *   message: '你好，我想咨询健康问题',
 *   history: []
 * }, {
 *   onStart: (id) => console.log('开始对话:', id),
 *   onContent: (content) => console.log('收到内容:', content),
 *   onComplete: (toolCalls) => console.log('对话完成')
 * })
 * ```
 */
export async function chatStream(
  req: ChatReqDto, 
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  try {
    // 获取正确的API基础URL
    const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
    const response = await fetch(`${baseURL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req),
      signal
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('无法获取响应流')
    }

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
              const data = JSON.parse(line.slice(6)) as StreamChunk
              
              switch (data.type) {
                case 'start':
                  callbacks.onStart?.(data.conversation_id || '')
                  break
                case 'content':
                  callbacks.onContent?.(data.content || '')
                  break
                case 'tool_call':
                  callbacks.onToolCall?.(data.tool || '')
                  break
                case 'complete':
                  callbacks.onComplete?.(data.tool_calls || [])
                  return
                case 'error':
                  callbacks.onError?.(data.error || '未知错误')
                  return
              }
            } catch (parseError) {
              console.warn('解析流数据失败:', parseError, '原始数据:', line)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  } catch (error) {
    console.error('流式聊天请求失败:', error)
    callbacks.onError?.(error instanceof Error ? error.message : '发送消息失败，请稍后再试')
  }
}

/**
 * 注意：删除会话功能已改为本地实现
 * 由于后端暂未提供删除会话的API接口，
 * 删除功能通过localStorage在客户端实现
 * 
 * 如果未来需要服务端删除功能，可以在此处添加：
 * 
 * export async function deleteConversation(conversationId: string): Promise<void> {
 *   await del(`/conversations/${conversationId}`)
 * }
 */


