/**
 * 临床智能体管理 API
 */
import { get, post, del } from '@/utils/request'

interface BaseResponse<T> {
  code: number
  data: T
  message: string
}

export interface ClinicalAgent {
  agent_id: string
  name: string
  description: string
  system_prompt: string
  base_dir: string
  user_id: number | null
  created_at: string
  updated_at: string
}

export interface CreateAgentParams {
  name: string
  description?: string
  system_prompt?: string
}

/**
 * 获取全部临床智能体列表
 */
export async function listClinicalAgents(): Promise<BaseResponse<ClinicalAgent[]>> {
  const response = await get<BaseResponse<ClinicalAgent[]>>('/clinical-agents/list')
  return response.data
}

/**
 * 创建临床智能体
 */
export async function createClinicalAgent(params: CreateAgentParams): Promise<BaseResponse<ClinicalAgent>> {
  const response = await post<BaseResponse<ClinicalAgent>>('/clinical-agents/create', params)
  return response.data
}

/**
 * 删除临床智能体
 */
export async function deleteClinicalAgent(agentId: string): Promise<BaseResponse<boolean>> {
  const response = await del<BaseResponse<boolean>>(`/clinical-agents/${agentId}`)
  return response.data
}

/**
 * 获取已安装的 Skill 列表
 */
export async function listInstalledSkills(agentId: string): Promise<BaseResponse<string[]>> {
  const response = await get<BaseResponse<string[]>>(`/clinical-agents/${agentId}/skills`)
  return response.data
}

/**
 * 安装 Skill
 */
export async function installSkill(agentId: string, skillSlug: string): Promise<BaseResponse<boolean>> {
  const response = await post<BaseResponse<boolean>>(`/clinical-agents/${agentId}/skills/${skillSlug}/install`, {})
  return response.data
}

/**
 * 卸载 Skill
 */
export async function uninstallSkill(agentId: string, skillSlug: string): Promise<BaseResponse<boolean>> {
  const response = await del<BaseResponse<boolean>>(`/clinical-agents/${agentId}/skills/${skillSlug}`)
  return response.data
}
