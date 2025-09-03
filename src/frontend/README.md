# MediAgent Frontend (简洁版)

一个使用 Vue 3 + TypeScript + Vue Router + Vite 构建的纯静态前端演示：
- 左侧固定 Sidebar（纯静态）
- 右侧由路由控制显示聊天区（ChatView）与其他页面
- 使用组合式 API（<script setup>）与 TypeScript
- 仅包含少量假数据与静态内容，代码简洁易读

## 🚀 技术栈
- **Vue 3**（Composition API）
- **TypeScript**
- **Vue Router 4**
- **Vite**

## 📁 当前项目结构
```
src/
├── components/
│   └── Sidebar.vue          # 左侧固定侧边栏（静态）
├── views/
│   ├── ChatView.vue         # 聊天界面（静态假数据）
│   ├── SettingsView.vue     # 设置页（静态）
│   └── NotFoundView.vue     # 404 页面（静态）
├── router/
│   └── index.ts             # 简单路由配置
├── App.vue                  # 根组件（Sidebar + <router-view />）
├── main.ts                  # 入口文件，注册路由
└── style.css                # 全局样式（保证全屏布局）
```

## ✨ 页面与路由
- `/`         → 聊天页面 ChatView（右侧内容区占满；渐变背景）
- `/settings` → 设置页面 SettingsView（静态示例）
- 404         → NotFoundView

## 🧩 布局说明
- `App.vue` 仅负责布局：`Sidebar` 固定在左侧，右侧为 `<router-view />`
- 全屏布局通过 `style.css` 与 `App.vue` 样式共同保证（`html/body/#app` 全高全宽）
- 所有页面为静态展示，未引入全局状态、store、composables、types 等复杂结构

## 🛠️ 开发与构建
安装依赖：
```bash
npm install
```

启动开发服务器：
```bash
npm run dev
```

构建生产版本：
```bash
npm run build
```

预览生产版本：
```bash
npm run preview
```

## ✅ 约定与风格
- 全部组件使用 `<script setup lang="ts">`
- 不使用多余的 props/emit/状态，保持“可读、可理解”的静态示例
- 侧边栏宽度固定，内容区自适应填满右侧

## 📄 许可证
MIT License
