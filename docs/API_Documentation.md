# MediAgent API 详细文档

## 📋 概述

MediAgent 是一个智能医疗助手后端 API，提供用户管理、聊天对话、文件管理和工具调用等功能。本文档详细描述了所有可用的 API 端点、请求参数、响应格式和错误处理。

### 基础信息
- **API 版本**: 2.0.0
- **基础 URL**: `http://localhost:8000`
- **认证方式**: Bearer Token
- **内容类型**: `application/json`
- **字符编码**: UTF-8

### 快速开始
1. 启动后端服务: `python main.py`
2. 访问 API 文档: http://localhost:8000/docs
3. 使用 Swagger UI 进行 API 测试

## 🔐 认证

### Bearer Token 认证
所有需要认证的 API 都需要在请求头中包含有效的 Bearer Token：

```http
Authorization: Bearer <your_token>
```

### 获取 Token
通过用户登录接口获取 Token：

```bash
curl -X POST "http://localhost:8000/user/login" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}'
```

响应示例：
```json
{
  "token": "abc123def456",
  "uid": 1234567890,
  "message": "login successful"
}
```

## 👤 用户管理 API

### 用户注册

**端点**: `POST /user/register`

**描述**: 创建新用户账户

**请求体**:
```json
{
  "user_name": "string",
  "password": "string"
}
```

**参数说明**:
- `user_name` (string, required): 用户名，3-20个字符
- `password` (string, required): 密码，6-50个字符

**响应**:
```json
{
  "uid": 1234567890,
  "message": "registered successfully"
}
```

**状态码**:
- `201`: 注册成功
- `400`: 请求参数错误
- `409`: 用户名已存在

**示例**:
```bash
curl -X POST "http://localhost:8000/user/register" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}'
```

### 用户登录

**端点**: `POST /user/login`

**描述**: 用户登录获取访问令牌

**请求体**:
```json
{
  "user_name": "string",
  "password": "string"
}
```

**响应**:
```json
{
  "token": "abc123def456",
  "uid": 1234567890,
  "message": "login successful"
}
```

**状态码**:
- `200`: 登录成功
- `400`: 请求参数错误
- `401`: 用户名或密码错误

**示例**:
```bash
curl -X POST "http://localhost:8000/user/login" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}'
```

### 获取用户信息

**端点**: `GET /user/info`

**描述**: 获取当前用户信息

**认证**: 需要 Bearer Token

**请求头**:
```http
Authorization: Bearer <your_token>
```

**响应**:
```json
{
  "uid": 1234567890,
  "user_name": "testuser",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "last_login": "2024-01-01T00:00:00Z"
}
```

**状态码**:
- `200`: 获取成功
- `401`: 认证失败

**示例**:
```bash
curl -X GET "http://localhost:8000/user/info" \
  -H "Authorization: Bearer abc123def456"
```

### 更新用户信息

**端点**: `PUT /user/info`

**描述**: 更新当前用户信息

**认证**: 需要 Bearer Token

**请求体**:
```json
{
  "user_name": "string",
  "password": "string"
}
```

**参数说明**:
- `user_name` (string, optional): 新用户名
- `password` (string, optional): 新密码

**响应**:
```json
{
  "message": "user info updated successfully"
}
```

**状态码**:
- `200`: 更新成功
- `400`: 请求参数错误
- `401`: 认证失败
- `409`: 用户名已存在

**示例**:
```bash
curl -X PUT "http://localhost:8000/user/info" \
  -H "Authorization: Bearer abc123def456" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "newusername"}'
```

## 💬 聊天对话 API

### 普通聊天

**端点**: `POST /chat`

**描述**: 与 AI 进行普通聊天对话

**请求体**:
```json
{
  "conversation_id": "string",
  "message": "string",
  "history": [
    {
      "role": "string",
      "content": "string"
    }
  ],
  "files": []
}
```

**参数说明**:
- `conversation_id` (string, required): 会话ID
- `message` (string, required): 用户消息
- `history` (array, optional): 历史消息记录
- `files` (array, optional): 关联文件列表

**响应**:
```json
{
  "conversation_id": "conv_001",
  "answer": "AI 回复内容",
  "tool_calls": []
}
```

**状态码**:
- `200`: 聊天成功
- `400`: 请求参数错误
- `500`: 服务器错误

**示例**:
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_001",
    "message": "你好",
    "history": []
  }'
```

### 流式聊天

**端点**: `POST /chat/stream`

**描述**: 与 AI 进行流式聊天对话，支持实时输出

**请求体**: 与普通聊天相同

**响应**: Server-Sent Events (SSE) 格式

**事件类型**:
- `start`: 开始信号
- `content`: 内容输出
- `tool_call`: 工具调用
- `complete`: 完成信号
- `error`: 错误信息

**示例**:
```bash
curl -X POST "http://localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_001",
    "message": "你好",
    "history": []
  }'
```

**SSE 响应示例**:
```
data: {"type": "start", "conversation_id": "conv_001"}

data: {"type": "content", "content": "你好！"}

data: {"type": "complete", "tool_calls": []}
```

## 📁 文件管理 API

### 上传文件

**端点**: `POST /files/upload`

**描述**: 上传文件到服务器

**请求**: multipart/form-data

**参数**:
- `file` (file, required): 要上传的文件

**文件限制**:
- 最大大小: 10MB
- 支持格式: .jpg, .jpeg, .png, .gif, .webp, .csv

**响应**:
```json
{
  "success": true,
  "file": {
    "id": "file_001",
    "originalName": "image.jpg",
    "size": 1024000,
    "type": "image/jpeg",
    "path": "/data/image.jpg",
    "uploadTime": "2024-01-01T00:00:00Z"
  }
}
```

**状态码**:
- `200`: 上传成功
- `400`: 文件格式不支持或大小超限
- `500`: 服务器错误

**示例**:
```bash
curl -X POST "http://localhost:8000/files/upload" \
  -F "file=@/path/to/image.jpg"
```

### 获取文件列表

**端点**: `GET /files`

**描述**: 获取已上传文件列表

**响应**:
```json
{
  "files": [
    {
      "id": "file_001",
      "originalName": "image.jpg",
      "size": 1024000,
      "type": "image/jpeg",
      "path": "/data/image.jpg",
      "uploadTime": "2024-01-01T00:00:00Z"
    }
  ]
}
```

**示例**:
```bash
curl -X GET "http://localhost:8000/files"
```

### 删除文件

**端点**: `POST /files/delete`

**描述**: 删除指定文件

**请求体**:
```json
{
  "fileId": "string"
}
```

**响应**:
```json
{
  "success": true
}
```

**状态码**:
- `200`: 删除成功
- `404`: 文件不存在
- `500`: 服务器错误

**示例**:
```bash
curl -X POST "http://localhost:8000/files/delete" \
  -H "Content-Type: application/json" \
  -d '{"fileId": "file_001"}'
```

### 批量删除文件

**端点**: `POST /files/batch-delete`

**描述**: 批量删除多个文件

**请求体**:
```json
{
  "fileIds": ["file_001", "file_002"]
}
```

**响应**:
```json
{
  "success": true,
  "deletedCount": 2
}
```

**示例**:
```bash
curl -X POST "http://localhost:8000/files/batch-delete" \
  -H "Content-Type: application/json" \
  -d '{"fileIds": ["file_001", "file_002"]}'
```

### 获取下载URL

**端点**: `POST /files/download`

**描述**: 获取文件下载URL

**请求体**:
```json
{
  "fileId": "string"
}
```

**响应**:
```json
{
  "success": true,
  "downloadUrl": "/files/serve/file_001"
}
```

**示例**:
```bash
curl -X POST "http://localhost:8000/files/download" \
  -H "Content-Type: application/json" \
  -d '{"fileId": "file_001"}'
```

### 下载文件

**端点**: `GET /files/serve/{file_id}`

**描述**: 直接下载文件

**参数**:
- `file_id` (string, required): 文件ID

**响应**: 文件内容

**示例**:
```bash
curl -X GET "http://localhost:8000/files/serve/file_001" \
  -O image.jpg
```

## 🛠️ 工具管理 API

### 获取工具列表

**端点**: `GET /tools`

**描述**: 获取可用的工具列表

**响应**:
```json
{
  "tools": [
    {
      "name": "resize_image",
      "description": "调整图像大小",
      "schema": {
        "type": "object",
        "properties": {
          "input_path": {"type": "string"},
          "output_path": {"type": "string"},
          "width": {"type": "integer"},
          "height": {"type": "integer"}
        },
        "required": ["input_path", "output_path", "width", "height"]
      }
    },
    {
      "name": "csv_summary",
      "description": "CSV文件统计分析",
      "schema": {
        "type": "object",
        "properties": {
          "csv_path": {"type": "string"},
          "delimiter": {"type": "string"},
          "max_rows": {"type": "integer"}
        },
        "required": ["csv_path"]
      }
    }
  ]
}
```

**示例**:
```bash
curl -X GET "http://localhost:8000/tools"
```

### 刷新工具列表

**端点**: `POST /tools/refresh`

**描述**: 刷新工具列表，重新加载工具

**响应**:
```json
{
  "ok": true,
  "count": 5
}
```

**示例**:
```bash
curl -X POST "http://localhost:8000/tools/refresh"
```

### 调用工具

**端点**: `POST /tools/call`

**描述**: 直接调用指定工具

**请求体**:
```json
{
  "name": "string",
  "args": {}
}
```

**参数说明**:
- `name` (string, required): 工具名称
- `args` (object, required): 工具参数

**响应**:
```json
{
  "ok": true,
  "result": "工具执行结果"
}
```

**状态码**:
- `200`: 调用成功
- `404`: 工具不存在
- `400`: 参数错误
- `500`: 工具执行失败

**示例**:
```bash
# 调用图像缩放工具
curl -X POST "http://localhost:8000/tools/call" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "resize_image",
    "args": {
      "input_path": "/data/input.jpg",
      "output_path": "/data/output.jpg",
      "width": 800,
      "height": 600
    }
  }'

# 调用CSV分析工具
curl -X POST "http://localhost:8000/tools/call" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "csv_summary",
    "args": {
      "csv_path": "/data/data.csv",
      "delimiter": ",",
      "max_rows": 1000
    }
  }'
```

## 🔧 系统管理 API

### 健康检查

**端点**: `GET /system/health`

**描述**: 检查系统健康状态

**响应**:
```json
{
  "status": "ok",
  "model": "gpt-3.5-turbo",
  "lm_server": "http://localhost:11434",
  "tools_count": 5,
  "python": "/usr/bin/python3"
}
```

**示例**:
```bash
curl -X GET "http://localhost:8000/system/health"
```

### 系统自测

**端点**: `GET /system/selftest`

**描述**: 执行系统自测，验证功能正常

**响应**:
```json
{
  "ok": true,
  "result": "自测结果"
}
```

**示例**:
```bash
curl -X GET "http://localhost:8000/system/selftest"
```

## 🚨 错误处理

### 错误响应格式

所有错误都遵循统一的响应格式：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "context": {}
  }
}
```

### 常见错误码

| 错误码 | HTTP状态码 | 描述 |
|--------|------------|------|
| `VALIDATION_ERROR` | 400 | 参数验证错误 |
| `AUTHENTICATION_ERROR` | 401 | 认证失败 |
| `AUTHORIZATION_ERROR` | 403 | 权限不足 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `CONFLICT_ERROR` | 409 | 资源冲突 |
| `DATABASE_ERROR` | 500 | 数据库错误 |
| `SERVICE_ERROR` | 500 | 服务错误 |

### 错误示例

**参数验证错误**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "用户名和密码不能为空",
    "context": {
      "user_name": null,
      "password": null
    }
  }
}
```

**认证失败**:
```json
{
  "error": {
    "code": "AUTHENTICATION_ERROR",
    "message": "用户名或密码错误",
    "context": {
      "user_name": "testuser"
    }
  }
}
```

**资源不存在**:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "文件不存在",
    "context": {
      "file_id": "file_001"
    }
  }
}
```

## 📊 状态码说明

| 状态码 | 含义 | 说明 |
|--------|------|------|
| 200 | 成功 | 请求成功处理 |
| 201 | 已创建 | 资源创建成功 |
| 400 | 错误请求 | 请求参数错误 |
| 401 | 未授权 | 认证失败 |
| 403 | 禁止访问 | 权限不足 |
| 404 | 未找到 | 资源不存在 |
| 409 | 冲突 | 资源冲突 |
| 500 | 服务器错误 | 内部服务器错误 |

## 🔧 开发工具

### Swagger UI
访问 http://localhost:8000/docs 使用 Swagger UI 进行 API 测试

### ReDoc
访问 http://localhost:8000/redoc 查看 ReDoc 格式的 API 文档

### OpenAPI JSON
访问 http://localhost:8000/openapi.json 获取 OpenAPI 规范文件

## 📝 使用示例

### 完整的用户注册和登录流程

```bash
# 1. 用户注册
curl -X POST "http://localhost:8000/user/register" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}'

# 2. 用户登录获取token
curl -X POST "http://localhost:8000/user/login" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "password": "password123"}'

# 3. 使用token获取用户信息
curl -X GET "http://localhost:8000/user/info" \
  -H "Authorization: Bearer <token>"
```

### 文件上传和聊天流程

```bash
# 1. 上传文件
curl -X POST "http://localhost:8000/files/upload" \
  -F "file=@/path/to/image.jpg"

# 2. 使用文件进行聊天
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_001",
    "message": "请分析这个图片",
    "history": [],
    "files": [{"id": "file_001", "path": "/data/image.jpg"}]
  }'
```

### 工具调用流程

```bash
# 1. 获取工具列表
curl -X GET "http://localhost:8000/tools"

# 2. 调用图像处理工具
curl -X POST "http://localhost:8000/tools/call" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "resize_image",
    "args": {
      "input_path": "/data/input.jpg",
      "output_path": "/data/output.jpg",
      "width": 800,
      "height": 600
    }
  }'

# 3. 调用数据处理工具
curl -X POST "http://localhost:8000/tools/call" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "csv_summary",
    "args": {
      "csv_path": "/data/data.csv",
      "delimiter": ",",
      "max_rows": 1000
    }
  }'
```

## 🚀 快速上手指南

### 新开发者快速开始

1. **环境准备**:
   ```bash
   # 安装依赖
   pip install -r requirements.txt
   
   # 启动服务
   python main.py
   ```

2. **API 测试**:
   - 访问 http://localhost:8000/docs
   - 使用 Swagger UI 测试 API
   - 查看请求和响应示例

3. **认证测试**:
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

4. **功能测试**:
   - 测试聊天功能
   - 测试文件上传
   - 测试工具调用
   - 测试系统健康检查

### 集成指南

1. **前端集成**:
   - 使用 axios 或 fetch 进行 HTTP 请求
   - 实现 Bearer Token 认证
   - 处理错误响应

2. **后端集成**:
   - 使用 FastAPI 客户端
   - 实现重试机制
   - 处理异常情况

## 📚 更多资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Pydantic 文档](https://pydantic-docs.helpmanual.io/)
- [SQLite 文档](https://www.sqlite.org/docs.html)
- [项目 GitHub 仓库](https://github.com/your-repo/mediagent)

---

**注意**: 本文档基于 API 版本 2.0.0，如有更新请查看最新版本。