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
      :current-path="currentPath"
      @upload-success="handleUploadSuccess"
      @upload-error="handleUploadError"
    />
  </a-modal>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import FileUpload from './FileUpload.vue'

// 响应式数据
const visible = ref(false)
const fileUploadRef = ref()
const currentPath = ref('.')

// 打开上传模态框
const handleOpenUpload = (event: Event) => {
  // 从事件中获取当前路径
  const customEvent = event as CustomEvent
  if (customEvent && customEvent.detail && customEvent.detail.currentPath) {
    currentPath.value = customEvent.detail.currentPath
  } else {
    currentPath.value = '.'
  }
  
  // 打开前先重置状态，确保是干净的界面
  if (fileUploadRef.value) {
    fileUploadRef.value.resetUploadState()
  }
  
  nextTick(() => {
    visible.value = true
  })
}

// 处理关闭
const handleClose = () => {
  visible.value = false
  // 关闭时立即清空状态
  nextTick(() => {
    if (fileUploadRef.value) {
      fileUploadRef.value.resetUploadState()
    }
  })
}

// 处理模态框完全关闭后
const handleAfterClose = () => {
  // 双重保险：模态框完全关闭后再次重置
  if (fileUploadRef.value) {
    fileUploadRef.value.resetUploadState()
  }
}

// 文件上传成功回调
const handleUploadSuccess = () => {
  // 批量上传在handleFiles中已统一提示，这里不再重复提示
  // 触发文件列表刷新
  window.dispatchEvent(new CustomEvent('refresh-file-list'))
  // 不立即关闭，让用户看到上传成功的文件列表
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
