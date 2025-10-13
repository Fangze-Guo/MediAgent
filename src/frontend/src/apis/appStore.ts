/**
 * App Store相关API接口
 * 提供应用商店的交互功能
 */
import { get, post, put, del } from '@/utils/request'

/**
 * 应用信息接口
 */
export interface AppInfo {
  id: string
  name: string
  category: string
  description: string
  full_description?: string
  features?: string  // 功能特点 (Markdown格式)
  icon: string
  version: string
  author: string
  downloads: number
  rating: number
  installed: boolean
  featured: boolean  // 是否精选
  tags: string[]
  created_at?: string  // 创建时间
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
  created_at: string  // 与后端字段名保持一致
  isHelpful?: boolean  // 前端状态，用于标记用户是否点了"有用"
  user_liked?: boolean // 后端返回的用户点赞状态
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
 * 获取精选应用列表
 * @param limit 返回数量限制
 * @returns Promise<AppInfo[]>
 */
export async function getFeaturedApps(limit: number = 6): Promise<AppInfo[]> {
  const response = await get<BaseResponse<AppInfo[]>>(`/app-store/featured?limit=${limit}`)
  return response.data.data
}

/**
 * 获取应用的评论列表
 * @param appId 应用ID
 * @param userId 用户ID（可选，用于获取用户点赞状态）
 * @returns Promise<ReviewsData>
 */
export async function getAppReviews(appId: string, userId?: number): Promise<ReviewsData> {
  const url = userId ? `/app-store/apps/${appId}/reviews?user_id=${userId}` : `/app-store/apps/${appId}/reviews`
  const response = await get<BaseResponse<ReviewsData>>(url)
  return response.data.data
}

/**
 * 添加评论请求接口
 */
export interface AddReviewRequest {
  user_name: string
  rating: number
  comment: string
}

/**
 * 添加应用评论
 * @param appId 应用ID
 * @param reviewData 评论数据
 * @returns Promise<{message: string}>
 */
export async function addAppReview(appId: string, reviewData: AddReviewRequest): Promise<{message: string}> {
  const response = await post<BaseResponse<{message: string}>>(`/app-store/apps/${appId}/reviews`, reviewData)
  return response.data.data
}

/**
 * 更新应用评论
 * @param appId 应用ID
 * @param reviewId 评论ID
 * @param reviewData 评论数据
 * @returns Promise<{message: string}>
 */
export async function updateAppReview(appId: string, reviewId: number, reviewData: AddReviewRequest): Promise<{message: string}> {
  const response = await put<BaseResponse<{message: string}>>(`/app-store/apps/${appId}/reviews/${reviewId}`, reviewData)
  return response.data.data
}

/**
 * 删除应用评论
 * @param appId 应用ID
 * @param reviewId 评论ID
 * @param userName 用户名
 * @returns Promise<{message: string}>
 */
export async function deleteAppReview(appId: string, reviewId: number, userName: string): Promise<{message: string}> {
  const response = await del<BaseResponse<{message: string}>>(`/app-store/apps/${appId}/reviews/${reviewId}?user_name=${encodeURIComponent(userName)}`)
  return response.data.data
}

/**
 * 切换评论的点赞状态
 * @param appId 应用ID
 * @param reviewId 评论ID
 * @param userId 用户ID
 * @returns Promise<{helpful_count: number, user_liked: boolean}>
 */
export async function toggleReviewHelpful(appId: string, reviewId: number, userId: number): Promise<{helpful_count: number, user_liked: boolean}> {
  const response = await post<BaseResponse<{helpful_count: number, user_liked: boolean}>>(`/app-store/apps/${appId}/reviews/${reviewId}/helpful`, { user_id: userId })
  return response.data.data
}

/**
 * 应用商店统计信息接口
 */
export interface AppStoreStats {
  total_apps: number
  total_downloads: number
  total_reviews: number
  category_stats: Array<{
    category: string
    count: number
  }>
}

/**
 * 获取应用商店统计信息
 * @returns Promise<AppStoreStats>
 */
export async function getAppStoreStats(): Promise<AppStoreStats> {
  const response = await get<BaseResponse<AppStoreStats>>('/app-store/stats')
  return response.data.data
}

/**
 * 更新应用功能特点
 * @param appId 应用ID
 * @param features 功能特点内容 (Markdown格式)
 * @returns Promise<{message: string}>
 */
export async function updateAppFeatures(appId: string, features: string): Promise<{message: string}> {
  const response = await put<BaseResponse<{message: string}>>(`/app-store/apps/${appId}/features`, { features })
  return response.data.data
}

