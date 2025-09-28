<template>
  <a-modal
    v-model:open="visible"
    title="上传文件"
    width="600px"
    :footer="null"
    @cancel="handleClose"
    @after-close="handleAfterClose"
  >
    <FileUpload
      ref="fileUploadRef"
      @upload-success="handleUploadSuccess"
      @upload-error="handleUploadError"
    />
  </a-modal>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import FileUpload from './FileUpload.vue'

// 响应式数据
const visible = ref(false)
const fileUploadRef = ref()

// 监听全局上传事件
const handleOpenUpload = () => {
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
}

// 文件上传成功回调
const handleUploadSuccess = (file: any) => {
  message.success(`文件 ${file.name} 上传成功`)
  // 触发文件列表刷新事件
  window.dispatchEvent(new CustomEvent('refresh-file-list'))
  handleClose()
}

// 文件上传失败回调
const handleUploadError = (error: string) => {
  message.error(`上传失败: ${error}`)
}

// 组件挂载时添加事件监听
onMounted(() => {
  window.addEventListener('open-dataset-file-upload', handleOpenUpload)
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('open-dataset-file-upload', handleOpenUpload)
})
</script>

<style scoped>
/* 模态框样式可以在这里自定义 */
</style>
