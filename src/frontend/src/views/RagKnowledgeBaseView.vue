<template>
  <div class="rag-knowledge-base-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2 class="page-title">
        <FileAddOutlined />
        {{ t('views_RagKnowledgeBaseView.title') }}
      </h2>
      <a-button type="primary" @click="handleCreateKnowledgeBase">
        <template #icon>
          <PlusOutlined />
        </template>
        {{ t('views_RagKnowledgeBaseView.createKnowledgeBase') }}
      </a-button>
    </div>

    <!-- 搜索和筛选栏 -->
    <a-card class="filter-card">
      <div class="filter-row">
        <a-input-search
          v-model:value="searchKeyword"
          :placeholder="t('views_RagKnowledgeBaseView.searchPlaceholder')"
          allow-clear
          style="width: 300px"
          @search="handleSearch"
        />
        <a-select
          v-model:value="statusFilter"
          :placeholder="t('views_RagKnowledgeBaseView.statusFilter')"
          style="width: 150px"
          allow-clear
        >
          <a-select-option value="">{{ t('views_RagKnowledgeBaseView.allStatus') }}</a-select-option>
          <a-select-option value="active">{{ t('views_RagKnowledgeBaseView.active') }}</a-select-option>
          <a-select-option value="inactive">{{ t('views_RagKnowledgeBaseView.inactive') }}</a-select-option>
        </a-select>
        <a-select
          v-model:value="typeFilter"
          :placeholder="t('views_RagKnowledgeBaseView.typeFilter')"
          style="width: 150px"
          allow-clear
        >
          <a-select-option value="">{{ t('views_RagKnowledgeBaseView.allTypes') }}</a-select-option>
          <a-select-option value="medical_literature">{{ t('views_RagKnowledgeBaseView.medicalLiterature') }}</a-select-option>
          <a-select-option value="clinical_guideline">{{ t('views_RagKnowledgeBaseView.clinicalGuideline') }}</a-select-option>
          <a-select-option value="case_library">{{ t('views_RagKnowledgeBaseView.caseLibrary') }}</a-select-option>
        </a-select>
        <a-button type="primary" @click="handleSearch">
          <template #icon>
            <SearchOutlined />
          </template>
          {{ t('views_RagKnowledgeBaseView.search') }}
        </a-button>
        <a-button @click="handleReset">
          <template #icon>
            <ReloadOutlined />
          </template>
          {{ t('views_RagKnowledgeBaseView.reset') }}
        </a-button>
      </div>
    </a-card>

    <!-- 知识库列表 -->
    <a-card class="table-card">
      <a-table
        :columns="columns"
        :data-source="filteredKnowledgeBases"
        :loading="loading"
        :pagination="paginationConfig"
        :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
        :row-key="(record: any) => record.id"
      >
        <template #bodyCell="{ column, record }: { column: any; record: any }">
          <template v-if="column.key === 'name'">
            <div class="knowledge-base-name">
              <FileTextOutlined class="name-icon" />
              <div class="name-content">
                <div class="name-title">{{ record.name }}</div>
                <div class="name-description">{{ record.description }}</div>
              </div>
            </div>
          </template>
          <template v-else-if="column.key === 'type'">
            <a-tag :color="getTypeColor(record.type)">
              {{ getTypeName(record.type) }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'documentCount'">
            <span class="number-cell">{{ formatNumber(record.documentCount) }}</span>
          </template>
          <template v-else-if="column.key === 'vectorDimension'">
            <span class="number-cell">{{ record.vectorDimension }}</span>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="record.status === 'active' ? 'success' : 'default'">
              {{ record.status === 'active' ? t('views_RagKnowledgeBaseView.active') : t('views_RagKnowledgeBaseView.inactive') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'createTime'">
            <span class="time-cell">{{ record.createTime }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <div class="action-buttons">
              <a-button type="link" size="small" @click="handleUploadDocuments(record)">
                <template #icon>
                  <UploadOutlined />
                </template>
                {{ t('views_RagKnowledgeBaseView.upload') }}
              </a-button>
              <a-button type="link" size="small" @click="handleViewDocuments(record)">
                <template #icon>
                  <EyeOutlined />
                </template>
                {{ t('views_RagKnowledgeBaseView.view') }}
              </a-button>
              <a-button type="link" size="small" @click="handleEdit(record)">
                <template #icon>
                  <EditOutlined />
                </template>
                {{ t('views_RagKnowledgeBaseView.edit') }}
              </a-button>
              <a-popconfirm
                :title="t('views_RagKnowledgeBaseView.deleteConfirm')"
                @confirm="handleDelete(record)"
              >
                <a-button type="link" danger size="small">
                  <template #icon>
                    <DeleteOutlined />
                  </template>
                  {{ t('views_RagKnowledgeBaseView.delete') }}
                </a-button>
              </a-popconfirm>
            </div>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 创建/编辑知识库模态框 -->
    <a-modal
      v-model:open="createModalVisible"
      :title="editingKnowledgeBase ? t('views_RagKnowledgeBaseView.editKnowledgeBase') : t('views_RagKnowledgeBaseView.createKnowledgeBase')"
      @ok="handleSubmitKnowledgeBase"
      @cancel="handleCancelKnowledgeBase"
    >
      <a-form :model="knowledgeBaseForm" layout="vertical">
        <a-form-item :label="t('views_RagKnowledgeBaseView.name')" required>
          <a-input v-model:value="knowledgeBaseForm.name" :placeholder="t('views_RagKnowledgeBaseView.namePlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('views_RagKnowledgeBaseView.description')">
          <a-textarea
            v-model:value="knowledgeBaseForm.description"
            :placeholder="t('views_RagKnowledgeBaseView.descriptionPlaceholder')"
            :rows="3"
          />
        </a-form-item>
        <a-form-item :label="t('views_RagKnowledgeBaseView.type')" required>
          <a-select v-model:value="knowledgeBaseForm.type" :placeholder="t('views_RagKnowledgeBaseView.selectType')">
            <a-select-option value="medical_literature">{{ t('views_RagKnowledgeBaseView.medicalLiterature') }}</a-select-option>
            <a-select-option value="clinical_guideline">{{ t('views_RagKnowledgeBaseView.clinicalGuideline') }}</a-select-option>
            <a-select-option value="case_library">{{ t('views_RagKnowledgeBaseView.caseLibrary') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('views_RagKnowledgeBaseView.vectorDimension')" required>
          <a-input-number
            v-model:value="knowledgeBaseForm.vectorDimension"
            :min="128"
            :max="2048"
            :step="128"
            style="width: 100%"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 上传文档模态框 -->
    <a-modal
      v-model:open="uploadModalVisible"
      :title="t('views_RagKnowledgeBaseView.uploadDocuments')"
      width="800px"
      @ok="handleConfirmUpload"
      @cancel="handleCancelUpload"
    >
      <div v-if="currentKnowledgeBase" class="upload-content">
        <div class="upload-info">
          <a-descriptions :column="2" size="small" bordered>
            <a-descriptions-item :label="t('views_RagKnowledgeBaseView.knowledgeBaseName')">
              {{ currentKnowledgeBase.name }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_RagKnowledgeBaseView.currentDocuments')">
              {{ formatNumber(currentKnowledgeBase.documentCount) }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_RagKnowledgeBaseView.vectorDimension')" :span="2">
              {{ currentKnowledgeBase.vectorDimension }}
            </a-descriptions-item>
          </a-descriptions>
        </div>

        <a-upload-dragger
          v-model:file-list="fileList"
          :multiple="true"
          :before-upload="beforeUpload"
          accept=".pdf"
          class="upload-dragger"
        >
          <p class="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p class="ant-upload-text">
            {{ t('views_RagKnowledgeBaseView.uploadText') }}
          </p>
          <p class="ant-upload-hint">
            {{ t('views_RagKnowledgeBaseView.uploadHint') }}
          </p>
        </a-upload-dragger>

        <div v-if="fileList.length > 0" class="file-list">
          <div class="file-list-header">
            <span>{{ t('views_RagKnowledgeBaseView.selectedFiles') }} ({{ fileList.length }})</span>
            <a-button type="link" size="small" @click="fileList = []">
              {{ t('views_RagKnowledgeBaseView.clearAll') }}
            </a-button>
          </div>
          <div class="file-items">
            <div v-for="(file, index) in fileList" :key="index" class="file-item">
              <FileTextOutlined class="file-icon" />
              <span class="file-name">{{ file.name }}</span>
              <span class="file-size">{{ formatFileSize(file.size || 0) }}</span>
              <a-button type="link" danger size="small" @click="removeFile(index)">
                <DeleteOutlined />
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 文档列表模态框 -->
    <a-modal
      v-model:open="documentsModalVisible"
      :title="t('views_RagKnowledgeBaseView.documentsList')"
      width="900px"
      :footer="null"
    >
      <div v-if="currentKnowledgeBase" class="documents-content">
        <a-table
          :columns="documentColumns"
          :data-source="currentDocuments"
          :pagination="{ pageSize: 10 }"
          :row-key="(record: any) => record.id"
        >
          <template #bodyCell="{ column, record }: { column: any; record: any }">
            <template v-if="column.key === 'name'">
              <div class="document-name">
                <FilePdfOutlined class="document-icon" />
                <span>{{ record.name }}</span>
              </div>
            </template>
            <template v-else-if="column.key === 'size'">
              <span>{{ formatFileSize(record.size) }}</span>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :color="getDocumentStatusColor(record.status)">
                {{ getDocumentStatusText(record.status) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button type="link" size="small" @click="handleAnalyzeDocument(record)">
                <template #icon>
                  <ThunderboltOutlined />
                </template>
                {{ t('views_RagKnowledgeBaseView.analyze') }}
              </a-button>
              <a-button type="link" danger size="small" @click="handleDeleteDocument(record)">
                <template #icon>
                  <DeleteOutlined />
                </template>
                {{ t('views_RagKnowledgeBaseView.delete') }}
              </a-button>
            </template>
          </template>
        </a-table>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  FileAddOutlined,
  PlusOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  SearchOutlined,
  ReloadOutlined,
  UploadOutlined,
  EyeOutlined,
  EditOutlined,
  DeleteOutlined,
  InboxOutlined,
  FilePdfOutlined
} from '@ant-design/icons-vue'
import type { UploadFile } from 'ant-design-vue'

const { t } = useI18n()

// 加载状态
const loading = ref(false)

// 搜索和筛选
const searchKeyword = ref('')
const statusFilter = ref('')
const typeFilter = ref('')

// 选中的行
const selectedRowKeys = ref<string[]>([])

// 知识库列表数据
const knowledgeBases = ref([
  {
    id: '1',
    name: '心血管疾病诊疗指南',
    description: '包含常见心血管疾病的诊断和治疗方案',
    type: 'clinical_guideline',
    documentCount: 1234,
    vectorDimension: 768,
    status: 'active',
    createTime: '2024-01-10 10:30'
  },
  {
    id: '2',
    name: '肿瘤学文献库',
    description: '收录最新肿瘤学研究论文和临床报告',
    type: 'medical_literature',
    documentCount: 5678,
    vectorDimension: 1536,
    status: 'active',
    createTime: '2024-01-08 14:20'
  },
  {
    id: '3',
    name: '罕见病病例库',
    description: '收集各类罕见疾病的诊断和治疗案例',
    type: 'case_library',
    documentCount: 892,
    vectorDimension: 768,
    status: 'active',
    createTime: '2024-01-05 09:15'
  },
  {
    id: '4',
    name: '儿科疾病诊疗指南',
    description: '涵盖儿科常见疾病的诊断和治疗规范',
    type: 'clinical_guideline',
    documentCount: 2345,
    vectorDimension: 1024,
    status: 'active',
    createTime: '2024-01-03 16:45'
  },
  {
    id: '5',
    name: '神经内科文献库',
    description: '神经内科相关医学文献和研究资料',
    type: 'medical_literature',
    documentCount: 3456,
    vectorDimension: 1536,
    status: 'inactive',
    createTime: '2023-12-28 11:20'
  }
])

// 表格列定义
const columns = [
  {
    title: t('views_RagKnowledgeBaseView.name'),
    key: 'name',
    width: '30%'
  },
  {
    title: t('views_RagKnowledgeBaseView.type'),
    key: 'type',
    width: '12%'
  },
  {
    title: t('views_RagKnowledgeBaseView.documentCount'),
    key: 'documentCount',
    width: '12%',
    align: 'right' as const
  },
  {
    title: t('views_RagKnowledgeBaseView.vectorDimension'),
    key: 'vectorDimension',
    width: '12%',
    align: 'right' as const
  },
  {
    title: t('views_RagKnowledgeBaseView.status'),
    key: 'status',
    width: '10%'
  },
  {
    title: t('views_RagKnowledgeBaseView.createTime'),
    key: 'createTime',
    width: '14%'
  },
  {
    title: t('views_RagKnowledgeBaseView.action'),
    key: 'action',
    width: '10%'
  }
]

// 文档表格列定义
const documentColumns = [
  {
    title: t('views_RagKnowledgeBaseView.documentName'),
    key: 'name',
    width: '40%'
  },
  {
    title: t('views_RagKnowledgeBaseView.fileSize'),
    key: 'size',
    width: '15%'
  },
  {
    title: t('views_RagKnowledgeBaseView.status'),
    key: 'status',
    width: '15%'
  },
  {
    title: t('views_RagKnowledgeBaseView.uploadTime'),
    key: 'uploadTime',
    width: '20%'
  },
  {
    title: t('views_RagKnowledgeBaseView.action'),
    key: 'action',
    width: '10%'
  }
]

// 分页配置
const paginationConfig = {
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `${t('views_RagKnowledgeBaseView.total')} ${total} ${t('views_RagKnowledgeBaseView.records')}`
}

// 过滤后的知识库列表
const filteredKnowledgeBases = computed(() => {
  let result = knowledgeBases.value

  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(
      kb =>
        kb.name.toLowerCase().includes(keyword) ||
        kb.description.toLowerCase().includes(keyword)
    )
  }

  if (statusFilter.value) {
    result = result.filter(kb => kb.status === statusFilter.value)
  }

  if (typeFilter.value) {
    result = result.filter(kb => kb.type === typeFilter.value)
  }

  paginationConfig.total = result.length
  return result
})

// 当前知识库
const currentKnowledgeBase = ref<any>(null)

// 模态框显示状态
const createModalVisible = ref(false)
const uploadModalVisible = ref(false)
const documentsModalVisible = ref(false)

// 编辑中的知识库
const editingKnowledgeBase = ref<any>(null)

// 知识库表单
const knowledgeBaseForm = ref({
  name: '',
  description: '',
  type: '',
  vectorDimension: 768
})

// 文件列表
const fileList = ref<UploadFile[]>([])

// 当前文档列表
const currentDocuments = ref([
  {
    id: '1',
    name: '心血管疾病诊疗指南_2024版.pdf',
    size: 2456789,
    status: 'processed',
    uploadTime: '2024-01-10 10:30'
  },
  {
    id: '2',
    name: '急性心肌梗死诊断与治疗.pdf',
    size: 1234567,
    status: 'processing',
    uploadTime: '2024-01-10 11:20'
  },
  {
    id: '3',
    name: '高血压管理指南.pdf',
    size: 3456789,
    status: 'processed',
    uploadTime: '2024-01-09 14:15'
  }
])

// 方法
const handleCreateKnowledgeBase = () => {
  editingKnowledgeBase.value = null
  knowledgeBaseForm.value = {
    name: '',
    description: '',
    type: '',
    vectorDimension: 768
  }
  createModalVisible.value = true
}

const handleEdit = (record: any) => {
  editingKnowledgeBase.value = record
  knowledgeBaseForm.value = {
    name: record.name,
    description: record.description,
    type: record.type,
    vectorDimension: record.vectorDimension
  }
  createModalVisible.value = true
}

const handleSubmitKnowledgeBase = () => {
  // 静态页面，仅展示
  console.log('提交知识库:', knowledgeBaseForm.value)
  createModalVisible.value = false
}

const handleCancelKnowledgeBase = () => {
  createModalVisible.value = false
  editingKnowledgeBase.value = null
}

const handleUploadDocuments = (record: any) => {
  currentKnowledgeBase.value = record
  fileList.value = []
  uploadModalVisible.value = true
}

const handleConfirmUpload = () => {
  // 静态页面，仅展示
  console.log('上传文档:', fileList.value)
  uploadModalVisible.value = false
}

const handleCancelUpload = () => {
  uploadModalVisible.value = false
  fileList.value = []
}

const handleViewDocuments = (record: any) => {
  currentKnowledgeBase.value = record
  documentsModalVisible.value = true
}

const handleDelete = (record: any) => {
  // 静态页面，仅展示
  console.log('删除知识库:', record)
}

const handleSearch = () => {
  // 静态页面，仅展示
  console.log('搜索')
}

const handleReset = () => {
  searchKeyword.value = ''
  statusFilter.value = ''
  typeFilter.value = ''
}

const handleAnalyzeDocument = (record: any) => {
  // 静态页面，仅展示
  console.log('分析文档:', record)
}

const handleDeleteDocument = (record: any) => {
  // 静态页面，仅展示
  console.log('删除文档:', record)
}

const onSelectChange = (keys: string[]) => {
  selectedRowKeys.value = keys
}

const beforeUpload = (file: File) => {
  // 只允许 PDF 文件
  const isPDF = file.type === 'application/pdf'
  if (!isPDF) {
    // 这里应该显示错误消息
    return false
  }
  return false // 阻止自动上传
}

const removeFile = (index: number) => {
  fileList.value.splice(index, 1)
}

const getTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    medical_literature: 'blue',
    clinical_guideline: 'green',
    case_library: 'orange'
  }
  return colors[type] || 'default'
}

const getTypeName = (type: string) => {
  const names: Record<string, string> = {
    medical_literature: t('views_RagKnowledgeBaseView.medicalLiterature'),
    clinical_guideline: t('views_RagKnowledgeBaseView.clinicalGuideline'),
    case_library: t('views_RagKnowledgeBaseView.caseLibrary')
  }
  return names[type] || type
}

const getDocumentStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    processed: 'success',
    processing: 'processing',
    failed: 'error'
  }
  return colors[status] || 'default'
}

const getDocumentStatusText = (status: string) => {
  const texts: Record<string, string> = {
    processed: t('views_RagKnowledgeBaseView.processed'),
    processing: t('views_RagKnowledgeBaseView.processing'),
    failed: t('views_RagKnowledgeBaseView.failed')
  }
  return texts[status] || status
}

const formatNumber = (num: number) => {
  return num.toLocaleString()
}

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

onMounted(() => {
  // 初始化数据
})
</script>

<style scoped>
.rag-knowledge-base-container {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.table-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.knowledge-base-name {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.name-icon {
  font-size: 20px;
  color: #1890ff;
  margin-top: 2px;
}

.name-content {
  flex: 1;
  min-width: 0;
}

.name-title {
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
}

.name-description {
  font-size: 12px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.number-cell {
  font-weight: 500;
  color: #333;
}

.time-cell {
  color: #666;
  font-size: 13px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.upload-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.upload-info {
  margin-bottom: 8px;
}

.upload-dragger {
  margin-top: 16px;
}

.file-list {
  margin-top: 16px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 12px;
  background: #fafafa;
}

.file-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 500;
}

.file-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  background: white;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}

.file-icon {
  font-size: 18px;
  color: #1890ff;
}

.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  color: #999;
  font-size: 12px;
}

.documents-content {
  margin-top: 16px;
}

.document-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.document-icon {
  font-size: 16px;
  color: #f5222d;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-row > * {
    width: 100% !important;
  }
}
</style>
