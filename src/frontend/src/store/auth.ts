import { defineStore } from 'pinia'
import { login, register, getUserInfo } from '@/apis/auth'

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
  state: () => {
    // 从localStorage恢复用户信息
    const savedUser = localStorage.getItem('mediagent_user')
    const user = savedUser ? JSON.parse(savedUser) : null
    
    return {
      user: user as UserInfo | null,
      token: localStorage.getItem('mediagent_token') || null,
      isAuthenticated: false
    }
  },

  getters: {
    isLoggedIn: (state) => !!state.token, // 只要有token就认为已登录，user会在需要时加载
    currentUser: (state) => state.user
  },

  actions: {
    // 用户登录
    async userLogin(credentials: LoginRequest) {
      try {
        const response = await login(credentials)
        if (response.code === 200) {
          // 从data中获取token
          const token = response.data?.token || response.token || null
          this.token = token
          this.isAuthenticated = true
          if (token) {
            localStorage.setItem('mediagent_token', token)
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
        
        // 检查是否成功：code为200或者message包含success
        if (response.code === 200 || (response.message && response.message.includes('success'))) {
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
        // 检查响应格式并获取用户数据
        const userData = response.data
        if (userData && userData.uid) {
          this.user = {
            uid: userData.uid,
            user_name: userData.user_name
          }
          // 将用户信息保存到localStorage
          localStorage.setItem('mediagent_user', JSON.stringify(this.user))
          return this.user
        }
      } catch (error: any) {
        console.error('Fetch user info error:', error)
        // 如果获取用户信息失败，可能是token过期，清除认证状态
        this.logout()
      }
      return null
    },

    // 登出
    logout() {
      this.user = null
      this.token = null
      this.isAuthenticated = false
      localStorage.removeItem('mediagent_token')
      // 清除所有相关的本地存储
      localStorage.removeItem('mediagent_user')
    },

    // 检查认证状态
    async checkAuth() {
      if (this.token) {
        await this.fetchUserInfo()
        this.isAuthenticated = !!this.user
      }
    },

    // 初始化认证状态
    async initAuth() {
      if (this.token) {
        // 如果已经有用户信息，直接设置认证状态
        if (this.user) {
          this.isAuthenticated = true
          return
        }
        
        // 如果没有用户信息，尝试获取
        try {
          await this.fetchUserInfo()
          this.isAuthenticated = !!this.user
        } catch (error) {
          console.error('Init auth error:', error)
          // 如果初始化失败，清除token
          this.logout()
        }
      }
    }
  }
})
