/**
 * 模型配置相关API接口
 * 提供与后端模型配置服务的交互功能
 */
import { get, postJson, putJson, del } from '@/utils/request'

/**
 * 模型配置数据传输对象
 * 用于前后端模型配置格式统一
 */
export interface ModelConfigDto {
  /** 模型ID */
  id: string
  /** 模型名称 */
  name: string
  /** 模型描述 */
  description: string
  /** 提供商 */
  provider: string
  /** API基础URL */
  base_url: string
  /** API密钥 */
  api_key?: string
  /** 状态 */
  status: 'online' | 'maintenance' | 'offline'
  /** 标签 */
  tags?: string[]
}

/**
 * 模型配置响应数据传输对象
 * 后端返回的模型配置数据
 */
export interface ModelConfigResponse {
  /** 当前模型ID */
  current_model_id: string
  /** 模型配置列表 */
  models: Record<string, ModelConfigDto>
}

/**
 * 创建模型配置请求数据传输对象
 */
export interface CreateModelConfigDto {
  /** 模型ID */
  id: string
  /** 模型名称 */
  name: string
  /** 模型描述 */
  description: string
  /** 提供商 */
  provider: string
  /** API基础URL */
  base_url: string
  /** API密钥 */
  api_key?: string
  /** 状态 */
  status?: 'online' | 'maintenance' | 'offline'
  /** 标签 */
  tags?: string[]
}

/**
 * 更新模型配置请求数据传输对象
 */
export interface UpdateModelConfigDto extends Partial<CreateModelConfigDto> {
  /** 模型ID（必填） */
  id: string
}

/**
 * 获取所有模型配置
 * @returns Promise<ModelConfigResponse> 返回所有模型配置
 * @throws {Error} 当请求失败时抛出错误
 * 
 * @example
 * ```typescript
 * const configs = await getModelConfigs()
 * console.log(configs.current_model_id) // 当前模型ID
 * console.log(configs.models) // 所有模型配置
 * ```
 */
export async function getModelConfigs(): Promise<ModelConfigResponse> {
  try {
    const response = await get<{ code: number; data: ModelConfigResponse; message: string }>('/models/configs')
    console.log('API 原始响应:', response)
    
    // 检查响应格式
    if (response.data && response.data.code === 200) {
      return response.data.data
    } else {
      throw new Error(response.data?.message || '获取模型配置失败')
    }
  } catch (error) {
    console.error('获取模型配置失败:', error)
    throw new Error('获取模型配置失败，请稍后再试')
  }
}

/**
 * 获取当前模型配置
 * @returns Promise<ModelConfigDto | null> 返回当前模型配置
 * @throws {Error} 当请求失败时抛出错误
 * 
 * @example
 * ```typescript
 * const currentModel = await getCurrentModel()
 * if (currentModel) {
 *   console.log(currentModel.name) // 当前模型名称
 * }
 * ```
 */
export async function getCurrentModel(): Promise<ModelConfigDto | null> {
  try {
    const response = await get<ModelConfigDto>('/models/current')
    return response.data
  } catch (error) {
    console.error('获取当前模型失败:', error)
    throw new Error('获取当前模型失败，请稍后再试')
  }
}

/**
 * 设置当前模型
 * @param modelId 模型ID
 * @returns Promise<boolean> 返回是否设置成功
 * @throws {Error} 当请求失败时抛出错误
 * 
 * @example
 * ```typescript
 * const success = await setCurrentModel('gpt-4')
 * if (success) {
 *   console.log('模型切换成功')
 * }
 * ```
 */
export async function setCurrentModel(modelId: string): Promise<boolean> {
  try {
    const response = await postJson<boolean, { model_id: string }>('/models/current', {
      model_id: modelId
    })
    return response
  } catch (error) {
    console.error('设置当前模型失败:', error)
    throw new Error('设置当前模型失败，请稍后再试')
  }
}

/**
 * 创建模型配置
 * @param config 模型配置数据
 * @returns Promise<ModelConfigDto> 返回创建的模型配置
 * @throws {Error} 当请求失败时抛出错误
 * 
 * @example
 * ```typescript
 * const newModel = await createModelConfig({
 *   id: 'custom-model',
 *   name: '自定义模型',
 *   description: '我的自定义模型',
 *   provider: 'Custom',
 *   base_url: 'https://api.custom.com/v1/chat/completions',
 *   api_key: 'your-api-key'
 * })
 * ```
 */
export async function createModelConfig(config: CreateModelConfigDto): Promise<ModelConfigDto> {
  try {
    const response = await postJson<ModelConfigDto, CreateModelConfigDto>('/models/configs', config)
    return response
  } catch (error) {
    console.error('创建模型配置失败:', error)
    throw new Error('创建模型配置失败，请稍后再试')
  }
}

/**
 * 更新模型配置
 * @param config 模型配置数据
 * @returns Promise<ModelConfigDto> 返回更新后的模型配置
 * @throws {Error} 当请求失败时抛出错误
 * 
 * @example
 * ```typescript
 * const updatedModel = await updateModelConfig({
 *   id: 'custom-model',
 *   name: '更新后的模型名称',
 *   description: '更新后的描述'
 * })
 * ```
 */
export async function updateModelConfig(config: UpdateModelConfigDto): Promise<ModelConfigDto> {
  try {
    const response = await putJson<ModelConfigDto, UpdateModelConfigDto>(`/models/configs/${config.id}`, config)
    return response
  } catch (error) {
    console.error('更新模型配置失败:', error)
    throw new Error('更新模型配置失败，请稍后再试')
  }
}

/**
 * 删除模型配置
 * @param modelId 模型ID
 * @returns Promise<boolean> 返回是否删除成功
 * @throws {Error} 当请求失败时抛出错误
 * 
 * @example
 * ```typescript
 * const success = await deleteModelConfig('custom-model')
 * if (success) {
 *   console.log('模型配置删除成功')
 * }
 * ```
 */
export async function deleteModelConfig(modelId: string): Promise<boolean> {
  try {
    const response = await del<{ success: boolean }>(`/models/configs/${modelId}`)
    return response.data.success
  } catch (error) {
    console.error('删除模型配置失败:', error)
    throw new Error('删除模型配置失败，请稍后再试')
  }
}

