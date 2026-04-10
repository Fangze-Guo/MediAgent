<template>
  <div class="rag-knowledge-base-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">
          <DatabaseOutlined />
          {{ t('views_RagKnowledgeBaseView.title') }}
        </h2>
        <p class="page-subtitle">{{ t('views_RagKnowledgeBaseView.subtitle') }}</p>
      </div>
      <a-button type="primary" @click="handleCreateKnowledgeBase">
        <template #icon>
          <PlusOutlined />
        </template>
        {{ t('views_RagKnowledgeBaseView.createKnowledgeBase') }}
      </a-button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
      <p class="loading-text">{{ t('views_RagKnowledgeBaseView.loading') }}</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-container">
      <a-alert type="error" :message="error" show-icon />
    </div>

    <!-- 空状态 -->
    <div v-else-if="knowledgeBases.length === 0" class="empty-container">
      <DatabaseOutlined class="empty-icon" />
      <h3 class="empty-title">{{ t('views_RagKnowledgeBaseView.emptyTitle') }}</h3>
      <p class="empty-description">{{ t('views_RagKnowledgeBaseView.emptyDescription') }}</p>
    </div>

    <!-- 知识库网格 -->
    <div v-else class="knowledge-bases-grid">
      <div
        v-for="kb in knowledgeBases"
        :key="kb.id"
        class="knowledge-base-card"
      >
        <div class="card-header">
          <div class="card-title-section">
            <h3 class="card-title">{{ kb.name }}</h3>
            <p class="card-description">{{ kb.description || 'No description' }}</p>
          </div>
          <div class="card-actions">
            <a-button type="text" size="small" @click="handleEdit(kb)">
              Edit
            </a-button>
            <a-popconfirm
              title="Are you sure you want to delete this knowledge base?"
              @confirm="handleDelete(kb)"
            >
              <a-button type="text" danger size="small">
                Delete
              </a-button>
            </a-popconfirm>
          </div>
        </div>

        <div class="card-stats">
          <div class="stat-item">
            <FileTextOutlined class="stat-icon" />
            <div class="stat-content">
              <span class="stat-value">{{ kb.document_count || kb.documents.length }}</span>
              <span class="stat-label">Documents</span>
            </div>
          </div>
          <div class="stat-item">
            <DatabaseOutlined class="stat-icon" />
            <div class="stat-content">
              <span class="stat-value">{{ kb.chunk_count || 0 }}</span>
              <span class="stat-label">Chunks</span>
            </div>
          </div>
        </div>

        <div class="card-documents">
          <h4 class="documents-title">Recent Documents</h4>
          <div class="documents-grid">
            <div
              v-for="doc in kb.documents.slice(0, 5)"
              :key="doc.id"
              class="document-item"
              @click="handleViewDocument(kb, doc)"
            >
              <FileTextOutlined class="document-icon" />
              <span class="document-name">{{ doc.file_name }}</span>
            </div>
            <div
              v-if="kb.documents.length > 5"
              class="document-item view-all"
              @click="handleViewKnowledgeBase(kb)"
            >
              <span class="document-count">+{{ kb.documents.length - 5 }}</span>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <a-button block @click="handleViewKnowledgeBase(kb)">
            View Details
          </a-button>
        </div>
      </div>
    </div>

    <!-- 创建/编辑知识库模态框 -->
    <a-modal
      v-model:open="createModalVisible"
      :title="editingKnowledgeBase ? t('views_RagKnowledgeBaseView.editKnowledgeBase') : t('views_RagKnowledgeBaseView.createKnowledgeBase')"
      :confirm-loading="isLoading"
      @ok="handleSubmitKnowledgeBase"
      @cancel="handleCancelKnowledgeBase"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('views_RagKnowledgeBaseView.name')">
          <a-input
            v-model:value="knowledgeBaseForm.name"
            :placeholder="t('views_RagKnowledgeBaseView.namePlaceholder')"
          />
        </a-form-item>
        <a-form-item :label="t('views_RagKnowledgeBaseView.description')">
          <a-textarea
            v-model:value="knowledgeBaseForm.description"
            :placeholder="t('views_RagKnowledgeBaseView.descriptionPlaceholder')"
            :rows="4"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  DatabaseOutlined,
  PlusOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'
import type { KnowledgeBase, Document } from '../types/knowledge-base'

const { t } = useI18n()
const router = useRouter()

// 状态管理
const loading = ref(true)
const isLoading = ref(false)
const error = ref<string | null>(null)
const knowledgeBases = ref<KnowledgeBase[]>([])

// 模态框状态
const createModalVisible = ref(false)
const editingKnowledgeBase = ref<KnowledgeBase | null>(null)

// 表单数据
const knowledgeBaseForm = ref({
  name: '',
  description: ''
})

// 获取知识库列表（静态演示数据）
const fetchKnowledgeBases = async () => {
  loading.value = true
  error.value = null

  // 模拟API延迟
  await new Promise(resolve => setTimeout(resolve, 500))

  // 静态演示数据
  knowledgeBases.value = [
    {
      id: 1,
      name: '医学文献知识库',
      description: '包含最新的医学研究文献、临床试验报告和医学期刊文章',
      created_at: '2024-01-15T10:30:00Z',
      updated_at: '2024-03-20T14:22:00Z',
      document_count: 128,
      chunk_count: 15240,
      documents: [
        {
          id: 1,
          file_name: '心血管疾病诊疗指南2024.pdf',
          file_path: '/uploads/cardio_guidelines_2024.pdf',
          file_size: 2458624,
          content_type: 'application/pdf',
          knowledge_base_id: 1,
          created_at: '2024-03-15T10:30:00Z',
          updated_at: '2024-03-20T14:22:00Z',
          processing_tasks: []
        },
        {
          id: 2,
          file_name: '糖尿病管理手册.docx',
          file_path: '/uploads/diabetes_manual.docx',
          file_size: 1524288,
          content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          knowledge_base_id: 1,
          created_at: '2024-03-18T09:15:00Z',
          updated_at: '2024-03-19T11:45:00Z',
          processing_tasks: []
        }
      ]
    },
    {
      id: 2,
      name: '临床指南库',
      description: '各种疾病的临床诊断和治疗指南，包括国际标准和本地化建议',
      created_at: '2024-02-01T09:15:00Z',
      updated_at: '2024-03-18T11:45:00Z',
      document_count: 56,
      chunk_count: 8340,
      documents: [
        {
          id: 3,
          file_name: '高血压治疗方案.txt',
          file_path: '/uploads/hypertension_treatment.txt',
          file_size: 45678,
          content_type: 'text/plain',
          knowledge_base_id: 2,
          created_at: '2024-03-20T16:00:00Z',
          updated_at: '2024-03-20T16:05:00Z',
          processing_tasks: []
        }
      ]
    },
    {
      id: 3,
      name: '药物数据库',
      description: '药品说明书、药物相互作用、副作用和用法用量信息',
      created_at: '2024-02-20T16:00:00Z',
      updated_at: '2024-03-19T13:30:00Z',
      document_count: 234,
      chunk_count: 35100,
      documents: []
    }
  ]

  loading.value = false
}

// 创建知识库
const handleCreateKnowledgeBase = () => {
  editingKnowledgeBase.value = null
  knowledgeBaseForm.value = {
    name: '',
    description: ''
  }
  createModalVisible.value = true
}

// 提交知识库表单（静态演示）
const handleSubmitKnowledgeBase = async () => {
  if (!knowledgeBaseForm.value.name) {
    message.error('Please enter a name')
    return
  }

  isLoading.value = true

  // 模拟API延迟
  await new Promise(resolve => setTimeout(resolve, 500))

  if (editingKnowledgeBase.value) {
    // 编辑现有知识库
    const index = knowledgeBases.value.findIndex(kb => kb.id === editingKnowledgeBase.value!.id)
    if (index !== -1) {
      knowledgeBases.value[index] = {
        ...knowledgeBases.value[index],
        name: knowledgeBaseForm.value.name,
        description: knowledgeBaseForm.value.description,
        updated_at: new Date().toISOString()
      }
    }
    message.success('Knowledge base updated successfully')
  } else {
    // 创建新知识库
    const newKB: KnowledgeBase = {
      id: Date.now(),
      name: knowledgeBaseForm.value.name,
      description: knowledgeBaseForm.value.description,
      documents: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      document_count: 0,
      chunk_count: 0
    }

    knowledgeBases.value.push(newKB)
    message.success('Knowledge base created successfully')
  }

  isLoading.value = false
  createModalVisible.value = false
}

// 编辑知识库
const handleEdit = (kb: KnowledgeBase) => {
  editingKnowledgeBase.value = kb
  knowledgeBaseForm.value = {
    name: kb.name,
    description: kb.description || ''
  }
  createModalVisible.value = true
}

// 取消编辑
const handleCancelKnowledgeBase = () => {
  createModalVisible.value = false
  editingKnowledgeBase.value = null
}

// 删除知识库（静态演示）
const handleDelete = (kb: KnowledgeBase) => {
  // 静态演示：删除知识库
  knowledgeBases.value = knowledgeBases.value.filter(item => item.id !== kb.id)
  message.success('Knowledge base deleted successfully')
}

// 查看知识库详情
const handleViewKnowledgeBase = (kb: KnowledgeBase) => {
  router.push(`/knowledge-base/${kb.id}`)
}

// 测试检索
const handleTestRetrieval = (kb: KnowledgeBase) => {
  router.push(`/knowledge-base/${kb.id}/test`)
}

// 查看文档详情
const handleViewDocument = (kb: KnowledgeBase, doc: Document) => {
  router.push(`/knowledge-base/${kb.id}/document/${doc.id}`)
}

// 工具函数
const isPDF = (contentType: string): boolean => {
  return contentType.toLowerCase().includes('pdf')
}

const isWord = (contentType: string): boolean => {
  return contentType.toLowerCase().includes('word') ||
         contentType.toLowerCase().includes('docx')
}

const formatDate = (dateString: string): string => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`

  return date.toLocaleDateString()
}

// 初始化
onMounted(() => {
  fetchKnowledgeBases()
})
</script>

<style scoped>
.rag-knowledge-base-container {
  padding: 24px;
  min-height: 100vh;
  background: #f5f5f5;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 32px;
  gap: 16px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
}

.page-subtitle {
  margin: 0;
  font-size: 14px;
  color: #666;
  line-height: 1.5;
}

.loading-container,
.error-container,
.empty-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 48px;
  text-align: center;
}

.loading-text {
  margin-top: 16px;
  font-size: 14px;
  color: #666;
}

.empty-icon {
  font-size: 64px;
  color: #d9d9d9;
  margin-bottom: 16px;
}

.empty-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 500;
  color: #333;
}

.empty-description {
  margin: 0;
  font-size: 14px;
  color: #666;
  max-width: 400px;
  line-height: 1.5;
}

/* 知识库网格布局 */
.knowledge-bases-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 24px;
  margin-bottom: 24px;
}

/* 知识库卡片 */
.knowledge-base-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid #e8e8e8;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.knowledge-base-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border-color: #1890ff;
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.card-title-section {
  flex: 1;
  min-width: 0;
}

.card-title {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-description {
  margin: 0;
  font-size: 14px;
  color: #666;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.card-stats {
  display: flex;
  gap: 24px;
  padding: 16px 0;
  border-top: 1px solid #f0f0f0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  font-size: 20px;
  color: #1890ff;
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  line-height: 1;
}

.stat-label {
  font-size: 12px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 文档部分 */
.card-documents {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.documents-title {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.documents-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.document-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px 8px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fafafa;
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: 100px;
}

.document-item:hover {
  background: #f0f7ff;
  border-color: #1890ff;
}

.document-item.view-all {
  background: #e6f7ff;
  border-color: #1890ff;
}

.document-item.view-all:hover {
  background: #bae7ff;
}

.document-icon {
  font-size: 24px;
  color: #1890ff;
}

.document-name {
  font-size: 12px;
  color: #333;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
  line-height: 1.2;
}

.document-count {
  font-size: 10px;
  color: #666;
  font-weight: 500;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .rag-knowledge-base-container {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-title {
    font-size: 24px;
  }

  .knowledge-bases-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .card-stats {
    gap: 16px;
  }

  .documents-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 480px) {
  .documents-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .card-header {
    flex-direction: column;
  }

  .card-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
