<template>
  <div class="knowledge-base-detail-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <a-button type="text" @click="handleGoBack">
          <template #icon>
            <ArrowLeftOutlined />
          </template>
          {{ t('views_RagKnowledgeBaseDetailView.back') }}
        </a-button>
        <div>
          <h2 class="page-title">
            <DatabaseOutlined />
            {{ knowledgeBase?.name }}
          </h2>
          <p class="page-subtitle">{{ knowledgeBase?.description || t('views_RagKnowledgeBaseDetailView.noDescription') }}</p>
        </div>
      </div>
      <a-space>
        <a-button @click="handleEditKnowledgeBase">
          <template #icon>
            <EditOutlined />
          </template>
          {{ t('views_RagKnowledgeBaseDetailView.edit') }}
        </a-button>
        <a-button type="primary" @click="() => { uploadKey++; showUploadModal = true }">
          <template #icon>
            <UploadOutlined />
          </template>
          {{ t('views_RagKnowledgeBaseDetailView.uploadDocuments') }}
        </a-button>
        <!-- uploadKey increments on open to force fresh component state -->
      </a-space>
    </div>

    <!-- 统计信息 -->
    <div class="stats-container">
      <div class="stat-card">
        <FileTextOutlined class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ knowledgeBase?.document_count || 0 }}</span>
          <span class="stat-label">{{ t('views_RagKnowledgeBaseDetailView.statsDocuments') }}</span>
        </div>
      </div>
      <div class="stat-card">
        <DatabaseOutlined class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ knowledgeBase?.chunk_count || 0 }}</span>
          <span class="stat-label">{{ t('views_RagKnowledgeBaseDetailView.statsChunks') }}</span>
        </div>
      </div>
      <div class="stat-card">
        <ClockCircleOutlined class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ formatDate(knowledgeBase?.updated_at) }}</span>
          <span class="stat-label">{{ t('views_RagKnowledgeBaseDetailView.statsLastUpdated') }}</span>
        </div>
      </div>
    </div>

    <!-- 语义检索 -->
    <div class="search-section">
      <div class="section-header">
        <h3 class="section-title">
          <SearchOutlined />
          语义检索
        </h3>
      </div>
      <a-input-search
        v-model:value="searchQuery"
        placeholder="输入临床问题，语义检索最相关片段…"
        size="large"
        :loading="searchLoading"
        enter-button="检索"
        @search="handleSearch"
      />
      <div v-if="searchResults.length === 0 && !searchLoading" class="search-empty">
        {{ searchHasSearched ? '未找到相关内容' : '输入问题后点击检索' }}
      </div>
      <div v-else class="search-results">
        <div
          v-for="(result, idx) in searchResults"
          :key="idx"
          class="search-result-card"
        >
          <div class="result-meta" @click="toggleResult(idx)">
            <div class="result-meta-left">
              <span :class="['result-expand-icon', { expanded: expandedResults.has(idx) }]">›</span>
              <span class="result-index">#{{ idx + 1 }}</span>
              <span class="result-source">{{ result.file_name || '未知来源' }}</span>
            </div>
            <span class="result-score">相关度 {{ Math.round((result.score ?? 0) * 100) }}%</span>
          </div>
          <div v-if="expandedResults.has(idx)" class="result-body">
            <p class="result-content">{{ result.content }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 文档列表 -->
    <div class="documents-section">
      <div class="section-header">
        <h3 class="section-title">
          <FileTextOutlined />
          {{ t('views_RagKnowledgeBaseDetailView.docSection') }}
        </h3>
        <a-button type="link" @click="handleRefresh">
          <template #icon>
            <ReloadOutlined />
          </template>
          {{ t('views_RagKnowledgeBaseDetailView.refresh') }}
        </a-button>
      </div>

      <DocumentList :knowledge-base-id="knowledgeBaseId" :refresh-key="refreshKey" />
    </div>

    <!-- 文档上传模态框 -->
    <a-modal
      v-model:open="showUploadModal"
      :title="t('views_RagKnowledgeBaseDetailView.uploadDocumentsModal')"
      :footer="null"
      width="800px"
      :body-style="{ maxHeight: '72vh', overflowY: 'auto', padding: '24px' }"
    >
      <DocumentUploadSteps :key="uploadKey" :knowledge-base-id="knowledgeBaseId" @complete="handleUploadComplete" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  DatabaseOutlined,
  ArrowLeftOutlined,
  EditOutlined,
  UploadOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
  SearchOutlined
} from '@ant-design/icons-vue'
import type { KnowledgeBase } from '../../../types/knowledge-base'
import DocumentList from "@/components/knowledge-base/DocumentList.vue";
import DocumentUploadSteps from "@/components/knowledge-base/DocumentUploadSteps.vue";
import { knowledgeBaseApi, type SearchResult } from '../../../apis/knowledgeBase'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const knowledgeBaseId = Number(route.params.id)

const knowledgeBase = ref<KnowledgeBase | null>(null)
const loading = ref(true)
const showUploadModal = ref(false)
const refreshKey = ref(0)
const uploadKey = ref(0)

const handleGoBack = () => {
  router.back()
}

const handleEditKnowledgeBase = () => {
  message.info(t('views_RagKnowledgeBaseDetailView.editComingSoon'))
}

const handleRefresh = () => {
  refreshKey.value++
  fetchKnowledgeBase()
}

const handleUploadComplete = () => {
  showUploadModal.value = false
  refreshKey.value++
  fetchKnowledgeBase()
}

const formatDate = (dateString?: string): string => {
  if (!dateString) return t('views_RagKnowledgeBaseDetailView.unknown')
  const date = new Date(dateString)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return t('views_RagKnowledgeBaseDetailView.today')
  if (diffDays === 1) return t('views_RagKnowledgeBaseDetailView.yesterday')
  if (diffDays < 7) return t('views_RagKnowledgeBaseDetailView.daysAgo', { n: diffDays })
  return date.toLocaleDateString()
}

const searchQuery = ref('')
const searchLoading = ref(false)
const searchResults = ref<SearchResult[]>([])
const searchHasSearched = ref(false)
const expandedResults = ref(new Set<number>())

const toggleResult = (idx: number) => {
  if (expandedResults.value.has(idx)) {
    expandedResults.value.delete(idx)
  } else {
    expandedResults.value.add(idx)
  }
  expandedResults.value = new Set(expandedResults.value)
}

const handleSearch = async (val: string) => {
  if (!val.trim()) return
  searchLoading.value = true
  searchHasSearched.value = true
  searchResults.value = []
  try {
    const raw = await knowledgeBaseApi.searchKnowledgeBase(knowledgeBaseId, val.trim())
    const docs = knowledgeBase.value?.documents ?? []
    searchResults.value = raw.map(r => ({
      ...r,
      file_name: docs.find(d => d.id === r.doc_id)?.file_name,
    }))
    expandedResults.value = new Set()
  } catch {
    message.error('检索失败')
  } finally {
    searchLoading.value = false
  }
}

const fetchKnowledgeBase = async () => {
  loading.value = true
  try {
    knowledgeBase.value = await knowledgeBaseApi.getKnowledgeBase(knowledgeBaseId)
  } catch (err: any) {
    message.error(err.response?.data?.message || 'Failed to load knowledge base')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchKnowledgeBase()
})
</script>

<style scoped>
.knowledge-base-detail-container {
  padding: 24px;
  min-height: 100vh;
  background: var(--bg-secondary);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: flex-start;
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
  max-width: 600px;
}

/* 统计卡片 */
.stats-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--bg-primary);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s ease;
}

.stat-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.stat-icon {
  font-size: 32px;
  color: var(--link-color);
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-value {
  font-size: 24px;
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

/* 语义检索区 */
.search-section {
  background: var(--bg-primary);
  border-radius: 12px;
  padding: 24px;
  border: 1px solid var(--border-color);
  margin-bottom: 24px;
}

.search-empty {
  text-align: center;
  color: var(--text-secondary);
  font-size: 14px;
  padding: 32px 0;
}

.search-results {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-result-card {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-secondary);
  transition: box-shadow 0.2s;
}

.search-result-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 11px 14px;
  cursor: pointer;
  user-select: none;
}

.result-meta:hover {
  background: color-mix(in srgb, var(--link-color) 5%, transparent);
}

.result-meta-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.result-expand-icon {
  font-size: 16px;
  color: var(--text-secondary);
  transition: transform 0.2s;
  line-height: 1;
  flex-shrink: 0;
}

.result-expand-icon.expanded {
  transform: rotate(90deg);
}

.result-index {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.result-source {
  font-size: 13px;
  color: var(--link-color);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-score {
  font-size: 12px;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--link-color) 8%, transparent);
  padding: 2px 8px;
  border-radius: 10px;
  flex-shrink: 0;
}

.result-body {
  padding: 0 14px 12px;
  border-top: 1px solid var(--border-color);
}

.result-content {
  margin: 10px 0 0 0;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.7;
  white-space: pre-wrap;
}

/* 文档区域 */
.documents-section {
  background: var(--bg-primary);
  border-radius: 12px;
  padding: 24px;
  border: 1px solid var(--border-color);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .knowledge-base-detail-container {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-left {
    width: 100%;
  }

  .page-title {
    font-size: 24px;
  }

  .stats-container {
    grid-template-columns: 1fr;
  }

  .stat-card {
    padding: 16px;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
