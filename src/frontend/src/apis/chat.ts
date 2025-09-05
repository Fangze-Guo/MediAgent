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


