<template>
  <div class="document-detail-container">
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
            <FileTextOutlined />
            {{ document?.file_name || 'Document Detail' }}
          </h2>
          <p class="page-subtitle">
            {{ knowledgeBase?.name || 'Knowledge Base' }} • {{ document?.file_size ? formatFileSize(document.file_size) : 'Unknown size' }}
          </p>
        </div>
      </div>
      <a-space>
        <a-button @click="handleAnalyze">
          <template #icon>
            <ThunderboltOutlined />
          </template>
          Analyze
        </a-button>
        <a-button @click="handleDownload">
          <template #icon>
            <DownloadOutlined />
          </template>
          Download
        </a-button>
        <a-popconfirm
          title="Are you sure you want to delete this document?"
          @confirm="handleDelete"
        >
          <a-button danger>
            <template #icon>
              <DeleteOutlined />
            </template>
            Delete
          </a-button>
        </a-popconfirm>
      </a-space>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
      <p class="loading-text">Loading document details...</p>
    </div>

    <!-- 内容区域 -->
    <div v-else-if="document" class="content-container">
      <!-- 文档信息卡片 -->
      <div class="info-card">
        <h3 class="card-title">Document Information</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">File Name:</span>
            <span class="info-value">{{ document.file_name }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">File Size:</span>
            <span class="info-value">{{ formatFileSize(document.file_size) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Content Type:</span>
            <span class="info-value">{{ document.content_type }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Uploaded:</span>
            <span class="info-value">{{ formatDate(document.created_at) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Last Updated:</span>
            <span class="info-value">{{ formatDate(document.updated_at) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Status:</span>
            <a-tag
              v-if="document.processing_tasks && document.processing_tasks.length > 0"
              :color="getStatusColor(document.processing_tasks[0].status)"
              class="status-tag"
            >
              {{ document.processing_tasks[0].status.toUpperCase() }}
            </a-tag>
          </div>
        </div>
      </div>

      <!-- PDF预览区域 -->
      <div class="preview-card">
        <div class="preview-header">
          <h3 class="card-title">
            <FilePdfOutlined />
            Document Preview
          </h3>
          <a-space>
            <a-button
              :type="previewMode === 'pdf' ? 'primary' : 'default'"
              size="small"
              @click="previewMode = 'pdf'"
            >
              PDF View
            </a-button>
            <a-button
              :type="previewMode === 'chunks' ? 'primary' : 'default'"
              size="small"
              @click="previewMode = 'chunks'"
            >
              Chunks View
            </a-button>
          </a-space>
        </div>

        <!-- PDF 预览模式 -->
        <div v-if="previewMode === 'pdf'" class="pdf-preview">
          <div class="pdf-placeholder">
            <FilePdfOutlined class="pdf-icon" />
            <p class="pdf-text">PDF Preview</p>
            <p class="pdf-hint">This would display the actual PDF content using a PDF viewer library</p>
            <a-button type="primary" @click="handleDownload">
              Download PDF
            </a-button>
          </div>
        </div>

        <!-- 分块预览模式 -->
        <div v-else class="chunks-preview">
          <div class="chunks-header">
            <div class="chunk-stats">
              <span class="stat-item">
                <DatabaseOutlined />
                {{ chunks.length }} Chunks
              </span>
              <span class="stat-item">
                <ClockCircleOutlined />
                Average {{ avgChunkTokens }} tokens
              </span>
            </div>
            <a-space>
              <a-select
                v-model:value="selectedChunkId"
                placeholder="Select chunk"
                style="width: 200px"
                @change="handleChunkSelect"
              >
                <a-select-option
                  v-for="(chunk, index) in chunks"
                  :key="index"
                  :value="index"
                >
                  Chunk {{ index + 1 }}
                </a-select-option>
              </a-select>
            </a-space>
          </div>

          <div class="chunks-container">
            <div
              v-for="(chunk, index) in chunks"
              :key="index"
              class="chunk-card"
              :class="{ 'active': selectedChunkId === index }"
              @click="selectedChunkId = index"
            >
              <div class="chunk-header">
                <div class="chunk-title">
                  <span class="chunk-number">Chunk {{ index + 1 }}</span>
                  <span class="chunk-tokens">{{ chunk.metadata?.tokens || 'Unknown' }} tokens</span>
                </div>
                <a-button
                  type="text"
                  size="small"
                  @click.stop="handleCopyChunk(chunk.content)"
                >
                  <CopyOutlined />
                </a-button>
              </div>
              <div class="chunk-content">
                <pre>{{ chunk.content }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 处理任务信息 -->
      <div v-if="document.processing_tasks && document.processing_tasks.length > 0" class="tasks-card">
        <h3 class="card-title">Processing Tasks</h3>
        <div class="task-list">
          <div
            v-for="task in document.processing_tasks"
            :key="task.id"
            class="task-item"
            :class="`task-${task.status}`"
          >
            <div class="task-info">
              <div class="task-id">Task #{{ task.id }}</div>
              <div class="task-status">
                <a-badge
                  :status="getStatusBadgeType(task.status)"
                  :text="task.status.toUpperCase()"
                />
              </div>
            </div>
            <div class="task-time">
              <ClockCircleOutlined />
              {{ formatDate(task.created_at) }}
            </div>
            <div v-if="task.error_message" class="task-error">
              <ExclamationCircleOutlined />
              {{ task.error_message }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-container">
      <a-alert
        type="error"
        :message="error"
        show-icon
      />
      <a-button type="primary" @click="fetchDocumentDetails">
        Retry
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  FileTextOutlined,
  ArrowLeftOutlined,
  ThunderboltOutlined,
  DownloadOutlined,
  DeleteOutlined,
  FilePdfOutlined,
  DatabaseOutlined,
  ClockCircleOutlined,
  CopyOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons-vue'
import type { Document, KnowledgeBase, PreviewChunk } from '../types/knowledge-base'

const route = useRoute()
const router = useRouter()
const knowledgeBaseId = Number(route.params.kbId)
const documentId = Number(route.params.docId)

// 状态管理
const document = ref<Document | null>(null)
const knowledgeBase = ref<KnowledgeBase | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const previewMode = ref<'pdf' | 'chunks'>('chunks')
const selectedChunkId = ref<number>(0)
const chunks = ref<PreviewChunk[]>([])

// 计算属性
const avgChunkTokens = computed(() => {
  if (chunks.value.length === 0) return 0
  const total = chunks.value.reduce((sum, chunk) => sum + (chunk.metadata?.tokens || 0), 0)
  return Math.round(total / chunks.value.length)
})

// 返回上一页
const handleGoBack = () => {
  router.back()
}

// 分析文档
const handleAnalyze = () => {
  message.info('Analysis functionality coming soon')
}

// 下载文档
const handleDownload = () => {
  message.info('Download functionality coming soon')
}

// 删除文档
const handleDelete = () => {
  message.success('Document deleted successfully')
  router.push(`/knowledge-base/${knowledgeBaseId}`)
}

// 复制分块内容
const handleCopyChunk = async (content: string) => {
  try {
    await navigator.clipboard.writeText(content)
    message.success('Chunk content copied to clipboard')
  } catch (err) {
    message.error('Failed to copy content')
  }
}

// 选择分块
const handleChunkSelect = (value: number) => {
  selectedChunkId.value = value
}

// 获取状态颜色
const getStatusColor = (status: string): string => {
  const colors: Record<string, string> = {
    completed: 'green',
    failed: 'red',
    processing: 'blue',
    pending: 'default'
  }
  return colors[status.toLowerCase()] || 'default'
}

// 获取状态徽章类型
const getStatusBadgeType = (status: string): 'success' | 'error' | 'processing' | 'default' => {
  const types: Record<string, 'success' | 'error' | 'processing' | 'default'> = {
    completed: 'success',
    failed: 'error',
    processing: 'processing',
    pending: 'default'
  }
  return types[status.toLowerCase()] || 'default'
}

// 格式化文件大小
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

// 格式化日期
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

// 获取文档详情（静态演示数据）
const fetchDocumentDetails = async () => {
  loading.value = true
  error.value = null

  // 模拟API延迟
  await new Promise(resolve => setTimeout(resolve, 800))

  // 静态演示数据 - 文档
  document.value = {
    id: documentId,
    file_name: '心血管疾病诊疗指南2024.pdf',
    file_path: '/uploads/cardio_guidelines_2024.pdf',
    file_size: 2458624,
    content_type: 'application/pdf',
    knowledge_base_id: knowledgeBaseId,
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
  }

  // 静态演示数据 - 知识库
  knowledgeBase.value = {
    id: knowledgeBaseId,
    name: '医学文献知识库',
    description: '包含最新的医学研究文献、临床试验报告和医学期刊文章',
    documents: [],
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-03-20T14:22:00Z',
    document_count: 128,
    chunk_count: 15240
  }

  // 静态演示数据 - 分块
  chunks.value = [
    {
      content: `第一章：心血管疾病的概述\n\n心血管疾病是全球范围内导致死亡和残疾的主要原因之一。根据世界卫生组织的统计，每年约有1790万人死于心血管疾病，占全球总死亡人数的31%。\n\n主要的风险因素包括高血压、高胆固醇、吸烟、糖尿病、肥胖、缺乏运动和不健康的饮食。这些因素共同作用，加速了动脉粥样硬化的发展进程。

动脉粥样硬化是一种慢性炎症性疾病，其特征是动脉壁内脂质、炎性细胞和纤维组织的积累。随着时间的推移，这种积累会导致血管腔狭窄，限制血流，最终可能导致心肌梗死、脑卒中等严重并发症。

预防心血管疾病需要综合性的策略，包括生活方式干预、药物治疗和定期筛查。早期识别风险因素并积极干预，可以显著降低心血管事件的发生率。`,
      metadata: { chunk_id: 1, tokens: 248 }
    },
    {
      content: `第二章：诊断方法\n\n现代医学提供了多种诊断心血管疾病的方法：\n\n1. 心电图（ECG）：记录心脏电活动，检测心律失常和心肌缺血\n\n心电图是最常用的心血管诊断工具之一，通过在体表放置电极，记录心脏在不同时间点的电活动变化。正常的心电图表现为特定的波形和间期，任何异常都可能提示心脏结构或功能的问题。\n\n2. 超声心动图：使用超声波创建心脏图像，评估心脏结构和功能\n\n超声心动图是一种无创检查方法，能够实时观察心脏的搏动、瓣膜的开闭以及心腔的大小。对于先天性心脏病、瓣膜疾病和心肌病的诊断具有重要价值。`,
      metadata: { chunk_id: 2, tokens: 186 }
    },
    {
      content: `3. 冠状动脉造影：通过X射线检查冠状动脉，诊断冠心病\n\n冠状动脉造影是诊断冠心病的"金标准"，通过导管将造影剂注入冠状动脉，在X射线下观察血管的狭窄程度。这种方法不仅能够明确诊断，还可以在检查过程中进行介入治疗。\n\n4. CT和MRI：提供详细的心脏和血管图像，用于复杂病例的诊断\n\n心脏CT和MRI能够提供高分辨率的三维图像，对于复杂先天性心脏病、心肌存活评估以及肿瘤侵犯范围的判断具有独特优势。\n\n诊断策略的选择应该基于患者的临床表现、风险分层以及医疗机构的技术能力。对于疑似急性心血管事件的患者，应该优先选择快速、准确的检查方法。`,
      metadata: { chunk_id: 3, tokens: 192 }
    },
    {
      content: `第三章：治疗策略\n\n心血管疾病的治疗需要综合考虑患者的具体情况：\n\n药物治疗：\n- 抗血小板药物：如阿司匹林，预防血栓形成\n- 他汀类药物：降低胆固醇水平，稳定斑块\n- β受体阻滞剂：控制心率，降低心肌耗氧\n- ACE抑制剂：改善心室重构，降低死亡率\n- 利尿剂：减轻心脏负荷，缓解症状\n\n介入治疗：\n- 冠脉支架植入术：微创治疗冠心病\n- 起搏器植入：治疗心律失常\n- 心脏搭桥手术：复杂冠心病的血运重建\n\n生活方式干预：\n- 戒烟限酒\n- 控制体重\n- 规律运动\n- 健康饮食（DASH饮食、地中海饮食）\n- 管理压力`,
      metadata: { chunk_id: 4, tokens: 156 }
    }
  ]

  loading.value = false
}

// 初始化
onMounted(() => {
  fetchDocumentDetails()
})
</script>

<style scoped>
.document-detail-container {
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
}

/* 加载和错误状态 */
.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  gap: 16px;
}

.loading-text {
  font-size: 14px;
  color: #666;
  margin: 0;
}

.error-container {
  padding: 24px;
  text-align: center;
}

/* 内容区域 */
.content-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 卡片通用样式 */
.info-card,
.preview-card,
.tasks-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid #e8e8e8;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.card-title {
  margin: 0 0 20px 0;
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 文档信息网格 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 14px;
  color: #1a1a1a;
  font-weight: 500;
}

.status-tag {
  border-radius: 4px;
  font-weight: 500;
}

/* 预览区域 */
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.pdf-preview {
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  padding: 48px;
  text-align: center;
}

.pdf-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.pdf-icon {
  font-size: 64px;
  color: #ff4d4f;
}

.pdf-text {
  font-size: 18px;
  font-weight: 500;
  color: #1a1a1a;
  margin: 0;
}

.pdf-hint {
  font-size: 14px;
  color: #666;
  margin: 0;
}

/* 分块预览 */
.chunks-preview {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chunks-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.chunk-stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #666;
}

.chunks-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 800px;
  overflow-y: auto;
}

.chunk-card {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #fafafa;
}

.chunk-card:hover {
  border-color: #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.1);
}

.chunk-card.active {
  border-color: #1890ff;
  background: #f0f7ff;
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.chunk-title {
  display: flex;
  gap: 12px;
  align-items: center;
}

.chunk-number {
  font-weight: 600;
  color: #1a1a1a;
}

.chunk-tokens {
  font-size: 12px;
  color: #666;
  background: #f0f0f0;
  padding: 2px 8px;
  border-radius: 4px;
}

.chunk-content {
  background: white;
  border-radius: 4px;
  padding: 12px;
  max-height: 300px;
  overflow-y: auto;
}

.chunk-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-size: 14px;
  color: #333;
  line-height: 1.6;
}

/* 任务列表 */
.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-item.task-completed {
  border-left: 4px solid #52c41a;
}

.task-item.task-failed {
  border-left: 4px solid #ff4d4f;
}

.task-item.task-processing {
  border-left: 4px solid #1890ff;
}

.task-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-id {
  font-weight: 500;
  color: #1a1a1a;
}

.task-time {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #666;
}

.task-error {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  color: #ff4d4f;
  font-size: 14px;
  padding: 8px;
  background: #fff2f0;
  border-radius: 4px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .document-detail-container {
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

  .info-grid {
    grid-template-columns: 1fr;
  }

  .preview-header,
  .chunks-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
