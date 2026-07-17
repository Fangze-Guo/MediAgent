# MedWiser 医学智能体平台

<div align="center">

<img src="./src/frontend/public/MedWiser.png" alt="MedWiser Logo" width="180">

**医学知识管理、专病智能体与患者影像数据的一体化工作平台**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D.svg)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6.svg)](https://www.typescriptlang.org/)

</div>

## 项目简介

MedWiser 是一个面向医疗与临床科研场景的智能体平台。它将分散的医学文献、专病分析工具、患者临床资料和医学影像统一到一个工作空间中，让用户可以从资料入库开始，完成知识检索、可信问答、智能体任务执行、影像结果复核和报告导出。

平台不是单一的医学聊天机器人，而是一套可扩展的临床科研工作台：医学资料经过解析和向量化后可用于有来源依据的问答；不同专病项目可以配置独立智能体与 Skill；智能体产生的 CT、mask 和指标结果还可以回流至患者数据集，供医生集中查看和复核。

| 登录界面 | 系统首页 |
| --- | --- |
| ![MedWiser 登录界面](./docs/images/medwiser/figure-1-login.png) | ![MedWiser 系统首页](./docs/images/medwiser/figure-2-home.png) |

整体业务流程如下：

```mermaid
flowchart LR
    A[医学资料知识化] --> B[可信问答与来源追溯]
    B --> C[专病智能体任务执行]
    C --> D[患者数据沉淀]
    D --> E[影像结果复核]
    E --> F[检查报告输出]
```

平台适合医学知识库建设、专病科研流程编排、治疗前后影像分析和科研原型验证。后端基于 FastAPI、PostgreSQL、LangChain、LangGraph、Chroma 和 Claude Agent SDK，前端基于 Vue 3、TypeScript、Vite、Pinia 和 Ant Design Vue。

> 当前仓库目录名及部分后端标识仍沿用 `MediAgent`，产品界面与本文档统一使用 **MedWiser**。
>
> 本文截图提取自《MedWiser 医学智能体平台 V1.0 说明文档》，完整原图保存在 `docs/images/medwiser/`。

## 核心能力

### 1. 医学知识库与可追溯问答

- 创建、编辑和删除医学知识库，查看文档数与切片数。
- 上传并解析 PDF、Word、Excel、TXT、Markdown、CSV 等医学资料。
- 完成文本抽取、清洗、分块、Embedding 生成与 Chroma 向量写入。
- 对知识库内容执行语义检索，并查看命中的来源片段。
- 支持普通医学多轮会话、SSE 流式输出、Markdown 渲染和知识库上下文注入。
- ReAct Agent 可按需调用知识库检索、网络搜索、本地数据集文件读取、医学影像报告生成等工具。
- PDF 优先提取文字层；扫描版或文字稀疏文档可自动降级至 OCR。
- Excel 按行生成语义化切片，减少表格数据被截断或脱离表头的问题。

#### 界面展示

| 知识库列表 | 创建知识库 |
| --- | --- |
| ![知识库列表](./docs/images/medwiser/figure-3-knowledge-base-list.png) | ![创建知识库](./docs/images/medwiser/figure-4-knowledge-base-create.png) |

| 知识库详情 | 上传医学文档 |
| --- | --- |
| ![知识库详情](./docs/images/medwiser/figure-5-knowledge-base-detail.png) | ![上传医学文档](./docs/images/medwiser/figure-6-document-upload.png) |

| 文档预览 | 文档解析与切片 |
| --- | --- |
| ![文档预览](./docs/images/medwiser/figure-7-document-preview.png) | ![文档解析与切片](./docs/images/medwiser/figure-8-document-analysis.png) |

| 知识库语义检索 | 普通医学对话 |
| --- | --- |
| ![知识库语义检索](./docs/images/medwiser/figure-9-knowledge-base-search.png) | ![普通医学对话与检索过程](./docs/images/medwiser/figure-10-medical-chat.png) |

| 来源片段与工具调用 |  |
| --- | --- |
| ![来源片段与工具调用](./docs/images/medwiser/figure-11-answer-sources.png) |  |

### 2. 专病临床智能体与 Skill 任务闭环

- 创建和维护临床智能体，为不同专病项目配置独立的系统提示词与工作目录。
- 默认注册 NICE-BCX 临床智能体，用于肺癌新辅助治疗前后影像分析场景。
- 通过 Claude Agent SDK 执行 Code Agent 会话，支持任务规划、流式输出、会话恢复与结果导出。
- 支持工具权限确认、取消、用户问题回应和任务中断。
- 支持从全局 Skill 仓库查看、上传和删除 Skill，并为指定临床智能体安装或卸载 Skill。
- Skill 后台任务状态持久化至 PostgreSQL，可查询、取消、删除、清理并在服务重启后恢复记录。
- 模型任务与 SSE 连接解耦；页面断开后后台任务可继续运行，重新连接后可通过会话状态和 JSONL 消息恢复进度。

#### 界面展示

| 临床智能体入口 | 创建临床智能体 |
| --- | --- |
| ![临床智能体入口](./docs/images/medwiser/figure-12-clinical-agent-list.png) | ![创建临床智能体](./docs/images/medwiser/figure-13-clinical-agent-create.png) |

| 临床智能体会话 | 临床任务流式执行 |
| --- | --- |
| ![临床智能体会话](./docs/images/medwiser/figure-14-clinical-agent-chat.png) | ![临床任务流式执行](./docs/images/medwiser/figure-15-clinical-task-stream.png) |

| Skill 任务管理器 | Skill 仓库 |
| --- | --- |
| ![Skill 任务管理器](./docs/images/medwiser/figure-16-skill-task-manager.png) | ![Skill 仓库](./docs/images/medwiser/figure-17-skill-repository.png) |

| Skill 详情 | 智能体 Skill 管理 |
| --- | --- |
| ![Skill 详情](./docs/images/medwiser/figure-18-skill-detail.png) | ![智能体 Skill 管理](./docs/images/medwiser/figure-19-agent-skill-management.png) |

### 3. 患者影像数据与智能报告

- 新增、检索、编辑、删除患者，集中维护基本资料和临床信息。
- 管理治疗前（PRE）与治疗后（POST）CT 数据，支持上传、替换、下载、删除和从智能体输出导入。
- 管理 `body-composition`、`spine`、`lung`、`tumor` 四类 PRE/POST mask。
- 基于 SimpleITK 读取 NIfTI 体数据，提供轴状面、矢状面和冠状面三切面预览。
- 展示体成分指标、肺癌 MPR 概率与 DFS 风险等计算结果，辅助医生复核。
- 自动识别并关联患者对应的智能体输出，区分手动上传数据与智能体生成数据。
- 根据患者现有资料、影像预览和计算结果生成 PDF 检查报告。
- 普通对话可基于图片或 NIfTI 文件生成结构化医学影像报告。

#### 界面展示

| 患者列表 | 新增患者 |
| --- | --- |
| ![患者列表](./docs/images/medwiser/figure-20-patient-list.png) | ![新增患者](./docs/images/medwiser/figure-21-patient-create.png) |

| 患者详情 | 体成分 mask |
| --- | --- |
| ![患者详情](./docs/images/medwiser/figure-22-patient-detail.png) | ![体成分 mask](./docs/images/medwiser/figure-23-body-composition-mask.png) |

| 脊柱 mask | 双肺 mask |
| --- | --- |
| ![脊柱 mask](./docs/images/medwiser/figure-24-spine-mask.png) | ![双肺 mask](./docs/images/medwiser/figure-25-lung-mask.png) |

| 肺部肿瘤 mask | 新辅助治疗相关指标 |
| --- | --- |
| ![肺部肿瘤 mask](./docs/images/medwiser/figure-26-tumor-mask.png) | ![新辅助治疗相关指标](./docs/images/medwiser/figure-27-treatment-metrics.png) |

| CT 与 mask 三切面预览 | 患者 PDF 检查报告 |
| --- | --- |
| ![CT 与 mask 三切面预览](./docs/images/medwiser/figure-28-mpr-viewer.png) | ![患者 PDF 检查报告](./docs/images/medwiser/figure-29-patient-report.png) |

| 智能体输出关联 |  |
| --- | --- |
| ![智能体输出关联](./docs/images/medwiser/figure-30-agent-output-association.png) |  |

### 4. 平台基础能力

- 用户注册、登录、资料更新、路由鉴权与管理员权限控制。
- 数据集文件浏览、上传、批量删除、重命名和文件夹创建。
- 聊天图片通过阿里云 OSS 预签名地址直传。
- 模型配置、启停、供应商与分类管理，以及用户当前模型选择。
- 中文、英文界面切换。

## 系统架构

```mermaid
flowchart TB
    UI[Vue 3 Web 客户端]
    API[FastAPI REST / SSE API]

    UI --> API
    API --> CHAT[普通会话与 ReAct Agent]
    API --> CLINICAL[临床智能体与 Code Agent]
    API --> PATIENT[患者影像与报告服务]
    API --> FILES[文件、用户与模型服务]

    CHAT --> LLM[OpenAI-compatible LLM]
    CHAT --> EMB[Embedding API]
    CHAT --> CHROMA[(Chroma)]
    CLINICAL --> CLAUDE[Claude Agent SDK]
    CLINICAL --> SKILLS[项目级 Skill]
    PATIENT --> DATA[(本地患者数据)]
    API --> PG[(PostgreSQL)]
    FILES --> OSS[阿里云 OSS]
```

## 技术栈

| 层级 | 技术 | 主要用途 |
| --- | --- | --- |
| 前端 | Vue 3、TypeScript、Vite | 单页应用与开发构建 |
| UI 与状态 | Ant Design Vue、Pinia、vue-router、vue-i18n | 组件、状态、路由鉴权与国际化 |
| 后端 | FastAPI、Uvicorn、Pydantic | REST API、SSE 与数据校验 |
| 智能体 | LangChain、LangGraph、Claude Agent SDK | ReAct 问答、工具决策与临床任务执行 |
| 数据库 | PostgreSQL、asyncpg | 用户、知识库、会话、智能体和任务状态持久化 |
| RAG | Chroma、langchain-chroma、OpenAI-compatible Embedding API | 文档向量化与语义检索 |
| 文档处理 | pypdf、pypdfium2、RapidOCR、python-docx、openpyxl | PDF、OCR、Word 和 Excel 解析 |
| 医学影像 | SimpleITK、Pillow、NumPy | NIfTI 读取、三切面预览与 PDF 报告绘制 |
| 对象存储 | Alibaba Cloud OSS SDK | 聊天图片预签名上传与文件清理 |

## 项目结构

```text
MediAgent/
├── main.py                              # FastAPI 启动入口
├── requirements.txt                     # Python 依赖
├── src/
│   ├── frontend/                        # Vue 3 前端
│   │   ├── public/                      # Logo 等静态资源
│   │   └── src/
│   │       ├── apis/                    # API 请求封装
│   │       ├── components/              # 通用、对话、知识库和影像组件
│   │       ├── i18n/                    # 中英文语言包
│   │       ├── router/                  # 页面路由与权限守卫
│   │       ├── store/                   # Pinia 状态管理
│   │       └── views/                   # 业务页面
│   ├── server_agent/                    # FastAPI 后端
│   │   ├── agent/                       # 普通、ReAct、影像报告与 Claude Agent
│   │   ├── configs/                     # PostgreSQL、模型与 OSS 配置
│   │   ├── controller/                  # API 控制器
│   │   ├── mapper/                      # 数据访问与数据目录管理
│   │   ├── model/                       # DTO、Entity 与 VO
│   │   └── service/                     # 业务服务与后台任务
│   └── server_new/data/                 # 默认本地数据目录（运行时生成）
├── docs/
│   ├── images/medwiser/                 # README 与软件说明文档界面截图
│   └── 软著/                            # MedWiser V1.0 软件说明文档
├── scripts/                             # 数据检查等辅助脚本
└── ref/                                 # 调试与优化参考材料
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 20.19+（或 22.12+）与 npm
- PostgreSQL 14+
- OpenAI-compatible LLM API
- OpenAI-compatible Embedding API
- Chrome、Edge 等现代浏览器
- 如需使用临床 Code Agent，需具备可用的 Claude Agent SDK 认证与运行环境

### 1. 获取项目并安装后端依赖

```bash
git clone <repository-url>
cd MediAgent

conda create -n medwiser python=3.10
conda activate medwiser
pip install -r requirements.txt
```

也可以使用其他 Python 虚拟环境工具，但请确保解释器版本不低于 3.10。

### 2. 创建 PostgreSQL 数据库

```sql
CREATE DATABASE mediagent;
```

后端首次启动时会初始化所需表结构。

### 3. 配置环境变量

在项目根目录创建 `.env` 文件，并按实际环境填写：

```dotenv
# PostgreSQL
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=mediagent
PG_USER=postgres
PG_PASSWORD=your_password

# 本地数据目录；默认值为 src/server_new/data
MEDIAGENT_DATA_DIR=/absolute/path/to/medwiser-data

# 普通问答模型兜底配置
# 系统存在有效模型配置时，优先读取 src/server_agent/configs 下的配置文件
MODEL=qwen-plus
MODEL_API_KEY=your_model_api_key
MODEL_URL=https://your-openai-compatible-endpoint/v1

# Embedding 服务
EMBEDDING_MODEL=qwen3-embedding:8b
EMBEDDING_API_BASE=http://localhost:11434/v1
EMBEDDING_API_KEY=ollama

# 临床智能体与 Skill 目录
CLINICAL_AGENTS_DIR=/absolute/path/to/clinical-agents
GLOBAL_SKILLS_DIR=/absolute/path/to/global-skills

# 可选：ReAct 网络搜索与本地安全读取目录
TAVILY_API_KEY=your_tavily_key
SAFE_READ_DIR=/absolute/path/to/safe-read-dir

# 可选：聊天图片 OSS 直传
OSS_ACCESS_KEY_ID=your_access_key_id
OSS_ACCESS_KEY_SECRET=your_access_key_secret
OSS_REGION=cn-hangzhou
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET_NAME=your_bucket
```

如果不设置目录变量，系统将使用以下默认位置：

| 配置项 | 默认位置 |
| --- | --- |
| `MEDIAGENT_DATA_DIR` | `src/server_new/data` |
| `CLINICAL_AGENTS_DIR` | `~/mediagent/agents` |
| `GLOBAL_SKILLS_DIR` | `~/.claude/skills` |
| `SAFE_READ_DIR` | `~/mediagent` |

### 4. 启动后端

在项目根目录执行：

```bash
python main.py
```

默认服务地址：

- 后端 API：`http://localhost:8000`
- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

### 5. 启动前端

新开一个终端执行：

```bash
cd src/frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5001`。开发服务器会将 `/api` 请求代理至 `http://localhost:8000`。

### 6. 生产构建

```bash
cd src/frontend
npm run build
```

构建产物位于 `src/frontend/dist/`，可交由 Nginx 等 Web 服务器部署；后端服务需单独运行并配置相应的 API 反向代理。

## 主要页面

| 路由 | 功能 |
| --- | --- |
| `/login` | 用户登录与注册 |
| `/` | 平台首页与功能入口 |
| `/conversation/:id` | 普通医学对话与可追溯问答 |
| `/knowledge-base` | 知识库列表与创建 |
| `/knowledge-base/:id` | 文档管理、解析、向量化与检索 |
| `/clinical-tools` | 专病临床智能体入口 |
| `/clinical-agent/:agentId` | 临床智能体流式会话 |
| `/clinical-agent/:agentId/skills` | 指定智能体的 Skill 管理 |
| `/skill-repository` | 全局 Skill 仓库 |
| `/patients` | 患者数据集管理 |
| `/patients/:patientId` | CT、mask、指标、智能体输出与报告 |
| `/files` | 用户数据集文件管理 |
| `/model-config` | 模型配置，限管理员访问 |

## 后端 API 分组

| Prefix | 功能 |
| --- | --- |
| `/user` | 用户注册、登录与资料维护 |
| `/conversation` | 普通会话、消息与流式问答 |
| `/knowledge-base` | 知识库、文档解析与语义检索 |
| `/clinical-agents` | 临床智能体与 Skill 绑定 |
| `/code-agent` | Code Agent 会话、权限、状态与后台任务 |
| `/skills` | 全局 Skill 仓库 |
| `/patients` | 患者、CT、mask、结果与 PDF 报告 |
| `/files` | 数据集文件与 OSS 上传 |
| `/models` | 模型配置与用户模型选择 |

具体请求参数与响应结构以后端运行时生成的 Swagger 文档为准。

## 数据与运行机制

### 本地数据目录

`MEDIAGENT_DATA_DIR` 用于统一承载运行时本地数据，主要包括：

- `chroma/`：知识库向量数据。
- `patient/`：患者资料、PRE/POST CT、mask、结果文件与导出报告。
- 用户私有数据集及其他业务文件。

患者 ID 也是患者目录的唯一标识。处理患者级临床任务时，应明确提供 `patient_id`，避免将分析结果关联至错误的数据集。

### 模型配置

普通问答模型优先读取 `src/server_agent/configs/model_configs.json` 和 `main_model_config.json` 中的当前模型配置；`.env` 中的 `MODEL`、`MODEL_API_KEY` 和 `MODEL_URL` 作为兜底配置。Embedding 模型使用独立配置，不与对话模型共用连接参数。

### 会话与任务恢复

普通业务数据和 Skill 任务状态保存在 PostgreSQL。Code Agent 的消息记录通过 JSONL 会话日志读取，长任务独立于 SSE 客户端连接运行；前端重新进入会话后，可结合会话状态与日志恢复消息和执行进度。

## 开发说明

### 新增后端能力

1. 在 `src/server_agent/controller/` 中注册接口。
2. 在 `src/server_agent/service/` 中实现业务逻辑。
3. 需要持久化时，在 `src/server_agent/mapper/` 中补充数据访问。
4. 在 `src/server_agent/model/` 中定义请求、实体或响应模型。

### 新增前端页面

1. 在 `src/frontend/src/views/` 中创建页面。
2. 在 `src/frontend/src/router/index.ts` 中注册路由及权限元数据。
3. 在 `src/frontend/src/apis/` 中封装后端请求。
4. 需要跨组件状态时，在 `src/frontend/src/store/` 中创建 Pinia store。

### 扩展临床智能体

1. 在临床工具页面创建智能体并配置系统提示词。
2. 为智能体设置独立工作目录。
3. 从 Skill 仓库安装该专病流程需要的工具。
4. 在临床智能体会话中验证权限确认、任务输出与患者数据关联。

## 注意事项

- 本项目输出仅用于医学科研、流程辅助与医生复核，不能替代专业医生的诊断或治疗决策。
- 在处理真实患者数据前，应完成数据脱敏、访问控制、传输与存储加密、操作审计及合规评估。
- 不要将 `.env`、模型密钥、OSS 密钥或包含真实患者信息的运行时数据提交到版本库。
- RAG 分析和检索依赖 Embedding 服务；服务不可用时，文档向量化与语义检索将失败。
- 网络搜索依赖 `TAVILY_API_KEY`；未配置时不应要求 Agent 调用该工具。
- 扫描版 PDF 的 OCR 处理通常慢于文字层提取，首次加载 OCR 模型时耗时会更明显。
- Code Agent 依赖 Claude Agent SDK 及其认证环境；项目级 Skill 可能执行文件读写或外部程序，应在授权前核对工具名称、参数与作用范围。
- 生产部署前应收紧当前开发环境的 CORS、文件访问范围、默认账号策略和接口暴露范围。

## 版本说明

当前文档对应 **MedWiser 医学智能体平台 V1.0**。README 根据软件说明文档与仓库现有实现整理，后续功能和接口变更请同步更新本文档。
