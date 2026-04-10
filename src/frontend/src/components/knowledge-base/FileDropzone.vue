<template>
  <div
    class="dropzone"
    :class="{ 'drag-active': isDragActive }"
    @dragover.prevent="handleDragOver"
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
    @click="handleClick"
  >
    <input
      ref="fileInput"
      type="file"
      multiple
      :accept="accept"
      style="display: none"
      @change="handleFileChange"
    />
    <div class="dropzone-content">
      <UploadOutlined class="dropzone-icon" />
      <p class="dropzone-text">{{ text }}</p>
      <p class="dropzone-hint">{{ hint }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UploadOutlined } from '@ant-design/icons-vue'

interface Props {
  accept?: string
  text?: string
  hint?: string
}

const props = withDefaults(defineProps<Props>(), {
  accept: '.pdf,.docx,.txt,.md',
  text: 'Drop your files here or click to browse',
  hint: 'Supports PDF, DOCX, TXT, and MD files'
})

const emit = defineEmits<{
  filesSelected: [files: File[]]
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const isDragActive = ref(false)

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
  isDragActive.value = true
}

const handleDragLeave = (e: DragEvent) => {
  e.preventDefault()
  isDragActive.value = false
}

const handleDrop = (e: DragEvent) => {
  e.preventDefault()
  isDragActive.value = false

  const files = Array.from(e.dataTransfer?.files || [])
  const acceptedFiles = filterFiles(files)

  if (acceptedFiles.length > 0) {
    emit('filesSelected', acceptedFiles)
  }
}

const handleClick = () => {
  fileInput.value?.click()
}

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  const files = Array.from(target.files || [])
  const acceptedFiles = filterFiles(files)

  if (acceptedFiles.length > 0) {
    emit('filesSelected', acceptedFiles)
  }

  // 重置input以允许再次选择相同文件
  target.value = ''
}

const filterFiles = (files: File[]): File[] => {
  const acceptedExtensions = props.accept.split(',').map(ext => ext.trim().toLowerCase())

  return files.filter(file => {
    const fileExt = '.' + file.name.split('.').pop()?.toLowerCase()
    return acceptedExtensions.includes(fileExt)
  })
}
</script>

<style scoped>
.dropzone {
  border: 2px dashed #e2e8f0;
  border-radius: 0.5rem;
  padding: 3rem 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #ffffff;
}

.dropzone:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.dropzone.drag-active {
  border-color: #3b82f6;
  background: #eff6ff;
}

.dropzone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.dropzone-icon {
  font-size: 3rem;
  color: #94a3b8;
}

.dropzone-text {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: #0f172a;
}

.dropzone-hint {
  margin: 0;
  font-size: 0.75rem;
  color: #64748b;
}
</style>
