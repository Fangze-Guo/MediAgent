/**
 * Skills API 接口
 * 从真实的 ~/.claude/skills 目录读取 skill 信息
 */
import { get, post, del } from '@/utils/request'

/**
 * 项目信息接口
 */
export interface SkillProject {
  id: string
  name: string
}

/**
 * Skill 信息接口
 */
export interface SkillInfo {
  id: string
  name: string
  type: string
  description: string
  full_description?: string
  features?: string
  version: string
  author: string
  downloads: number
  rating: number
  installed: boolean
  featured: boolean
  tags: string[]
  created_at?: string
  skill_level?: 'plain_claude_skill' | 'patient_skill' | 'pipeline_ready' | 'invalid'
  valid_patient_skill?: boolean
  pipeline_ready?: boolean
  global_skill_level?: 'plain_claude_skill' | 'patient_skill' | 'pipeline_ready' | 'invalid'
  global_valid_patient_skill?: boolean
  global_pipeline_ready?: boolean
  global_version?: string
  installed_skill_level?: 'plain_claude_skill' | 'patient_skill' | 'pipeline_ready' | 'invalid' | null
  installed_valid_patient_skill?: boolean | null
  installed_pipeline_ready?: boolean | null
  installed_version?: string | null
  update_available?: boolean
  validation?: SkillValidationResult
}

export interface SkillValidationResult {
  skill_dir: string
  installable: boolean
  skill_level: 'plain_claude_skill' | 'patient_skill' | 'pipeline_ready' | 'invalid'
  valid_patient_skill: boolean
  pipeline_ready: boolean
  skill_id?: string | null
  errors: string[]
  warnings: string[]
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
  if (category) params.type = category
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
export async function getSkillTypes(projectId?: string): Promise<string[]> {
  const params: Record<string, string> = {}
  if (projectId) params.project_id = projectId
  const response = await get<BaseResponse<string[]>>('/skills/types', { params })
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

/**
 * 删除 Skill（管理员专属）
 */
export async function deleteSkill(slug: string): Promise<void> {
  await del<BaseResponse<{ deleted: string }>>(`/skills/${slug}`)
}

/**
 * 上传 Skill zip 包
 * @param file zip 文件
 * @param onProgress 上传进度回调 (0-100)
 */
export async function uploadSkill(
  file: File,
  onProgress?: (percent: number) => void
): Promise<SkillInfo> {
  const form = new FormData()
  form.append('file', file)
  const response = await post<BaseResponse<SkillInfo>>('/skills/upload', form, {
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    },
  })
  const data: any = response.data.data
  return {
    id: data.id || data.slug,
    name: data.name || data.slug,
    type: data.type || 'user-invocable',
    description: data.description || '',
    full_description: data.full_description,
    features: data.features,
    version: data.version || '1.0.0',
    author: data.author || '',
    downloads: data.downloads || 0,
    rating: data.rating || 0,
    installed: true,
    featured: false,
    tags: data.tags || (data.type ? [data.type] : []),
    created_at: data.created_at,
    skill_level: data.skill_level,
    valid_patient_skill: data.valid_patient_skill,
    pipeline_ready: data.pipeline_ready,
    global_skill_level: data.global_skill_level,
    global_valid_patient_skill: data.global_valid_patient_skill,
    global_pipeline_ready: data.global_pipeline_ready,
    global_version: data.global_version,
    installed_skill_level: data.installed_skill_level,
    installed_valid_patient_skill: data.installed_valid_patient_skill,
    installed_pipeline_ready: data.installed_pipeline_ready,
    installed_version: data.installed_version,
    update_available: data.update_available,
    validation: data.validation,
  }
}

/**
 * 预校验 Skill zip 包，不安装
 */
export async function validateSkillUpload(file: File): Promise<SkillValidationResult> {
  const form = new FormData()
  form.append('file', file)
  const response = await post<BaseResponse<SkillValidationResult>>('/skills/validate-upload', form)
  return response.data.data
}
