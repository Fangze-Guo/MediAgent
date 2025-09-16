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
