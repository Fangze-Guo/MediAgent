<template>
  <div class="knowledge-base-detail-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <a-button type="text" @click="handleGoBack">
          <template #icon>
            <ArrowLeftOutlined />
          </template>
          Back
        </a-button>
        <div>
          <h2 class="page-title">
            <DatabaseOutlined />
            {{ knowledgeBase?.name }}
          </h2>
          <p class="page-subtitle">{{ knowledgeBase?.description || 'No description' }}</p>
        </div>
      </div>
      <a-space>
        <a-button @click="handleEditKnowledgeBase">
          <template #icon>
            <EditOutlined />
          </template>
          Edit
        </a-button>
        <a-button type="primary" @click="showUploadModal = true">
          <template #icon>
            <UploadOutlined />
          </template>
          Upload Documents
        </a-button>
      </a-space>
    </div>

    <!-- 统计信息 -->
    <div class="stats-container">
      <div class="stat-card">
        <FileTextOutlined class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ knowledgeBase?.document_count || 0 }}</span>
          <span class="stat-label">Documents</span>
        </div>
      </div>
      <div class="stat-card">
        <DatabaseOutlined class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ knowledgeBase?.chunk_count || 0 }}</span>
          <span class="stat-label">Chunks</span>
        </div>
      </div>
      <div class="stat-card">
        <ClockCircleOutlined class="stat-icon" />
        <div class="stat-content">
          <span class="stat-value">{{ formatDate(knowledgeBase?.updated_at) }}</span>
          <span class="stat-label">Last Updated</span>
        </div>
      </div>
    </div>

    <!-- 文档列表 -->
    <div class="documents-section">
      <div class="section-header">
        <h3 class="section-title">
          <FileTextOutlined />
          Documents
        </h3>
        <a-button type="link" @click="handleRefresh">
          <template #icon>
            <ReloadOutlined />
          </template>
          Refresh
        </a-button>
      </div>

      <DocumentList :knowledge-base-id="knowledgeBaseId" :refresh-key="refreshKey" />
    </div>

    <!-- 文档上传模态框 -->
    <a-modal
      v-model:open="showUploadModal"
      title="Upload Documents"
      :footer="null"
      width="800px"
    >
      <DocumentUploadSteps :knowledge-base-id="knowledgeBaseId" @complete="handleUploadComplete" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  DatabaseOutlined,
  ArrowLeftOutlined,
  EditOutlined,
  UploadOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'
import type { KnowledgeBase } from '../types/knowledge-base'
import DocumentList from '../components/knowledge-base/DocumentList.vue'
import DocumentUploadSteps from '../components/knowledge-base/DocumentUploadSteps.vue'

const route = useRoute()
const router = useRouter()
const knowledgeBaseId = Number(route.params.id)

// 状态管理
const knowledgeBase = ref<KnowledgeBase | null>(null)
const loading = ref(true)
const showUploadModal = ref(false)
const refreshKey = ref(0)

// 返回上一页
const handleGoBack = () => {
  router.back()
}

// 编辑知识库
const handleEditKnowledgeBase = () => {
  message.info('Edit functionality coming soon')
}

// 刷新列表
const handleRefresh = () => {
  refreshKey.value++
  message.success('Documents refreshed')
}

// 上传完成
const handleUploadComplete = () => {
  showUploadModal.value = false
  refreshKey.value++
  message.success('Documents uploaded successfully')
}

// 格式化日期
const formatDate = (dateString?: string): string => {
  if (!dateString) return 'Unknown'
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`

  return date.toLocaleDateString()
}

// 获取知识库详情（静态演示数据）
const fetchKnowledgeBase = async () => {
  loading.value = true

  // 模拟API延迟
  await new Promise(resolve => setTimeout(resolve, 500))

  // 静态演示数据
  knowledgeBase.value = {
    id: knowledgeBaseId,
    name: '医学文献知识库',
    description: '包含最新的医学研究文献、临床试验报告和医学期刊文章，涵盖心血管疾病、糖尿病、肿瘤等多个领域。',
    documents: [],
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-03-20T14:22:00Z',
    document_count: 128,
    chunk_count: 15240
  }

  loading.value = false
}

// 初始化
onMounted(() => {
  fetchKnowledgeBase()
})
</script>

<style scoped>
.knowledge-base-detail-container {
  padding: 24px;
  min-height: 100vh;
  background: #f5f5f5;
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
  color: #1a1a1a;
}

.page-subtitle {
  margin: 0;
  font-size: 14px;
  color: #666;
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
  background: white;
  border-radius: 12px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  border: 1px solid #e8e8e8;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s ease;
}

.stat-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.stat-icon {
  font-size: 32px;
  color: #1890ff;
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-value {
  font-size: 24px;
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

/* 文档区域 */
.documents-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid #e8e8e8;
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
  color: #1a1a1a;
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
