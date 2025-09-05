<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <h3>MediAgent</h3>
    </div>
    
    <div class="sidebar-content">
      <router-link to="/" class="new-chat-link">
        <a-button type="primary" block class="new-chat-btn">新建对话</a-button>
      </router-link>
      
      <div class="history-section">
        <h4>历史对话</h4>
        <a-list class="chat-list" :split="false">
          <a-list-item 
            v-for="c in conversations" 
            :key="c.id" 
            :class="['chat-item', { active: c.id === currentId }]"
            @click="openConversation(c.id)"
          >
            <div class="chat-item-link">
              <div class="chat-title">{{ c.title || c.id }}</div>
              <div class="chat-preview">{{ c.messages[c.messages.length - 1]?.content || '...' }}</div>
            </div>
          </a-list-item>
        </a-list>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 侧边栏组件
 * 显示应用标题、新建对话按钮和历史会话列表
 * 提供会话切换功能
 */
import { useConversationsStore } from '@/store/conversations'
import { useRouter, useRoute } from 'vue-router'
import { computed } from 'vue'

// 路由相关
const router = useRouter()
const route = useRoute()

// 状态管理
const conversationsStore = useConversationsStore()

// 计算属性
/** 当前活跃的会话ID，从路由参数获取 */
const currentId = computed(() => String(route.params.id || ''))
/** 会话列表，从store获取 */
const conversations = computed(() => conversationsStore.conversations)

/**
 * 打开指定会话
 * @param id 会话ID
 */
const openConversation = (id: string) => {
  if (id && id !== currentId.value) {
    router.push(`/chat/${id}`)
  }
}
</script>

<style scoped>
/* 侧边栏根容器：固定宽度、白底、右侧分割线与阴影 */
.sidebar {
  width: 300px;
  height: 100%;
  background: white;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 8px rgba(0,0,0,0.1);
  flex-shrink: 0;
}

/* 顶部标题区：内边距与底部分隔线 */
.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #e0e0e0;
}

/* 标题文本：大小与颜色 */
.sidebar-header h3 {
  margin: 0;
  color: #333;
  font-size: 18px;
}

/* 内容滚动区：撑满剩余高度，允许纵向滚动 */
.sidebar-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

/* 新建对话按钮：渐变背景、圆角、悬浮上移阴影 */
.new-chat-btn {
  width: 100%;
  height: 60px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 12px;
  cursor: pointer;
  font-size: 16px;
  margin-bottom: 24px;
  transition: all 0.2s ease;
}

.new-chat-link, .chat-item-link { text-decoration: none; color: inherit; display: block; }

/* 新建对话按钮悬停效果：轻微上移与阴影 */
.new-chat-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

/* 历史区域标题：间距、字号与颜色 */
.history-section h4 {
  margin: 0 0 16px 0;
  color: #666;
  font-size: 14px;
  font-weight: 500;
}

/* 对话列表容器：纵向间距 */
.chat-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 单条对话项：圆角、边框、过渡与可点击 */
.chat-item {
  padding: 12px !important;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid #e5e7eb;
  margin-bottom: 10px;
  background: #fff;
}

/* 对话项悬停：浅灰背景与边框高亮 */
.chat-item:hover {
  background: #f8f9fa;
  border-color: #e9ecef;
}

/* 激活中的对话项：浅蓝背景与主色边框 */
.chat-item.active {
  background: #e3f2fd;
  border-color: #2196f3;
}

/* 对话标题：加粗、字号与颜色 */
.chat-title {
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
  font-size: 14px;
}

/* 对话预览：灰色小号文字，超出省略 */
.chat-preview {
  color: #666;
  font-size: 12px;
  display: block;
  width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 滚动条：窄条、圆角、轻度着色 */
.sidebar-content::-webkit-scrollbar {
  width: 6px;
}

/* 滚动条轨道：透明 */
.sidebar-content::-webkit-scrollbar-track {
  background: transparent;
}

/* 滚动条拇指：半透明深色、圆角 */
.sidebar-content::-webkit-scrollbar-thumb {
  background: rgba(0,0,0,0.2);
  border-radius: 3px;
}

/* 滚动条拇指悬停：稍深颜色 */
.sidebar-content::-webkit-scrollbar-thumb:hover {
  background: rgba(0,0,0,0.3);
}
</style>