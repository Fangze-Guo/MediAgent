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

### 统一响应格式

所有文件管理API都使用统一的 `BaseResponse<T>` 格式：

```json
{
  "code": 200,
  "data": <响应数据>,
  "message": "ok"
}
```

**响应字段说明**：
- `code` (number): 状态码，200表示成功
- `data` (any): 响应数据
- `message` (string): 响应消息

### 上传文件

**端点**: `POST /files/upload`

**描述**: 上传文件到服务器

**请求**: multipart/form-data

**参数**:
- `file` (file, required): 要上传的文件

**文件限制**:
- 最大大小: 10MB
- 支持格式: .jpg, .jpeg, .png, .gif, .webp, .csv, .dcm

**响应**:
```json
{
  "code": 200,
  "data": {
    "id": "upload_123456789",
    "name": "image.jpg",
    "size": 1024000,
    "type": "image/jpeg",
    "path": "data/image.jpg",
    "modifiedTime": "2024-01-01T00:00:00Z",
    "isDirectory": false
  },
  "message": "ok"
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
  "code": 200,
  "data": {
    "files": [
      {
        "id": "upload_123456789",
        "name": "image.jpg",
        "size": 1024000,
        "type": "image/jpeg",
        "path": "data/image.jpg",
        "modifiedTime": "2024-01-01T00:00:00Z",
        "isDirectory": false
      },
      {
        "id": "upload_987654321",
        "name": "folder",
        "size": 0,
        "type": "directory",
        "path": "data/folder",
        "modifiedTime": "2024-01-01T00:00:00Z",
        "isDirectory": true
      }
    ],
    "currentPath": "data",
    "parentPath": "."
  },
  "message": "ok"
}
```

**示例**:
```bash
curl -X GET "http://localhost:8000/files"
```

### 删除文件

**端点**: `POST /files/delete`

**描述**: 删除指定文件或空目录

**请求体**:
```json
{
  "fileId": "string"
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

**状态码**:
- `200`: 删除成功
- `404`: 文件不存在
- `400`: 目录不为空，无法删除
- `500`: 服务器错误

**示例**:
```bash
curl -X POST "http://localhost:8000/files/delete" \
  -H "Content-Type: application/json" \
  -d '{"fileId": "upload_123456789"}'
```

### 批量删除文件

**端点**: `POST /files/batch-delete`

**描述**: 批量删除多个文件

**请求体**:
```json
{
  "fileIds": ["upload_123456789", "upload_987654321"]
}
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "successCount": 2,
    "failureCount": 0,
    "successDetails": ["upload_123456789", "upload_987654321"],
    "failureDetails": []
  },
  "message": "ok"
}
```

**示例**:
```bash
curl -X POST "http://localhost:8000/files/batch-delete" \
  -H "Content-Type: application/json" \
  -d '{"fileIds": ["upload_123456789", "upload_987654321"]}'
```

### 创建文件夹

**端点**: `POST /files/create-folder`

**描述**: 在当前目录创建新文件夹

**请求体**:
```json
{
  "folderName": "string"
}
```

**响应**:
```json
{
  "code": 200,
  "data": {
    "id": "upload_111222333",
    "name": "new_folder",
    "size": 0,
    "type": "directory",
    "path": "data/new_folder",
    "modifiedTime": "2024-01-01T00:00:00Z",
    "isDirectory": true
  },
  "message": "ok"
}
```

**状态码**:
- `200`: 创建成功
- `400`: 文件夹名称无效或已存在
- `500`: 服务器错误

**示例**:
```bash
curl -X POST "http://localhost:8000/files/create-folder" \
  -H "Content-Type: application/json" \
  -d '{"folderName": "new_folder"}'
```

### 获取本地文件列表

**端点**: `GET /files/local`

**描述**: 获取本地文件系统文件列表

**响应**:
```json
{
  "code": 200,
  "data": {
    "files": [
      {
        "id": "local_123456789",
        "name": "data.csv",
        "size": 2048000,
        "type": "text/csv",
        "path": "data/data.csv",
        "modifiedTime": "2024-01-01T00:00:00Z",
        "isDirectory": false
      }
    ],
    "currentPath": "data",
    "parentPath": "."
  },
  "message": "ok"
}
```

**示例**:
```bash
curl -X GET "http://localhost:8000/files/local"
```

### 删除本地文件

**端点**: `POST /files/local/delete`

**描述**: 删除本地文件系统中的文件

**请求体**:
```json
{
  "fileId": "string"
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

**示例**:
```bash
curl -X POST "http://localhost:8000/files/local/delete" \
  -H "Content-Type: application/json" \
  -d '{"fileId": "local_123456789"}'
```

### 获取输出文件列表

**端点**: `GET /files/output`

**描述**: 获取输出目录文件列表

**响应**:
```json
{
  "code": 200,
  "data": {
    "files": [
      {
        "id": "output_123456789",
        "name": "result.nii",
        "size": 5120000,
        "type": "application/octet-stream",
        "path": "output/result.nii",
        "modifiedTime": "2024-01-01T00:00:00Z",
        "isDirectory": false
      }
    ],
    "currentPath": "output",
    "parentPath": "."
  },
  "message": "ok"
}
```

**示例**:
```bash
curl -X GET "http://localhost:8000/files/output"
```

### 删除输出文件

**端点**: `POST /files/output/delete`

**描述**: 删除输出目录中的文件

**请求体**:
```json
{
  "fileId": "string"
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

**示例**:
```bash
curl -X POST "http://localhost:8000/files/output/delete" \
  -H "Content-Type: application/json" \
  -d '{"fileId": "output_123456789"}'
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
  "code": 200,
  "data": {
    "downloadUrl": "/files/serve/upload_123456789"
  },
  "message": "ok"
}
```

**示例**:
```bash
curl -X POST "http://localhost:8000/files/download" \
  -H "Content-Type: application/json" \
  -d '{"fileId": "upload_123456789"}'
```

### 下载文件

**端点**: `GET /files/serve/{file_id}`

**描述**: 直接下载文件

**参数**:
- `file_id` (string, required): 文件ID

**响应**: 文件内容

**示例**:
```bash
curl -X GET "http://localhost:8000/files/serve/upload_123456789" \
  -O image.jpg
```

### 文件类型说明

**FileInfo 对象结构**:
```json
{
  "id": "string",           // 文件唯一标识符
  "name": "string",         // 文件名
  "size": "number",         // 文件大小（字节）
  "type": "string",         // MIME类型
  "path": "string",         // 文件路径
  "modifiedTime": "string", // 修改时间（ISO格式）
  "isDirectory": "boolean"  // 是否为目录
}
```

**目录操作说明**:
- 可以删除空目录
- 非空目录删除会返回错误
- 支持创建新目录
- 目录导航支持相对路径

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

所有错误都遵循统一的 `BaseResponse<T>` 格式：

```json
{
  "code": 400,
  "data": null,
  "message": "错误描述"
}
```

**错误响应字段说明**：
- `code` (number): HTTP状态码，非200表示错误
- `data` (null): 错误时数据为null
- `message` (string): 错误描述信息

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
  "code": 400,
  "data": null,
  "message": "用户名和密码不能为空"
}
```

**认证失败**:
```json
{
  "code": 401,
  "data": null,
  "message": "用户名或密码错误"
}
```

**资源不存在**:
```json
{
  "code": 404,
  "data": null,
  "message": "文件不存在"
}
```

**目录不为空**:
```json
{
  "code": 400,
  "data": null,
  "message": "目录不为空，无法删除"
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

# 响应示例:
# {
#   "code": 200,
#   "data": {
#     "id": "upload_123456789",
#     "name": "image.jpg",
#     "size": 1024000,
#     "type": "image/jpeg",
#     "path": "data/image.jpg",
#     "modifiedTime": "2024-01-01T00:00:00Z",
#     "isDirectory": false
#   },
#   "message": "ok"
# }

# 2. 使用文件进行聊天
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_001",
    "message": "请分析这个图片",
    "history": [],
    "files": [{"id": "upload_123456789", "path": "data/image.jpg"}]
  }'
```

### 文件管理操作流程

```bash
# 1. 获取文件列表
curl -X GET "http://localhost:8000/files"

# 响应示例:
# {
#   "code": 200,
#   "data": {
#     "files": [...],
#     "currentPath": "data",
#     "parentPath": "."
#   },
#   "message": "ok"
# }

# 2. 创建文件夹
curl -X POST "http://localhost:8000/files/create-folder" \
  -H "Content-Type: application/json" \
  -d '{"folderName": "new_folder"}'

# 3. 删除文件
curl -X POST "http://localhost:8000/files/delete" \
  -H "Content-Type: application/json" \
  -d '{"fileId": "upload_123456789"}'

# 4. 批量删除文件
curl -X POST "http://localhost:8000/files/batch-delete" \
  -H "Content-Type: application/json" \
  -d '{"fileIds": ["upload_123456789", "upload_987654321"]}'
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