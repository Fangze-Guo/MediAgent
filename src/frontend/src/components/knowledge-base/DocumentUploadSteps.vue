<template>
  <div class="upload-steps-container">
    <div class="shadcn-steps">
      <div 
        v-for="(step, index) in steps" 
        :key="step.number" 
        class="step-item"
      >
        <div 
          class="step-circle"
          :class="{
            'active': currentStep === step.number,
            'completed': currentStep > step.number,
            'pending': currentStep < step.number
          }"
        >
          <component :is="step.icon" class="step-icon" />
        </div>
        <span class="step-label">{{ step.number }}. {{ step.label }}</span>
        
        <div 
          v-if="index < steps.length - 1" 
          class="step-connector"
          :class="{ 'completed': currentStep > step.number }"
        />
      </div>
    </div>

    <div class="steps-content-wrapper">
      
      <div v-show="currentStep === 1" class="step-card fade-in">
        <div class="card-body space-y-4">
          <div class="dropzone-wrapper">
            <FileDropzone
              accept=".pdf,.docx,.txt,.md"
              text="Drop your files here or click to browse"
              hint="Supports PDF, DOCX, TXT, and MD files"
              @files-selected="handleFilesSelected"
            />
          </div>

          <div v-if="files.length > 0" class="files-list">
            <div
              v-for="(fileStatus, index) in files"
              :key="index"
              class="shadcn-file-item"
            >
              <div class="file-info-left">
                <div class="file-icon-wrapper" :class="getFileTypeClass(fileStatus.file.name)">
                  <span class="file-extension">{{ getExtension(fileStatus.file.name) }}</span>
                </div>
                <div class="file-details">
                  <p class="file-name">{{ fileStatus.file.name }}</p>
                  <p class="file-size">{{ formatFileSize(fileStatus.file.size) }}</p>
                </div>
              </div>
              
              <div class="file-actions-right">
                <span v-if="fileStatus.status === 'uploaded'" class="status-text text-success">Uploaded</span>
                <span v-else-if="fileStatus.status === 'error'" class="status-text text-destructive">{{ fileStatus.error }}</span>
                
                <button class="icon-button" @click="removeFile(index)">
                  <CloseOutlined class="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          <a-button
            type="primary"
            class="shadcn-btn-primary w-full mt-4"
            size="large"
            :loading="isLoading"
            :disabled="!hasPendingFiles"
            @click="handleUpload"
          >
            <template #icon><UploadOutlined v-if="!isLoading" /></template>
            {{ isLoading ? 'Uploading...' : 'Upload Files' }}
          </a-button>
        </div>
      </div>

      <div v-show="currentStep === 2" class="step-card fade-in">
        <div class="card-body space-y-6">
          <h3 class="shadcn-title">Select Document to Preview</h3>

          <a-select
            v-model:value="selectedDocumentId"
            placeholder="Select a document to preview"
            class="shadcn-select w-full"
            size="large"
            @change="handlePreview"
          >
            <a-select-option
              v-for="fileStatus in uploadedFiles"
              :key="fileStatus.uploadId"
              :value="fileStatus.uploadId"
            >
              {{ fileStatus.file.name }}
            </a-select-option>
          </a-select>

          <a-collapse class="shadcn-collapse" :bordered="false" expand-icon-position="right">
            <a-collapse-panel key="1" header="Advanced Settings" class="shadcn-panel">
              <div class="settings-grid pt-4">
                <div class="setting-item">
                  <label>Chunk Size (tokens)</label>
                  <a-input-number
                    v-model:value="chunkSize"
                    :min="100" :max="5000" :step="100"
                    class="w-full shadcn-input"
                    @change="handlePreview"
                  />
                </div>
                <div class="setting-item">
                  <label>Chunk Overlap (tokens)</label>
                  <a-input-number
                    v-model:value="chunkOverlap"
                    :min="0" :max="1000" :step="50"
                    class="w-full shadcn-input"
                    @change="handlePreview"
                  />
                </div>
              </div>
            </a-collapse-panel>
          </a-collapse>

          <div class="flex space-x-4 mt-6">
            <a-button
              class="shadcn-btn-outline flex-1"
              size="large"
              :loading="isLoading"
              :disabled="!selectedDocumentId"
              @click="handlePreview"
            >
              Preview Chunks
            </a-button>
            <a-button 
              class="shadcn-btn-secondary flex-1" 
              size="large"
              @click="currentStep = 3"
            >
              Continue
            </a-button>
          </div>

          <div v-if="previewChunks && previewChunks.length > 0" class="preview-container">
            <div class="preview-header">
              <h4 class="font-medium text-slate-900">{{ selectedDocumentFile?.name }}</h4>
              <span class="text-sm text-slate-500">{{ previewChunks.length }} chunks</span>
            </div>
            <div class="chunks-list">
              <div
                v-for="(chunk, index) in previewChunks"
                :key="index"
                class="chunk-item"
              >
                <div class="chunk-label">Chunk {{ index + 1 }}</div>
                <pre class="chunk-content">{{ chunk.content }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-show="currentStep === 3" class="step-card fade-in">
        <div class="card-body space-y-4">
          <div v-if="uploadedFiles.length > 0" class="processing-list">
            <div
              v-for="fileStatus in uploadedFiles"
              :key="fileStatus.uploadId"
              class="shadcn-file-item flex-col items-stretch"
            >
              <div class="flex justify-between items-start w-full">
                <div class="file-info-left">
                  <div class="file-icon-wrapper" :class="getFileTypeClass(fileStatus.file.name)">
                    <span class="file-extension">{{ getExtension(fileStatus.file.name) }}</span>
                  </div>
                  <div class="file-details">
                    <p class="file-name">{{ fileStatus.file.name }}</p>
                    <p class="file-size">{{ formatFileSize(fileStatus.file.size) }}</p>
                    <p v-if="fileStatus.uploadId && getTaskStatus(fileStatus.uploadId)" class="task-status-text mt-1">
                      Status: {{ getTaskStatus(fileStatus.uploadId!)?.status || 'pending' }}
                    </p>
                  </div>
                </div>
                
                <div v-if="isFailed(fileStatus.uploadId)" class="text-destructive text-sm mt-1">
                  {{ getTaskStatus(fileStatus.uploadId!)?.error || 'Failed' }}
                </div>
              </div>

              <div v-if="fileStatus.uploadId && (isProcessing(fileStatus.uploadId) || getTaskStatus(fileStatus.uploadId)?.status === 'pending')" class="mt-4">
                <a-progress
                  :percent="isProcessing(fileStatus.uploadId) ? 50 : 25"
                  :show-info="false"
                  strokeColor="#0f172a"
                  class="shadcn-progress"
                />
              </div>
            </div>
          </div>

          <a-button
            type="primary"
            class="shadcn-btn-primary w-full mt-4"
            size="large"
            :loading="isLoading"
            :disabled="uploadedFiles.length === 0 || isAnyProcessing"
            @click="handleProcess"
          >
            <template #icon><SettingOutlined v-if="!isLoading" /></template>
            {{ isLoading ? 'Processing...' : 'Process Documents' }}
          </a-button>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  UploadOutlined,
  SettingOutlined,
  CloseOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'
import FileDropzone from './FileDropzone.vue'
import type { FileUploadStatus, PreviewChunk } from '../../types/knowledge-base'
import { knowledgeBaseApi } from '../../apis/knowledgeBase'

interface Props {
  knowledgeBaseId?: number
  onComplete?: () => void
}

const props = withDefaults(defineProps<Props>(), {
  knowledgeBaseId: 1
})

const emit = defineEmits<{
  complete: []
}>()

// 步骤定义
const steps = [
  { number: 1, label: 'Upload', icon: UploadOutlined },
  { number: 2, label: 'Preview', icon: FileTextOutlined },
  { number: 3, label: 'Process', icon: SettingOutlined }
]

// 状态管理
const currentStep = ref(1)
const isLoading = ref(false)

// 文件列表
const files = ref<FileUploadStatus[]>([])
const uploadedFiles = computed(() => files.value.filter(f => f.status === 'uploaded'))

// 预览设置
const selectedDocumentId = ref<number | null>(null)
const chunkSize = ref(1000)
const chunkOverlap = ref(200)
const previewChunks = ref<PreviewChunk[]>([])

// 任务状态
const taskStatuses = ref<Record<number, { status: string; error?: string }>>({})

// 文件图标相关函数
const getExtension = (filename: string): string => {
  if (!filename) return 'FILE'
  const parts = filename.split('.')
  return parts.length > 1 ? parts.pop()!.substring(0, 4).toUpperCase() : 'FILE'
}

const getFileTypeClass = (filename: string = ''): string => {
  const ext = filename.toLowerCase()
  if (ext.includes('.pdf')) return 'icon-pdf'
  if (ext.includes('.doc') || ext.includes('.docx')) return 'icon-word'
  if (ext.includes('.txt') || ext.includes('.md')) return 'icon-text'
  return 'icon-default'
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

// 计算属性
const hasPendingFiles = computed(() =>
  files.value.some(f => f.status === 'pending')
)

const selectedDocumentFile = computed(() => {
  if (!selectedDocumentId.value) return null
  return uploadedFiles.value.find(f => f.uploadId === selectedDocumentId.value)?.file
})

// 获取任务状态
const getTaskStatus = (uploadId: number) => {
  return taskStatuses.value[uploadId]
}

const isProcessing = (uploadId?: number) => {
  if (!uploadId) return false
  const status = getTaskStatus(uploadId)
  return status?.status === 'processing'
}

const isFailed = (uploadId?: number) => {
  if (!uploadId) return false
  const status = getTaskStatus(uploadId)
  return status?.status === 'failed'
}

const isAnyProcessing = computed(() => {
  return uploadedFiles.value.some(f => {
    if (!f.uploadId) return false
    const status = getTaskStatus(f.uploadId)
    return status?.status === 'processing' || status?.status === 'pending'
  })
})

// 文件选择处理
const handleFilesSelected = (selectedFiles: File[]) => {
  const newFiles = selectedFiles.map(file => ({
    file,
    status: 'pending' as const,
    uploadId: Date.now() + Math.random()
  }))
  files.value.push(...newFiles)
}

// 移除文件
const removeFile = (index: number) => {
  files.value.splice(index, 1)
}

const resetState = () => {
  files.value = []
  currentStep.value = 1
  isLoading.value = false
  selectedDocumentId.value = null
  previewChunks.value = []
  taskStatuses.value = {}
}

const handleUpload = async () => {
  isLoading.value = true
  try {
    const formData = new FormData()
    files.value.filter(f => f.status === 'pending').forEach(f => {
      formData.append('files', f.file)
    })

    await knowledgeBaseApi.uploadDocuments(props.knowledgeBaseId!, formData)

    message.success('Files uploaded successfully')
    resetState()
    emit('complete')
  } catch (err: any) {
    files.value.forEach(f => {
      if (f.status === 'pending') {
        f.status = 'error'
        f.error = 'Upload failed'
      }
    })
    message.error(err.response?.data?.message || 'Upload failed')
  } finally {
    isLoading.value = false
  }
}

const handlePreview = async () => {
  message.info('Chunk preview is not available in this version')
}

const handleProcess = async () => {
  emit('complete')
}
</script>

<style scoped>
/* --------------------------------------
   Shadcn UI 深度复刻样式集
-------------------------------------- */
.upload-steps-container {
  width: 100%;
  max-width: 56rem; /* max-w-4xl */
  margin: 0 auto;
}

/* --- 1. 步骤指示器 (React flex-col 复刻) --- */
.shadcn-steps {
  display: flex;
  justify-content: space-between;
  margin-bottom: 2rem;
}
.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  position: relative;
}
.step-circle {
  width: 3rem;
  height: 3rem;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid;
  transition: all 0.2s ease;
  z-index: 2;
  background-color: var(--bg-primary);
}
.step-circle.active {
  background-color: var(--link-color);
  border-color: var(--link-color);
  color: #ffffff;
}
.step-circle.completed {
  background-color: var(--bg-secondary);
  border-color: var(--border-color);
  color: var(--text-primary);
}
.step-circle.pending {
  border-color: var(--border-color);
  color: var(--text-tertiary);
}
.step-icon {
  font-size: 24px;
}
.step-label {
  margin-top: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
}
.step-connector {
  position: absolute;
  bottom: -0.5rem; /* React版使用的是 mt-2 在底部 */
  left: 50%;
  width: 100%;
  height: 2px;
  background-color: var(--border-color);
  z-index: 1;
}
.step-connector.completed {
  background-color: var(--border-color-light);
}

/* --- 2. 卡片与布局 --- */
.steps-content-wrapper {
  margin-top: 1.5rem;
}
.step-card {
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
}
.card-body {
  padding: 1.5rem;
}
.space-y-4 > * + * { margin-top: 1rem; }
.space-y-6 > * + * { margin-top: 1.5rem; }
.mt-4 { margin-top: 1rem; }
.mt-6 { margin-top: 1.5rem; }
.flex { display: flex; }
.flex-col { flex-direction: column; }
.items-center { align-items: center; }
.items-stretch { align-items: stretch; }
.justify-between { justify-content: space-between; }
.w-full { width: 100%; }
.flex-1 { flex: 1; }
.space-x-4 > * + * { margin-left: 1rem; }

/* --- 3. 文件列表项 (Shadcn 风格) --- */
.files-list, .processing-list {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.shadcn-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background-color: var(--bg-primary);
}
.file-info-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.file-details {
  display: flex;
  flex-direction: column;
}
.file-name { margin: 0; font-size: 0.875rem; font-weight: 500; color: var(--text-primary); }
.file-size, .task-status-text { margin: 0; font-size: 0.75rem; color: var(--text-secondary); }
.file-actions-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.status-text { font-size: 0.875rem; font-weight: 500; }
.text-success { color: #22c55e; }
.text-destructive { color: #ef4444; }

.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 9999px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color 0.2s;
}
.icon-button:hover { background-color: var(--hover-bg); color: var(--text-primary); }

/* --- 4. 真实质感文件图标 --- */
.file-icon-wrapper {
  width: 2rem;
  height: 2.5rem;
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
.file-extension { font-size: 8px; font-weight: 700; color: white; letter-spacing: 0.5px; z-index: 1; }
.icon-pdf { background: linear-gradient(135deg, #ef4444, #b91c1c); }
.icon-word { background: linear-gradient(135deg, #3b82f6, #1d4ed8); }
.icon-text { background: linear-gradient(135deg, #94a3b8, #475569); }
.icon-default { background: linear-gradient(135deg, #cbd5e1, #64748b); }

/* --- 5. 表单与按钮复刻 (覆盖 Ant Design) --- */
.shadcn-title { font-size: 1.125rem; font-weight: 500; margin: 0; color: var(--text-primary); }
.settings-grid { display: grid; gap: 1rem; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.setting-item label { display: block; font-size: 0.875rem; font-weight: 500; margin-bottom: 0.5rem; color: var(--text-primary); }

/* 覆盖 AntD 默认样式以匹配 Shadcn */
:deep(.shadcn-btn-primary) {
  background-color: var(--link-color);
  border-color: var(--link-color);
  border-radius: 0.375rem;
  font-weight: 500;
}
:deep(.shadcn-btn-primary:hover) { background-color: var(--link-hover); border-color: var(--link-hover); }
:deep(.shadcn-btn-primary[disabled]) { background-color: var(--bg-secondary); border-color: var(--border-color); color: var(--text-tertiary); }

:deep(.shadcn-btn-secondary) {
  background-color: var(--bg-secondary);
  border-color: transparent;
  color: var(--text-primary);
  border-radius: 0.375rem;
  font-weight: 500;
}
:deep(.shadcn-btn-secondary:hover) { background-color: var(--hover-bg); }

:deep(.shadcn-btn-outline) {
  background-color: transparent;
  border-color: var(--border-color);
  color: var(--text-primary);
  border-radius: 0.375rem;
  font-weight: 500;
}
:deep(.shadcn-btn-outline:hover) { background-color: var(--hover-bg); }

:deep(.shadcn-select .ant-select-selector),
:deep(.shadcn-input) {
  border-radius: 0.375rem;
  border-color: var(--border-color);
}
:deep(.shadcn-collapse) { background: transparent; }
:deep(.shadcn-panel) { border-bottom: none; border-top: 1px solid var(--border-color); }
:deep(.shadcn-progress .ant-progress-bg) { height: 0.5rem !important; border-radius: 9999px; }

/* --- 6. Preview 容器样式 --- */
.preview-container { margin-top: 1rem; }
.preview-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.chunks-list { max-height: 300px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.chunk-item { padding: 1rem; background-color: var(--bg-secondary); border-radius: 0.5rem; }
.chunk-label { font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 0.5rem; }
.chunk-content { margin: 0; white-space: pre-wrap; font-size: 0.875rem; color: var(--text-primary); font-family: inherit; }

/* 简单淡入动画 */
.fade-in { animation: fadeIn 0.3s ease-in-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
</style>