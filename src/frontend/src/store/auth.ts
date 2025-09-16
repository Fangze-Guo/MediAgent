import { defineStore } from 'pinia'
import { login, register, getUserInfo, updateUserInfo } from '@/apis/auth'

// 类型定义
export interface LoginRequest {
  user_name: string
  password: string
}

export interface RegisterRequest {
  user_name: string
  password: string
}

export interface UserInfo {
  uid: number
  user_name: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as UserInfo | null,
    token: localStorage.getItem('mediagent_token') || null,
    isAuthenticated: false
  }),

  getters: {
    isLoggedIn: (state) => !!state.token && !!state.user,
    currentUser: (state) => state.user
  },

  actions: {
    // 用户登录
    async userLogin(credentials: LoginRequest) {
      try {
        const response = await login(credentials)
        // 检查是否成功：ok为true或者message包含success
        if (response.ok === true || (response.message && response.message.includes('success'))) {
          this.token = response.token || null
          this.isAuthenticated = true
          if (response.token) {
            localStorage.setItem('mediagent_token', response.token)
          }
          
          // 登录成功后获取用户信息
          await this.fetchUserInfo()
          return { success: true, message: response.message }
        } else {
          return { success: false, message: response.message || '登录失败' }
        }
      } catch (error: any) {
        console.error('Login error:', error)
        return { 
          success: false, 
          message: error.response?.data?.message || '登录失败，请检查网络连接' 
        }
      }
    },

    // 用户注册
    async userRegister(userData: RegisterRequest) {
      try {
        const response = await register(userData)
        console.log('Register response:', response) // 调试信息
        console.log('response.ok type:', typeof response.ok, 'value:', response.ok) // 调试信息
        // 检查是否成功：ok为true或者message包含success
        if (response.ok === true || (response.message && response.message.includes('success'))) {
          return { success: true, message: response.message }
        } else {
          return { success: false, message: response.message || '注册失败' }
        }
      } catch (error: any) {
        console.error('Register error:', error)
        return { 
          success: false, 
          message: error.response?.data?.message || '注册失败，请检查网络连接' 
        }
      }
    },

    // 获取用户信息
    async fetchUserInfo() {
      if (!this.token) return null
      
      try {
        const response = await getUserInfo()
        if (response.uid) {
          this.user = {
            uid: response.uid,
            user_name: response.user_name
          }
          return this.user
        }
      } catch (error: any) {
        console.error('Fetch user info error:', error)
        // 如果获取用户信息失败，可能是token过期，清除认证状态
        this.logout()
      }
      return null
    },

    // 更新用户信息
    async updateUser(userData: { user_name?: string; password?: string }) {
      try {
        const response = await updateUserInfo(userData)
        if (response.message) {
          // 如果更新了用户名，更新本地状态
          if (userData.user_name && this.user) {
            this.user.user_name = userData.user_name
          }
          return { success: true, message: response.message }
        } else {
          return { success: false, message: '更新失败' }
        }
      } catch (error: any) {
        console.error('Update user error:', error)
        return { 
          success: false, 
          message: error.response?.data?.message || '更新失败，请检查网络连接' 
        }
      }
    },

    // 登出
    logout() {
      this.user = null
      this.token = null
      this.isAuthenticated = false
      localStorage.removeItem('mediagent_token')
    },

    // 检查认证状态
    async checkAuth() {
      if (this.token) {
        await this.fetchUserInfo()
        this.isAuthenticated = !!this.user
      }
    }
  }
})

// 类型定义
export interface LoginRequest {
  user_name: string
  password: string
}

export interface RegisterRequest {
  user_name: string
  password: string
}

export interface UserInfo {
  uid: number
  user_name: string
}
