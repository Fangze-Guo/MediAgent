import axios from 'axios'
import type {
  KnowledgeBase,
  Document,
  UploadResult,
  PreviewResponse,
  TaskResponse,
  TaskStatus
} from '../types/knowledge-base'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

// 模拟数据模式 - 当后端不可用时使用
const USE_MOCK_DATA = true // 设置为 false 以使用真实 API

// 模拟知识库数据
const mockKnowledgeBases: KnowledgeBase[] = [
  {
    id: 1,
    name: '心血管疾病诊疗指南',
    description: '包含常见心血管疾病的诊断和治疗方案，涵盖高血压、冠心病、心力衰竭等疾病的最新诊疗规范',
    documents: [
      {
        id: 1,
        file_name: '心血管疾病诊疗指南_2024版.pdf',
        file_path: '/kb_1/cardio_guide_2024.pdf',
        file_size: 2456789,
        content_type: 'application/pdf',
        knowledge_base_id: 1,
        created_at: '2024-01-10T10:30:00Z',
        updated_at: '2024-01-10T10:30:00Z',
        processing_tasks: [
          {
            id: 1,
            status: 'completed',
            error_message: null,
            created_at: '2024-01-10T10:30:00Z',
            updated_at: '2024-01-10T10:35:00Z'
          }
        ]
      },
      {
        id: 2,
        file_name: '急性心肌梗死诊断与治疗.pdf',
        file_path: '/kb_1/ami_treatment.pdf',
        file_size: 1234567,
        content_type: 'application/pdf',
        knowledge_base_id: 1,
        created_at: '2024-01-10T11:20:00Z',
        updated_at: '2024-01-10T11:20:00Z',
        processing_tasks: [
          {
            id: 2,
            status: 'completed',
            error_message: null,
            created_at: '2024-01-10T11:20:00Z',
            updated_at: '2024-01-10T11:25:00Z'
          }
        ]
      },
      {
        id: 3,
        file_name: '高血压管理指南.pdf',
        file_path: '/kb_1/hypertension_guide.pdf',
        file_size: 3456789,
        content_type: 'application/pdf',
        knowledge_base_id: 1,
        created_at: '2024-01-09T14:15:00Z',
        updated_at: '2024-01-09T14:15:00Z',
        processing_tasks: [
          {
            id: 3,
            status: 'completed',
            error_message: null,
            created_at: '2024-01-09T14:15:00Z',
            updated_at: '2024-01-09T14:20:00Z'
          }
        ]
      }
    ],
    created_at: '2024-01-10T10:30:00Z',
    updated_at: '2024-01-10T10:30:00Z'
  },
  {
    id: 2,
    name: '肿瘤学文献库',
    description: '收录最新肿瘤学研究论文和临床报告，包括肺癌、乳腺癌、消化道肿瘤等主要肿瘤类型的研究进展',
    documents: [
      {
        id: 4,
        file_name: '肺癌免疫治疗最新进展.pdf',
        file_path: '/kb_2/lung_cancer_immuno.pdf',
        file_size: 1876543,
        content_type: 'application/pdf',
        knowledge_base_id: 2,
        created_at: '2024-01-08T14:20:00Z',
        updated_at: '2024-01-08T14:20:00Z',
        processing_tasks: [
          {
            id: 4,
            status: 'completed',
            error_message: null,
            created_at: '2024-01-08T14:20:00Z',
            updated_at: '2024-01-08T14:25:00Z'
          }
        ]
      },
      {
        id: 5,
        file_name: '乳腺癌靶向治疗指南.pdf',
        file_path: '/kb_2/breast_cancer_targeted.pdf',
        file_size: 2345678,
        content_type: 'application/pdf',
        knowledge_base_id: 2,
        created_at: '2024-01-07T09:30:00Z',
        updated_at: '2024-01-07T09:30:00Z',
        processing_tasks: [
          {
            id: 5,
            status: 'completed',
            error_message: null,
            created_at: '2024-01-07T09:30:00Z',
            updated_at: '2024-01-07T09:35:00Z'
          }
        ]
      }
    ],
    created_at: '2024-01-08T14:20:00Z',
    updated_at: '2024-01-08T14:20:00Z'
  },
  {
    id: 3,
    name: '罕见病病例库',
    description: '收集各类罕见疾病的诊断和治疗案例，包括遗传性疾病、代谢性疾病等',
    documents: [
      {
        id: 6,
        file_name: '罕见病诊疗手册.pdf',
        file_path: '/kb_3/rare_disease_manual.pdf',
        file_size: 4567890,
        content_type: 'application/pdf',
        knowledge_base_id: 3,
        created_at: '2024-01-05T09:15:00Z',
        updated_at: '2024-01-05T09:15:00Z',
        processing_tasks: [
          {
            id: 6,
            status: 'completed',
            error_message: null,
            created_at: '2024-01-05T09:15:00Z',
            updated_at: '2024-01-05T09:20:00Z'
          }
        ]
      }
    ],
    created_at: '2024-01-05T09:15:00Z',
    updated_at: '2024-01-05T09:15:00Z'
  },
  {
    id: 4,
    name: '儿科疾病诊疗指南',
    description: '涵盖儿科常见疾病的诊断和治疗规范，包括新生儿疾病、呼吸系统疾病、消化系统疾病等',
    documents: [],
    created_at: '2024-01-03T16:45:00Z',
    updated_at: '2024-01-03T16:45:00Z'
  }
]

// 获取token
const getAuthToken = () => {
  return localStorage.getItem('token') || ''
}

// 创建axios实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
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
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const knowledgeBaseApi = {
  // 获取知识库列表
  getKnowledgeBases: async () => {
    if (USE_MOCK_DATA) {
      // 模拟延迟
      await new Promise(resolve => setTimeout(resolve, 500))
      return mockKnowledgeBases
    }
    const response = await apiClient.get<KnowledgeBase[]>('/knowledge-base')
    return response.data
  },

  // 创建知识库
  createKnowledgeBase: async (data: { name: string; description?: string }) => {
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 300))
      const newKb: KnowledgeBase = {
        id: mockKnowledgeBases.length + 1,
        name: data.name,
        description: data.description,
        documents: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
      mockKnowledgeBases.push(newKb)
      return newKb
    }
    const response = await apiClient.post<KnowledgeBase>('/knowledge-base', data)
    return response.data
  },

  // 获取知识库详情
  getKnowledgeBase: async (id: number) => {
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 300))
      const kb = mockKnowledgeBases.find(kb => kb.id === id)
      if (!kb) {
        throw new Error('Knowledge base not found')
      }
      return kb
    }
    const response = await apiClient.get<KnowledgeBase>(`/knowledge-base/${id}`)
    return response.data
  },

  // 更新知识库
  updateKnowledgeBase: async (id: number, data: { name?: string; description?: string }) => {
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 300))
      const kb = mockKnowledgeBases.find(kb => kb.id === id)
      if (!kb) {
        throw new Error('Knowledge base not found')
      }
      if (data.name) kb.name = data.name
      if (data.description !== undefined) kb.description = data.description
      kb.updated_at = new Date().toISOString()
      return kb
    }
    const response = await apiClient.put<KnowledgeBase>(`/knowledge-base/${id}`, data)
    return response.data
  },

  // 删除知识库
  deleteKnowledgeBase: async (id: number) => {
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 300))
      const index = mockKnowledgeBases.findIndex(kb => kb.id === id)
      if (index === -1) {
        throw new Error('Knowledge base not found')
      }
      mockKnowledgeBases.splice(index, 1)
      return { message: 'Knowledge base deleted successfully' }
    }
    const response = await apiClient.delete(`/knowledge-base/${id}`)
    return response.data
  },

  // 上传文档
  uploadDocuments: async (kbId: number, formData: FormData) => {
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      const files = Array.from(formData.values()) as File[]
      const results: UploadResult[] = files.map(file => ({
        upload_id: Math.floor(Math.random() * 10000) + 1000,
        file_name: file.name,
        temp_path: `/kb_${kbId}/temp/${file.name}`,
        status: 'pending',
        skip_processing: false
      }))
      return results
    }
    const response = await apiClient.post<UploadResult[]>(
      `/knowledge-base/${kbId}/documents/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      }
    )
    return response.data
  },

  // 预览文档
  previewDocuments: async (
    kbId: number,
    data: { document_ids: number[]; chunk_size?: number; chunk_overlap?: number }
  ) => {
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 800))
      const chunkSize = data.chunk_size || 1000
      const mockPreview: PreviewResponse = {
        chunks: [
          {
            content: '这是文档的第一个分块示例内容。'.repeat(chunkSize / 20),
            metadata: { page: 1, chunk_index: 0 }
          },
          {
            content: '这是文档的第二个分块示例内容。'.repeat(chunkSize / 20),
            metadata: { page: 1, chunk_index: 1 }
          },
          {
            content: '这是文档的第三个分块示例内容。'.repeat(chunkSize / 20),
            metadata: { page: 2, chunk_index: 2 }
          }
        ],
        total_chunks: 3
      }
      return { [data.document_ids[0]]: mockPreview }
    }
    const response = await apiClient.post<Record<number, PreviewResponse>>(
      `/knowledge-base/${kbId}/documents/preview`,
      data
    )
    return response.data
  },

  // 处理文档
  processDocuments: async (kbId: number, uploadResults: Array<UploadResult>) => {
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 500))
      const tasks = uploadResults
        .filter(r => !r.skip_processing)
        .map(result => ({
          upload_id: result.upload_id!,
          task_id: Math.floor(Math.random() * 10000) + 1000
        }))
      return { tasks }
    }
    const response = await apiClient.post<TaskResponse>(
      `/knowledge-base/${kbId}/documents/process`,
      uploadResults
    )
    return response.data
  },

  // 获取处理任务状态
  getTaskStatus: async (kbId: number, taskIds: number[]) => {
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 300))
      const statuses: Record<number, TaskStatus> = {}
      taskIds.forEach(taskId => {
        const random = Math.random()
        let status: 'pending' | 'processing' | 'completed' | 'failed'
        if (random < 0.3) {
          status = 'completed'
        } else if (random < 0.6) {
          status = 'processing'
        } else {
          status = 'pending'
        }
        statuses[taskId] = {
          document_id: taskId,
          status,
          upload_id: taskId,
          file_name: 'test_document.pdf'
        }
      })
      return statuses
    }
    const response = await apiClient.get<Record<number, TaskStatus>>(
      `/knowledge-base/${kbId}/documents/tasks`,
      {
        params: {
          task_ids: taskIds.join(',')
        }
      }
    )
    return response.data
  },

  // 获取文档详情
  getDocument: async (kbId: number, docId: number) => {
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 300))
      const kb = mockKnowledgeBases.find(kb => kb.id === kbId)
      if (!kb) {
        throw new Error('Knowledge base not found')
      }
      const doc = kb.documents.find(d => d.id === docId)
      if (!doc) {
        throw new Error('Document not found')
      }
      return doc
    }
    const response = await apiClient.get<Document>(`/knowledge-base/${kbId}/documents/${docId}`)
    return response.data
  },

  // 测试检索
  testRetrieval: async (kbId: number, query: string, topK: number = 5) => {
    if (USE_MOCK_DATA) {
      await new Promise(resolve => setTimeout(resolve, 800))
      const mockResults = [
        {
          content: `针对"${query}"的相关内容示例1。这是从知识库中检索到的文档片段。`,
          metadata: { file_name: '心血管疾病诊疗指南_2024版.pdf', page: 15 },
          score: 0.95
        },
        {
          content: `针对"${query}"的相关内容示例2。这是另一个相关的文档片段。`,
          metadata: { file_name: '急性心肌梗死诊断与治疗.pdf', page: 8 },
          score: 0.87
        },
        {
          content: `针对"${query}"的相关内容示例3。这个片段也包含相关信息。`,
          metadata: { file_name: '高血压管理指南.pdf', page: 22 },
          score: 0.76
        }
      ]
      return { results: mockResults.slice(0, topK) }
    }
    const response = await apiClient.post('/knowledge-base/test-retrieval', {
      kb_id: kbId,
      query,
      top_k: topK
    })
    return response.data
  }
}
