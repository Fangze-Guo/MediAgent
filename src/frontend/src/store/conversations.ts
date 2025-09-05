/**
 * 会话管理Store
 * 使用Pinia管理聊天会话的状态，包括创建、删除、消息管理等功能
 * 数据持久化存储在localStorage中
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 聊天消息类型定义
 * 表示单条聊天消息的数据结构
 */
export type ChatMessage = { 
  /** 消息角色：用户或AI助手 */
  role: 'user' | 'assistant'
  /** 消息内容 */
  content: string 
}

/**
 * 会话类型定义
 * 表示一个完整的聊天会话
 */
export type Conversation = { 
  /** 会话唯一标识符 */
  id: string
  /** 会话标题，通常取第一条用户消息的前20个字符 */
  title: string
  /** 会话中的所有消息列表 */
  messages: ChatMessage[] 
}

/**
 * localStorage存储键名
 * 用于在浏览器本地存储中保存会话数据
 */
const STORAGE_KEY = 'mediagent_conversations'

/**
 * 从localStorage加载会话数据
 * @returns Conversation[] 返回解析后的会话列表，解析失败时返回空数组
 */
function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      console.log('localStorage中没有会话数据')
      return []
    }
    const data = JSON.parse(raw)
    // 确保数据是数组格式
    if (Array.isArray(data)) {
      console.log('从localStorage加载会话数据:', data.length, '个会话')
      return data
    }
    console.warn('localStorage中的数据格式不正确')
    return []
  } catch (error) {
    console.error('加载会话数据失败:', error)
    return []
  }
}

/**
 * 保存会话数据到localStorage
 * @param conversations 要保存的会话列表
 */
function saveConversations(conversations: Conversation[]) {
  try { 
    const data = JSON.stringify(conversations)
    localStorage.setItem(STORAGE_KEY, data)
    console.log('会话数据已保存到localStorage:', conversations.length, '个会话')
  } catch (error) {
    console.error('保存会话数据失败:', error)
  }
}

/**
 * 会话管理Store
 * 使用Pinia的Composition API风格定义store
 * 提供会话的CRUD操作和消息管理功能
 */
export const useConversationsStore = defineStore('conversations', () => {
  // 响应式会话列表，从localStorage初始化
  const conversations = ref<Conversation[]>(loadConversations())

  // 计算属性：返回会话列表的只读版本
  const conversationsList = computed(() => conversations.value)

  /**
   * 创建新会话
   * @param initialUserText 可选的初始用户消息，用于生成会话标题
   * @returns Conversation 返回新创建的会话对象
   */
  function createConversation(initialUserText?: string): Conversation {
    // 生成唯一ID：web-前缀 + 时间戳
    const id = 'web-' + Date.now()
    
    // 生成会话标题：取用户消息的前20个字符，超出则加省略号
    const title = initialUserText 
      ? (initialUserText.length > 20 ? initialUserText.slice(0, 20) + '…' : initialUserText) 
      : ''
    
    // 创建会话对象
    const conv: Conversation = { id, title, messages: [] }
    
    // 如果有初始消息，添加到会话中
    if (initialUserText) {
      conv.messages.push({ role: 'user', content: initialUserText })
    }
    
    // 将会话添加到列表开头（最新的在前面）
    conversations.value.unshift(conv)
    
    // 保存到localStorage
    saveConversations(conversations.value)
    
    return conv
  }

  /**
   * 根据ID获取会话
   * @param id 会话ID
   * @returns Conversation | undefined 找到的会话或undefined
   */
  function getConversation(id: string): Conversation | undefined {
    return conversations.value.find(c => c.id === id)
  }

  /**
   * 向指定会话添加消息
   * @param id 会话ID
   * @param msg 要添加的消息
   */
  function appendMessage(id: string, msg: ChatMessage) {
    const conversation = getConversation(id)
    if (!conversation) {
      console.warn(`会话 ${id} 不存在，无法添加消息`)
      return
    }
    
    // 添加消息到会话
    conversation.messages.push(msg)
    
    // 如果是用户消息且会话还没有标题，则生成标题
    if (!conversation.title && msg.role === 'user') {
      conversation.title = msg.content.length > 20 
        ? msg.content.slice(0, 20) + '…' 
        : msg.content
    }
    
    // 保存到localStorage
    saveConversations(conversations.value)
  }

  /**
   * 删除指定会话
   * @param id 要删除的会话ID
   */
  function deleteConversation(id: string) {
    console.log('开始删除会话:', id)
    console.log('删除前会话列表:', conversations.value.map(c => ({ id: c.id, title: c.title })))
    
    const index = conversations.value.findIndex(c => c.id === id)
    if (index !== -1) {
      const deletedConversation = conversations.value[index]
      conversations.value.splice(index, 1)
      saveConversations(conversations.value)
      
      console.log('成功删除会话:', deletedConversation.title)
      console.log('删除后会话列表:', conversations.value.map(c => ({ id: c.id, title: c.title })))
    } else {
      console.warn(`会话 ${id} 不存在，无法删除`)
    }
  }

  /**
   * 清空所有会话
   * 谨慎使用，会删除所有历史对话
   */
  function clearAllConversations() {
    conversations.value = []
    saveConversations(conversations.value)
  }

  // 返回store的公共接口
  return {
    /** 会话列表（只读） */
    conversations: conversationsList,
    /** 创建新会话 */
    createConversation,
    /** 获取指定会话 */
    getConversation,
    /** 添加消息到会话 */
    appendMessage,
    /** 删除会话 */
    deleteConversation,
    /** 清空所有会话 */
    clearAllConversations
  }
})