# MediAgent 开发者文档

欢迎使用 MediAgent 智能医疗助手开发者文档！

## 🎯 文档定位

本目录专门为**开发者**提供技术文档，包括架构设计、API 参考、开发指南等。如果你是最终用户，请查看 [项目主页](../README.md)。

### 📖 核心文档

| 文档 | 描述 | 适用场景 |
|------|------|----------|
| [API 详细文档](API_Documentation.md) | 完整的 API 参考文档 | API 集成开发 |
| [后端架构文档](../src/server_agent/README.md) | 后端服务架构和设计 | 后端开发 |
| [前端架构文档](../src/frontend/README.md) | 前端应用架构和设计 | 前端开发 |

### 🏗️ 架构文档

| 层级 | 文档 | 描述 |
|------|------|------|
| **Controller** | [控制器层文档](../src/server_agent/controller/README.md) | API 控制器设计 |
| **Service** | [服务层文档](../src/server_agent/service/README.md) | 业务逻辑层设计 |
| **Mapper** | [数据访问层文档](../src/server_agent/mapper/README.md) | 数据访问层设计 |
| **Exceptions** | [异常处理文档](../src/server_agent/exceptions/README.md) | 异常处理机制 |
| **Tools** | [工具模块文档](../src/server_agent/tools/README.md) | 工具模块设计 |

## 🚀 开发者快速开始

### 环境准备
```bash
# 1. 克隆项目
git clone <repository-url>
cd MediAgent

# 2. 安装后端依赖
pip install -r requirements.txt

# 3. 安装前端依赖
cd src/frontend
npm install
```

### 启动开发环境
```bash
# 启动后端服务
cd src/server_agent
python main.py

# 启动前端服务 (新终端)
cd src/frontend
npm run dev
```

### 开发工具
- **API 文档**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **前端应用**: http://localhost:5173

## 📋 项目结构

```
MediAgent/
├── docs/                    # 项目文档
│   ├── API_Documentation.md # API 详细文档
│   ├── Developer_Quick_Start.md # 开发者快速上手指南
│   └── README.md           # 文档索引（本文件）
├── src/
│   ├── frontend/           # Vue 3 前端应用
│   └── server_agent/       # FastAPI 后端服务
└── README.md               # 项目主文档
```

## 🔧 技术栈

### 后端
- **FastAPI**: 现代、快速的 Web 框架
- **Python 3.8+**: 编程语言
- **SQLite**: 数据库
- **Pydantic**: 数据验证
- **Aiosqlite**: 异步数据库驱动

### 前端
- **Vue 3**: 渐进式 JavaScript 框架
- **TypeScript**: 类型安全的 JavaScript
- **Vite**: 快速的前端构建工具
- **Pinia**: 状态管理库
- **Vue Router**: 路由管理器

## 📊 功能特性

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
- **医疗图像处理工具**: 医学影像缩放 (`resize_image`)、图像信息获取 (`get_image_info`)
- **医疗数据处理工具**: CSV 统计分析 (`csv_summary`)、CSV 预览 (`csv_preview`)
- 工具列表展示和调用界面

### 系统管理
- 健康检查
- 系统自测
- 性能监控

## 🛠️ 开发工具

### API 测试
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 开发环境
- **后端**: http://localhost:8000
- **前端**: http://localhost:5173

## 📝 开发规范

### 代码规范
- 使用类型提示
- 遵循 PEP 8 规范（Python）
- 使用 ESLint 和 Prettier（前端）
- 添加文档字符串

### 提交规范
- 使用有意义的提交信息
- 遵循 Conventional Commits 规范
- 提交前运行测试

### 文档规范
- 保持文档更新
- 使用 Markdown 格式
- 提供代码示例

## 🔍 故障排除

### 常见问题
1. **端口冲突**: 检查 8000 和 5173 端口是否被占用
2. **依赖问题**: 确保 Python 和 Node.js 版本正确
3. **数据库问题**: 检查数据库文件权限
4. **API 调用失败**: 检查后端服务是否启动

### 获取帮助
- 查看项目 Issues
- 阅读相关文档
- 检查日志输出
- 使用调试工具

## 📈 贡献指南

### 如何贡献
1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

### 贡献类型
- 新功能开发
- Bug 修复
- 文档改进
- 性能优化

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](../LICENSE) 文件了解详情。

## 📞 联系方式

- 项目地址: [GitHub Repository]
- 问题反馈: [GitHub Issues]
- 文档地址: [Documentation]

---

**感谢您使用 MediAgent！** 🎉

如有任何问题或建议，请随时联系我们。
