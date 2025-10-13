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
│   ├── AppStore_API_Documentation.md # 应用商店 API 文档
│   └── README.md           # 文档索引（本文件）
├── src/
│   ├── frontend/           # Vue 3 前端应用
│   ├── server_agent/       # FastAPI 后端服务
│   └── server_new/         # 新架构服务
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
- **Vue 3**: 渐进式 JavaScript 框架 (Composition API)
- **TypeScript**: 类型安全的 JavaScript
- **Vite**: 快速的前端构建工具
- **Ant Design Vue**: UI 组件库
- **Pinia**: 状态管理库
- **Vue Router**: 路由管理器

## 📊 功能特性

### 🏪 医疗应用商店 (新增)
- **应用浏览**: Chrome Web Store 风格的应用展示界面
- **分类筛选**: 按医学影像、数据分析等分类浏览应用
- **搜索功能**: 支持应用名称、描述和标签搜索
- **应用详情**: 详细的应用介绍页面，包含功能特点和用户评价
- **安装管理**: 一键安装/卸载医疗应用

### 💬 智能评论系统 (新增)
- **用户评价**: 5星评分系统和详细文字评论
- **点赞功能**: 支持评论点赞，每用户每评论限制一次点赞
- **评论管理**: 用户可以编辑、删除自己的评论
- **排序筛选**: 按时间、评分、有用性等多种方式排序
- **用户高亮**: 突出显示用户自己发表的评论

### 🤖 AI聊天对话 (增强)
- **多模型支持**: 集成 DeepSeek、通义千问等多种 AI 模型
- **流式对话**: 实时流式消息显示，提升用户体验
- **推理展示**: DeepSeek-Reasoner 模型的思考过程展示
- **历史记录**: 完整的对话历史管理和持久化
- **工具调用**: AI 智能调用医疗数据处理工具

### 👤 用户管理 (完善)
- **注册登录**: 安全的用户认证系统
- **用户信息**: 个人信息管理和更新
- **JWT认证**: 基于令牌的安全认证机制
- **权限控制**: 基于用户角色的权限管理

### 📁 文件管理 (完善)
- **文件上传**: 支持医疗图像、CSV 等多种格式文件
- **文件浏览**: 树形目录结构浏览和导航
- **批量操作**: 支持批量删除和文件管理操作
- **文件预览**: 在线预览和安全下载功能

### 🛠️ 医疗工具 (扩展)
- **图像处理**: 医学影像缩放 (`resize_image`)、图像信息获取 (`get_image_info`)
- **数据分析**: CSV 统计分析 (`csv_summary`)、CSV 预览 (`csv_preview`)
- **nnU-Net**: 医学图像分割和深度学习处理
- **DICOM处理**: DICOM 文件转换和医学影像处理

### ⚙️ 系统管理 (增强)
- **模型配置**: 动态切换和配置 AI 模型
- **健康监控**: 系统状态和性能实时监控
- **错误处理**: 完善的异常处理和用户友好提示
- **日志管理**: 详细的操作日志和调试信息

## 🛠️ 开发工具

### API 测试
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 开发环境
- **后端服务**: http://localhost:8000
- **前端应用**: http://localhost:5173
- **应用商店**: http://localhost:5173/app-store
- **聊天界面**: http://localhost:5173/chat

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
2. **依赖问题**: 确保 Python 3.8+ 和 Node.js 16+ 版本正确
3. **数据库问题**: 检查 SQLite 数据库文件权限和路径
4. **API 调用失败**: 检查后端服务是否启动，CORS 配置是否正确
5. **应用商店404**: 确保数据库已初始化，检查 `src/server_new/data/db/app.sqlite3`
6. **点赞功能异常**: 检查 `review_likes` 表是否存在，用户是否已登录
7. **AI模型切换失败**: 检查模型配置文件和API密钥设置

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
- **新功能开发**: 应用商店新功能、AI模型集成等
- **Bug 修复**: 修复已知问题和异常处理
- **文档改进**: 完善API文档、使用指南等
- **性能优化**: 前后端性能优化、数据库查询优化
- **UI/UX改进**: 界面设计优化、用户体验提升

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](../LICENSE) 文件了解详情。

## 📞 联系方式

- 项目地址: [GitHub Repository]
- 问题反馈: [GitHub Issues]
- 文档地址: [Documentation]

---

**感谢您使用 MediAgent！** 🎉

如有任何问题或建议，请随时联系我们。
