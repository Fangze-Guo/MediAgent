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
          <div class="documents-header">
            <h4 class="documents-title">Recent Documents</h4>
            <span v-if="kb.documents.length > 3" class="documents-more" @click="handleViewKnowledgeBase(kb)">
              +{{ kb.documents.length - 3 }} more
            </span>
          </div>
          <div v-if="kb.documents.length === 0" class="documents-empty">No documents yet</div>
          <div v-else class="documents-list">
            <div
              v-for="doc in kb.documents.slice(0, 3)"
              :key="doc.id"
              class="document-row"
              @click="handleViewDocument(kb, doc)"
            >
              <FileTextOutlined class="document-row-icon" />
              <span class="document-row-name">{{ doc.file_name }}</span>
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
import type { KnowledgeBase, Document } from '../../../types/knowledge-base'
import { knowledgeBaseApi } from '../../../apis/knowledgeBase'

const { t } = useI18n()
const router = useRouter()

const loading = ref(true)
const isLoading = ref(false)
const error = ref<string | null>(null)
const knowledgeBases = ref<KnowledgeBase[]>([])

const createModalVisible = ref(false)
const editingKnowledgeBase = ref<KnowledgeBase | null>(null)

const knowledgeBaseForm = ref({
  name: '',
  description: ''
})

const fetchKnowledgeBases = async () => {
  loading.value = true
  error.value = null
  try {
    knowledgeBases.value = await knowledgeBaseApi.getKnowledgeBases()
  } catch (err: any) {
    error.value = err.response?.data?.message || 'Failed to load knowledge bases'
  } finally {
    loading.value = false
  }
}

const handleCreateKnowledgeBase = () => {
  editingKnowledgeBase.value = null
  knowledgeBaseForm.value = { name: '', description: '' }
  createModalVisible.value = true
}

const handleSubmitKnowledgeBase = async () => {
  if (!knowledgeBaseForm.value.name) {
    message.error('Please enter a name')
    return
  }
  isLoading.value = true
  try {
    if (editingKnowledgeBase.value) {
      const updated = await knowledgeBaseApi.updateKnowledgeBase(editingKnowledgeBase.value.id, {
        name: knowledgeBaseForm.value.name,
        description: knowledgeBaseForm.value.description,
      })
      const index = knowledgeBases.value.findIndex(kb => kb.id === editingKnowledgeBase.value!.id)
      if (index !== -1) knowledgeBases.value[index] = updated
      message.success('Knowledge base updated successfully')
    } else {
      const newKb = await knowledgeBaseApi.createKnowledgeBase({
        name: knowledgeBaseForm.value.name,
        description: knowledgeBaseForm.value.description,
      })
      knowledgeBases.value.push(newKb)
      message.success('Knowledge base created successfully')
    }
    createModalVisible.value = false
  } catch (err: any) {
    message.error(err.response?.data?.message || 'Operation failed')
  } finally {
    isLoading.value = false
  }
}

const handleEdit = (kb: KnowledgeBase) => {
  editingKnowledgeBase.value = kb
  knowledgeBaseForm.value = { name: kb.name, description: kb.description || '' }
  createModalVisible.value = true
}

const handleCancelKnowledgeBase = () => {
  createModalVisible.value = false
  editingKnowledgeBase.value = null
}

const handleDelete = async (kb: KnowledgeBase) => {
  try {
    await knowledgeBaseApi.deleteKnowledgeBase(kb.id)
    knowledgeBases.value = knowledgeBases.value.filter(item => item.id !== kb.id)
    message.success('Knowledge base deleted successfully')
  } catch (err: any) {
    message.error(err.response?.data?.message || 'Failed to delete knowledge base')
  }
}

const handleViewKnowledgeBase = (kb: KnowledgeBase) => {
  router.push(`/knowledge-base/${kb.id}`)
}

const handleViewDocument = (kb: KnowledgeBase, doc: Document) => {
  router.push(`/knowledge-base/${kb.id}/document/${doc.id}`)
}

onMounted(() => {
  fetchKnowledgeBases()
})
</script>

<style scoped>
.rag-knowledge-base-container {
  padding: 24px;
  min-height: 100vh;
  background: var(--bg-secondary);
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
  color: var(--text-primary);
}

.page-subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
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
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 64px;
  color: var(--border-color);
  margin-bottom: 16px;
}

.empty-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 500;
  color: var(--text-primary);
}

.empty-description {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
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
  background: var(--bg-primary);
  border-radius: 12px;
  padding: 24px;
  border: 1px solid var(--border-color);
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.knowledge-base-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border-color: var(--link-color);
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
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-description {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
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
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  font-size: 20px;
  color: var(--link-color);
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 文档部分 */
.card-documents {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.documents-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.documents-title {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.documents-more {
  font-size: 12px;
  color: var(--link-color);
  cursor: pointer;
  flex-shrink: 0;
}

.documents-more:hover {
  text-decoration: underline;
}

.documents-empty {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 8px 0;
}

.documents-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.document-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--bg-secondary);
  cursor: pointer;
  transition: background 0.15s ease;
  min-width: 0;
}

.document-row:hover {
  background: color-mix(in srgb, var(--link-color) 10%, transparent);
}

.document-row-icon {
  font-size: 14px;
  color: var(--link-color);
  flex-shrink: 0;
}

.document-row-name {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
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
