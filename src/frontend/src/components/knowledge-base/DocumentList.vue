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

    <template v-else>
      <transition name="toolbar-slide">
        <div v-if="selectedRowKeys.length > 0" class="batch-toolbar">
          <div class="batch-toolbar-left">
            <div class="batch-count-badge">{{ selectedRowKeys.length }}</div>
            <span class="batch-info">document{{ selectedRowKeys.length > 1 ? 's' : '' }} selected</span>
          </div>
          <div class="batch-toolbar-right">
            <a-button class="batch-cancel-btn" size="small" @click="selectedRowKeys = []">Cancel</a-button>
            <a-popconfirm
              :title="`Permanently delete ${selectedRowKeys.length} document(s)?`"
              ok-text="Delete"
              ok-type="danger"
              @confirm="handleBatchDelete"
            >
              <a-button class="batch-delete-btn" size="small" :loading="batchDeleting">
                <template #icon><DeleteOutlined /></template>
                Delete Selected
              </a-button>
            </a-popconfirm>
          </div>
        </div>
      </transition>

      <a-table
        :columns="columns"
        :data-source="documents"
        :pagination="{ pageSize: 10 }"
        :row-key="(record: Document) => record.id"
        :row-selection="rowSelection"
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
            <a-button type="link" size="small" class="btn-view" @click="handleView(record)">
              <EyeOutlined />
              View
            </a-button>
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
    </template>

    <!-- 文档预览弹框 -->
    <a-modal
      v-model:open="showPreviewModal"
      :title="previewData?.file_name || 'Document Preview'"
      :footer="null"
      width="860px"
      :body-style="{ padding: '0', height: '76vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }"
      destroy-on-close
    >
      <div v-if="previewLoading" class="preview-loading">
        <a-spin size="large" />
        <p>Loading preview...</p>
      </div>

      <template v-else-if="previewData">
        <!-- PDF -->
        <iframe
          v-if="previewData.type === 'url'"
          :src="previewData.serve_url"
          class="preview-iframe"
          frameborder="0"
        />

        <!-- 纯文本 -->
        <div v-else-if="previewData.type === 'text'" class="preview-text-wrap">
          <pre class="preview-text">{{ previewData.content }}</pre>
        </div>

        <!-- Excel 表格 -->
        <div v-else-if="previewData.type === 'table'" class="preview-table-wrap">
          <a-tabs v-if="previewData.sheets">
            <a-tab-pane
              v-for="(rows, sheetName) in previewData.sheets"
              :key="sheetName"
              :tab="sheetName"
            >
              <div class="sheet-scroll">
                <table class="excel-table">
                  <thead>
                    <tr>
                      <th v-for="(cell, ci) in rows[0]" :key="ci">{{ cell }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, ri) in rows.slice(1)" :key="ri">
                      <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </a-tab-pane>
          </a-tabs>
        </div>
      </template>

      <div v-else class="preview-loading">
        <p>No preview available.</p>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onBeforeUnmount } from 'vue'
import { message } from 'ant-design-vue'
import {
  FileTextOutlined,
  ThunderboltOutlined,
  DeleteOutlined,
  EyeOutlined
} from '@ant-design/icons-vue'
import { formatDistanceToNow } from 'date-fns'
import type { Document } from '../../types/knowledge-base'
import { knowledgeBaseApi } from '../../apis/knowledgeBase'

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
const selectedRowKeys = ref<number[]>([])
const batchDeleting = ref(false)

const showPreviewModal = ref(false)
const previewLoading = ref(false)
const previewData = ref<{
  type: 'url' | 'text' | 'table'
  serve_url?: string
  content?: string
  sheets?: Record<string, string[][]>
  file_name: string
} | null>(null)
let _currentBlobUrl: string | null = null

const revokeBlobUrl = () => {
  if (_currentBlobUrl) {
    URL.revokeObjectURL(_currentBlobUrl)
    _currentBlobUrl = null
  }
}

watch(showPreviewModal, (open) => {
  if (!open) revokeBlobUrl()
})

onBeforeUnmount(revokeBlobUrl)

const rowSelection = {
  selectedRowKeys,
  onChange: (keys: number[]) => { selectedRowKeys.value = keys },
}

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
  try {
    const kb = await knowledgeBaseApi.getKnowledgeBase(props.knowledgeBaseId)
    documents.value = kb.documents
  } catch (err: any) {
    error.value = err.response?.data?.message || 'Failed to load documents'
  } finally {
    loading.value = false
  }
}

const handleDelete = async (document: Document) => {
  try {
    await knowledgeBaseApi.deleteDocument(props.knowledgeBaseId, document.id)
    message.success('Document deleted successfully')
    emit('documentDeleted', document)
    await fetchDocuments()
  } catch (err: any) {
    message.error(err.response?.data?.message || 'Failed to delete document')
  }
}

const handleBatchDelete = async () => {
  if (selectedRowKeys.value.length === 0) return
  batchDeleting.value = true
  const ids = [...selectedRowKeys.value]
  try {
    const results = await Promise.allSettled(
      ids.map(id => knowledgeBaseApi.deleteDocument(props.knowledgeBaseId, id))
    )
    const failed = results.filter(r => r.status === 'rejected').length
    const succeeded = ids.length - failed
    if (failed === 0) {
      message.success(`${succeeded} document(s) deleted`)
    } else {
      message.warning(`${succeeded} deleted, ${failed} failed`)
    }
    selectedRowKeys.value = []
    await fetchDocuments()
  } finally {
    batchDeleting.value = false
  }
}

const handleView = async (document: Document) => {
  revokeBlobUrl()
  showPreviewModal.value = true
  previewLoading.value = true
  previewData.value = null
  try {
    const preview = await knowledgeBaseApi.previewDocument(props.knowledgeBaseId, document.id)
    if (preview.type === 'url' && preview.serve_url) {
      // Fetch PDF as blob to bypass URL-encoding issues with special characters
      const resp = await fetch(preview.serve_url)
      if (!resp.ok) throw new Error(`Failed to fetch file: ${resp.status}`)
      const blob = await resp.blob()
      _currentBlobUrl = URL.createObjectURL(blob)
      previewData.value = { ...preview, serve_url: _currentBlobUrl }
    } else {
      previewData.value = preview
    }
  } catch (err: any) {
    message.error(err?.message || err?.response?.data?.message || 'Failed to load preview')
    showPreviewModal.value = false
  } finally {
    previewLoading.value = false
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
  background: var(--bg-primary);
  border-radius: 8px;
}

.batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  margin-bottom: 10px;
  border-radius: 10px;
  background: linear-gradient(135deg,
    color-mix(in srgb, var(--link-color) 10%, var(--bg-primary)),
    color-mix(in srgb, var(--link-color) 5%, var(--bg-primary))
  );
  border: 1px solid color-mix(in srgb, var(--link-color) 25%, transparent);
  box-shadow: 0 2px 8px color-mix(in srgb, var(--link-color) 12%, transparent);
  animation: toolbar-in 0.2s ease;
}

@keyframes toolbar-in {
  from { opacity: 0; transform: translateY(-6px); }
  to   { opacity: 1; transform: translateY(0); }
}

.batch-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.batch-count-badge {
  min-width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--link-color);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
}

.batch-info {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.batch-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.batch-cancel-btn {
  border-radius: 6px !important;
  color: var(--text-secondary) !important;
  border-color: var(--border-color) !important;
}

.batch-delete-btn {
  border-radius: 6px !important;
  background: #ef4444 !important;
  border-color: #ef4444 !important;
  color: #fff !important;
}

.batch-delete-btn:hover {
  background: #dc2626 !important;
  border-color: #dc2626 !important;
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
.loading-text { color: var(--text-secondary); font-size: 14px; margin: 0; }
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
  background-color: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}
.empty-icon { font-size: 32px; color: var(--text-tertiary); }
.empty-title { font-size: 20px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.empty-description { color: var(--text-secondary); font-size: 14px; max-width: 400px; margin: 0; }

/* 列表内元素样式 */
.document-name { display: flex; align-items: center; gap: 12px; }
.font-medium { font-weight: 500; color: var(--text-primary); }
.text-gray-600 { color: var(--text-secondary); }
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

.btn-view {
  color: #16a34a !important;
}
.btn-view:hover {
  color: #15803d !important;
}

/* 预览弹框 */
.preview-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  color: var(--text-secondary);
}

.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
  display: block;
  flex: 1;
}

.preview-text-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  background: var(--bg-secondary);
}

.preview-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-primary);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.preview-table-wrap {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0 16px 16px;
}

.sheet-scroll {
  overflow: auto;
  flex: 1;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.excel-table {
  border-collapse: collapse;
  width: max-content;
  min-width: 100%;
  font-size: 13px;
}

.excel-table th {
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 600;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
}

.excel-table td {
  padding: 7px 12px;
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  white-space: nowrap;
}

.excel-table tr:hover td {
  background: var(--hover-bg);
}

/* 优化 Ant Design Table 的默认边框和背景 */
:deep(.ant-table-thead > tr > th) {
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 500;
  border-bottom: 1px solid var(--border-color);
}
:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid var(--border-color);
}
</style>