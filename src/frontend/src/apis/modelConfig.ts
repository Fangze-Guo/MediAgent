/**
 * 模型配置管理API
 */
import axios from 'axios'

const API_BASE = `${(import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'}/models`

// ==================== 数据类型定义 ====================

export interface ModelConfig {
  id: string
  name: string
  provider: string
  description: string
  category: string
  capabilities: string[]
  max_tokens: number
  input_cost_per_1k: number
  output_cost_per_1k: number
  enabled: boolean
  config: Record<string, any>
  requirements: Record<string, any>
}

export interface ModelCreateRequest {
  id: string
  name: string
  provider: string
  description: string
  category: string
  capabilities: string[]
  max_tokens: number
  input_cost_per_1k: number
  output_cost_per_1k: number
  config: Record<string, any>
  requirements: Record<string, any>
}

export interface ModelUpdateRequest {
  name?: string
  provider?: string
  description?: string
  category?: string
  capabilities?: string[]
  max_tokens?: number
  input_cost_per_1k?: number
  output_cost_per_1k?: number
  enabled?: boolean
  config?: Record<string, any>
  requirements?: Record<string, any>
}

export interface UserModelSelection {
  current_model_id: string
  api_key?: string
  base_url?: string
}

export interface ModelCategory {
  name: string
  description: string
  icon: string
}

export interface ModelProvider {
  name: string
  website: string
  api_docs: string
  avatar?: string
}

// ==================== 管理员API ====================

/**
 * 获取所有模型配置（管理员）
 */
export const getAllModels = async () => {
  const response = await axios.get(`${API_BASE}/admin/models`)
  return response.data
}

/**
 * 创建新模型（管理员）
 */
export const createModel = async (modelData: ModelCreateRequest) => {
  const response = await axios.post(`${API_BASE}/admin/models`, modelData)
  return response.data
}

/**
 * 更新模型配置（管理员）
 */
export const updateModel = async (modelId: string, modelData: ModelUpdateRequest) => {
  const response = await axios.put(`${API_BASE}/admin/models/${modelId}`, modelData)
  return response.data
}

/**
 * 删除模型（管理员）
 */
export const deleteModel = async (modelId: string) => {
  const response = await axios.delete(`${API_BASE}/admin/models/${modelId}`)
  return response.data
}

/**
 * 切换模型启用状态（管理员）
 */
export const toggleModelStatus = async (modelId: string) => {
  const response = await axios.put(`${API_BASE}/admin/models/${modelId}/toggle`)
  return response.data
}

// ==================== 用户API ====================

/**
 * 获取用户可用的模型列表
 */
export const getAvailableModels = async () => {
  const response = await axios.get(`${API_BASE}/configs`)
  return response.data
}

/**
 * 获取用户当前的模型选择
 */
export const getCurrentSelection = async () => {
  const response = await axios.get(`${API_BASE}/user/current-selection`)
  return response.data
}

/**
 * 用户选择模型
 */
export const selectModel = async (selection: UserModelSelection) => {
  const response = await axios.post(`${API_BASE}/user/select-model`, selection)
  return response.data
}

/**
 * 获取模型分类
 */
export const getCategories = async (): Promise<Record<string, ModelCategory>> => {
  const response = await axios.get(`${API_BASE}/categories`)
  return response.data
}

/**
 * 获取模型提供商
 */
export const getProviders = async (): Promise<Record<string, ModelProvider>> => {
  const response = await axios.get(`${API_BASE}/providers`)
  return response.data
}

/**
 * 删除用户模型配置
 */
export const removeUserModel = async (modelId: string) => {
  const response = await axios.delete(`${API_BASE}/configs/${modelId}`)
  return response.data
}

/**
 * 检查模型状态
 */
export const checkModelStatus = async (modelId: string) => {
  const response = await axios.get(`${API_BASE}/user/model-status/${modelId}`)
  return response.data
}
