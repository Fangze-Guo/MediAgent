// 认证相关类型定义

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
  role?: string  // 用户角色：user, admin
  avatar?: string  // 用户头像（Base64）
}

export interface UpdateUserProfileRequest {
  user_name: string
  avatar?: string
}

export interface LoginResponse {
  ok: boolean
  message: string
  token?: string
  code?: string
}

export interface RegisterResponse {
  ok: boolean
  message: string
}

export interface UpdateUserRequest {
  user_name?: string
  password?: string
}

export interface UpdateUserResponse {
  message: string
}
