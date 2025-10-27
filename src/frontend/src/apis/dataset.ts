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
  files.forEach((file, index) => {
    console.log(`添加到 FormData - 文件 ${index + 1}:`, file.name, file instanceof File);
    formData.append('files', file)
  })
  
  // 打印 FormData 内容
  console.log('FormData entries:');
  for (let pair of formData.entries()) {
    console.log(pair[0], pair[1]);
  }
  
  // 不要手动设置 Content-Type，让 axios 自动处理 multipart/form-data 的 boundary
  return api.post(`/dataset/${datasetId}/upload`, formData, {
    timeout: 300000 // 5分钟超时（大文件上传）
  })
}

