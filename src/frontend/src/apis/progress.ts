/**
 * 进度相关API接口
 */
import { request } from '@/utils/request'

// 进度更新请求接口
export interface ProgressUpdateRequest {
  task_id: string
  progress: number
  status: string
  message?: string
  details?: Record<string, any>
}

// 进度响应接口
export interface ProgressResponse {
  task_id: string
  progress: number
  status: string
  message?: string
  details?: Record<string, any>
  timestamp: string
  completed: boolean
}

// 更新任务进度
export const updateProgress = async (update: ProgressUpdateRequest) => {
  const response = await request({
    method: 'POST',
    url: '/api/progress/update',
    data: update
  })
  return response.data
}

// 获取任务进度
export const getProgress = async (taskId: string) => {
  const response = await request({
    method: 'GET',
    url: `/api/progress/${taskId}`
  })
  return response.data
}

// 清除任务进度
export const clearProgress = async (taskId: string) => {
  const response = await request({
    method: 'DELETE',
    url: `/api/progress/${taskId}`
  })
  return response.data
}

// 列出所有任务进度
export const listProgress = async () => {
  const response = await request({
    method: 'GET',
    url: '/api/progress/'
  })
  return response.data
}
