import axios from 'axios'
import type {
  KnowledgeBase,
  Document,
  UploadResult,
} from '../types/knowledge-base'

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/api'

// 获取token
const getAuthToken = () => {
  return localStorage.getItem('medwiser_token') || ''
}

// 创建axios实例
const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 添加token
apiClient.interceptors.request.use(
  (config) => {
    const token = getAuthToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理错误
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('medwiser_token')
      localStorage.removeItem('medwiser_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 从统一响应体中提取 data
const unwrap = <T>(response: { data: { data: T } }): T => response.data.data

export interface SearchResult {
  content: string
  score: number
  doc_id?: number
  file_name?: string
  chunk_index?: number
}

export const knowledgeBaseApi = {
  // 获取知识库列表
  getKnowledgeBases: async (): Promise<KnowledgeBase[]> => {
    return unwrap(await apiClient.get('/knowledge-base'))
  },

  // 创建知识库
  createKnowledgeBase: async (data: { name: string; description?: string }): Promise<KnowledgeBase> => {
    return unwrap(await apiClient.post('/knowledge-base', data))
  },

  // 获取知识库详情
  getKnowledgeBase: async (id: number): Promise<KnowledgeBase> => {
    return unwrap(await apiClient.get(`/knowledge-base/${id}`))
  },

  // 更新知识库
  updateKnowledgeBase: async (id: number, data: { name?: string; description?: string }): Promise<KnowledgeBase> => {
    return unwrap(await apiClient.put(`/knowledge-base/${id}`, data))
  },

  // 删除知识库
  deleteKnowledgeBase: async (id: number): Promise<void> => {
    await apiClient.delete(`/knowledge-base/${id}`)
  },

  // 上传文档（支持 PDF/Word/Excel/TXT）
  uploadDocuments: async (kbId: number, formData: FormData): Promise<UploadResult[]> => {
    const response = await apiClient.post(
      `/knowledge-base/${kbId}/documents/upload`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    // 后端直接返回文档 VO 列表，包装成前端期望的 UploadResult 格式
    const docs: Document[] = unwrap(response)
    return docs.map(doc => ({
      document_id: doc.id,
      file_name: doc.file_name,
      status: 'exists' as const,
      skip_processing: true,
    }))
  },

  // 删除文档
  deleteDocument: async (kbId: number, docId: number): Promise<void> => {
    await apiClient.delete(`/knowledge-base/${kbId}/documents/${docId}`)
  },

  // 预览文档（返回预览信息：PDF 返回 serve_url，Word/Excel 返回内容）
  previewDocument: async (kbId: number, docId: number): Promise<{
    type: 'url' | 'text' | 'table'
    serve_url?: string
    content?: string
    sheets?: Record<string, string[][]>
    file_name: string
    content_type?: string
  }> => {
    return unwrap(await apiClient.get(`/knowledge-base/${kbId}/documents/${docId}/preview`))
  },

  // 语义检索知识库（向量相似度搜索）
  searchKnowledgeBase: async (kbId: number, query: string, topK: number = 5): Promise<SearchResult[]> => {
    return unwrap(await apiClient.post(`/knowledge-base/${kbId}/search`, { query, top_k: topK }))
  },

  // 触发文档 embedding（Analyze）
  analyzeDocument: async (
    kbId: number,
    docId: number,
    chunkSize?: number,
    chunkOverlap?: number,
  ): Promise<Document> => {
    const body: Record<string, number> = {}
    if (chunkSize !== undefined) body.chunk_size = chunkSize
    if (chunkOverlap !== undefined) body.chunk_overlap = chunkOverlap
    return unwrap(await apiClient.post(`/knowledge-base/${kbId}/documents/${docId}/analyze`, body))
  },
}
