<template>
  <div class="uploaded-file-browser">
    <!-- 路径导航 -->
    <div class="path-navigation">
      <a-breadcrumb>
        <a-breadcrumb-item>
          <a @click="navigateToPath('.')">
            <HomeOutlined style="margin-right: 4px;" />
            文件目录
          </a>
        </a-breadcrumb-item>
        <a-breadcrumb-item v-for="(part, index) in pathParts" :key="index">
          <a @click="navigateToPath(getPathUpTo(index))">{{ part }}</a>
        </a-breadcrumb-item>
      </a-breadcrumb>
    </div>

    <div class="toolbar">
      <div class="toolbar-left">
        <a-button @click="goUp" :disabled="!canGoUp">
          <template #icon>
            <ArrowUpOutlined />
          </template>
          上级目录
        </a-button>
        <a-button @click="refresh" :loading="fileStore.loading">
          <template #icon>
            <ReloadOutlined />
          </template>
          刷新
        </a-button>
        <a-button type="primary" @click="handleUploadClick">
          <template #icon>
            <UploadOutlined />
          </template>
          上传文件
        </a-button>
      </div>
      <div class="toolbar-right">
        <span class="file-count">共 {{ fileStore.fileList.length }} 个文件</span>
        <a-button
            v-if="fileStore.selectedCount > 0"
            danger
            @click="handleBatchDelete"
        >
          <template #icon>
            <DeleteOutlined />
          </template>
          批量删除 ({{ fileStore.selectedCount }})
        </a-button>
      </div>
    </div>

    <div class="file-list" @drop="handleDrop" @dragover="handleDragOver" @dragenter="handleDragEnter"
         @dragleave="handleDragLeave" :class="{ 'drag-over': isDragOver }">
      <a-table
          :data-source="dataSource"
          :columns="columns"
          :pagination="false"
          :loading="fileStore.loading"
          :row-selection="{ selectedRowKeys: fileStore.selectedFileIds, onChange: onSelectChange }"
          size="middle"
          class="file-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'originalName'">
            <div class="file-name-cell">
              <component
                  :is="record.type.startsWith('image/') ? PictureOutlined : (record.type.includes('csv') ? FileExcelOutlined : FileOutlined)"
                  class="file-icon" />
              <span class="file-name" :title="record.originalName">{{ record.originalName }}</span>
            </div>
          </template>
          <template v-else-if="column.dataIndex === 'type'">
            <a-tag
                :color="record.type.startsWith('image/') ? 'blue' : (record.type.includes('csv') ? 'green' : 'default')">
              {{ record.type.startsWith('image/') ? '图片' : (record.type.includes('csv') ? 'CSV' : '其他') }}
            </a-tag>
          </template>
          <template v-else-if="column.dataIndex === 'size'">
            {{ formatFileSize(record.size) }}
          </template>
          <template v-else-if="column.dataIndex === 'uploadTime'">
            {{ new Date(record.uploadTime).toLocaleString('zh-CN') }}
          </template>
          <template v-else-if="column.dataIndex === 'actions'">
            <div class="actions">
              <a-button type="text" size="small" title="预览" @click="previewFileHandler(record)">
                <EyeOutlined />
              </a-button>
              <a-button type="text" size="small" title="下载" @click="downloadFile(record)">
                <DownloadOutlined />
              </a-button>
              <a-button type="text" size="small" danger title="删除" @click="deleteFileHandler(record)">
                <DeleteOutlined />
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal v-model:open="previewVisible" title="文件预览" width="800px" :footer="null">
      <div v-if="previewFile" class="file-preview">
        <div v-if="previewFile.type.startsWith('image/')" class="image-preview">
          <img :src="getImageUrl(previewFile)" :alt="previewFile.originalName"
               style="max-width: 100%; max-height: 500px; object-fit: contain;" />
        </div>
        <div v-else class="file-info">
          <FileOutlined style="font-size: 48px; color: #1890ff; margin-bottom: 16px;" />
          <h3>{{ previewFile.originalName }}</h3>
          <p>文件大小: {{ previewFile.size }}</p>
          <p>文件类型: {{ previewFile.type }}</p>
          <p>上传时间: {{ previewFile.uploadTime }}</p>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  ArrowUpOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EyeOutlined,
  FileExcelOutlined,
  FileOutlined,
  HomeOutlined,
  PictureOutlined,
  ReloadOutlined,
  UploadOutlined,
} from '@ant-design/icons-vue'
import { formatFileSize, uploadFile } from '@/apis/files'
import { useFileStore } from '@/store/files'

const fileStore = useFileStore()

const previewVisible = ref(false)
const previewFile = ref<any>(null)
const isDragOver = ref(false)

// 与 OutputFileBrowser 一致的列定义与 bodyCell 渲染习惯
const columns = [
  {
    title: '名称',
    dataIndex: 'originalName',
    key: 'originalName',
    sorter: (a: any, b: any) => a.originalName.localeCompare(b.originalName),
  },
  {
    title: '类型',
    dataIndex: 'type',
    key: 'type',
    width: 120,
  },
  {
    title: '大小',
    dataIndex: 'size',
    key: 'size',
    width: 120,
    sorter: (a: any, b: any) => a.size - b.size,
  },
  {
    title: '上传时间',
    dataIndex: 'uploadTime',
    key: 'uploadTime',
    width: 180,
    sorter: (a: any, b: any) => new Date(a.uploadTime).getTime() - new Date(b.uploadTime).getTime(),
  },
  {title: '操作', dataIndex: 'actions', key: 'actions', width: 150},
]

// 仍保持原始数据类型，模板中格式化展示
const dataSource = computed(() => fileStore.filteredFiles.map(f => ({
  key: f.id,
  id: f.id,
  originalName: f.originalName,
  size: f.size,
  type: f.type,
  uploadTime: f.uploadTime,
})))

// 路径导航（已上传文件没有目录结构，这里做禁用处理）
const pathParts = computed(() => [])
const canGoUp = computed(() => false)
const getPathUpTo = (_index: number) => '.'
const navigateToPath = (_path: string) => {
  refresh()
}
const goUp = () => {
}

const onSelectChange = (keys: string[]) => {
  fileStore.setSelectedFileIds(keys)
}

const refresh = async () => {
  try {
    await fileStore.fetchFileList()
  } catch (e) {
    message.error('获取文件列表失败')
  }
}

const deleteFileHandler = (file: any) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除文件 "${file.originalName}" 吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      const ok = await fileStore.removeFile(file.id)
      if (ok) message.success('文件删除成功')
      else message.error(fileStore.error || '删除文件失败')
    }
  })
}

const handleBatchDelete = () => {
  if (fileStore.selectedCount === 0) {
    message.warning('请选择要删除的文件')
    return
  }
  Modal.confirm({
    title: '确认批量删除',
    content: `确定要删除选中的 ${fileStore.selectedCount} 个文件吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      const result = await fileStore.removeFiles(fileStore.selectedFileIds)
      if (result.success) message.success(`成功删除 ${result.deletedCount} 个文件`)
      else message.error(fileStore.error || '批量删除失败')
    }
  })
}

const downloadFile = async (file: any) => {
  const result = await fileStore.downloadFileById(file.id)
  if (result.success && result.downloadUrl) {
    const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
    const fullUrl = `${baseURL}${result.downloadUrl}`
    const link = document.createElement('a')
    link.href = fullUrl
    link.download = file.originalName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    message.success('文件下载开始')
  } else {
    message.error(fileStore.error || '下载文件失败')
  }
}

const previewFileHandler = (file: any) => {
  previewFile.value = file
  previewVisible.value = true
}

const getImageUrl = (file: any) => {
  const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
  return `${baseURL}/files/serve/${file.id}`
}

const handleUploadClick = () => {
  openFileUploadDialog()
}

const openFileUploadDialog = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = true
  input.onchange = async (event) => {
    const files = (event.target as HTMLInputElement).files
    if (files && files.length > 0) {
      await uploadSelectedFiles(Array.from(files))
    }
  }
  input.click()
}

const uploadSelectedFiles = async (files: File[]) => {
  try {
    for (const file of files) {
      const result = await uploadFile(file)
      if (result.success) {
        await refresh()
      } else {
        throw new Error(result.error || '上传失败')
      }
    }
    message.success(`成功上传 ${files.length} 个文件`)
  } catch (error) {
    message.error(`上传失败: ${error instanceof Error ? error.message : '未知错误'}`)
  }
}

const handleDragOver = (e: DragEvent) => {
  e.preventDefault();
  e.stopPropagation()
}
const handleDragEnter = (e: DragEvent) => {
  e.preventDefault();
  e.stopPropagation();
  isDragOver.value = true
}
const handleDragLeave = (e: DragEvent) => {
  e.preventDefault();
  e.stopPropagation();
  isDragOver.value = false
}
const handleDrop = async (e: DragEvent) => {
  e.preventDefault();
  e.stopPropagation();
  isDragOver.value = false
  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length > 0) await uploadSelectedFiles(files)
}

const handleOpenUploadEvent = () => {
  openFileUploadDialog()
}
const handleRefreshEvent = () => {
  refresh()
}

onMounted(() => {
  refresh()
  window.addEventListener('open-file-upload', handleOpenUploadEvent)
  window.addEventListener('refresh-file-list', handleRefreshEvent)
})

onUnmounted(() => {
  window.removeEventListener('open-file-upload', handleOpenUploadEvent)
  window.removeEventListener('refresh-file-list', handleRefreshEvent)
})
</script>

<style scoped>
.uploaded-file-browser {
  padding: 16px;
}

.path-navigation {
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 6px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-count {
  font-size: 14px;
  color: #666;
}

.file-list {
  background: white;
  border-radius: 6px;
  transition: all 0.3s ease;
}

.file-list.drag-over {
  background: #f0f9ff;
  border: 2px dashed #1890ff;
  box-shadow: 0 0 10px rgba(24, 144, 255, 0.3);
}

.file-table {
  border: 1px solid #f0f0f0;
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  font-size: 16px;
  color: #1890ff;
}

.file-name {
  font-weight: 500;
  color: #333;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions {
  display: flex;
  gap: 8px;
}

.file-preview {
  text-align: center;
  padding: 20px;
}

.image-preview {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

.file-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.file-info h3 {
  margin: 0;
  color: #333;
}

.file-info p {
  margin: 0;
  color: #666;
  font-size: 14px;
}
</style>