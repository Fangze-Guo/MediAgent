# MediAgent

<div align="center">

<img src="./src/frontend/public/MediAgent.png" alt="MediAgent Logo" width="180">

**面向医疗场景的智能体协同处理平台**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-green.svg)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D.svg)](https://vuejs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org)

</div>

## 项目概述

MediAgent 是一个面向医疗和临床科研场景的智能体平台。当前版本重点围绕医疗知识库、检索增强问答、临床智能体、Skill 工具仓库、文件管理、模型配置和长任务状态管理展开，支持把本地医学资料、专病规则、模型对话和外部工具整合到同一套工作流中。

项目采用前后端分离架构：后端基于 FastAPI、PostgreSQL、LangChain、LangGraph、Chroma 和 Claude Agent SDK；前端基于 Vue 3、TypeScript、Vite、Pinia 和 Ant Design Vue。

## 当前能力

### 医疗知识库与 RAG

- 支持创建、编辑、删除知识库。
- 支持上传 PDF、Word、Excel、TXT、Markdown、CSV 等文档。
- 支持文档解析、文本清洗、分块、向量化和 Chroma 持久化存储。
- PDF 支持文字层提取；扫描版或文字稀疏 PDF 可降级到 OCR。
- Excel 采用按行语义化 chunk，减少表格行被截断的问题。
- 支持知识库内语义检索，并在对话中返回引用来源。

### 医疗对话与工具调用

- 支持普通多轮对话和流式输出。
- 支持基于 RAG 的知识库上下文注入。
- 支持 ReAct Agent 按需调用工具，包括知识库检索、网络搜索、本地文件读取和当前时间查询。
- 支持图片附件上传到 OSS 后进入对话上下文。
- 支持 Markdown 渲染、思考过程展示、工具调用过程展示和来源片段展示。

### 临床智能体与 Code Agent

- 支持创建和管理临床智能体。
- 支持为不同专病项目配置独立 system prompt、工作目录和 Skill。
- 默认注册 NICE-BCX 临床智能体，用于肺癌新辅助治疗影像分析相关流程约束。
- Code Agent 基于 Claude Agent SDK，支持会话创建、恢复、流式输出、工具调用、权限确认和中断。
- SSE 断开后，后台任务可继续运行，并可通过会话状态和 JSONL 消息恢复进度。

### Skill 仓库与后台任务

- 支持从文件系统同步 Skill。
- 支持上传、查看、安装和卸载 Skill。
- 支持按临床智能体安装 Skill，形成项目级工具集合。
- Skill 任务状态会写入 PostgreSQL，服务重启后可恢复任务记录。
- 支持查询、删除和清理后台任务，记录运行状态、耗时和异常信息。

### 文件、用户与模型管理

- 支持用户注册、登录、资料更新和权限守卫。
- 支持数据集文件浏览、上传、批量删除、重命名和新建文件夹。
- 支持聊天图片 OSS 预签名上传。
- 支持模型配置管理、当前模型选择、模型启停、供应商和分类管理。
- 支持多语言界面，目前包含中文和英文 locale。

## 技术栈

### 后端

| 技术 | 用途 |
| --- | --- |
| FastAPI / Uvicorn | Web API 与服务运行 |
| PostgreSQL / asyncpg | 用户、会话、知识库、任务等数据持久化 |
| LangChain / LangGraph | 对话 Agent、ReAct 工具调用和 RAG 流程 |
| Chroma / langchain-chroma | 本地向量库 |
| OpenAI-compatible API | LLM 与 embedding 调用接口 |
| Claude Agent SDK | Code Agent 与工具会话 |
| pypdf / pypdfium2 / RapidOCR | PDF 文本提取与 OCR |
| python-docx / openpyxl | Word 与 Excel 解析 |
| Alibaba Cloud OSS SDK | 图片等对象存储直传与清理 |

### 前端

| 技术 | 用途 |
| --- | --- |
| Vue 3 / TypeScript | 前端应用 |
| Vite | 开发服务器与构建 |
| Ant Design Vue | UI 组件 |
| Pinia | 状态管理 |
| vue-router | 路由与页面权限 |
| vue-i18n | 国际化 |
| marked / highlight.js | Markdown 与代码高亮 |

## 项目结构

```text
MediAgent/
├── main.py                         # 后端启动入口
├── requirements.txt                # Python 依赖
├── src/
│   ├── frontend/                   # Vue 3 前端
│   │   └── src/
│   │       ├── apis/               # 前端 API 封装
│   │       ├── components/         # 通用组件
│   │       ├── router/             # 路由与守卫
│   │       ├── store/              # Pinia 状态
│   │       └── views/              # 页面视图
│   └── server_agent/               # FastAPI 后端
│       ├── agent/                  # Conversation / ReAct / Claude Agent
│       ├── configs/                # 模型、数据库、OSS 配置
│       ├── controller/             # API 控制器
│       ├── mapper/                 # 数据访问层
│       ├── model/                  # DTO / Entity / VO
│       └── service/                # 业务服务
├── scripts/                        # 辅助脚本
├── docs/                           # 文档
└── tests/                          # 测试目录
```

## 主要路由

### 前端页面

| 路由 | 页面 |
| --- | --- |
| `/login` | 登录 / 注册 |
| `/` | 首页 |
| `/conversation/:id` | 普通医疗对话 |
| `/files` | 文件管理 |
| `/knowledge-base` | RAG 知识库 |
| `/knowledge-base/:id` | 知识库详情 |
| `/clinical-tools` | 临床智能体列表 |
| `/clinical-agent/:agentId` | 临床智能体对话 |
| `/clinical-agent/:agentId/skills` | 智能体 Skill 管理 |
| `/skill-repository` | Skill 仓库 |
| `/model-config` | 模型配置，管理员可见 |

### 后端 API 分组

| Prefix | 说明 |
| --- | --- |
| `/user` | 用户注册、登录、资料 |
| `/conversation` | 普通会话与流式对话 |
| `/knowledge-base` | 知识库、文档、检索 |
| `/clinical-agents` | 临床智能体与 Skill 绑定 |
| `/code-agent` | Code Agent 会话、权限、任务 |
| `/skills` | Skill 仓库 |
| `/files` | 文件与 OSS 上传 |
| `/models` | 模型配置与选择 |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+（推荐）
- PostgreSQL 14+
- 可访问的 OpenAI-compatible LLM 服务
- 可访问的 OpenAI-compatible embedding 服务

### 1. 安装后端依赖

```bash
conda create -n MediAgent python=3.10
conda activate MediAgent
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件。以下为最小示例，请按本地环境替换：

```bash
# PostgreSQL
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=mediagent
PG_USER=postgres
PG_PASSWORD=your_password

# 数据目录，未配置时默认使用 src/server_new/data
MEDIAGENT_DATA_DIR=/path/to/mediagent-data

# Embedding 服务，需兼容 OpenAI embeddings API
EMBEDDING_MODEL=bge-m3
EMBEDDING_API_BASE=http://localhost:11434/v1
EMBEDDING_API_KEY=ollama

# 普通对话模型兜底配置；实际优先读取 configs/model_configs.json
MODEL=qwen-plus
MODEL_API_KEY=your_model_api_key
MODEL_URL=https://your-openai-compatible-endpoint/v1

# 可选：网络搜索工具
TAVILY_API_KEY=your_tavily_key

# 可选：临床智能体目录
CLINICAL_AGENTS_DIR=/path/to/clinical-agents

# 可选：本地文件读取工具安全目录
SAFE_READ_DIR=/path/to/safe-read-dir

# 可选：OSS 图片直传
OSS_ACCESS_KEY_ID=your_access_key_id
OSS_ACCESS_KEY_SECRET=your_access_key_secret
OSS_REGION=cn-hangzhou
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET_NAME=your_bucket
```

### 3. 初始化数据库

先创建 PostgreSQL 数据库：

```sql
CREATE DATABASE mediagent;
```

后端 mapper 会在启动时初始化所需表结构。

### 4. 启动后端

从项目根目录启动：

```bash
python main.py
```

服务默认运行在 `http://localhost:8000`。

### 5. 启动前端

```bash
cd src/frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5001`，并通过 Vite proxy 将 `/api` 转发到后端 `http://localhost:8000`。

## API 文档

后端启动后访问：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 开发说明

### 后端新增接口

1. 在 `src/server_agent/controller/` 中新增或扩展 Controller。
2. 在 `src/server_agent/service/` 中实现业务逻辑。
3. 在 `src/server_agent/mapper/` 中补充数据库访问。
4. 在 `src/server_agent/model/` 中补充 DTO、Entity 或 VO。

### 前端新增页面

1. 在 `src/frontend/src/views/` 中新增页面组件。
2. 在 `src/frontend/src/router/index.ts` 中注册路由。
3. 在 `src/frontend/src/apis/` 中补充接口封装。
4. 如需状态共享，在 `src/frontend/src/store/` 中新增 Pinia store。

## 注意事项

- `configs/main_model_config.json` 和 `.env` 可能包含模型或云服务密钥，提交代码前请替换为占位值或改用本地私有配置。
- RAG 检索依赖 embedding 服务；若 embedding 服务不可用，知识库分析和检索会失败。
- 网络搜索工具依赖 `TAVILY_API_KEY`；未配置时相关工具调用不可用。
- OCR 依赖 `rapidocr-onnxruntime` 和 `pypdfium2`，首次处理扫描 PDF 时速度会比普通文本 PDF 慢。
- Code Agent 依赖 Claude Agent SDK 及本机可用的 Claude 相关运行环境。

## 项目定位

当前版本更适合作为医疗智能体平台、RAG 知识库系统和临床科研工具编排框架的原型与开发底座。对于具体疾病诊断、治疗建议或影像结论，应结合真实医学验证、模型评估、权限审计和临床安全流程后再用于生产环境。
