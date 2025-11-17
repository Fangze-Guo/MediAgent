/**
 * 应用入口文件
 * 初始化Vue应用，配置插件和挂载根组件
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import i18n from '@/i18n'
import { useAuthStore } from '@/store/auth'

/**
 * 创建Vue应用实例
 */
const app = createApp(App)

/**
 * 创建Pinia状态管理实例
 */
const pinia = createPinia()

/**
 * 注册插件
 * 1. Pinia - 状态管理
 * 2. Vue Router - 路由管理
 * 3. i18n - 国际化
 * 4. Ant Design Vue - UI组件库
 */
app.use(pinia)
app.use(router)
app.use(i18n)
app.use(Antd)

/**
 * 挂载应用到DOM
 * 将Vue应用挂载到id为'app'的DOM元素上
 */
app.mount('#app')

/**
 * 初始化认证状态
 * 在应用启动时检查本地存储的token并验证用户状态
 */
const authStore = useAuthStore()
authStore.initAuth()
