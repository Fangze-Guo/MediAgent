import { request } from '@/utils/request'
import type { LoginRequest, RegisterRequest, UserInfo, UpdateUserProfileRequest } from '@/types/auth'

// API 响应类型
interface ApiResponse<T = any> {
  code: number
  message: string
  data?: T
  token?: string
}

// 登录请求
export function login(data: LoginRequest): Promise<ApiResponse> {
  return request({
    url: '/user/login',
    method: 'POST',
    data
  }).then((response: any) => response.data)
}

// 注册请求
export function register(data: RegisterRequest): Promise<ApiResponse> {
  return request({
    url: '/user/register',
    method: 'POST',
    data
  }).then((response: any) => response.data)
}

// 获取用户信息
export function getUserInfo(): Promise<ApiResponse<UserInfo>> {
  return request({
    url: '/user/info',
    method: 'GET'
  }).then((response: any) => response.data)
}

// 更新用户信息
export function updateUserProfile(data: UpdateUserProfileRequest): Promise<ApiResponse<UserInfo>> {
  return request({
    url: '/user/profile',
    method: 'PUT',
    data
  }).then((response: any) => response.data)
}

