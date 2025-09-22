<template>
  <div class="file-attachment">
    <div class="attachment-header">
      <FileOutlined class="attachment-icon" />
      <span class="attachment-label">已上传文件</span>
    </div>
    <div class="attachment-content">
      <div class="file-info">
        <div class="file-icon-wrapper">
          <FileOutlined v-if="!isImage" class="file-icon" />
          <img v-else :src="filePreview" :alt="file.name" class="file-preview" />
        </div>
        <div class="file-details">
          <div class="file-name" :title="file.name">{{ file.name }}</div>
          <div class="file-meta">
            {{ formatFileSize(file.size) }} • {{ file.type }}
          </div>
        </div>
      </div>
      <div class="attachment-actions">
        <a-button type="link" size="small" @click="handleRemove">
          <DeleteOutlined />
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { FileOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { formatFileSize } from '@/apis/files'

interface Props {
  file: {
    id: string
    name: string
    size: number
    type: string
    path: string
    modifiedTime: string
    isDirectory: boolean
  }
}

interface Emits {
  (e: 'remove', fileId: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 判断是否为图片文件
const isImage = computed(() => {
  return props.file.type.startsWith('image/')
})

// 生成文件预览URL（如果是图片）
const filePreview = computed(() => {
  if (isImage.value) {
    // 这里可以根据实际需求生成预览URL
    // 可能需要调用后端API获取文件预览
    return `data:${props.file.type};base64,` // 临时占位符
  }
  return ''
})

// 处理删除
const handleRemove = () => {
  emit('remove', props.file.id)
}
</script>

<style scoped>
.file-attachment {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fafafa;
  margin: 8px 0;
  overflow: hidden;
}

.attachment-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f0f0f0;
  border-bottom: 1px solid #e8e8e8;
  font-size: 12px;
  color: #666;
}

.attachment-icon {
  font-size: 14px;
  color: #1890ff;
}

.attachment-label {
  font-weight: 500;
}

.attachment-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.file-icon-wrapper {
  flex-shrink: 0;
}

.file-icon {
  font-size: 24px;
  color: #1890ff;
}

.file-preview {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
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

.attachment-actions {
  flex-shrink: 0;
}

.attachment-actions .ant-btn {
  padding: 4px 8px;
  height: auto;
  color: #999;
}

.attachment-actions .ant-btn:hover {
  color: #ff4d4f;
}
</style>
