/**
 * App Store相关API接口
 * 提供应用商店的交互功能
 */
import { get, post } from '@/utils/request'

/**
 * 应用信息接口
 */
export interface AppInfo {
  id: string
  name: string
  category: string
  description: string
  icon: string
  version: string
  author: string
  downloads: number
  rating: number
  installed: boolean
  tags: string[]
  fullDescription?: string
}

/**
 * 评论信息接口
 */
export interface Review {
  id: number
  app_id: string
  user_name: string
  rating: number
  comment: string
  helpful_count: number
  date: string
}

/**
 * 评论数据响应接口
 */
export interface ReviewsData {
  reviews: Review[]
  total: number
  average_rating: number
  rating_distribution: {
    [key: string]: number
  }
}

/**
 * 后端响应结构
 */
interface BaseResponse<T> {
  code: number
  data: T
  message: string
}

/**
 * 获取应用列表
 * @param category 分类过滤
 * @param search 搜索关键词
 * @returns Promise<AppInfo[]>
 */
export async function getApps(category?: string, search?: string) {
  const params: Record<string, string> = {}
  if (category) params.category = category
  if (search) params.search = search
  
  const response = await get<BaseResponse<AppInfo[]>>('/app-store/apps', { params })
  return response.data.data
}

/**
 * 获取应用详情
 * @param appId 应用ID
 * @returns Promise<AppInfo>
 */
export async function getAppDetail(appId: string): Promise<AppInfo> {
  const response = await get<BaseResponse<AppInfo>>(`/app-store/apps/${appId}`)
  return response.data.data
}

/**
 * 获取所有分类
 * @returns Promise<string[]>
 */
export async function getCategories() {
  const response = await get<BaseResponse<string[]>>('/app-store/categories')
  return response.data.data
}

/**
 * 安装应用
 * @param appId 应用ID
 * @returns Promise<string>
 */
export async function installApp(appId: string) {
  const response = await post<BaseResponse<string>>(`/app-store/apps/${appId}/install`)
  return response.data.data
}

/**
 * 卸载应用
 * @param appId 应用ID
 * @returns Promise<string>
 */
export async function uninstallApp(appId: string) {
  const response = await post<BaseResponse<string>>(`/app-store/apps/${appId}/uninstall`)
  return response.data.data
}

/**
 * 获取应用的评论列表
 * @param appId 应用ID
 * @returns Promise<ReviewsData>
 */
export async function getAppReviews(appId: string): Promise<ReviewsData> {
  const response = await get<BaseResponse<ReviewsData>>(`/app-store/apps/${appId}/reviews`)
  return response.data.data
}

