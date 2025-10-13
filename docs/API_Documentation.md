# MediAgent API 接口文档 v2.0

## 📋 概述

MediAgent 是一个智能医疗助手系统，提供完整的后端API服务。本文档基于项目实际代码结构，详细描述了所有可用的API接口。

### 🏗️ 架构说明
项目包含两套服务器架构：
- **主服务器** (`server_agent`): 完整功能的生产环境API
- **新架构** (`server_new`): 重构中的新版本API

### 📊 基础信息
- **API 版本**: 2.0.0
- **基础 URL**: `http://localhost:8000`
- **认证方式**: Bearer Token
- **内容类型**: `application/json`
- **字符编码**: UTF-8

### 🚀 快速开始
```bash
# 启动主服务器
python main.py

# 访问API文档
curl http://localhost:8000/docs

# 访问ReDoc文档
curl http://localhost:8000/redoc
```

---

## 🔐 用户管理 API

### 用户注册
**端点**: `POST /user/register`

**请求体**:
```json
{
  "user_name": "testuser",
  "password": "password123"
}
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "uid": 1234567890
  },
  "message": "ok"
}
```

**示例**:
```bash
curl -X POST "http://localhost:8000/user/register" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}'
```

### 用户登录
**端点**: `POST /user/login`

**请求体**:
```json
{
  "user_name": "testuser",
  "password": "password123"
}
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "token": "abc123def456ghi789"
  },
  "message": "ok"
}
```

**示例**:
```bash
curl -X POST "http://localhost:8000/user/login" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}'
```

### 获取用户信息
**端点**: `GET /user/info`

**请求头**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "uid": 1234567890,
    "user_name": "testuser"
  },
  "message": "ok"
}
```

**示例**:
```bash
curl -X GET "http://localhost:8000/user/info" \
  -H "Authorization: Bearer abc123def456ghi789"
```

---

## 🏪 应用商店 API

### 获取应用列表
**端点**: `GET /app-store/apps`

**查询参数**:
- `category` (string, optional): 分类筛选
- `search` (string, optional): 搜索关键词

**响应**:
```json
{
  "code": 200,
  "data": [
    {
      "id": "dicom-converter",
      "name": "DICOM转换器",
      "category": "医学影像",
      "description": "专业的DICOM格式转换工具",
      "icon": "🏥",
      "version": "1.0.0",
      "author": "MediTech团队",
      "downloads": 1250,
      "rating": 4.5,
      "installed": false,
      "featured": true,
      "tags": ["DICOM", "转换", "医学影像"]
    }
  ],
  "message": "ok"
}
```

### 获取应用详情
**端点**: `GET /app-store/apps/{app_id}`

**路径参数**:
- `app_id` (string): 应用ID

**响应**:
```json
{
  "code": 200,
  "data": {
    "id": "dicom-converter",
    "name": "DICOM转换器",
    "category": "医学影像",
    "description": "专业的DICOM格式转换工具",
    "full_description": "这是一个功能强大的DICOM格式转换工具...",
    "icon": "🏥",
    "version": "1.0.0",
    "author": "MediTech团队",
    "downloads": 1250,
    "rating": 4.5,
    "installed": false,
    "featured": true,
    "tags": ["DICOM", "转换", "医学影像"]
  },
  "message": "ok"
}
```

### 获取应用分类
**端点**: `GET /app-store/categories`

**响应**:
```json
{
  "code": 200,
  "data": [
    "医学影像",
    "数据分析",
    "文件管理",
    "标注工具",
    "报告生成"
  ],
  "message": "ok"
}
```

### 获取精选应用
**端点**: `GET /app-store/featured`

**查询参数**:
- `limit` (int, optional): 返回数量限制，默认6

**响应**:
```json
{
  "code": 200,
  "data": [
    {
      "id": "dicom-converter",
      "name": "DICOM转换器",
      "category": "医学影像",
      "description": "专业的DICOM格式转换工具",
      "icon": "🏥",
      "version": "1.0.0",
      "author": "MediTech团队",
      "downloads": 1250,
      "rating": 4.5,
      "installed": false,
      "featured": true,
      "tags": ["DICOM", "转换", "医学影像"]
    }
  ],
  "message": "ok"
}
```

### 安装应用
**端点**: `POST /app-store/apps/{app_id}/install`

**路径参数**:
- `app_id` (string): 应用ID

**响应**:
```json
{
  "code": 200,
  "data": {
    "message": "安装成功"
  },
  "message": "ok"
}
```

### 卸载应用
**端点**: `POST /app-store/apps/{app_id}/uninstall`

**路径参数**:
- `app_id` (string): 应用ID

**响应**:
```json
{
  "code": 200,
  "data": {
    "message": "卸载成功"
  },
  "message": "ok"
}
```

### 获取应用评论
**端点**: `GET /app-store/apps/{app_id}/reviews`

**路径参数**:
- `app_id` (string): 应用ID

**查询参数**:
- `user_id` (int, optional): 用户ID，用于获取用户点赞状态

**响应**:
```json
{
  "code": 200,
  "data": {
    "reviews": [
      {
        "id": 1,
        "app_id": "dicom-converter",
        "user_name": "张医生",
        "rating": 5,
        "comment": "非常好用的工具！转换速度快，支持的格式多。",
        "helpful_count": 24,
        "created_at": "2024-01-01T00:00:00Z",
        "user_liked": true
      }
    ],
    "total": 10,
    "average_rating": 4.5,
    "rating_distribution": {
      "5": 6,
      "4": 2,
      "3": 1,
      "2": 1,
      "1": 0
    }
  },
  "message": "ok"
}
```

### 添加应用评论
**端点**: `POST /app-store/apps/{app_id}/reviews`

**路径参数**:
- `app_id` (string): 应用ID

**请求体**:
```json
{
  "user_name": "张医生",
  "rating": 5,
  "comment": "非常好用的工具！"
}
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "message": "评论添加成功"
  },
  "message": "ok"
}
```

### 更新应用评论
**端点**: `PUT /app-store/apps/{app_id}/reviews/{review_id}`

**路径参数**:
- `app_id` (string): 应用ID
- `review_id` (int): 评论ID

**请求体**:
```json
{
  "user_name": "张医生",
  "rating": 4,
  "comment": "更新后的评论内容"
}
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "message": "评论修改成功"
  },
  "message": "ok"
}
```

### 删除应用评论
**端点**: `DELETE /app-store/apps/{app_id}/reviews/{review_id}`

**路径参数**:
- `app_id` (string): 应用ID
- `review_id` (int): 评论ID

**查询参数**:
- `user_name` (string): 用户名

**响应**:
```json
{
  "code": 200,
  "data": {
    "message": "评论删除成功"
  },
  "message": "ok"
}
```

### 切换评论点赞
**端点**: `POST /app-store/apps/{app_id}/reviews/{review_id}/helpful`

**路径参数**:
- `app_id` (string): 应用ID
- `review_id` (int): 评论ID

**请求体**:
```json
{
  "user_id": 123
}
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "helpful_count": 25,
    "user_liked": true
  },
  "message": "ok"
}
```

### 获取应用商店统计
**端点**: `GET /app-store/stats`

**响应**:
```json
{
  "code": 200,
  "data": {
    "total_apps": 50,
    "total_downloads": 12500,
    "total_reviews": 234,
    "average_rating": 4.2,
    "categories": [
      {
        "name": "医学影像",
        "count": 15
      },
      {
        "name": "数据分析",
        "count": 12
      }
    ]
  },
  "message": "ok"
}
```

---

## 💬 对话管理 API

### 创建对话
**端点**: `POST /conversation/create`

**查询参数**:
- `user_id` (string): 用户ID

**响应**:
```json
{
  "code": 200,
  "data": {
    "conversation_uid": "conv_abc123",
    "owner_uid": "user_123"
  },
  "message": "ok"
}
```

### 添加消息到对话
**端点**: `POST /conversation/add`

**查询参数**:
- `conversation_id` (string): 对话ID
- `content` (string): 消息内容

**响应**:
```json
{
  "code": 200,
  "data": "AI助手的回复内容",
  "message": "ok"
}
```

### 获取对话消息
**端点**: `GET /conversation`

**查询参数**:
- `conversation_id` (string): 对话ID
- `target` (string): 目标类型

**响应**:
```json
{
  "code": 200,
  "data": [
    {
      "role": "user",
      "content": "用户消息内容",
      "timestamp": "2024-01-01T00:00:00Z"
    },
    {
      "role": "assistant",
      "content": "AI助手回复内容",
      "timestamp": "2024-01-01T00:00:01Z"
    }
  ],
  "message": "ok"
}
```

### 获取用户对话列表
**端点**: `GET /conversation/user/{user_id}`

**路径参数**:
- `user_id` (string): 用户ID

**响应**:
```json
{
  "code": 200,
  "data": [
    "conv_abc123",
    "conv_def456",
    "conv_ghi789"
  ],
  "message": "ok"
}
```

### 删除对话
**端点**: `DELETE /conversation/{conversation_id}`

**路径参数**:
- `conversation_id` (string): 对话ID

**响应**:
```json
{
  "code": 200,
  "data": true,
  "message": "ok"
}
```

---

## 📁 文件管理 API

### 获取数据集文件列表
**端点**: `GET /files/dataset`

**查询参数**:
- `target_path` (string, optional): 目标路径，默认为"."

**响应**:
```json
{
  "code": 200,
  "data": {
    "files": [
      {
        "id": "file_123",
        "name": "example.dcm",
        "path": "/data/example.dcm",
        "size": 1024000,
        "type": "file",
        "created_at": "2024-01-01T00:00:00Z",
        "modified_at": "2024-01-01T00:00:00Z"
      }
    ],
    "total": 1,
    "current_path": "/data"
  },
  "message": "ok"
}
```

### 上传文件
**端点**: `POST /files/upload`

**请求体** (multipart/form-data):
- `file`: 文件
- `target_dir`: 目标目录

**响应**:
```json
{
  "code": 200,
  "data": {
    "id": "file_123",
    "name": "example.dcm",
    "path": "/data/example.dcm",
    "size": 1024000,
    "type": "file",
    "created_at": "2024-01-01T00:00:00Z",
    "modified_at": "2024-01-01T00:00:00Z"
  },
  "message": "ok"
}
```

### 批量上传文件
**端点**: `POST /files/upload-multiple`

**请求体** (multipart/form-data):
- `files`: 多个文件
- `target_dir`: 目标目录

**响应**:
```json
{
  "code": 200,
  "data": [
    {
      "id": "file_123",
      "name": "example1.dcm",
      "path": "/data/example1.dcm",
      "size": 1024000,
      "type": "file",
      "created_at": "2024-01-01T00:00:00Z",
      "modified_at": "2024-01-01T00:00:00Z"
    },
    {
      "id": "file_124",
      "name": "example2.dcm",
      "path": "/data/example2.dcm",
      "size": 2048000,
      "type": "file",
      "created_at": "2024-01-01T00:00:00Z",
      "modified_at": "2024-01-01T00:00:00Z"
    }
  ],
  "message": "ok"
}
```

### 删除文件
**端点**: `POST /files/delete`

**请求体**:
```json
{
  "fileId": "file_123"
}
```

**响应**:
```json
{
  "code": 200,
  "data": null,
  "message": "ok"
}
```

### 批量删除文件
**端点**: `POST /files/batch-delete`

**请求体**:
```json
{
  "fileIds": ["file_123", "file_124", "file_125"]
}
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "deleted_count": 3,
    "failed_count": 0,
    "failed_files": []
  },
  "message": "ok"
}
```

### 创建文件夹
**端点**: `POST /files/create-folder`

**请求体**:
```json
{
  "folderName": "new_folder",
  "currentPath": "/data"
}
```

**响应**:
```json
{
  "code": 200,
  "data": null,
  "message": "ok"
}
```

---

## ⚙️ 模型管理 API

### 获取所有模型配置
**端点**: `GET /models/configs`

**响应**:
```json
{
  "code": 200,
  "data": {
    "current_model_id": "qwen3-max",
    "models": {
      "qwen3-max": {
        "id": "qwen3-max",
        "name": "通义千问3-Max",
        "description": "阿里巴巴最新的大语言模型",
        "provider": "tongyi",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-xxx",
        "status": "online",
        "tags": ["对话", "推理", "创作"]
      },
      "deepseek-chat": {
        "id": "deepseek-chat",
        "name": "DeepSeek Chat",
        "description": "DeepSeek的对话模型",
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "sk-xxx",
        "status": "online",
        "tags": ["对话", "编程"]
      }
    }
  },
  "message": "ok"
}
```

### 获取当前模型
**端点**: `GET /models/current`

**响应**:
```json
{
  "code": 200,
  "data": {
    "id": "qwen3-max",
    "name": "通义千问3-Max",
    "description": "阿里巴巴最新的大语言模型",
    "provider": "tongyi",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key": "sk-xxx",
    "status": "online",
    "tags": ["对话", "推理", "创作"]
  },
  "message": "ok"
}
```

### 设置当前模型
**端点**: `POST /models/current`

**请求体**:
```json
{
  "model_id": "deepseek-chat"
}
```

**响应**:
```json
{
  "code": 200,
  "data": true,
  "message": "ok"
}
```

### 创建模型配置
**端点**: `POST /models/configs`

**请求体**:
```json
{
  "id": "custom-model",
  "name": "自定义模型",
  "description": "用户自定义的模型配置",
  "provider": "openai",
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-xxx",
  "status": "online",
  "tags": ["自定义", "测试"]
}
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "id": "custom-model",
    "name": "自定义模型",
    "description": "用户自定义的模型配置",
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-xxx",
    "status": "online",
    "tags": ["自定义", "测试"]
  },
  "message": "ok"
}
```

### 更新模型配置
**端点**: `PUT /models/configs/{model_id}`

**路径参数**:
- `model_id` (string): 模型ID

**请求体**:
```json
{
  "name": "更新后的模型名称",
  "description": "更新后的描述",
  "status": "offline"
}
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "id": "custom-model",
    "name": "更新后的模型名称",
    "description": "更新后的描述",
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-xxx",
    "status": "offline",
    "tags": ["自定义", "测试"]
  },
  "message": "ok"
}
```

### 删除模型配置
**端点**: `DELETE /models/configs/{model_id}`

**路径参数**:
- `model_id` (string): 模型ID

**响应**:
```json
{
  "code": 200,
  "data": true,
  "message": "ok"
}
```

---

## 🧪 任务管理 API (测试版)

### 健康检查
**端点**: `GET /_test_tm/health`

**响应**:
```json
{
  "ok": true,
  "task_manager": {
    "available": true,
    "tool_count": 15,
    "tools_error": null,
    "tools_preview": ["step1_ingest", "step2_preprocess", "step3_train"]
  },
  "settings": {
    "MODEL_URL": "https://api.deepseek.com/v1",
    "MODEL": "deepseek-chat",
    "MODEL_API_KEY_masked": "sk-ab...xy",
    "paths": {
      "data_dir": {
        "path": "/data",
        "exists": true,
        "is_file": false,
        "is_dir": true
      }
    }
  }
}
```

### 获取工具列表
**端点**: `GET /_test_tm/tools`

**查询参数**:
- `limit` (int, optional): 返回数量限制，默认10

**响应**:
```json
{
  "count": 15,
  "preview": [
    "step1_ingest",
    "step2_preprocess", 
    "step3_train",
    "step4_evaluate"
  ]
}
```

### 创建任务
**端点**: `POST /_test_tm/create`

**请求体**:
```json
{
  "user_uid": "user_123",
  "steps": [
    {
      "step_number": 1,
      "tool_name": "step1_ingest",
      "parameters": {
        "input_path": "/data/input",
        "output_path": "/data/processed"
      }
    }
  ],
  "check_tools": true
}
```

**响应**:
```json
{
  "task_uid": "task_abc123",
  "status": "created",
  "user_uid": "user_123",
  "steps_count": 1
}
```

### 获取任务状态
**端点**: `GET /_test_tm/status/{task_uid}`

**路径参数**:
- `task_uid` (string): 任务ID

**响应**:
```json
{
  "task_uid": "task_abc123",
  "status": "running",
  "current_step": 1,
  "total_steps": 3,
  "progress": 33.3,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:01:00Z"
}
```

---

## 📊 响应格式

### 成功响应
所有成功的API响应都遵循以下格式：
```json
{
  "code": 200,
  "data": <响应数据>,
  "message": "ok"
}
```

### 错误响应
所有错误响应都遵循以下格式：
```json
{
  "error": "ERROR_CODE",
  "message": "错误描述",
  "detail": "详细错误信息",
  "context": {},
  "path": "/api/path"
}
```

### 常见错误码
- `INVALID_PARAMETER`: 参数错误
- `NOT_FOUND`: 资源不存在
- `AUTHENTICATION_ERROR`: 认证失败
- `AUTHORIZATION_ERROR`: 权限不足
- `SYSTEM_ERROR`: 系统错误

---

## 🔧 开发工具

### Swagger UI
访问 `http://localhost:8000/docs` 使用交互式API文档

### ReDoc
访问 `http://localhost:8000/redoc` 查看ReDoc格式的API文档

### OpenAPI JSON
访问 `http://localhost:8000/openapi.json` 获取OpenAPI规范文件

---

## 📝 使用示例

### 完整的用户注册和登录流程
```bash
# 1. 用户注册
curl -X POST "http://localhost:8000/user/register" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}'

# 2. 用户登录获取token
TOKEN=$(curl -X POST "http://localhost:8000/user/login" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}' | jq -r '.data.token')

# 3. 使用token获取用户信息
curl -X GET "http://localhost:8000/user/info" \
  -H "Authorization: Bearer $TOKEN"
```

### 应用商店完整流程
```bash
# 1. 获取应用列表
curl -X GET "http://localhost:8000/app-store/apps"

# 2. 查看应用详情
curl -X GET "http://localhost:8000/app-store/apps/dicom-converter"

# 3. 安装应用
curl -X POST "http://localhost:8000/app-store/apps/dicom-converter/install"

# 4. 添加评论
curl -X POST "http://localhost:8000/app-store/apps/dicom-converter/reviews" \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "张医生",
    "rating": 5,
    "comment": "非常好用的工具！"
  }'

# 5. 点赞评论
curl -X POST "http://localhost:8000/app-store/apps/dicom-converter/reviews/1/helpful" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123}'
```

### 对话管理流程
```bash
# 1. 创建对话
CONV_ID=$(curl -X POST "http://localhost:8000/conversation/create?user_id=123" | jq -r '.data.conversation_uid')

# 2. 发送消息
curl -X POST "http://localhost:8000/conversation/add?conversation_id=$CONV_ID&content=你好"

# 3. 获取对话历史
curl -X GET "http://localhost:8000/conversation?conversation_id=$CONV_ID&target=messages"

# 4. 删除对话
curl -X DELETE "http://localhost:8000/conversation/$CONV_ID"
```

### 文件管理流程
```bash
# 1. 获取文件列表
curl -X GET "http://localhost:8000/files/dataset"

# 2. 上传文件
curl -X POST "http://localhost:8000/files/upload" \
  -F "file=@example.dcm" \
  -F "target_dir=/data"

# 3. 创建文件夹
curl -X POST "http://localhost:8000/files/create-folder" \
  -H "Content-Type: application/json" \
  -d '{"folderName": "new_folder", "currentPath": "/data"}'

# 4. 删除文件
curl -X POST "http://localhost:8000/files/delete" \
  -H "Content-Type: application/json" \
  -d '{"fileId": "file_123"}'
```

---

## 🚀 快速上手指南

### 1. 环境准备
```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
```

### 2. API测试
- 访问 http://localhost:8000/docs
- 使用 Swagger UI 测试 API
- 查看请求和响应示例

### 3. 认证测试
```bash
# 注册用户
curl -X POST "http://localhost:8000/user/register" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}'

# 登录获取token
curl -X POST "http://localhost:8000/user/login" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}'
```

### 4. 功能测试
- 测试应用商店功能
- 测试对话功能
- 测试文件上传
- 测试模型管理
- 测试任务管理

---

## 📚 更多资源

### 项目文档
- [应用商店 API 详细文档](AppStore_API_Documentation.md)
- [开发者文档](README.md)
- [项目主页](../README.md)

### 技术文档
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Pydantic 文档](https://pydantic-docs.helpmanual.io/)
- [SQLite 文档](https://www.sqlite.org/docs.html)
- [Vue 3 文档](https://vuejs.org/)
- [Ant Design Vue 文档](https://antdv.com/)

### 项目资源
- [项目 GitHub 仓库](https://github.com/your-repo/mediagent)
- [问题反馈](https://github.com/your-repo/mediagent/issues)
- [贡献指南](../README.md#贡献指南)

---

**注意**: 本文档基于项目实际代码结构编写，版本 2.0.0。如有更新请查看最新版本。
