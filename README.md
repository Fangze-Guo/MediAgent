# MediAgent - 智能医疗助手

<div align="center">

![MediAgent Logo](https://via.placeholder.com/200x80/4CAF50/FFFFFF?text=MediAgent)

**一个现代化的智能医疗助手系统**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D.svg)](https://vuejs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## 📋 项目概述

MediAgent 是一个智能医疗助手系统，提供用户管理、聊天对话、文件管理和工具调用等功能。系统采用前后端分离架构，后端使用 FastAPI + Python，前端使用 Vue 3 + TypeScript，为医疗场景提供智能化的数据处理和分析解决方案。

## 🏗️ 系统架构

```
MediAgent/
├── src/
│   ├── frontend/          # Vue 3 前端应用
│   ├── server_agent/      # FastAPI 后端服务
│   └── server_new/        # 数据库服务
├── docs/                  # 项目文档
└── requirements.txt       # Python 依赖
```

### 技术栈
- **后端**: FastAPI + Python + SQLite
- **前端**: Vue 3 + TypeScript + Vite
- **数据库**: SQLite + 数据库迁移
- **AI**: 支持多种 AI 模型集成

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

# 2. 启动后端服务
pip install -r requirements.txt
cd src/server_agent && python main.py

# 3. 启动前端应用 (新终端)
cd src/frontend && npm install && npm run dev
```

### 🌐 访问应用
- **前端应用**: http://localhost:5173
- **后端 API**: http://localhost:8000  
- **API 文档**: http://localhost:8000/docs
- **ReDoc 文档**: http://localhost:8000/redoc

### 📱 功能演示

1. **用户注册/登录** - 创建账户并获取访问令牌
2. **智能聊天** - 与 AI 进行医疗相关对话
3. **文件管理** - 上传医疗文档和图片
4. **工具调用** - 使用医疗数据处理工具（图像处理、CSV分析）
5. **系统监控** - 查看系统健康状态

## 📁 项目结构

### 后端结构 (`src/server_agent/`)
```
server_agent/
├── controller/          # API 控制器层
├── service/            # 业务逻辑层
├── mapper/             # 数据访问层
├── exceptions/         # 异常处理
├── tools/              # 工具模块
├── constants/          # 常量配置
├── agent.py            # AI Agent 核心
├── main.py             # 应用入口
└── tools_server.py     # 工具服务器
```

### 前端结构 (`src/frontend/`)
```
frontend/
├── src/
│   ├── apis/           # API 接口
│   ├── components/     # Vue 组件
│   ├── views/          # 页面视图
│   ├── store/          # 状态管理
│   ├── router/         # 路由配置
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
- 多目录文件管理

### 工具调用
- 医疗图像处理工具（缩放、信息获取）
- 医疗数据CSV处理工具（统计分析、预览）
- 工具列表展示和调用

### 系统管理
- 健康检查
- 系统自测
- 性能监控

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