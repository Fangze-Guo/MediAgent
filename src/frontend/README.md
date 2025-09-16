# Frontend 前端应用

## 📁 项目结构

```
src/frontend/
├── public/              # 静态资源
├── src/
│   ├── apis/           # API 接口
│   ├── assets/         # 静态资源
│   ├── components/     # Vue 组件
│   ├── layout/         # 布局组件
│   ├── router/         # 路由配置
│   ├── store/          # 状态管理
│   ├── utils/          # 工具函数
│   └── views/          # 页面视图
├── package.json         # 项目配置
├── vite.config.ts      # Vite 配置
└── tsconfig.json       # TypeScript 配置
```

## 🏗️ 技术栈

### 核心框架
- **Vue 3**: 渐进式 JavaScript 框架
- **TypeScript**: 类型安全的 JavaScript
- **Vite**: 快速的前端构建工具

### UI 组件
- **Vue Router**: 官方路由管理器
- **Pinia**: 状态管理库
- **Axios**: HTTP 客户端

### 开发工具
- **ESLint**: 代码质量检查
- **Prettier**: 代码格式化
- **TypeScript**: 类型检查

## 🚀 快速开始

### 安装依赖
```bash
cd src/frontend
npm install
```

### 启动开发服务器
```bash
npm run dev
```

### 构建生产版本
```bash
npm run build
```

## 📋 主要功能

### 用户管理
- 用户注册和登录
- 用户信息管理
- Token 认证

### 聊天对话
- 实时聊天界面
- 流式消息显示
- 历史记录管理

### 文件管理
- 文件上传和下载
- 文件列表浏览
- 文件删除操作

### 工具调用
- 工具列表展示
- 工具调用界面
- 工具结果展示

## 🔧 开发指南

### 组件开发
```vue
<template>
  <div class="component">
    <h1>{{ title }}</h1>
    <button @click="handleClick">点击</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  title: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  click: [value: string]
}>()

const handleClick = () => {
  emit('click', 'Hello')
}
</script>

<style scoped>
.component {
  padding: 20px;
}
</style>
```

### API 调用
```typescript
// apis/chat.ts
import { request } from '@/utils/request'

export interface ChatRequest {
  conversation_id: string
  message: string
  history: Array<{ role: string; content: string }>
}

export interface ChatResponse {
  conversation_id: string
  answer: string
  tool_calls: any[]
}

export const chatApi = {
  async chat(data: ChatRequest): Promise<ChatResponse> {
    return request.post('/chat', data)
  },
  
  async chatStream(data: ChatRequest): Promise<ReadableStream> {
    return request.post('/chat/stream', data, {
      responseType: 'stream'
    })
  }
}
```

### 状态管理
```typescript
// store/conversations.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useConversationsStore = defineStore('conversations', () => {
  const conversations = ref<Conversation[]>([])
  const currentConversation = ref<Conversation | null>(null)
  
  const addMessage = (conversationId: string, message: Message) => {
    const conversation = conversations.value.find(c => c.id === conversationId)
    if (conversation) {
      conversation.messages.push(message)
    }
  }
  
  const createConversation = (title: string) => {
    const conversation: Conversation = {
      id: generateId(),
      title,
      messages: [],
      createdAt: new Date()
    }
    conversations.value.push(conversation)
    return conversation
  }
  
  return {
    conversations,
    currentConversation,
    addMessage,
    createConversation
  }
})
```

### 路由配置
```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import ChatView from '@/views/ChatView.vue'
import FileManageView from '@/views/FileManageView.vue'
import SettingsView from '@/views/SettingsView.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView
  },
  {
    path: '/chat',
    name: 'chat',
    component: ChatView
  },
  {
    path: '/files',
    name: 'files',
    component: FileManageView
  },
  {
    path: '/settings',
    name: 'settings',
    component: SettingsView
  }
]

export const router = createRouter({
  history: createWebHistory(),
  routes
})
```

## 📊 项目结构说明

### 组件层次
```
App.vue
├── Layout.vue
│   ├── Sidebar.vue
│   └── MainContent
│       ├── HomeView.vue
│       ├── ChatView.vue
│       ├── FileManageView.vue
│       └── SettingsView.vue
```

### 数据流
```
View Component
    ↓
Store (Pinia)
    ↓
API Service
    ↓
Backend API
```

### 文件组织
- **`apis/`**: API 接口封装
- **`components/`**: 可复用组件
- **`views/`**: 页面级组件
- **`store/`**: 状态管理
- **`utils/`**: 工具函数
- **`router/`**: 路由配置

## 🚀 部署指南

### 构建生产版本
```bash
npm run build
```

### 部署到服务器
```bash
# 将 dist 目录上传到服务器
scp -r dist/* user@server:/var/www/html/
```

### Nginx 配置
```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/html;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🔧 开发工具

### VS Code 推荐插件
- Vue Language Features (Volar)
- TypeScript Vue Plugin (Volar)
- ESLint
- Prettier
- Auto Rename Tag

### 调试工具
- Vue DevTools
- Chrome DevTools
- Network 面板
- Console 面板