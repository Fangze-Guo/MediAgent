/**
 * 任务管理API接口
 */
import { get, del } from '@/utils/request'

/**
 * 通用响应接口
 */
export interface BaseResponse<T = any> {
  /** 响应码 */
  code: number
  /** 响应数据 */
  data: T
  /** 响应消息 */
  message: string
}

/**
 * 任务信息接口
 */
export interface TaskInfo {
  /** 任务ID */
  task_uid: string
  /** 总步骤数 */
  total_steps: number
  /** 任务状态: queued, running, succeeded, failed */
  status: string
  /** 当前步骤编号 */
  current_step_number?: number
  /** 当前步骤ID */
  current_step_uid?: string
  /** 最后完成的步骤 */
  last_completed_step?: number
  /** 失败的步骤编号 */
  failed_step_number?: number
  /** 失败的步骤ID */
  failed_step_uid?: string
  /** 用户ID */
  user_uid: number
  /** 请求JSON */
  request_json: string
  /** 进度百分比 */
  progress_percentage: number
  /** 状态文本 */
  status_text: string
  /** 状态颜色 */
  status_color: string
}

/**
 * 任务统计信息接口
 */
export interface TaskStatistics {
  /** 总任务数 */
  total: number
  /** 排队中的任务数 */
  queued: number
  /** 执行中的任务数 */
  running: number
  /** 已完成的任务数 */
  succeeded: number
  /** 已失败的任务数 */
  failed: number
}

/**
 * 获取任务列表
 * @param status 任务状态过滤（可选）
 * @param limit 返回记录数
 * @param offset 偏移量
 */
export const getTaskList = async (
  status?: string,
  limit: number = 100,
  offset: number = 0
): Promise<BaseResponse<TaskInfo[]>> => {
  const params: any = { limit, offset }
  if (status) {
    params.status = status
  }
  const response = await get('/tasks/list', { params })
  return response.data as BaseResponse<TaskInfo[]>
}

/**
 * 获取任务详情
 * @param taskUid 任务ID
 */
export const getTaskDetail = async (taskUid: string): Promise<BaseResponse<TaskInfo>> => {
  const response = await get(`/tasks/detail/${taskUid}`)
  return response.data as BaseResponse<TaskInfo>
}

/**
 * 获取任务统计信息
 */
export const getTaskStatistics = async (): Promise<BaseResponse<TaskStatistics>> => {
  const response = await get('/tasks/statistics')
  return response.data as BaseResponse<TaskStatistics>
}

export const deleteTask = async (taskUid: string): Promise<BaseResponse<boolean>> => {
  const response = await del(`/tasks/delete/${taskUid}`)
  return response.data as BaseResponse<boolean>
}

