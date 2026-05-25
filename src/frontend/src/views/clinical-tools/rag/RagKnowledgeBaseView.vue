<template>
  <div class="rag-knowledge-base-container">
    <!-- ==================== 顶部 Hero 横幅 ==================== -->
    <div class="kb-hero">
      <div class="hero-decor hero-decor-1"></div>
      <div class="hero-decor hero-decor-2"></div>
      <div class="hero-inner">
        <div class="hero-text">
          <div class="hero-icon-wrap">📚</div>
          <div>
            <h1 class="hero-title">{{ t('views_RagKnowledgeBaseView.title') }}</h1>
            <p class="hero-subtitle">{{ t('views_RagKnowledgeBaseView.subtitle') }}</p>
          </div>
        </div>
        <div class="hero-action">
          <a-button class="create-btn" @click="handleCreateKnowledgeBase">
            <template #icon><PlusOutlined /></template>
            {{ t('views_RagKnowledgeBaseView.createKnowledgeBase') }}
          </a-button>
        </div>
      </div>
    </div>

    <!-- ==================== 主内容区 ==================== -->
    <div class="kb-body">

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
            <span v-if="kb.documents.length > 3" class="documents-more" @click="openDrawer(kb)">
              +{{ kb.documents.length - 3 }} more
            </span>
          </div>
          <div v-if="kb.documents.length === 0" class="documents-empty">No documents yet</div>
          <div v-else class="documents-list">
            <div
              v-for="doc in kb.documents.slice(0, 3)"
              :key="doc.id"
              class="document-row"
              @click="openDrawer(kb)"
            >
              <FileTextOutlined class="document-row-icon" />
              <span class="document-row-name">{{ doc.file_name }}</span>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <a-button block @click="handleViewKnowledgeBase(kb)">View Details</a-button>
        </div>
      </div>
    </div>

    </div><!-- end kb-body -->

    <!-- ==================== 知识库详情抽屉 ==================== -->
    <a-drawer
      v-model:open="drawerVisible"
      :title="selectedKb?.name || '知识库详情'"
      placement="right"
      :width="620"
      :body-style="{ padding: '0', display: 'flex', flexDirection: 'column', height: '100%' }"
      @close="closeDrawer"
    >
      <a-tabs v-model:activeKey="drawerTab" class="drawer-tabs">
        <!-- ===== 文档管理 tab ===== -->
        <a-tab-pane key="docs" tab="文档管理">
          <div class="drawer-section">
            <!-- 上传区 -->
            <a-upload
              :show-upload-list="false"
              :custom-request="handleDrawerUpload"
              multiple
              accept=".pdf,.doc,.docx,.xls,.xlsx,.txt"
            >
              <a-button type="dashed" block style="margin-bottom: 16px">
                <template #icon><UploadOutlined /></template>
                上传文档（PDF / Word / Excel / TXT）
              </a-button>
            </a-upload>

            <!-- 文档列表 -->
            <a-spin :spinning="drawerDocsLoading">
              <div v-if="!selectedKb || selectedKb.documents.length === 0" class="drawer-empty">
                暂无文档，请先上传
              </div>
              <div v-else class="drawer-doc-list">
                <div
                  v-for="doc in selectedKb.documents"
                  :key="doc.id"
                  class="drawer-doc-row"
                >
                  <FileTextOutlined class="ddoc-icon" />
                  <div class="ddoc-info">
                    <span class="ddoc-name">{{ doc.file_name }}</span>
                    <span
                      v-if="doc.processing_tasks?.length"
                      :class="['ddoc-status', `status-${doc.processing_tasks[0].status}`]"
                    >{{ doc.processing_tasks[0].status }}</span>
                  </div>
                  <div class="ddoc-actions">
                    <a-button
                      size="small"
                      :loading="analyzingId === doc.id"
                      @click="handleAnalyzeDoc(doc)"
                    >Analyze</a-button>
                    <a-popconfirm
                      title="确认删除该文档？"
                      ok-text="删除"
                      cancel-text="取消"
                      @confirm="handleDeleteDoc(doc)"
                    >
                      <a-button size="small" danger :loading="deletingDocId === doc.id">删除</a-button>
                    </a-popconfirm>
                  </div>
                </div>
              </div>
            </a-spin>
          </div>
        </a-tab-pane>

        <!-- ===== 语义检索 tab ===== -->
        <a-tab-pane key="search" tab="语义检索">
          <div class="drawer-section">
            <a-input-search
              v-model:value="searchQuery"
              placeholder="输入临床问题，语义检索最相关片段…"
              size="large"
              :loading="searchLoading"
              enter-button="检索"
              @search="handleSearch"
            />
            <div v-if="searchResults.length === 0 && !searchLoading" class="drawer-empty" style="margin-top: 24px">
              {{ searchHasSearched ? '未找到相关内容' : '输入问题后点击检索' }}
            </div>
            <div class="search-results">
              <div
                v-for="(result, idx) in searchResults"
                :key="idx"
                class="search-result-card"
              >
                <div class="result-meta">
                  <span class="result-source">{{ result.file_name || '未知来源' }}</span>
                  <span class="result-score">相关度 {{ Math.round((result.score ?? 0) * 100) }}%</span>
                </div>
                <p class="result-content">{{ result.content }}</p>
              </div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-drawer>

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
  FileTextOutlined,
  UploadOutlined
} from '@ant-design/icons-vue'
import type { KnowledgeBase, Document } from '../../../types/knowledge-base'
import { knowledgeBaseApi, type SearchResult } from '../../../apis/knowledgeBase'

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

// ==================== 抽屉状态 ====================
const drawerVisible = ref(false)
const drawerTab = ref<'docs' | 'search'>('docs')
const selectedKb = ref<KnowledgeBase | null>(null)
const drawerDocsLoading = ref(false)
const analyzingId = ref<number | null>(null)
const deletingDocId = ref<number | null>(null)

const searchQuery = ref('')
const searchLoading = ref(false)
const searchResults = ref<SearchResult[]>([])
const searchHasSearched = ref(false)

const openDrawer = async (kb: KnowledgeBase) => {
  selectedKb.value = kb
  drawerTab.value = 'docs'
  searchQuery.value = ''
  searchResults.value = []
  searchHasSearched.value = false
  drawerVisible.value = true
  drawerDocsLoading.value = true
  try {
    const fresh = await knowledgeBaseApi.getKnowledgeBase(kb.id)
    selectedKb.value = fresh
    const idx = knowledgeBases.value.findIndex(k => k.id === kb.id)
    if (idx !== -1) knowledgeBases.value[idx] = fresh
  } catch {
    message.error('加载知识库详情失败')
  } finally {
    drawerDocsLoading.value = false
  }
}

const closeDrawer = () => {
  drawerVisible.value = false
  selectedKb.value = null
}

const handleDrawerUpload = async ({ file, onSuccess, onError }: any) => {
  if (!selectedKb.value) return
  const formData = new FormData()
  formData.append('files', file)
  drawerDocsLoading.value = true
  try {
    await knowledgeBaseApi.uploadDocuments(selectedKb.value.id, formData)
    onSuccess({})
    message.success(`上传成功: ${file.name}`)
    const fresh = await knowledgeBaseApi.getKnowledgeBase(selectedKb.value.id)
    selectedKb.value = fresh
    const idx = knowledgeBases.value.findIndex(k => k.id === fresh.id)
    if (idx !== -1) knowledgeBases.value[idx] = fresh
  } catch (e) {
    onError(e)
    message.error('上传失败')
  } finally {
    drawerDocsLoading.value = false
  }
}

const handleAnalyzeDoc = async (doc: Document) => {
  if (!selectedKb.value) return
  analyzingId.value = doc.id
  try {
    await knowledgeBaseApi.analyzeDocument(selectedKb.value.id, doc.id)
    message.success(`${doc.file_name} 分析完成`)
    const fresh = await knowledgeBaseApi.getKnowledgeBase(selectedKb.value.id)
    selectedKb.value = fresh
  } catch {
    message.error('分析失败')
  } finally {
    analyzingId.value = null
  }
}

const handleDeleteDoc = async (doc: Document) => {
  if (!selectedKb.value) return
  deletingDocId.value = doc.id
  try {
    await knowledgeBaseApi.deleteDocument(selectedKb.value.id, doc.id)
    message.success('已删除')
    if (selectedKb.value) {
      selectedKb.value.documents = selectedKb.value.documents.filter(d => d.id !== doc.id)
      const idx = knowledgeBases.value.findIndex(k => k.id === selectedKb.value!.id)
      if (idx !== -1) knowledgeBases.value[idx] = { ...selectedKb.value }
    }
  } catch {
    message.error('删除失败')
  } finally {
    deletingDocId.value = null
  }
}

const handleSearch = async (val: string) => {
  if (!selectedKb.value || !val.trim()) return
  searchLoading.value = true
  searchHasSearched.value = true
  searchResults.value = []
  try {
    searchResults.value = await knowledgeBaseApi.searchKnowledgeBase(selectedKb.value.id, val.trim())
  } catch {
    message.error('检索失败')
  } finally {
    searchLoading.value = false
  }
}

onMounted(() => {
  fetchKnowledgeBases()
})
</script>

<style scoped>
.rag-knowledge-base-container {
  min-height: 100%;
  background: var(--bg-secondary);
}

/* ==================== Hero 横幅 ==================== */
.kb-hero {
  position: relative;
  background: linear-gradient(135deg, #0c2d20 0%, #0a5540 55%, #0d8a6a 100%);
  padding: 44px 32px 40px;
  overflow: hidden;
}

.hero-decor {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.hero-decor-1 {
  width: 320px;
  height: 320px;
  background: #fff;
  opacity: 0.07;
  top: -100px;
  left: 40px;
}

.hero-decor-2 {
  width: 240px;
  height: 240px;
  background: #a8ffdc;
  opacity: 0.1;
  bottom: -80px;
  right: 100px;
}

.hero-inner {
  position: relative;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 40px;
  flex-wrap: wrap;
}

.hero-text {
  display: flex;
  align-items: center;
  gap: 18px;
  flex: 1;
  min-width: 0;
}

.hero-icon-wrap {
  font-size: 40px;
  width: 64px;
  height: 64px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.18);
}

.hero-title {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 6px 0;
  letter-spacing: -0.3px;
}

.hero-subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.65);
  margin: 0;
  line-height: 1.5;
}

.hero-action {
  flex-shrink: 0;
}

.create-btn {
  height: 40px;
  padding: 0 22px;
  font-size: 14px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
  color: #fff;
  border-radius: 10px;
}

.create-btn:hover {
  background: rgba(255, 255, 255, 0.26) !important;
  border-color: rgba(255, 255, 255, 0.55) !important;
  color: #fff !important;
}

/* ==================== 主内容区 ==================== */
.kb-body {
  max-width: 1400px;
  margin: 0 auto;
  padding: 32px;
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
  .kb-hero {
    padding: 32px 20px 28px;
  }

  .hero-inner {
    flex-direction: column;
    gap: 20px;
    align-items: flex-start;
  }

  .hero-icon-wrap {
    width: 52px;
    height: 52px;
    font-size: 32px;
  }

  .hero-title {
    font-size: 22px;
  }

  .kb-body {
    padding: 24px 20px;
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

/* ==================== 抽屉样式 ==================== */
.drawer-tabs :deep(.ant-tabs-nav) {
  padding: 0 20px;
  margin-bottom: 0;
}

.drawer-section {
  padding: 20px;
  overflow-y: auto;
  max-height: calc(100vh - 120px);
}

.drawer-empty {
  text-align: center;
  color: var(--text-secondary);
  font-size: 14px;
  padding: 40px 0;
}

/* 文档行 */
.drawer-doc-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.drawer-doc-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.ddoc-icon {
  font-size: 16px;
  color: var(--link-color);
  flex-shrink: 0;
}

.ddoc-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ddoc-name {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ddoc-status {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  width: fit-content;
}

.status-completed { background: rgba(82,196,26,.12); color: #52c41a; }
.status-processing { background: rgba(24,144,255,.12); color: #1890ff; }
.status-pending   { background: rgba(250,173,20,.12); color: #faad14; }
.status-error     { background: rgba(255,77,79,.12);  color: #ff4d4f; }

.ddoc-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

/* 检索结果 */
.search-results {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-result-card {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 14px 16px;
  background: var(--bg-primary);
}

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.result-source {
  font-size: 12px;
  color: var(--link-color);
  font-weight: 500;
}

.result-score {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 10px;
}

.result-content {
  margin: 0;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
