/**
 * Skills API 接口
 * 从真实的 ~/.claude/skills 目录读取 skill 信息
 */
import { get } from '@/utils/request'

/**
 * 项目信息接口
 */
export interface SkillProject {
  id: string
  name: string
}

/**
 * Skill 信息接口（复用 AppInfo 结构以保持前端兼容）
 */
export interface SkillInfo {
  id: string
  name: string
  category: string
  description: string
  full_description?: string
  features?: string
  icon: string
  version: string
  author: string
  downloads: number
  rating: number
  installed: boolean
  featured: boolean
  tags: string[]
  created_at?: string
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
 * 获取 skill 列表
 * @param category 分类过滤
 * @param search 搜索关键词
 * @returns Promise<SkillInfo[]>
 */
export async function getSkills(category?: string, search?: string, projectId?: string): Promise<SkillInfo[]> {
  const params: Record<string, string> = {}
  if (category) params.category = category
  if (search) params.search = search
  if (projectId) params.project_id = projectId
  
  const response = await get<BaseResponse<SkillInfo[]>>('/skills/list', { params })
  return response.data.data
}

/**
 * 获取 skill 详情
 * @param skillId skill ID
 * @returns Promise<SkillInfo>
 */
export async function getSkillDetail(skillId: string, projectId?: string): Promise<SkillInfo> {
  const params: Record<string, string> = {}
  if (projectId) params.project_id = projectId
  const response = await get<BaseResponse<SkillInfo>>(`/skills/detail/${skillId}`, { params })
  return response.data.data
}

/**
 * 获取所有分类
 * @returns Promise<string[]>
 */
export async function getSkillCategories(projectId?: string): Promise<string[]> {
  const params: Record<string, string> = {}
  if (projectId) params.project_id = projectId
  const response = await get<BaseResponse<string[]>>('/skills/categories', { params })
  return response.data.data
}

/**
 * 文件树节点接口
 */
export interface FileTreeNode {
  name: string
  type: 'file' | 'directory'
  path: string
  size?: number
  children?: FileTreeNode[]
}

/**
 * 文件内容接口
 */
export interface FileContent {
  content: string
  encoding: string
  size: number
  is_binary: boolean
}

/**
 * 获取 skill 的文件树结构
 * @param skillId skill ID
 * @returns Promise<FileTreeNode[]>
 */
export async function getSkillFiles(skillId: string, projectId?: string): Promise<FileTreeNode[]> {
  const params: Record<string, string> = {}
  if (projectId) params.project_id = projectId
  const response = await get<BaseResponse<FileTreeNode[]>>(`/skills/files/${skillId}`, { params })
  return response.data.data
}

/**
 * 获取 skill 中某个文件的内容
 * @param skillId skill ID
 * @param filePath 文件相对路径
 * @returns Promise<FileContent>
 */
export async function getSkillFileContent(skillId: string, filePath: string, projectId?: string): Promise<FileContent> {
  const params: Record<string, string> = { path: filePath }
  if (projectId) params.project_id = projectId
  const response = await get<BaseResponse<FileContent>>(`/skills/file-content/${skillId}`, { params })
  return response.data.data
}

/**
 * 获取有 skills 的项目列表
 */
export async function getSkillProjects(): Promise<SkillProject[]> {
  const response = await get<BaseResponse<SkillProject[]>>('/skills/projects')
  return response.data.data
}
