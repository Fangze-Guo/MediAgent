/**
 * 数据集管理 API
 */
import { api } from '@/utils/request'

// ==================== 类型定义 ====================

export interface DatasetInfo {
  id?: number
  dataset_name: string
  case_count: number
  clinical_data_desc?: string
  text_data_desc?: string
  imaging_data_desc?: string
  pathology_data_desc?: string
  genomics_data_desc?: string
  annotation_desc?: string
  notes?: string
  user_id?: number
  has_data?: number
  has_description_file?: number
  data_path?: string
  description_file_path?: string
  create_time?: string
}

export interface CreateDatasetRequest {
  dataset_name: string
  case_count?: number
  clinical_data_desc?: string
  text_data_desc?: string
  imaging_data_desc?: string
  pathology_data_desc?: string
  genomics_data_desc?: string
  annotation_desc?: string
  notes?: string
}

export interface UpdateDatasetRequest {
  id: number
  dataset_name?: string
  case_count?: number
  clinical_data_desc?: string
  text_data_desc?: string
  imaging_data_desc?: string
  pathology_data_desc?: string
  genomics_data_desc?: string
  annotation_desc?: string
  notes?: string
}

export interface UploadResult {
  uploaded_count: number
  total_case_count: number
  files: any[]
}

// ==================== API 方法 ====================

/**
 * 创建数据集
 */
export function createDataset(data: CreateDatasetRequest) {
  return api.post('/dataset/create', data)
}

/**
 * 获取数据集列表
 */
export function getDatasetList() {
  return api.get('/dataset/list')
}

/**
 * 获取数据集详情
 */
export function getDatasetDetail(datasetId: number) {
  return api.get(`/dataset/${datasetId}`)
}

/**
 * 更新数据集
 */
export function updateDataset(data: UpdateDatasetRequest) {
  return api.put('/dataset/update', data)
}

/**
 * 删除数据集
 */
export function deleteDataset(datasetId: number) {
  return api.delete(`/dataset/${datasetId}`)
}

/**
 * 上传文件到数据集
 */
export function uploadFilesToDataset(datasetId: number, files: File[]) {
  console.log('API uploadFilesToDataset 收到文件:', files.length);
  
  const formData = new FormData()
  const filePaths: string[] = []
  
  files.forEach((file, index) => {
    const relativePath = (file as any).webkitRelativePath || file.name
    console.log(`添加到 FormData - 文件 ${index + 1}:`, file.name, '完整路径:', relativePath);
    formData.append('files', file)
    filePaths.push(relativePath)
  })
  
  // 将路径信息作为 JSON 字符串添加到 FormData
  formData.append('file_paths', JSON.stringify(filePaths))
  
  console.log('文件路径示例:', filePaths.slice(0, 5));
  console.log('总共', filePaths.length, '个文件');
  
  // 不要手动设置 Content-Type，让 axios 自动处理 multipart/form-data 的 boundary
  return api.post(`/dataset/${datasetId}/upload`, formData, {
    timeout: 300000 // 5分钟超时（大文件上传）
  })
}

/**
 * 上传数据集描述文件（CSV）
 */
export function uploadDescriptionFile(datasetId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  
  return api.post(`/dataset/${datasetId}/upload-description`, formData, {
    timeout: 60000 // 1分钟超时
  })
}

