# MediAgent - 智能医疗助手

<div align="center">

<img src="./src/frontend/public/MediAgent.png" alt="MediAgent Logo" width="200">

**一个现代化的智能医疗助手系统**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-green.svg)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D.svg)](https://vuejs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## 项目概述

MediAgent 是一个现代化的智能医疗助手系统，集成了用户管理、AI 智能对话、文件管理、医学影像处理、专业工具调用和 RAG 知识库等功能。系统采用前后端分离架构，后端使用 FastAPI + Python + PostgreSQL，前端使用 Vue 3 + TypeScript + Ant Design Vue，为医疗场景提供智能化的数据处理、分析和应用管理解决方案。

## 技术栈

### 后端

| 技术 | 说明 |
|------|------|
| FastAPI 0.116 | Web 框架 |
| Python 3.10 | 编程语言 |
| claude-agent-sdk | Claude Code Agent SDK |
| langchain + langgraph | RAG 和 Agent 框架 |
| PostgreSQL + asyncpg | 异步数据库 |
| pydantic + pydantic-settings | 数据验证与配置管理 |
| MCP (Model Context Protocol) | 工具调用协议 |

### 前端

| 技术 | 说明 |
|------|------|
| Vue 3.5 | UI 框架 |
| TypeScript 5 | 类型系统 |
| Vite 7 | 构建工具 |
| Ant Design Vue 4 | UI 组件库 |
| Pinia 3 | 状态管理 |
| vue-i18n | 国际化 |
| marked + highlight.js | Markdown 渲染与代码高亮 |

## 项目结构

```
MediAgent/
├── src/
│   ├── frontend/                    # Vue 3 前端应用
│   │   └── src/
│   │       ├── apis/               # API 接口层
│   │       ├── components/         # Vue 组件
│   │       │   ├── file/           # 文件管理组件
│   │       │   ├── knowledge-base/ # 知识库组件
│   │       │   ├── markdown-renderer/ # Markdown 渲染组件
│   │       │   └── model/           # 模型配置组件
│   │       ├── views/              # 页面视图
│   │       │   ├── clinical_tools/ # 临床工具
│   │       │   │   ├── code_agent/ # Code Agent 视图
│   │       │   │   └── rag/        # RAG 知识库视图
│   │       │   └── workspace/      # 工作区视图
│   │       └── store/              # Pinia 状态管理
│   └── server_agent/               # FastAPI 后端服务
│       ├── agent/                  # AI Agent 模块
│       │   ├── claude/            # Claude Code Agent
│       │   └── rag/               # RAG Agent
│       ├── controller/             # API 控制器
│       │   └── clinical_tools/    # 临床工具 API
│       ├── service/                # 业务逻辑层
│       │   └── clinical_tools/    # 临床工具服务
│       ├── mapper/                # 数据访问层
│       └── model/                 # 数据模型 (DTO/Entity/VO)
├── docs/                          # 项目文档
├── requirements.txt               # Python 依赖
└── README.md                      # 项目说明
```

## 主要功能

### 1. Code Agent

Claude SDK 驱动的代码智能体，支持：
- 会话管理（创建、切换、删除）
- 流式输出与实时响应
- AI 思考过程折叠显示
- Markdown 代码高亮渲染

### 2. RAG 知识库

基于 langchain 的检索增强生成系统：
- 文档上传与管理
- 向量知识库构建
- 智能问答与检索

### 3. CT 智能诊断

医学影像处理与 AI 辅助诊断：
- 医学影像上传与浏览
- DICOM 格式支持
- AI 辅助分析

### 4. AI 智能对话

多模型支持的对话系统：
- 流式对话输出
- AI 思考过程展示
- 多轮对话上下文
- Markdown 内容渲染

### 5. 医疗应用商店

类 Chrome Web Store 的应用管理：
- 应用浏览与搜索
- 分类筛选
- 用户评价与评分
- 应用安装管理

### 6. 文件与数据集管理

- 医疗数据文件上传
- 树形目录浏览
- 批量操作支持
- 数据集管理

### 7. 模型配置

灵活的 AI 模型配置：
- 多模型切换（DeepSeek、通义千问等）
- 用户个性化配置
- API 密钥管理

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 16+
- PostgreSQL 14+
- conda（推荐）

### 1. 创建 Conda 环境

```bash
conda create -n MediAgent python=3.10
conda activate MediAgent
```

### 2. 安装后端依赖

```bash
cd MediAgent
pip install -r requirements.txt
```

### 3. 配置环境变量

创建 `.env` 文件：

```bash
# 数据库配置
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=mediagent
PG_USER=postgres
PG_PASSWORD=your_password

# Code Agent 配置（可选）
CODE_AGENT_TYPE=claude
CLAUDE_CODE_PATH=/path/to/claude
```

### 4. 初始化数据库

```sql
CREATE DATABASE mediagent;
```

### 5. 启动后端服务

```bash
cd src/server_agent
python main.py
# 服务运行在 http://localhost:8000
```

### 6. 启动前端开发服务器

```bash
cd src/frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发指南

### 添加新的 API 端点

1. 在 `controller/` 目录创建新的 Controller 类
2. 在 `service/` 目录实现业务逻辑
3. 在 `mapper/` 目录添加数据访问方法

### 添加新的前端页面

1. 在 `views/` 目录创建 Vue 组件
2. 在 `router/` 配置路由
3. 在 `apis/` 添加对应的 API 接口

## 部署

### 开发环境

```bash
# 后端
cd src/server_agent && python main.py

# 前端
cd src/frontend && npm run dev
```

### 生产环境

```bash
# 前端构建
cd src/frontend && npm run build
# 产物在 dist/ 目录

# 后端启动（推荐使用 uvicorn）
cd src/server_agent
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker 部署

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 依赖说明

核心依赖：
- **Web**: fastapi, uvicorn, starlette
- **AI**: claude-agent-sdk, langchain, langgraph, openai
- **数据库**: asyncpg, aiosqlite
- **医学影像**: monai, SimpleITK, opencv-python
- **数据处理**: pandas, numpy, scipy, scikit-image

详细依赖列表见 [requirements.txt](requirements.txt)

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

<div align="center">

**感谢使用 MediAgent！**

*让医疗数据处理更智能，让医学分析更简单*

</div>
