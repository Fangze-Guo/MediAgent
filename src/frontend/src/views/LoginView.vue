<template>
  <!-- 登录页面主容器 -->
  <div class="login-container">
    <div class="login-wrapper">
      <!-- 左侧欢迎区域 -->
      <div class="welcome-section">
        <div class="welcome-content">
          <!-- Logo 区域 -->
          <div class="logo-section">
            <div class="logo-icon">
              <img src="../../public/MediAgent.png" alt="Logo" style="width: 60px; height: 60px" />
            </div>

            <h1 class="logo-text">MediAgent</h1>
          </div>

          <!-- 欢迎文字 -->
          <div class="welcome-text">
            <h2 class="welcome-title">{{ t('views_LoginView.welcome') }}</h2>
            <p class="welcome-subtitle">{{ t('views_LoginView.welcomeSubtitle') }}</p>
          </div>

          <!-- 装饰插图 -->
          <div class="illustration">
            <svg viewBox="0 0 400 300" class="welcome-svg">
              <!-- 医疗图标插图 -->
              <circle cx="200" cy="150" r="80" fill="#e6f7ff" opacity="0.5" />
              <circle cx="200" cy="150" r="60" fill="#bae7ff" opacity="0.6" />
              <path d="M200 110v80M160 150h80" stroke="#1890ff" stroke-width="4" stroke-linecap="round" />
              <circle cx="180" cy="120" r="15" fill="#52c41a" opacity="0.7" />
              <circle cx="220" cy="180" r="12" fill="#fa541c" opacity="0.7" />
              <circle cx="160" cy="180" r="10" fill="#722ed1" opacity="0.7" />
            </svg>
          </div>
        </div>
      </div>

      <!-- 右侧表单区域 -->
      <div class="form-section">
        <div class="form-container">
          <!-- 表单头部 -->
          <div class="form-header">
            <h2 class="form-title">{{ activeTab === 'login' ? t('views_LoginView.login') : t('views_LoginView.register') }}</h2>
            <p class="form-subtitle">{{
                activeTab === 'login' ? t('views_LoginView.loginSubtitle') : t('views_LoginView.registerSubtitle')
              }}</p>
          </div>

          <!-- 标签切换 -->
          <div class="tab-switcher">
            <button
                :class="['tab-button', { active: activeTab === 'login' }]"
                @click="activeTab = 'login'"
            >
              {{ t('views_LoginView.login') }}
            </button>
            <button
                :class="['tab-button', { active: activeTab === 'register' }]"
                @click="activeTab = 'register'"
            >
              {{ t('views_LoginView.register') }}
            </button>
          </div>

          <!-- 登录表单 -->
          <a-form
              v-if="activeTab === 'login'"
              :model="loginForm"
              :rules="loginRules"
              @finish="handleLogin"
              layout="vertical"
              class="auth-form"
          >

            <!-- 用户名输入框 -->
            <a-form-item name="user_name" class="form-item">
              <a-input
                  v-model:value="loginForm.user_name"
                  :placeholder="t('views_LoginView.usernamePlaceholder')"
                  size="large"
                  :disabled="loading"
                  class="form-input"
              >
                <template #prefix>
                  <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                    <path
                        d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                  </svg>
                </template>
              </a-input>
            </a-form-item>

            <!-- 密码输入框 -->
            <a-form-item name="password" class="form-item">
              <a-input-password
                  v-model:value="loginForm.password"
                  :placeholder="t('views_LoginView.passwordPlaceholder')"
                  size="large"
                  :disabled="loading"
                  class="form-input"
              >
                <template #prefix>
                  <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                    <path
                        d="M18,8h-1V6c0-2.76-2.24-5-5-5S7,3.24,7,6v2H6c-1.1,0-2,0.9-2,2v10c0,1.1,0.9,2,2,2h12c1.1,0,2-0.9,2-2V10C20,8.9,19.1,8,18,8z M12,17c-1.1,0-2-0.9-2-2s0.9-2,2-2s2,0.9,2,2S13.1,17,12,17z M15.1,8H8.9V6c0-1.71,1.39-3.1,3.1-3.1s3.1,1.39,3.1,3.1V8z" />
                  </svg>
                </template>
              </a-input-password>
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
                {{ loading ? t('common.loading') : t('views_LoginView.loginButton').toUpperCase() }}
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
              class="auth-form"
          >
            <!-- 用户名输入框 -->
            <a-form-item name="user_name" class="form-item">
              <a-input
                  v-model:value="registerForm.user_name"
                  :placeholder="t('views_LoginView.usernamePlaceholder')"
                  size="large"
                  :disabled="loading"
                  class="form-input"
              >
                <template #prefix>
                  <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                    <path
                        d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                  </svg>
                </template>
              </a-input>
            </a-form-item>

            <!-- 密码输入框 -->
            <a-form-item name="password" class="form-item">
              <a-input-password
                  v-model:value="registerForm.password"
                  :placeholder="t('views_LoginView.passwordPlaceholder')"
                  size="large"
                  :disabled="loading"
                  class="form-input"
              >
                <template #prefix>
                  <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                    <path
                        d="M18,8h-1V6c0-2.76-2.24-5-5-5S7,3.24,7,6v2H6c-1.1,0-2,0.9-2,2v10c0,1.1,0.9,2,2,2h12c1.1,0,2-0.9,2-2V10C20,8.9,19.1,8,18,8z M12,17c-1.1,0-2-0.9-2-2s0.9-2,2-2s2,0.9,2,2S13.1,17,12,17z M15.1,8H8.9V6c0-1.71,1.39-3.1,3.1-3.1s3.1,1.39,3.1,3.1V8z" />
                  </svg>
                </template>
              </a-input-password>
            </a-form-item>

            <!-- 确认密码输入框 -->
            <a-form-item name="confirmPassword" class="form-item">
              <a-input-password
                  v-model:value="registerForm.confirmPassword"
                  :placeholder="t('views_LoginView.confirmPasswordPlaceholder')"
                  size="large"
                  :disabled="loading"
                  class="form-input"
              >
                <template #prefix>
                  <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                    <path
                        d="M18,8h-1V6c0-2.76-2.24-5-5-5S7,3.24,7,6v2H6c-1.1,0-2,0.9-2,2v10c0,1.1,0.9,2,2,2h12c1.1,0,2-0.9,2-2V10C20,8.9,19.1,8,18,8z M12,17c-1.1,0-2-0.9-2-2s0.9-2,2-2s2,0.9,2,2S13.1,17,12,17z M15.1,8H8.9V6c0-1.71,1.39-3.1,3.1-3.1s3.1,1.39,3.1,3.1V8z" />
                  </svg>
                </template>
              </a-input-password>
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
                {{ loading ? t('common.loading') : t('views_LoginView.registerButton').toUpperCase() }}
              </a-button>
            </a-form-item>
          </a-form>

          <!-- 社交登录 -->
          <div class="social-login">
            <div class="divider">
              <span></span>
            </div>
            <div class="social-subtitle">{{ t('views_LoginView.orLoginWith') }}</div>
            <div class="social-buttons">
              <button class="social-btn facebook" @click="">
                <svg viewBox="0 0 24 24" width="20" height="20">
                  <path fill="currentColor"
                        d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                </svg>
              </button>
              <button class="social-btn twitter" @click="">
                <svg viewBox="0 0 24 24" width="20" height="20">
                  <path fill="currentColor"
                        d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z" />
                </svg>
              </button>
              <button class="social-btn google" @click="">
                <svg viewBox="0 0 24 24" width="20" height="20">
                  <path fill="currentColor"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="currentColor"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="currentColor"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="currentColor"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 全局提示信息 -->
    <div class="alert-container">
      <a-alert
          v-if="registerSuccessMessage"
          :message="registerSuccessMessage"
          type="success"
          show-icon
          closable
          @close="registerSuccessMessage = ''"
          class="alert-message success-alert"
      />
      <a-alert
          v-if="loginSuccessMessage"
          :message="loginSuccessMessage"
          type="success"
          show-icon
          closable
          @close="loginSuccessMessage = ''"
          class="alert-message success-alert"
      />
      <a-alert
          v-if="errorMessage"
          :message="errorMessage"
          type="error"
          show-icon
          closable
          @close="errorMessage = ''"
          class="alert-message error-alert"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { useI18n } from 'vue-i18n'
import type { LoginRequest, RegisterRequest } from '@/types/auth'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()

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
const loginRules = computed(() => ({
  user_name: [
    {required: true, message: t('views_LoginView.rules.usernameRequired'), trigger: 'blur'},
    {min: 3, max: 20, message: t('views_LoginView.rules.usernameLength'), trigger: 'blur'}
  ],
  password: [
    {required: true, message: t('views_LoginView.rules.passwordRequired'), trigger: 'blur'},
    {min: 6, message: t('views_LoginView.rules.passwordLength'), trigger: 'blur'}
  ]
}))

// 注册表单验证规则
const registerRules = computed(() => ({
  user_name: [
    {required: true, message: t('views_LoginView.rules.usernameRequired'), trigger: 'blur'},
    {min: 3, max: 20, message: t('views_LoginView.rules.usernameLength'), trigger: 'blur'}
  ],
  password: [
    {required: true, message: t('views_LoginView.rules.passwordRequired'), trigger: 'blur'},
    {min: 6, message: t('views_LoginView.rules.passwordLength'), trigger: 'blur'}
  ],
  confirmPassword: [
    {required: true, message: t('views_LoginView.rules.confirmPasswordRequired'), trigger: 'blur'},
    {
      validator: (_: any, value: string) => {
        if (value !== registerForm.password) {
          return Promise.reject(new Error(t('views_LoginView.rules.passwordMismatch')))
        }
        return Promise.resolve()
      },
      trigger: 'blur'
    }
  ]
}))

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
      loginSuccessMessage.value = result.message || t('views_LoginView.messages.loginSuccess')
      await router.push('/')
    } else {
      // 登录失败，显示错误信息
      errorMessage.value = result.message
    }
  } catch (error: any) {
    // 网络错误或其他异常，使用后端返回的错误信息
    errorMessage.value = error.response?.data?.message || error.message || t('views_LoginView.messages.loginFailed')
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
    errorMessage.value = error.response?.data?.message || error.message || t('views_LoginView.messages.registerFailed')
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
  background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 50%, #10b981 100%);
  padding: 20px;
  position: relative;
}

/* 登录主体包装器 */
.login-wrapper {
  display: flex;
  background: white;
  border-radius: 24px;
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  max-width: 1000px;
  width: 100%;
  min-height: 600px;
}

/* 左侧欢迎区域 */
.welcome-section {
  flex: 1;
  background: linear-gradient(135deg, #1890ff 0%, #40a9ff 50%, #69c0ff 100%);
  padding: 60px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  color: white;
  position: relative;
  overflow: hidden;
}

.welcome-section::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="2" fill="white" opacity="0.1"/></svg>') repeat;
  animation: float 20s linear infinite;
}

@keyframes float {
  0% {
    transform: translate(0, 0);
  }
  100% {
    transform: translate(-50px, -50px);
  }
}

.welcome-content {
  position: relative;
  z-index: 1;
}

.logo-section {
  display: flex;
  align-items: center;
  margin-bottom: 40px;
}

.logo-icon {
  background: rgba(255, 255, 255, 0.2);
  padding: 12px;
  border-radius: 16px;
  margin-right: 16px;
  color: white;
}

.logo-text {
  font-size: 32px;
  font-weight: 700;
  margin: 0;
  color: white;
}

.welcome-text {
  margin-bottom: 40px;
}

.welcome-title {
  font-size: 48px;
  font-weight: 800;
  margin: 0 0 16px 0;
  color: white;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.welcome-subtitle {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
  line-height: 1.6;
}

.illustration {
  display: flex;
  justify-content: center;
  margin-top: 40px;
}

.welcome-svg {
  width: 100%;
  max-width: 300px;
  height: auto;
}

/* 右侧表单区域 */
.form-section {
  flex: 1;
  padding: 60px 50px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.form-container {
  max-width: 400px;
  width: 100%;
}

.form-header {
  text-align: center;
  margin-bottom: 40px;
}

.form-title {
  font-size: 32px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.form-subtitle {
  font-size: 16px;
  color: #6b7280;
  margin: 0;
}

/* 标签切换器 */
.tab-switcher {
  display: flex;
  background: #f3f4f6;
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 32px;
}

.tab-button {
  flex: 1;
  padding: 12px 16px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #6b7280;
}

.tab-button.active {
  background: white;
  color: #1890ff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 表单样式 */
.auth-form {
  margin-bottom: 32px;
}

.form-item {
  margin-bottom: 20px;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.remember-checkbox {
  font-size: 14px;
  color: #6b7280;
}

.forgot-link {
  font-size: 14px;
  color: #1890ff;
  text-decoration: none;
  font-weight: 500;
}

.forgot-link:hover {
  text-decoration: underline;
}

/* 社交登录 */
.social-login {
  text-align: center;
}

.divider {
  position: relative;
  margin: 24px 0;
  text-align: center;
}

.divider::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  background: #e5e7eb;
}

.divider span {
  background: white;
  padding: 0 16px;
  color: #9ca3af;
  font-size: 14px;
}

.social-subtitle {
  font-size: 14px;
  color: #9ca3af;
  margin-bottom: 16px;
}

.social-buttons {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.social-btn {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  border: 2px solid #e5e7eb;
  background: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.social-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.social-btn.facebook {
  color: #4267B2;
}

.social-btn.facebook:hover {
  border-color: #4267B2;
  background: #f0f4ff;
}

.social-btn.twitter {
  color: #1DA1F2;
}

.social-btn.twitter:hover {
  border-color: #1DA1F2;
  background: #f0f9ff;
}

.social-btn.google {
  color: #DB4437;
}

.social-btn.google:hover {
  border-color: #DB4437;
  background: #fff5f5;
}

/* 提示信息 */
.alert-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
  max-width: 400px;
}

.alert-message {
  margin-bottom: 12px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* Ant Design 样式覆盖 */
:deep(.ant-input) {
  border-radius: 12px;
  border: 2px solid #e5e7eb;
  padding: 12px 16px;
  height: auto;
  font-size: 16px;
  transition: all 0.3s ease;
}

:deep(.ant-input:focus) {
  border-color: #1890ff;
  box-shadow: 0 0 0 3px rgba(24, 144, 255, 0.1);
}

:deep(.ant-input-affix-wrapper) {
  border-radius: 12px;
  border: 2px solid #e5e7eb;
  padding: 12px 16px;
  transition: all 0.3s ease;
}

:deep(.ant-input-affix-wrapper:focus-within) {
  border-color: #1890ff;
  box-shadow: 0 0 0 3px rgba(24, 144, 255, 0.1);
}

:deep(.ant-input-prefix) {
  margin-right: 12px;
  color: #9ca3af;
}

:deep(.ant-btn-primary) {
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%);
  border: none;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
  transition: all 0.3s ease;
}

:deep(.ant-btn-primary:hover) {
  background: linear-gradient(135deg, #40a9ff 0%, #69c0ff 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(24, 144, 255, 0.4);
}

:deep(.ant-checkbox-wrapper) {
  font-size: 14px;
}

:deep(.ant-checkbox-checked .ant-checkbox-inner) {
  background-color: #1890ff;
  border-color: #1890ff;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .login-wrapper {
    flex-direction: column;
    max-width: 400px;
    border-radius: 16px;
  }

  .welcome-section {
    padding: 40px 30px;
    min-height: 200px;
  }

  .welcome-title {
    font-size: 32px;
  }

  .form-section {
    padding: 40px 30px;
  }

  .form-title {
    font-size: 24px;
  }
}
</style>
