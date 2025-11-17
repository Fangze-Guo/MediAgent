<template>
  <div class="file-upload">
    <!-- 上传区域 -->
    <div class="upload-area" :class="{
      'uploading': uploading,
      'drag-over': dragOver,
      'error': uploadError
    }" @click="triggerFileInput" @dragover.prevent="handleDragOver" @dragleave.prevent="handleDragLeave"
      @drop.prevent="handleDrop">
      <input ref="fileInput" type="file" :accept="acceptedTypes" multiple @change="handleFileSelect"
        style="display: none" />

      <div v-if="!uploading" class="upload-content">
        <UploadOutlined class="upload-icon" />
        <div class="upload-text">
          <p class="upload-title">{{ t('components_FileUpload.dropzoneText') }}</p>
          <p class="upload-hint">{{ uploadHintText }}</p>
          <p class="upload-hint-small">{{ t('components_FileUpload.dropzoneHint') }}</p>
        </div>
      </div>

      <div v-else class="uploading-content">
        <a-spin size="large" />
        <p class="uploading-text">{{ t('components_FileUpload.uploading') }}</p>
        <a-progress :percent="uploadProgress" :show-info="false" stroke-color="#1890ff" />
      </div>
    </div>

    <!-- 待上传文件列表 -->
    <div v-if="pendingFiles.length > 0" class="pending-files">
      <div class="files-header">
        <h4 class="files-title">
          <FileOutlined />
          {{ t('components_FileUpload.pendingFiles', { count: pendingFiles.length }) }}
        </h4>
        <div class="batch-actions">
          <a-button type="primary" size="small" @click="startUploadPendingFiles"
            :disabled="pendingFiles.length === 0 || uploading" :loading="uploading">
            {{ t('components_FileUpload.startUpload') }}
          </a-button>
          <a-button type="link" size="small" danger @click="clearPendingFiles" :disabled="pendingFiles.length === 0">
            {{ t('components_FileUpload.clearList') }}
          </a-button>
        </div>
      </div>
      <div class="files-list">
        <div v-for="(file, index) in pendingFiles" :key="`pending-${index}`" class="file-item">
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
            <a-button type="link" size="small" danger @click="removePendingFile(index)">
              {{ t('components_FileUpload.remove') }}
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
          {{ t('components_FileUpload.uploadedFiles', { count: uploadedFiles.length }) }}
        </h4>
        <div class="success-info">
          <a-tag color="success">{{ t('components_FileUpload.uploadSuccess') }}</a-tag>
          <span class="hint-text">{{ t('components_FileUpload.uploadSuccessHint') }}</span>
        </div>
      </div>
      <div class="files-list">
        <div v-for="file in uploadedFiles" :key="file.id" class="file-item uploaded">
          <div class="file-info">
            <FileOutlined class="file-icon success-icon" />
            <div class="file-details">
              <div class="file-name" :title="file.name">
                {{ file.name }}
              </div>
              <div class="file-meta">
                {{ formatFileSize(file.size) }} • {{ t('components_FileUpload.uploadSuccess') }}
              </div>
            </div>
          </div>
          <div class="file-status">
            <a-tag color="success">✓</a-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="uploadError" class="error-message">
      <a-alert :message="uploadError" type="error" show-icon closable @close="uploadError = ''" />
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
import { useI18n } from 'vue-i18n'

// 国际化
const { t } = useI18n()

// Props
interface Props {
  /** 是否允许多文件上传 */
  multiple?: boolean
  /** 接受的文件类型 */
  accept?: string
  /** 最大文件大小（MB） */
  maxSize?: number
  /** 当前路径，用于上传到指定目录 */
  currentPath?: string
}

const props = withDefaults(defineProps<Props>(), {
  multiple: true,
  accept: 'image/*,.csv,.dcm,.DCM',
  maxSize: 10,
  currentPath: '.'
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
  return t('components_FileUpload.supportedFormats')
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

  for (const file of files) {
    if (!isSupportedFileType(file)) {
      message.error(file.name)
      continue
    }

    if (file.size > props.maxSize * 1024 * 1024) {
      message.error(t('components_FileUpload.messages.sizeExceeded', { fileName: file.name, maxSize: props.maxSize }))
      continue
    }

    validFiles.push(file)
  }

  // 添加到待上传列表
  pendingFiles.value.push(...validFiles)

  if (validFiles.length > 0) {
    message.success(t('components_FileUpload.messages.filesAdded', { count: validFiles.length }))
  }
}

/**
 * 处理文件上传（批量模式，统一提示）
 */
const handleFiles = async (files: File[]) => {
  let successCount = 0
  let failedCount = 0
  const errors: string[] = []

  // 上传文件
  for (const file of files) {
    if (!isSupportedFileType(file)) {
      errors.push(t('components_FileUpload.messages.unsupportedType', { fileName: file.name }))
      failedCount++
      continue
    }

    if (file.size > props.maxSize * 1024 * 1024) {
      errors.push(t('components_FileUpload.messages.sizeExceeded', { fileName: file.name, maxSize: props.maxSize }))
      failedCount++
      continue
    }

    const result = await uploadSingleFile(file, true)  // true表示批量模式
    if (result) {
      successCount++
    } else {
      failedCount++
    }
  }

  // 批量上传完成后，统一显示结果
  if (successCount > 0 && failedCount === 0) {
    message.success(t('components_FileUpload.messages.allSuccess', { successCount }))
    // 刷新文件列表
    window.dispatchEvent(new CustomEvent('refresh-file-list'))
  } else if (successCount > 0 && failedCount > 0) {
    message.warning(t('components_FileUpload.messages.partialSuccess', { successCount, failedCount }))
    if (errors.length > 0) {
      console.error(t('components_FileUpload.messages.failureDetails'), errors)
    }
    window.dispatchEvent(new CustomEvent('refresh-file-list'))
  } else if (failedCount > 0) {
    message.error(t('components_FileUpload.messages.allFailed', { failedCount }))
    if (errors.length > 0) {
      console.error(t('components_FileUpload.messages.failureDetails'), errors)
    }
  }
}

/**
 * 上传单个文件
 * @param file 要上传的文件
 * @param isBatch 是否为批量上传模式（批量模式不显示单个文件提示）
 * @returns 上传是否成功
 */
const uploadSingleFile = async (file: File, isBatch: boolean = false): Promise<boolean> => {
  try {
    uploading.value = true
    uploadProgress.value = 0
    uploadError.value = ''

    // 数据集上传，使用props.currentPath作为上传目标目录
    const response = await uploadFile(file, props.currentPath, (progress) => {
      uploadProgress.value = progress
    })

    if (response.code === 200) {
      uploadedFiles.value.push(response.data)
      emit('uploadSuccess', response.data)

      // 非批量模式才显示单个文件成功提示
      if (!isBatch) {
        message.success(t('components_FileUpload.messages.fileSuccess', { fileName: file.name }))
        window.dispatchEvent(new CustomEvent('refresh-file-list'))
      }

      return true
    } else {
      const errorMsg = response.message || t('components_FileUpload.messages.uploadFailed')
      uploadError.value = errorMsg
      emit('uploadError', errorMsg)

      // 非批量模式才显示单个文件错误提示
      if (!isBatch) {
        message.error(errorMsg)
      }

      return false
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : t('components_FileUpload.messages.uploadFailed')
    uploadError.value = errorMessage
    emit('uploadError', errorMessage)

    // 非批量模式才显示单个文件错误提示
    if (!isBatch) {
      message.error(errorMessage)
    }

    return false
  } finally {
    uploading.value = false
    uploadProgress.value = 0
  }
}

/**
 * 开始上传待上传列表中的文件
 */
const startUploadPendingFiles = async () => {
  if (pendingFiles.value.length === 0) {
    message.warning(t('components_FileUpload.messages.noFiles'))
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
  message.success(t('components_FileUpload.messages.fileRemoved'))
}

/**
 * 清空待上传列表
 */
const clearPendingFiles = () => {
  const count = pendingFiles.value.length
  pendingFiles.value = []
  if (count > 0) {
    message.success(t('components_FileUpload.messages.listCleared', { count }))
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

.file-status {
  flex-shrink: 0;
}

/* 成功信息样式 */
.success-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hint-text {
  font-size: 12px;
  color: #52c41a;
}

/* 已上传文件项样式优化 */
.file-item.uploaded {
  background: #f6ffed;
  border-color: #b7eb8f;
}

.file-item.uploaded:hover {
  border-color: #52c41a;
  box-shadow: 0 2px 8px rgba(82, 196, 26, 0.15);
}

.success-icon {
  color: #52c41a;
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
