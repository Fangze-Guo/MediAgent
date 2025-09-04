import { postJson } from '@/utils/request'

export interface ChatMessageDto {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatReqDto {
  conversation_id: string
  message: string
  history: ChatMessageDto[]
}

export interface ChatRespDto {
  conversation_id: string
  answer: string
  tool_calls: unknown[]
}

export async function chat(req: ChatReqDto, signal?: AbortSignal) {
  return postJson<ChatRespDto, ChatReqDto>('/chat', req, signal)
}


