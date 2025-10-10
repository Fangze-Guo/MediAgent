<template>
  <div class="file-upload">
    <!-- 上传区域 -->
    <div
        class="upload-area"
        :class="{
        'uploading': uploading,
        'drag-over': dragOver,
        'error': uploadError
      }"
        @click="triggerFileInput"
        @dragover.prevent="handleDragOver"
        @dragleave.prevent="handleDragLeave"
        @drop.prevent="handleDrop"
    >
      <input
          ref="fileInput"
          type="file"
          :accept="acceptedTypes"
          multiple
          @change="handleFileSelect"
          style="display: none"
      />

      <div v-if="!uploading" class="upload-content">
        <UploadOutlined class="upload-icon" />
        <div class="upload-text">
          <p class="upload-title">点击或拖拽文件到此处上传</p>
          <p class="upload-hint">{{ uploadHintText }}</p>
          <p class="upload-hint-small">可同时选择多个文件进行批量上传</p>
        </div>
      </div>

      <div v-else class="uploading-content">
        <a-spin size="large" />
        <p class="uploading-text">正在上传...</p>
        <a-progress
            :percent="uploadProgress"
            :show-info="false"
            stroke-color="#1890ff"
        />
      </div>
    </div>

    <!-- 待上传文件列表 -->
    <div v-if="pendingFiles.length > 0" class="pending-files">
      <div class="files-header">
        <h4 class="files-title">
          <FileOutlined />
          待上传文件 ({{ pendingFiles.length }})
        </h4>
        <div class="batch-actions">
          <a-button
              type="primary"
              size="small"
              @click="startUploadPendingFiles"
              :disabled="pendingFiles.length === 0 || uploading"
              :loading="uploading"
          >
            开始上传
          </a-button>
          <a-button
              type="link"
              size="small"
              danger
              @click="clearPendingFiles"
              :disabled="pendingFiles.length === 0"
          >
            清空列表
          </a-button>
        </div>
      </div>
      <div class="files-list">
        <div
            v-for="(file, index) in pendingFiles"
            :key="`pending-${index}`"
            class="file-item"
        >
          <div class="file-info">
            <FileOutlined class="file-icon" />
            <div class="file-details">
              <div class="file-name" :title="file.name">
                {{ file.name }}
              </div>
              <div class="file-meta">
                {{ formatFileSize(file.size) }} • {{ formatTime(file.lastModified.toString()) }}
              </div>
            </div>
          </div>
          <div class="file-actions">
            <a-button
                type="link"
                size="small"
                danger
                @click="removePendingFile(index)"
            >
              移除
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 已上传文件列表 -->
    <div v-if="uploadedFiles.length > 0" class="uploaded-files">
      <div class="files-header">
        <h4 class="files-title">
          <FileOutlined />
          已上传文件 ({{ uploadedFiles.length }})
        </h4>
        <div class="batch-actions">
          <a-button
              type="primary"
              size="small"
              @click="handleUseAllFiles"
              :disabled="uploadedFiles.length === 0"
          >
            全部使用
          </a-button>
          <a-button
              type="link"
              size="small"
              danger
              @click="handleRemoveAllFiles"
              :disabled="uploadedFiles.length === 0"
          >
            全部删除
          </a-button>
        </div>
      </div>
      <div class="files-list">
        <div
            v-for="file in uploadedFiles"
            :key="file.id"
            class="file-item"
        >
          <div class="file-info">
            <FileOutlined class="file-icon" />
            <div class="file-details">
              <div class="file-name" :title="file.name">
                {{ file.name }}
              </div>
              <div class="file-meta">
                {{ formatFileSize(file.size) }} • {{ formatTime(file.modifiedTime) }}
              </div>
            </div>
          </div>
          <div class="file-actions">
            <a-button
                type="link"
                size="small"
                @click="handleUseFile(file)"
            >
              使用
            </a-button>
            <a-button
                type="link"
                size="small"
                danger
                @click="handleRemoveFile(file.id)"
            >
              删除
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="uploadError" class="error-message">
      <a-alert
          :message="uploadError"
          type="error"
          show-icon
          closable
          @close="uploadError = ''"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件上传组件
 * 支持拖拽上传、进度显示和文件管理
 */
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined, FileOutlined } from '@ant-design/icons-vue'
import {
  uploadFile,
  formatFileSize,
  isSupportedFileType,
  type FileInfo
} from '@/apis/files.ts'

// Props
interface Props {
  /** 是否允许多文件上传 */
  multiple?: boolean
  /** 接受的文件类型 */
  accept?: string
  /** 最大文件大小（MB） */
  maxSize?: number
}

const props = withDefaults(defineProps<Props>(), {
  multiple: true,
  accept: 'image/*,.csv,.dcm,.DCM',
  maxSize: 10
})

// Emits
const emit = defineEmits<{
  /** 文件上传成功事件 */
  uploadSuccess: [file: FileInfo]
  /** 文件上传失败事件 */
  uploadError: [error: string]
  /** 使用文件事件 */
  useFile: [file: FileInfo]
  /** 批量使用完成事件 */
  batchUseComplete: []
}>()

// 响应式数据
const fileInput = ref<HTMLInputElement>()
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadError = ref('')
const dragOver = ref(false)
const uploadedFiles = ref<FileInfo[]>([])
const pendingFiles = ref<File[]>([])

// 计算属性
const acceptedTypes = computed(() => {
  return props.accept
})

const uploadHintText = computed(() => {
  return '支持多文件上传：图片文件 (JPG, PNG, GIF, WebP)、CSV 文件和 DICOM 文件 (.dcm)'
})

/**
 * 触发文件选择
 */
const triggerFileInput = () => {
  if (!uploading.value) {
    fileInput.value?.click()
  }
}

/**
 * 处理文件选择
 */
const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (files && files.length > 0) {
    // 先添加到待上传列表，不立即上传
    addFilesToUploadList(Array.from(files))
  }
  // 清空input，允许重复选择同一文件
  target.value = ''
}

/**
 * 处理拖拽进入
 */
const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  dragOver.value = true
}

/**
 * 处理拖拽离开
 */
const handleDragLeave = (event: DragEvent) => {
  event.preventDefault()
  dragOver.value = false
}

/**
 * 处理文件拖拽放置
 */
const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  dragOver.value = false

  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    // 先添加到待上传列表，不立即上传
    addFilesToUploadList(Array.from(files))
  }
}

/**
 * 添加文件到待上传列表
 */
const addFilesToUploadList = (files: File[]) => {
  const validFiles: File[] = []

  // 验证文件
  for (const file of files) {
    if (!isSupportedFileType(file)) {
      message.error(`不支持的文件类型: ${file.name}`)
      continue
    }

    if (file.size > props.maxSize * 1024 * 1024) {
      message.error(`文件 ${file.name} 超过大小限制 (${props.maxSize}MB)`)
      continue
    }

    validFiles.push(file)
  }

  // 添加到待上传列表
  pendingFiles.value.push(...validFiles)

  if (validFiles.length > 0) {
    message.success(`已添加 ${validFiles.length} 个文件到上传列表`)
  }
}

/**
 * 处理文件上传
 */
const handleFiles = async (files: File[]) => {
  // 验证文件
  for (const file of files) {
    if (!isSupportedFileType(file)) {
      message.error(`不支持的文件类型: ${file.name}`)
      continue
    }

    if (file.size > props.maxSize * 1024 * 1024) {
      message.error(`文件 ${file.name} 超过大小限制 (${props.maxSize}MB)`)
    }
  }

  // 上传文件
  for (const file of files) {
    if (isSupportedFileType(file) && file.size <= props.maxSize * 1024 * 1024) {
      await uploadSingleFile(file)
    }
  }
}

/**
 * 上传单个文件
 */
const uploadSingleFile = async (file: File) => {
  try {
    uploading.value = true
    uploadProgress.value = 0
    uploadError.value = ''

    // 数据集上传
    const response = await uploadFile(file, '.', (progress) => {
      uploadProgress.value = progress
    })

    if (response.code === 200) {
      uploadedFiles.value.push(response.data)
      emit('uploadSuccess', response.data)
    } else {
      const errorMsg = response.message || '上传失败'
      uploadError.value = errorMsg
      emit('uploadError', errorMsg)
      message.error(errorMsg)
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '上传失败'
    uploadError.value = errorMessage
    emit('uploadError', errorMessage)
    message.error(errorMessage)
  } finally {
    uploading.value = false
    uploadProgress.value = 0
  }
}

/**
 * 使用文件
 */
const handleUseFile = (file: FileInfo) => {
  emit('useFile', file)
}

/**
 * 删除文件
 */
const handleRemoveFile = (fileId: string) => {
  uploadedFiles.value = uploadedFiles.value.filter(f => f.id !== fileId)
  message.success('文件已删除')
}

/**
 * 使用所有文件
 */
const handleUseAllFiles = () => {
  if (uploadedFiles.value.length === 0) {
    message.warning('没有可用的文件')
    return
  }

  // 触发所有文件的使用事件
  uploadedFiles.value.forEach(file => {
    emit('useFile', file)
  })

  message.success(`已添加 ${uploadedFiles.value.length} 个文件到当前会话`)

  // 批量使用后关闭模态框
  emit('batchUseComplete')
}

/**
 * 删除所有文件
 */
const handleRemoveAllFiles = () => {
  if (uploadedFiles.value.length === 0) {
    message.warning('没有可删除的文件')
    return
  }

  const fileCount = uploadedFiles.value.length
  uploadedFiles.value = []
  message.success(`已删除 ${fileCount} 个文件`)
}


/**
 * 开始上传待上传列表中的文件
 */
const startUploadPendingFiles = async () => {
  if (pendingFiles.value.length === 0) {
    message.warning('没有待上传的文件')
    return
  }

  const filesToUpload = [...pendingFiles.value]
  pendingFiles.value = [] // 清空待上传列表

  await handleFiles(filesToUpload)
}

/**
 * 删除待上传文件
 */
const removePendingFile = (index: number) => {
  pendingFiles.value.splice(index, 1)
  message.success('文件已从上传列表移除')
}

/**
 * 清空待上传列表
 */
const clearPendingFiles = () => {
  const count = pendingFiles.value.length
  pendingFiles.value = []
  if (count > 0) {
    message.success(`已清空 ${count} 个待上传文件`)
  }
}

/**
 * 格式化时间
 */
const formatTime = (timeString: string): string => {
  return new Date(timeString).toLocaleString('zh-CN')
}

/**
 * 重置上传状态（供父组件调用）
 */
const resetUploadState = () => {
  uploading.value = false
  uploadProgress.value = 0
  uploadError.value = ''
  pendingFiles.value = []
  uploadedFiles.value = []
}

// 暴露方法给父组件
defineExpose({
  resetUploadState
})

</script>

<style scoped>
.file-upload {
  width: 100%;
}

.upload-area {
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: #fafafa;
  min-height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-area:hover {
  border-color: #1890ff;
  background: #f0f8ff;
}

.upload-area.drag-over {
  border-color: #1890ff;
  background: #e6f7ff;
}

.upload-area.uploading {
  border-color: #1890ff;
  background: #f0f8ff;
  cursor: not-allowed;
}

.upload-area.error {
  border-color: #ff4d4f;
  background: #fff2f0;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.upload-icon {
  font-size: 32px;
  color: #1890ff;
}

.upload-title {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
  color: #333;
}

.upload-hint {
  font-size: 12px;
  color: #666;
  margin: 0;
}

.upload-hint-small {
  font-size: 11px;
  color: #999;
  margin: 4px 0 0 0;
}

.uploading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.uploading-text {
  font-size: 16px;
  color: #1890ff;
  margin: 0;
}

.pending-files {
  margin-top: 24px;
}

.uploaded-files {
  margin-top: 24px;
}

.files-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.files-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: #333;
}

.batch-actions {
  display: flex;
  gap: 8px;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  background: #fff;
  transition: all 0.3s ease;
}

.file-item:hover {
  border-color: #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.1);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.file-icon {
  font-size: 24px;
  color: #1890ff;
  flex-shrink: 0;
}

.file-details {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta {
  font-size: 12px;
  color: #666;
  margin-top: 2px;
}

.file-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.error-message {
  margin-top: 16px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .upload-area {
    padding: 20px 16px;
    min-height: 100px;
  }

  .upload-icon {
    font-size: 32px;
  }

  .upload-title {
    font-size: 14px;
  }

  .upload-hint {
    font-size: 12px;
  }

  .file-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .file-actions {
    align-self: flex-end;
  }
}
</style>
