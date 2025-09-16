<template>
  <!-- 登录页面主容器 -->
  <div class="login-container">
    <div class="login-card">
      <!-- 页面标题区域 -->
      <div class="login-header">
        <h1 class="login-title">MediAgent</h1>
        <p class="login-subtitle">医学智能助手</p>
      </div>

      <!-- 登录/注册标签页切换 -->
      <a-tabs v-model:activeKey="activeTab" centered class="login-tabs">
        <a-tab-pane key="login" tab="登录" />
        <a-tab-pane key="register" tab="注册" />
      </a-tabs>

      <!-- 登录表单 -->
      <a-form
        v-if="activeTab === 'login'"
        :model="loginForm"
        :rules="loginRules"
        @finish="handleLogin"
        layout="vertical"
        class="login-form"
      >
        <!-- 用户名输入框 -->
        <a-form-item label="用户名" name="user_name">
          <a-input
            v-model:value="loginForm.user_name"
            placeholder="请输入用户名"
            size="large"
            :disabled="loading"
          />
        </a-form-item>

        <!-- 密码输入框 -->
        <a-form-item label="密码" name="password">
          <a-input-password
            v-model:value="loginForm.password"
            placeholder="请输入密码"
            size="large"
            :disabled="loading"
          />
        </a-form-item>

        <!-- 登录按钮 -->
        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            size="large"
            block
            :loading="loading"
            class="submit-button"
          >
            {{ loading ? '登录中...' : '登录' }}
          </a-button>
        </a-form-item>
      </a-form>

      <!-- 注册表单 -->
      <a-form
        v-if="activeTab === 'register'"
        :model="registerForm"
        :rules="registerRules"
        @finish="handleRegister"
        layout="vertical"
        class="login-form"
      >
        <!-- 用户名输入框 -->
        <a-form-item label="用户名" name="user_name">
          <a-input
            v-model:value="registerForm.user_name"
            placeholder="请输入用户名"
            size="large"
            :disabled="loading"
          />
        </a-form-item>

        <!-- 密码输入框 -->
        <a-form-item label="密码" name="password">
          <a-input-password
            v-model:value="registerForm.password"
            placeholder="请输入密码"
            size="large"
            :disabled="loading"
          />
        </a-form-item>

        <!-- 确认密码输入框 -->
        <a-form-item label="确认密码" name="confirmPassword">
          <a-input-password
            v-model:value="registerForm.confirmPassword"
            placeholder="请再次输入密码"
            size="large"
            :disabled="loading"
          />
        </a-form-item>

        <!-- 注册按钮 -->
        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            size="large"
            block
            :loading="loading"
            class="submit-button"
          >
            {{ loading ? '注册中...' : '注册' }}
          </a-button>
        </a-form-item>
      </a-form>

      <!-- 注册成功提示 -->
      <a-alert
        v-if="registerSuccessMessage"
        :message="registerSuccessMessage"
        type="success"
        show-icon
        closable
        @close="registerSuccessMessage = ''"
        class="success-alert"
      />

      <!-- 登录成功提示 -->
      <a-alert
        v-if="loginSuccessMessage"
        :message="loginSuccessMessage"
        type="success"
        show-icon
        closable
        @close="loginSuccessMessage = ''"
        class="success-alert"
      />

      <!-- 错误提示 -->
      <a-alert
        v-if="errorMessage"
        :message="errorMessage"
        type="error"
        show-icon
        closable
        @close="errorMessage = ''"
        class="error-alert"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import type { LoginRequest, RegisterRequest } from '@/types/auth'

const router = useRouter()
const authStore = useAuthStore()

// 当前激活的标签页：登录或注册
const activeTab = ref<'login' | 'register'>('login')
// 表单提交加载状态
const loading = ref(false)
// 错误提示信息
const errorMessage = ref('')
// 注册成功提示信息
const registerSuccessMessage = ref('')
// 登录成功提示信息
const loginSuccessMessage = ref('')

// 登录表单数据
const loginForm = reactive<LoginRequest>({
  user_name: '',
  password: ''
})

// 注册表单数据（包含确认密码字段）
const registerForm = reactive<RegisterRequest & { confirmPassword: string }>({
  user_name: '',
  password: '',
  confirmPassword: ''
})

// 登录表单验证规则
const loginRules = {
  user_name: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度在 3 到 20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' }
  ]
}

// 注册表单验证规则
const registerRules = {
  user_name: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度在 3 到 20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_: any, value: string) => {
        if (value !== registerForm.password) {
          return Promise.reject(new Error('两次输入的密码不一致'))
        }
        return Promise.resolve()
      },
      trigger: 'blur'
    }
  ]
}

/**
 * 处理用户登录
 * 验证用户凭据，登录成功后跳转到首页
 */
async function handleLogin() {
  loading.value = true
  errorMessage.value = ''
  loginSuccessMessage.value = ''
  
  try {
    const result = await authStore.userLogin(loginForm)
    if (result.success) {
      // 登录成功，显示成功提示并立即跳转到首页
      loginSuccessMessage.value = result.message || '登录成功！'
      router.push('/')
    } else {
      // 登录失败，显示错误信息
      errorMessage.value = result.message
    }
  } catch (error: any) {
    // 网络错误或其他异常，使用后端返回的错误信息
    errorMessage.value = error.response?.data?.message || error.message || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}

/**
 * 处理用户注册
 * 创建新用户账户，注册成功后切换到登录标签页
 */
async function handleRegister() {
  loading.value = true
  errorMessage.value = ''
  
  try {
    const result = await authStore.userRegister({
      user_name: registerForm.user_name,
      password: registerForm.password
    })
    console.log('Register result:', result) // 调试信息
    if (result.success) {
      // 注册成功，显示成功提示并切换到登录标签页
      registerSuccessMessage.value = result.message
      errorMessage.value = ''
      // 清空注册表单
      registerForm.user_name = ''
      registerForm.password = ''
      registerForm.confirmPassword = ''
      // 立即切换到登录标签页
      activeTab.value = 'login'
    } else {
      // 注册失败，显示错误信息
      errorMessage.value = result.message
    }
  } catch (error: any) {
    console.error('Register error in component:', error) // 调试信息
    // 网络错误或其他异常，使用后端返回的错误信息
    errorMessage.value = error.response?.data?.message || error.message || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 登录页面主容器样式 */
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

/* 登录卡片样式 */
.login-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  padding: 40px;
  width: 100%;
  max-width: 400px;
}

/* 页面标题区域样式 */
.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-title {
  font-size: 32px;
  font-weight: bold;
  color: #1890ff;
  margin: 0 0 8px 0;
}

.login-subtitle {
  color: #666;
  margin: 0;
  font-size: 16px;
}

/* 标签页样式 */
.login-tabs {
  margin-bottom: 24px;
}

/* 表单样式 */
.login-form {
  margin-top: 24px;
}

/* 提交按钮样式 */
.submit-button {
  height: 48px;
  font-size: 16px;
  font-weight: 500;
}

/* 成功提示样式 */
.success-alert {
  margin-top: 16px;
}

/* 错误提示样式 */
.error-alert {
  margin-top: 16px;
}

/* Ant Design Vue 样式覆盖 */
:deep(.ant-tabs-tab) {
  font-size: 16px;
  font-weight: 500;
}

:deep(.ant-form-item-label > label) {
  font-weight: 500;
  color: #333;
}

:deep(.ant-input) {
  border-radius: 8px;
}

:deep(.ant-btn-primary) {
  border-radius: 8px;
  background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%);
  border: none;
}

:deep(.ant-btn-primary:hover) {
  background: linear-gradient(135deg, #40a9ff 0%, #69c0ff 100%);
}
</style>
