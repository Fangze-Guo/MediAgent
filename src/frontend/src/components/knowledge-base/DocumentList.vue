<template>
  <div class="document-list">
    <div v-if="loading" class="loading-state">
      <a-spin size="large" />
      <p class="loading-text">Loading documents...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <a-alert type="error" :message="error" show-icon />
    </div>

    <div v-else-if="documents.length === 0" class="empty-state">
      <div class="empty-icon-wrapper">
        <FileTextOutlined class="empty-icon" />
      </div>
      <div class="empty-text-content">
        <h3 class="empty-title">No documents yet</h3>
        <p class="empty-description">
          Upload your first document to start building your knowledge base.
        </p>
      </div>
    </div>

    <a-table
      v-else
      :columns="columns"
      :data-source="documents"
      :pagination="{ pageSize: 10 }"
      :row-key="(record: Document) => record.id"
    >
      <template #bodyCell="{ column, record }: { column: any; record: Document }">
        
        <template v-if="column.key === 'name'">
          <div class="document-name">
            <div class="file-icon-wrapper" :class="getFileTypeClass(record.content_type, record.file_name)">
              <span class="file-extension">{{ getExtension(record.file_name) }}</span>
            </div>
            <span class="font-medium">{{ record.file_name }}</span>
          </div>
        </template>

        <template v-else-if="column.key === 'size'">
          <span class="text-gray-600">{{ formatFileSize(record.file_size) }}</span>
        </template>

        <template v-else-if="column.key === 'created'">
          <span class="text-gray-600">{{ formatDate(record.created_at) }}</span>
        </template>

        <template v-else-if="column.key === 'status'">
          <a-tag
            v-if="record.processing_tasks && record.processing_tasks.length > 0"
            :color="getStatusColor(record.processing_tasks[0].status)"
            class="status-tag"
          >
            {{ record.processing_tasks[0].status.toUpperCase() }}
          </a-tag>
        </template>

        <template v-else-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleAnalyze(record)">
              <ThunderboltOutlined />
              Analyze
            </a-button>
            <a-popconfirm
              title="Are you sure you want to delete this document?"
              @confirm="handleDelete(record)"
            >
              <a-button type="link" danger size="small">
                <DeleteOutlined />
                Delete
              </a-button>
            </a-popconfirm>
          </a-space>
        </template>

      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  FileTextOutlined,
  ThunderboltOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import { formatDistanceToNow } from 'date-fns'
import type { Document } from '../../types/knowledge-base'

interface Props {
  knowledgeBaseId: number
  refreshKey?: number
}

const props = withDefaults(defineProps<Props>(), {
  refreshKey: 0
})

const emit = defineEmits<{
  documentDeleted: [document: Document]
  documentAnalyzed: [document: Document]
}>()

const documents = ref<Document[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const columns = [
  { title: 'Name', key: 'name', width: '40%' },
  { title: 'Size', key: 'size', width: '15%' },
  { title: 'Created', key: 'created', width: '20%' },
  { title: 'Status', key: 'status', width: '15%' },
  { title: 'Action', key: 'action', width: '10%' }
]

const fetchDocuments = async () => {
  loading.value = true
  error.value = null

  // 模拟API延迟
  await new Promise(resolve => setTimeout(resolve, 800))

  // 静态演示数据
  documents.value = [
    {
      id: 1,
      file_name: '心血管疾病诊疗指南2024.pdf',
      file_path: '/uploads/cardio_guidelines_2024.pdf',
      file_size: 2458624,
      content_type: 'application/pdf',
      knowledge_base_id: props.knowledgeBaseId,
      created_at: '2024-03-15T10:30:00Z',
      updated_at: '2024-03-20T14:22:00Z',
      processing_tasks: [
        {
          id: 1,
          status: 'completed',
          error_message: null,
          created_at: '2024-03-15T10:31:00Z',
          updated_at: '2024-03-15T10:35:00Z'
        }
      ]
    },
    {
      id: 2,
      file_name: '糖尿病管理手册.docx',
      file_path: '/uploads/diabetes_manual.docx',
      file_size: 1524288,
      content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      knowledge_base_id: props.knowledgeBaseId,
      created_at: '2024-03-18T09:15:00Z',
      updated_at: '2024-03-19T11:45:00Z',
      processing_tasks: [
        {
          id: 2,
          status: 'completed',
          error_message: null,
          created_at: '2024-03-18T09:16:00Z',
          updated_at: '2024-03-18T09:20:00Z'
        }
      ]
    },
    {
      id: 3,
      file_name: '高血压治疗方案.txt',
      file_path: '/uploads/hypertension_treatment.txt',
      file_size: 45678,
      content_type: 'text/plain',
      knowledge_base_id: props.knowledgeBaseId,
      created_at: '2024-03-20T16:00:00Z',
      updated_at: '2024-03-20T16:05:00Z',
      processing_tasks: [
        {
          id: 3,
          status: 'processing',
          error_message: null,
          created_at: '2024-03-20T16:01:00Z',
          updated_at: '2024-03-20T16:05:00Z'
        }
      ]
    },
    {
      id: 4,
      file_name: '肿瘤免疫治疗进展.pdf',
      file_path: '/uploads/oncology_immunotherapy.pdf',
      file_size: 3245678,
      content_type: 'application/pdf',
      knowledge_base_id: props.knowledgeBaseId,
      created_at: '2024-03-21T08:30:00Z',
      updated_at: '2024-03-21T08:35:00Z',
      processing_tasks: [
        {
          id: 4,
          status: 'failed',
          error_message: 'PDF parsing failed: encrypted document',
          created_at: '2024-03-21T08:31:00Z',
          updated_at: '2024-03-21T08:35:00Z'
        }
      ]
    },
    {
      id: 5,
      file_name: '神经科学研究报告.md',
      file_path: '/uploads/neuroscience_research.md',
      file_size: 128945,
      content_type: 'text/markdown',
      knowledge_base_id: props.knowledgeBaseId,
      created_at: '2024-03-22T13:45:00Z',
      updated_at: '2024-03-22T13:50:00Z',
      processing_tasks: [
        {
          id: 5,
          status: 'completed',
          error_message: null,
          created_at: '2024-03-22T13:46:00Z',
          updated_at: '2024-03-22T13:50:00Z'
        }
      ]
    }
  ]

  loading.value = false
}

const handleDelete = async (document: Document) => {
  try {
    // await knowledgeBaseApi.deleteDocument(props.knowledgeBaseId, document.id)
    message.success('Document deleted successfully')
    emit('documentDeleted', document)
    await fetchDocuments()
  } catch (err: any) {
    message.error(err.response?.data?.detail || 'Failed to delete document')
  }
}

const handleAnalyze = (document: Document) => {
  emit('documentAnalyzed', document)
}

// --- 核心优化：图标与格式化逻辑 ---

const getExtension = (filename: string): string => {
  if (!filename) return 'FILE'
  const parts = filename.split('.')
  return parts.length > 1 ? parts.pop()!.substring(0, 4).toUpperCase() : 'FILE'
}

const getFileTypeClass = (contentType: string = '', filename: string = ''): string => {
  const type = contentType.toLowerCase()
  const ext = filename.toLowerCase()
  if (type.includes('pdf') || ext.includes('.pdf')) return 'icon-pdf'
  if (type.includes('word') || type.includes('doc') || ext.includes('.doc')) return 'icon-word'
  if (type.includes('text') || ext.includes('.txt') || ext.includes('.md')) return 'icon-text'
  return 'icon-default'
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

const formatDate = (dateString: string): string => {
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
  } catch (e) {
    return dateString || 'Unknown date'
  }
}

const getStatusColor = (status: string): string => {
  const statusLower = status.toLowerCase()
  const colors: Record<string, string> = {
    completed: 'green',
    failed: 'red',
    processing: 'blue',
    pending: 'default'
  }
  return colors[statusLower] || 'default'
}

watch(() => props.refreshKey, () => {
  fetchDocuments()
})

onMounted(() => {
  fetchDocuments()
})
</script>

<style scoped>
.document-list {
  width: 100%;
  background: #ffffff;
  border-radius: 8px;
}

/* 状态样式 */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px;
  gap: 16px;
}
.loading-text { color: #64748b; font-size: 14px; margin: 0; }
.error-state { padding: 24px; }

/* 深度复刻 Shadcn UI 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 48px;
  text-align: center;
}
.empty-icon-wrapper {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background-color: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}
.empty-icon { font-size: 32px; color: #94a3b8; }
.empty-title { font-size: 20px; font-weight: 600; color: #0f172a; margin-bottom: 8px; }
.empty-description { color: #64748b; font-size: 14px; max-width: 400px; margin: 0; }

/* 列表内元素样式 */
.document-name { display: flex; align-items: center; gap: 12px; }
.font-medium { font-weight: 500; color: #0f172a; }
.text-gray-600 { color: #475569; }
.status-tag { border-radius: 4px; font-weight: 500; font-size: 12px; }

/* 纯 CSS 拟真文件图标 (核心复刻) */
.file-icon-wrapper {
  width: 26px;
  height: 32px;
  border-radius: 4px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 4px;
  position: relative;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  flex-shrink: 0;
}
.file-icon-wrapper::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  border-width: 0 10px 10px 0;
  border-style: solid;
  border-color: rgba(255,255,255,0.4) #fff transparent transparent;
  border-bottom-left-radius: 3px;
  box-shadow: -1px 1px 2px rgba(0,0,0,0.1);
}
.file-extension {
  font-size: 8px;
  font-weight: 700;
  color: white;
  letter-spacing: 0.5px;
  z-index: 1;
}

/* 匹配不用文件类型的渐变色彩 */
.icon-pdf { background: linear-gradient(135deg, #ef4444, #b91c1c); } /* Tailwind Red */
.icon-word { background: linear-gradient(135deg, #3b82f6, #1d4ed8); } /* Tailwind Blue */
.icon-text { background: linear-gradient(135deg, #94a3b8, #475569); } /* Tailwind Slate */
.icon-default { background: linear-gradient(135deg, #cbd5e1, #64748b); }

/* 优化 Ant Design Table 的默认边框和背景 */
:deep(.ant-table-thead > tr > th) {
  background: #f8fafc;
  color: #64748b;
  font-weight: 500;
  border-bottom: 1px solid #e2e8f0;
}
:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #f1f5f9;
}
</style>