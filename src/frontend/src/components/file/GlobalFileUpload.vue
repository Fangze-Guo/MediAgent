<template>
  <a-modal
    v-model:open="visible"
    :title="modalTitle"
    :width="uploadMode === 'sandbox' ? '700px' : '600px'"
    :footer="null"
    @cancel="handleClose"
    @after-close="handleAfterClose"
  >
    <FileUpload
      ref="fileUploadRef"
      :upload-mode="uploadMode"
      :sandbox-type="sandboxType"
      @upload-success="handleUploadSuccess"
      @upload-error="handleUploadError"
      @batch-use-complete="handleBatchUseComplete"
    />
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import FileUpload from './FileUpload.vue'

// 响应式数据
const visible = ref(false)
const fileUploadRef = ref()

// 监听全局上传事件
// 沙盒上传状态
const uploadMode = ref<'dataset' | 'sandbox'>('dataset')
const sandboxType = ref<'dicom' | 'nii'>('dicom')

// 计算属性
const modalTitle = computed(() => {
  if (uploadMode.value === 'sandbox') {
    return `上传${sandboxType.value === 'dicom' ? 'DICOM' : 'NII'}文件`
  }
  return '上传文件'
})

const handleOpenUpload = () => {
  visible.value = true
}

// 监听沙盒上传事件
const handleOpenSandboxUpload = (event: any) => {
  uploadMode.value = 'sandbox'
  sandboxType.value = event.detail.type || 'dicom'
  visible.value = true
}

// 处理关闭
const handleClose = () => {
  visible.value = false
}

// 处理模态框完全关闭后
const handleAfterClose = () => {
  // 重置FileUpload组件的状态
  if (fileUploadRef.value) {
    fileUploadRef.value.resetUploadState()
  }
  // 重置为数据集模式
  uploadMode.value = 'dataset'
  sandboxType.value = 'dicom'
}

// 文件上传成功回调
const handleUploadSuccess = (file: any) => {
  message.success(`文件 ${file.name} 上传成功`)
  
  if (uploadMode.value === 'sandbox') {
    // 沙盒模式：触发沙盒文件统计刷新，但不关闭模态框
    window.dispatchEvent(new CustomEvent('refresh-sandbox-stats'))
  } else {
    // 数据集模式：触发文件列表刷新并关闭模态框
    window.dispatchEvent(new CustomEvent('refresh-file-list'))
    handleClose()
  }
}

// 文件上传失败回调
const handleUploadError = (error: string) => {
  message.error(`上传失败: ${error}`)
}

// 批量操作完成回调（沙盒模式关闭模态框）
const handleBatchUseComplete = () => {
  if (uploadMode.value === 'sandbox') {
    message.success('文件上传完成！')
    handleClose()
  }
}

// 组件挂载时添加事件监听
onMounted(() => {
  window.addEventListener('open-dataset-file-upload', handleOpenUpload)
  window.addEventListener('open-sandbox-file-upload', handleOpenSandboxUpload)
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('open-dataset-file-upload', handleOpenUpload)
  window.removeEventListener('open-sandbox-file-upload', handleOpenSandboxUpload)
})
</script>

<style scoped>
/* 模态框样式可以在这里自定义 */
</style>
