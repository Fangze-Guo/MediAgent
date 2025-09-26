/**
 * 会话管理Store
 * 使用Pinia管理聊天会话的状态，包括创建、删除、消息管理等功能
 * 数据从后端API获取，不再使用localStorage
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { createConversation as createConversationAPI, addMessageToAgent, getMessages } from '@/apis/conversation'
import { useAuthStore } from '@/store/auth'

/**
 * 聊天消息类型定义
 * 表示单条聊天消息的数据结构
 */
export type ChatMessage = { 
  /** 消息角色：用户或AI助手 */
  role: 'user' | 'assistant'
  /** 消息内容 */
  content: string 
  /** 消息是否完成 */
  typingComplete?: boolean
  /** 助手类型：用于标识不同的AI助手 */
  assistantType?: 'general' | 'medical' | 'data' | 'document'
}

/**
 * 工具信息类型定义
 * 表示医学助手中使用的工具信息
 */
export type ToolInfo = {
  /** 工具ID */
  toolId: string
  /** 工具名称 */
  toolName: string
  /** 工具图标组件 */
  toolIcon: any
  /** 工具渐变背景 */
  toolGradient: string
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
  /** 当前会话使用的助手类型 */
  assistantType?: 'general' | 'medical' | 'data' | 'document'
  /** 工具信息（仅医学助手会话使用） */
  toolInfo?: ToolInfo
  /** 是否正在加载消息 */
  loading?: boolean
}

/**
 * 会话管理Store
 * 使用Pinia的Composition API风格定义store
 * 提供会话的CRUD操作和消息管理功能
 */
export const useConversationsStore = defineStore('conversations', () => {
  // 响应式会话列表，不再使用localStorage
  const conversations = ref<Conversation[]>([])
  
  // 当前活跃的会话ID
  const currentConversationId = ref<string>('')

  // 计算属性：返回会话列表的只读版本
  const conversationsList = computed(() => conversations.value)
  
  // 计算属性：当前活跃的会话
  const currentConversation = computed(() => 
    conversations.value.find(c => c.id === currentConversationId.value)
  )

  /**
   * 创建新会话
   * @param assistantType 可选的助手类型
   * @param toolInfo 可选的工具信息（仅医学助手会话使用）
   * @returns Promise<Conversation> 返回新创建的会话对象
   */
  async function createConversation(
    assistantType?: 'general' | 'medical' | 'data' | 'document',
    toolInfo?: ToolInfo
  ): Promise<Conversation> {
    try {
      // 获取当前登录用户
      const authStore = useAuthStore()
      if (!authStore.user) {
        throw new Error('用户未登录，无法创建会话')
      }
      
      // 调用后端API创建对话，使用当前登录用户的ID
      const conversationInfo = await createConversationAPI(authStore.user.uid.toString())
      
      // 生成会话标题
      let title = '新对话'
      if (assistantType === 'medical') {
        if (toolInfo) {
          title = toolInfo.toolName
        } else {
          title = '医学助手对话'
        }
      }
      
      // 创建会话对象
      const conv: Conversation = { 
        id: conversationInfo.conversation_uid, 
        title, 
        messages: [],
        assistantType: assistantType || 'general',
        toolInfo: toolInfo,
        loading: false
      }
      
      // 将会话添加到列表开头（最新的在前面）
      conversations.value.unshift(conv)
      
      // 设置为当前活跃会话
      currentConversationId.value = conv.id
      
      return conv
    } catch (error) {
      console.error('创建会话失败:', error)
      throw error
    }
  }

  /**
   * 根据ID获取会话
   * @param id 会话ID
   * @returns Conversation | undefined 找到的会话或undefined
   */
  function getConversation(id: string): Conversation | undefined {
    if (!id || !conversations.value) {
      return undefined
    }
    return conversations.value.find(c => c.id === id)
  }

  /**
   * 加载会话消息
   * @param id 会话ID
   * @param target 目标消息流，默认为'main_chat'
   * @param forceReload 是否强制重新加载，默认为false
   * @returns Promise<void>
   */
  async function loadConversationMessages(id: string, target: string = 'main_chat', forceReload: boolean = false): Promise<void> {
    const conversation = getConversation(id)
    if (!conversation) {
      console.warn(`会话 ${id} 不存在`)
      return
    }

    // 如果正在加载且不是强制重新加载，则跳过
    if (conversation.loading && !forceReload) {
      console.log(`会话 ${id} 正在加载中，跳过重复加载`)
      return
    }

    // 如果已有消息且不是强制重新加载，则跳过
    if (conversation.messages.length > 0 && !forceReload) {
      console.log(`会话 ${id} 已有 ${conversation.messages.length} 条消息，跳过加载`)
      return
    }

    try {
      conversation.loading = true
      console.log(`开始从后端加载会话 ${id} 的消息...`)
      const messages = await getMessages(id, target)
      console.log(`从后端获取到 ${messages.length} 条消息`)
      
      // 转换消息格式，确保消息正确解析
      conversation.messages = messages.map(msg => ({
        role: msg.role as 'user' | 'assistant',
        content: msg.content || '',
        typingComplete: true
      }))
      
      // 如果没有标题且有消息，生成标题
      if (!conversation.title && conversation.messages.length > 0) {
        const firstUserMessage = conversation.messages.find(m => m.role === 'user')
        if (firstUserMessage) {
          conversation.title = firstUserMessage.content.length > 20 
            ? firstUserMessage.content.slice(0, 20) + '…' 
            : firstUserMessage.content
        }
      }
      
      console.log(`会话 ${id} 消息加载完成，共 ${conversation.messages.length} 条消息`)
    } catch (error) {
      console.error('加载会话消息失败:', error)
      throw error
    } finally {
      conversation.loading = false
    }
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
  }

  /**
   * 发送消息到Agent并获取响应
   * @param id 会话ID
   * @param content 消息内容
   * @returns Promise<string> Agent的响应
   */
  async function sendMessageToAgent(id: string, content: string): Promise<string> {
    const conversation = getConversation(id)
    if (!conversation) {
      throw new Error(`会话 ${id} 不存在`)
    }

    try {
      // 添加用户消息
      const userMessage: ChatMessage = {
        role: 'user',
        content,
        typingComplete: true
      }
      appendMessage(id, userMessage)

      // 添加加载中的助手消息
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: '',
        typingComplete: false
      }
      appendMessage(id, assistantMessage)

      // 调用后端API获取Agent响应
      const response = await addMessageToAgent(id, content)
      
      // 更新助手消息
      assistantMessage.content = response
      assistantMessage.typingComplete = true
      
      // Agent响应后，从后端重新获取最新的会话数据
      try {
        console.log(`Agent响应完成，准备刷新会话 ${id} 的数据...`)
        // 延迟一点时间确保后端数据已保存
        await new Promise(resolve => setTimeout(resolve, 100))
        await loadConversationMessages(id, 'main_chat', true) // 强制重新加载
        console.log(`会话 ${id} 数据刷新完成`)
      } catch (error) {
        console.warn('刷新会话数据失败:', error)
        // 即使刷新失败，也继续使用本地数据
      }
      
      return response
    } catch (error) {
      console.error('发送消息失败:', error)
      // 移除加载中的助手消息
      const lastMessage = conversation.messages[conversation.messages.length - 1]
      if (lastMessage && !lastMessage.typingComplete) {
        conversation.messages.pop()
      }
      throw error
    }
  }

  /**
   * 设置当前活跃会话
   * @param id 会话ID
   */
  function setCurrentConversation(id: string) {
    currentConversationId.value = id
  }

  /**
   * 删除指定会话（本地删除，后端暂不支持）
   * @param id 要删除的会话ID
   */
  function deleteConversation(id: string) {
    console.log('开始删除会话:', id)
    
    const index = conversations.value.findIndex(c => c.id === id)
    if (index !== -1) {
      const deletedConversation = conversations.value[index]
      conversations.value.splice(index, 1)
      
      // 如果删除的是当前会话，清空当前会话ID
      if (currentConversationId.value === id) {
        currentConversationId.value = ''
      }
      
      console.log('成功删除会话:', deletedConversation.title)
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
    currentConversationId.value = ''
  }

  /**
   * 更新会话的助手类型
   * @param id 会话ID
   * @param assistantType 助手类型
   */
  function updateConversationAssistantType(id: string, assistantType: string) {
    const conversation = conversations.value.find(c => c.id === id)
    if (conversation) {
      conversation.assistantType = assistantType as 'general' | 'medical' | 'data' | 'document'
    }
  }

  // 返回store的公共接口
  return {
    /** 会话列表（只读） */
    conversations: conversationsList,
    /** 当前活跃会话ID */
    currentConversationId: computed(() => currentConversationId.value),
    /** 当前活跃会话 */
    currentConversation,
    /** 创建新会话 */
    createConversation,
    /** 获取指定会话 */
    getConversation,
    /** 加载会话消息 */
    loadConversationMessages,
    /** 添加消息到会话 */
    appendMessage,
    /** 发送消息到Agent */
    sendMessageToAgent,
    /** 设置当前活跃会话 */
    setCurrentConversation,
    /** 删除会话 */
    deleteConversation,
    /** 清空所有会话 */
    clearAllConversations,
    /** 更新会话助手类型 */
    updateConversationAssistantType
  }
})