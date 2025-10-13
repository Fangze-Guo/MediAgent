# MediAgent - 智能医疗助手

<div align="center">

<img src="./src/frontend/public/MediAgent.png" alt="MediAgent Logo" width="200">

**一个现代化的智能医疗助手系统**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D.svg)](https://vuejs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## 📋 项目概述

MediAgent 是一个现代化的智能医疗助手系统，集成了用户管理、AI聊天对话、文件管理、医疗应用商店和专业工具调用等功能。系统采用前后端分离架构，后端使用 FastAPI + Python，前端使用 Vue 3 + TypeScript + Ant Design Vue，为医疗场景提供智能化的数据处理、分析和应用管理解决方案。

### 🆕 最新功能
- **医疗应用商店**: 类似Chrome Web Store的应用管理平台
- **智能评论系统**: 支持用户评价、点赞和评论管理
- **多模型支持**: 集成DeepSeek、通义千问等多种AI模型
- **实时流式对话**: 支持流式AI对话和工具调用

## 🏗️ 系统架构

```
MediAgent/
├── src/
│   ├── frontend/          # Vue 3 前端应用
│   ├── server_agent/      # FastAPI 后端服务
│   └── server_new/        # 其他架构
├── docs/                  # 项目文档
└── requirements.txt       # Python 依赖
```

### 技术栈
- **后端**: FastAPI + Python + SQLite + Pydantic
- **前端**: Vue 3 + TypeScript + Vite + Ant Design Vue + Pinia
- **数据库**: SQLite + 异步数据库操作 + 外键约束
- **AI模型**: DeepSeek、通义千问、GPT等多模型支持
- **UI组件**: Ant Design Vue + 自定义组件库
- **状态管理**: Pinia + 持久化存储

## 🚀 快速开始

### 环境要求
- **Python**: 3.8+ 
- **Node.js**: 16+
- **包管理器**: npm 或 yarn

### 一键启动

```bash
# 1. 克隆项目
git clone <repository-url>
cd MediAgent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动后端服务
python main.py

# 4. 启动前端应用 (新终端)
cd src/frontend
npm install
npm run dev
```

### 🌐 访问应用
- **前端应用**: http://localhost:5173
- **后端 API**: http://localhost:8000  
- **API 文档**: http://localhost:8000/docs
- **ReDoc 文档**: http://localhost:8000/redoc

### 📱 功能演示

1. **用户注册/登录** - 创建账户并获取访问令牌
2. **智能聊天** - 与多种AI模型进行医疗相关对话
3. **医疗应用商店** - 浏览、安装和管理医疗应用
4. **应用详情页** - 查看应用详情、用户评价和评论
5. **评论系统** - 发表评论、点赞和管理个人评价
6. **文件管理** - 上传医疗文档和图片
7. **工具调用** - 使用医疗数据处理工具（图像处理、CSV分析）
8. **系统监控** - 查看系统健康状态

## 📁 项目结构

### 后端结构 (`src/server_agent/`)
```
server_agent/
├── controller/          # API 控制器层
│   ├── AppStoreController.py    # 应用商店API
│   ├── UserController.py        # 用户管理API
│   ├── ConversationController.py # 对话管理API
│   ├── FileController.py        # 文件管理API
│   └── ModelController.py       # 模型配置API
├── service/            # 业务逻辑层
│   ├── AppStoreService.py       # 应用商店服务
│   ├── UserService.py           # 用户服务
│   ├── ConversationService.py   # 对话服务
│   └── FileService.py           # 文件服务
├── model/              # 数据模型
│   ├── entity/         # 实体类
│   ├── dto/           # 数据传输对象
│   └── vo/            # 视图对象
├── database/           # 数据库相关
├── exceptions/         # 异常处理
├── configs/           # 配置管理
├── script/            # 医疗数据处理脚本
└── runtime_registry.py # 运行时注册
```

### 前端结构 (`src/frontend/`)
```
frontend/
├── src/
│   ├── apis/           # API 接口层
│   │   ├── appStore.ts      # 应用商店API
│   │   ├── auth.ts          # 认证API
│   │   ├── chat.ts          # 聊天API
│   │   └── files.ts         # 文件API
│   ├── components/     # Vue 组件
│   │   ├── file/           # 文件相关组件
│   │   ├── ModelSelector.vue # 模型选择器
│   │   └── Sidebar.vue      # 侧边栏
│   ├── views/          # 页面视图
│   │   ├── AppStoreView.vue    # 应用商店页面
│   │   ├── AppDetailView.vue   # 应用详情页面
│   │   ├── ChatView.vue        # 聊天页面
│   │   └── LoginView.vue       # 登录页面
│   ├── store/          # Pinia 状态管理
│   │   ├── auth.ts         # 认证状态
│   │   ├── conversations.ts # 对话状态
│   │   └── files.ts        # 文件状态
│   ├── router/         # Vue Router 配置
│   ├── types/          # TypeScript 类型定义
│   └── utils/          # 工具函数
├── package.json         # 项目配置
└── vite.config.ts      # Vite 配置
```

## 🔧 开发指南

### 后端开发
1. **添加新功能**:
   - 在 `controller/` 添加 API 端点
   - 在 `service/` 实现业务逻辑
   - 在 `mapper/` 添加数据访问

2. **代码规范**:
   - 使用类型提示
   - 遵循 PEP 8 规范
   - 添加文档字符串

### 前端开发
1. **组件开发**:
   - 使用 Vue 3 Composition API
   - TypeScript 类型安全
   - 组件化设计

2. **状态管理**:
   - 使用 Pinia 进行状态管理
   - 模块化状态设计

## 📋 主要功能

### 🏪 医疗应用商店
- **应用浏览**: Chrome Web Store风格的应用展示
- **分类筛选**: 按医学影像、数据分析等分类浏览
- **搜索功能**: 支持应用名称和描述搜索
- **应用详情**: 详细的应用介绍、功能特点和用户评价
- **安装管理**: 一键安装/卸载医疗应用

### 💬 智能评论系统
- **用户评价**: 5星评分系统和文字评论
- **点赞功能**: 支持评论点赞，每用户每评论限一次
- **评论管理**: 用户可编辑、删除自己的评论
- **排序筛选**: 按时间、评分等多种方式排序
- **用户高亮**: 突出显示用户自己的评论

### 🤖 AI聊天对话
- **多模型支持**: DeepSeek、通义千问等多种AI模型
- **流式对话**: 实时流式消息显示
- **推理展示**: DeepSeek-Reasoner思考过程展示
- **历史记录**: 完整的对话历史管理
- **工具调用**: AI智能调用医疗工具

### 👤 用户管理
- **注册登录**: 安全的用户认证系统
- **用户信息**: 个人信息管理和更新
- **Token认证**: JWT令牌安全认证
- **权限控制**: 基于用户的权限管理

### 📁 文件管理
- **文件上传**: 支持医疗图像、CSV等多种格式
- **文件浏览**: 树形目录结构浏览
- **批量操作**: 支持批量删除和管理
- **文件预览**: 在线预览和下载功能

### 🛠️ 医疗工具
- **图像处理**: 医学影像缩放、格式转换
- **数据分析**: CSV医疗数据统计分析
- **nnU-Net**: 医学图像分割和处理
- **DICOM处理**: DICOM文件转换和处理

### ⚙️ 系统管理
- **模型配置**: 动态切换和配置AI模型
- **健康监控**: 系统状态和性能监控
- **错误处理**: 完善的异常处理机制
- **日志管理**: 详细的操作日志记录

## 🛠️ 部署指南

### 开发环境
```bash
# 后端
cd src/server_agent
python main.py

# 前端
cd src/frontend
npm run dev
```

### 生产环境
```bash
# 构建前端
cd src/frontend
npm run build

# 启动后端
cd src/server_agent
python main.py
```

### Docker 部署
```dockerfile
# Dockerfile 示例
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## 🎯 使用场景

### 👨‍⚕️ 医疗专业人员
- **病历数据处理**: 使用 CSV 工具处理病历数据，进行统计分析
- **医疗图像处理**: 批量调整医学影像尺寸，获取图像信息
- **医疗数据分析**: 通过 AI 助手分析医疗数据特征和模式

### 🏥 医疗机构
- **临床数据处理**: 处理临床实验产生的 CSV 数据
- **医学影像分析**: 分析医学影像，调整尺寸用于报告
- **医疗数据洞察**: 通过 AI 助手理解医疗数据趋势

### 🔬 医学研究人员
- **研究数据处理**: 处理医学研究数据和统计信息
- **医学图像管理**: 批量处理研究中的医学图像
- **数据可视化**: 通过对话方式理解医学数据含义


## 🔒 隐私与安全

- **数据加密**: 所有敏感医疗数据加密存储
- **隐私保护**: 严格遵守医疗数据隐私法规
- **安全传输**: HTTPS 加密传输
- **访问控制**: 基于角色的权限管理

## 📱 特色功能

### 🤖 智能对话
- 自然语言交互
- 上下文理解
- 多轮对话支持

### 📄 文件处理
- 支持多种医疗数据文件格式（CSV、医学影像等）
- 智能医疗文件分析
- 批量处理能力

### 🛠️ 专业工具
- **医疗图像处理**: 医学影像缩放、格式转换、信息获取
- **医疗数据处理**: CSV 统计分析、数据预览、格式转换
- **工具集成**: 通过 AI 助手智能调用医疗工具

## 📞 获取帮助

### 💬 用户支持
- **在线帮助**: 访问应用内的帮助中心
- **常见问题**: 查看 FAQ 解答
- **用户反馈**: 通过应用内反馈功能

### 🔧 技术支持
- **开发者文档**: [查看开发者文档](docs/README.md)
- **API 文档**: [查看 API 文档](docs/API_Documentation.md)
- **问题反馈**: [GitHub Issues]

## 📄 许可证

本项目采用 **MIT 许可证** - 查看 [LICENSE](LICENSE) 文件了解详情。

---

<div align="center">

**感谢使用 MediAgent！** 🎉

*让医疗数据处理更智能，让医学分析更简单*

**开始体验**: [http://localhost:5173](http://localhost:5173)

</div>