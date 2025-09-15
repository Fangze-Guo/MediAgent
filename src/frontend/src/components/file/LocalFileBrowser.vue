<template>
  <div class="local-file-browser">
    <!-- 路径导航 -->
    <div class="path-navigation">
      <a-breadcrumb>
        <a-breadcrumb-item>
          <a @click="navigateToPath('.')">
            <HomeOutlined style="margin-right: 4px;" />
            根目录
          </a>
        </a-breadcrumb-item>
        <a-breadcrumb-item v-for="(part, index) in pathParts" :key="index">
          <a @click="navigateToPath(getPathUpTo(index))">{{ part }}</a>
        </a-breadcrumb-item>
      </a-breadcrumb>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <a-button @click="goUp" :disabled="!canGoUp">
          <template #icon>
            <ArrowUpOutlined />
          </template>
          上级目录
        </a-button>
        <a-button @click="refresh">
          <template #icon>
            <ReloadOutlined />
          </template>
          刷新
        </a-button>
        <a-button type="primary" @click="handleUploadClick">
          <template #icon>
            <UploadOutlined />
          </template>
          上传到当前目录
        </a-button>
      </div>
      <div class="toolbar-right">
        <span class="file-count">共 {{ fileList.length }} 个项目</span>
        <a-button
          v-if="selectedFiles.length > 0"
          danger
          @click="handleBatchDelete"
        >
          <template #icon>
            <DeleteOutlined />
          </template>
          批量删除 ({{ selectedFiles.length }})
        </a-button>
      </div>
    </div>

    <!-- 文件列表 -->
    <div 
      class="file-list"
      @drop="handleDrop"
      @dragover="handleDragOver"
      @dragenter="handleDragEnter"
      @dragleave="handleDragLeave"
      :class="{ 'drag-over': isDragOver }"
    >
      <a-table
        :data-source="dataSource"
        :columns="columns"
        :pagination="false"
        :loading="loading"
        :row-selection="{ selectedRowKeys: selectedFiles, onChange: onSelectChange }"
        size="middle"
        class="file-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'name'">
            <div class="file-name-cell" :class="{ 'clickable': record.isDirectory }" @click="handleItemClick(record)">
              <component 
                :is="record.isDirectory ? FolderOutlined : getFileIcon(record.type)"
                class="file-icon"
                :class="{ 'directory-icon': record.isDirectory }"
              />
              <span class="file-name" :title="record.name">{{ record.name }}</span>
            </div>
          </template>
          <template v-else-if="column.dataIndex === 'type'">
            <a-tag :color="record.isDirectory ? 'blue' : getTypeColor(record.type)">
              {{ record.isDirectory ? '目录' : getTypeName(record.type) }}
            </a-tag>
          </template>
          <template v-else-if="column.dataIndex === 'size'">
            <span v-if="record.isDirectory">-</span>
            <span v-else>{{ formatFileSize(record.size) }}</span>
          </template>
          <template v-else-if="column.dataIndex === 'actions'">
            <div class="actions">
              <a-button 
                v-if="!record.isDirectory"
                type="text" 
                size="small" 
                title="下载"
                @click="downloadFile(record)"
              >
                <DownloadOutlined />
              </a-button>
              <a-button 
                v-if="!record.isDirectory"
                type="text" 
                size="small" 
                title="预览"
                @click="previewFileHandler(record)"
              >
                <EyeOutlined />
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 文件预览模态框 -->
    <a-modal
      v-model:open="previewVisible"
      title="文件预览"
      width="800px"
      :footer="null"
    >
      <div v-if="previewFile" class="file-preview">
        <div v-if="isImageFile(previewFile)" class="image-preview">
          <img 
            :src="getLocalFileDownloadUrl(previewFile.path)" 
            :alt="previewFile.name"
            style="max-width: 100%; max-height: 500px; object-fit: contain;"
          />
        </div>
        <div v-else class="file-info">
          <FileOutlined style="font-size: 48px; color: #1890ff; margin-bottom: 16px;" />
          <h3>{{ previewFile.name }}</h3>
          <p>文件大小: {{ formatFileSize(previewFile.size) }}</p>
          <p>文件类型: {{ previewFile.type }}</p>
          <p>修改时间: {{ new Date(previewFile.modifiedTime).toLocaleString('zh-CN') }}</p>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  ArrowUpOutlined,
  ReloadOutlined,
  DownloadOutlined,
  EyeOutlined,
  FileOutlined,
  FolderOutlined,
  PictureOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  UploadOutlined,
  DeleteOutlined,
  HomeOutlined
} from '@ant-design/icons-vue'
import { getLocalFiles, getLocalFileDownloadUrl, formatFileSize, type LocalFileInfo } from '@/apis/files.ts'

// 响应式数据
const fileList = ref<LocalFileInfo[]>([])
const currentPath = ref('.')
const parentPath = ref<string | null>(null)
const loading = ref(false)
const previewVisible = ref(false)
const previewFile = ref<LocalFileInfo | null>(null)
const selectedFiles = ref<string[]>([])
const isDragOver = ref(false)

// 表格列定义
const columns = [
  {
    title: '名称',
    dataIndex: 'name',
    key: 'name',
    sorter: (a: LocalFileInfo, b: LocalFileInfo) => a.name.localeCompare(b.name),
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
    sorter: (a: LocalFileInfo, b: LocalFileInfo) => a.size - b.size,
  },
  {
    title: '修改时间',
    dataIndex: 'modifiedTime',
    key: 'modifiedTime',
    width: 180,
    sorter: (a: LocalFileInfo, b: LocalFileInfo) => new Date(a.modifiedTime).getTime() - new Date(b.modifiedTime).getTime(),
  },
  {
    title: '操作',
    dataIndex: 'actions',
    key: 'actions',
    width: 120,
  },
]

// 计算属性
const dataSource = computed(() => {
  return fileList.value.map(file => ({
    key: file.id,
    ...file,
    modifiedTime: new Date(file.modifiedTime).toLocaleString('zh-CN'),
  }))
})

const pathParts = computed(() => {
  if (!currentPath.value || currentPath.value === '.') return []
  return currentPath.value.split('/').filter(part => part)
})

const canGoUp = computed(() => {
  return parentPath.value !== null && parentPath.value !== undefined
})

// 获取文件图标
const getFileIcon = (fileType: string) => {
  if (fileType.startsWith('image/')) {
    return PictureOutlined
  } else if (fileType.includes('csv') || fileType.includes('excel')) {
    return FileExcelOutlined
  } else {
    return FileTextOutlined
  }
}

// 获取类型颜色
const getTypeColor = (fileType: string) => {
  if (fileType.startsWith('image/')) return 'blue'
  if (fileType.includes('csv') || fileType.includes('excel')) return 'green'
  if (fileType.includes('text')) return 'orange'
  return 'default'
}

// 获取类型名称
const getTypeName = (fileType: string) => {
  if (fileType.startsWith('image/')) return '图片'
  if (fileType.includes('csv')) return 'CSV'
  if (fileType.includes('excel')) return 'Excel'
  if (fileType.includes('text')) return '文本'
  return '文件'
}

// 检查是否为图片文件
const isImageFile = (file: LocalFileInfo | null) => {
  return file ? file.type.startsWith('image/') : false
}

// 获取文件列表
const fetchFiles = async (path: string = '.') => {
  try {
    loading.value = true
    const response = await getLocalFiles(path)
    fileList.value = response.files
    currentPath.value = response.currentPath
    parentPath.value = response.parentPath
    console.log('文件列表响应:', { currentPath: response.currentPath, parentPath: response.parentPath })
  } catch (error) {
    message.error('获取文件列表失败')
    console.error('获取文件列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 导航到指定路径
const navigateToPath = (path: string) => {
  fetchFiles(path)
}

// 获取到指定索引的路径
const getPathUpTo = (index: number) => {
  const parts = pathParts.value.slice(0, index + 1)
  return parts.length > 0 ? parts.join('/') : '.'
}

// 返回上级目录
const goUp = () => {
  if (!canGoUp.value || !parentPath.value) return
  
  console.log('返回上级目录:', currentPath.value, '->', parentPath.value)
  fetchFiles(parentPath.value)
}

// 刷新当前目录
const refresh = () => {
  fetchFiles(currentPath.value)
}

// 处理文件/目录点击
const handleItemClick = (item: LocalFileInfo) => {
  if (item.isDirectory) {
    // 进入目录
    const newPath = currentPath.value === '.' ? item.name : `${currentPath.value}/${item.name}`
    fetchFiles(newPath)
  } else {
    // 预览文件
    previewFileHandler(item)
  }
}

// 下载文件
const downloadFile = (file: LocalFileInfo) => {
  const downloadUrl = getLocalFileDownloadUrl(file.path)
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = file.name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  message.success('文件下载开始')
}

// 预览文件
const previewFileHandler = (file: LocalFileInfo) => {
  previewFile.value = file
  previewVisible.value = true
}

// 处理上传按钮点击
const handleUploadClick = () => {
  openFileUploadDialog()
}

// 打开文件上传对话框
const openFileUploadDialog = () => {
  // 创建文件输入元素
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = true
  input.onchange = async (event) => {
    const files = (event.target as HTMLInputElement).files
    if (files && files.length > 0) {
      await uploadFilesToCurrentDirectory(Array.from(files))
    }
  }
  input.click()
}

// 上传文件到当前目录
const uploadFilesToCurrentDirectory = async (files: File[]) => {
  try {
    const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
    const uploadUrl = `${baseURL}/files/local/upload`
    
    console.log('上传URL:', uploadUrl)
    console.log('目标目录:', currentPath.value)
    
    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('target_dir', currentPath.value)
      
      console.log('上传文件:', file.name, '到目录:', currentPath.value)
      
      const response = await fetch(uploadUrl, {
        method: 'POST',
        body: formData
      })
      
      console.log('响应状态:', response.status)
      console.log('响应头:', response.headers)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('响应错误:', errorText)
        throw new Error(`上传失败: ${response.status} ${response.statusText}`)
      }
      
      const result = await response.json()
      console.log('上传结果:', result)
      
      if (!result.success) {
        throw new Error(result.message || '上传失败')
      }
    }
    
    message.success(`成功上传 ${files.length} 个文件到当前目录`)
    // 刷新当前目录
    refresh()
  } catch (error) {
    console.error('上传文件失败:', error)
    message.error(`上传失败: ${error instanceof Error ? error.message : '未知错误'}`)
  }
}

// 处理选择变化
const onSelectChange = (keys: string[]) => {
  selectedFiles.value = keys
}

// 批量删除文件
const handleBatchDelete = () => {
  if (selectedFiles.value.length === 0) {
    message.warning('请选择要删除的文件')
    return
  }

  const selectedFileNames = selectedFiles.value.map(id => {
    const file = fileList.value.find(f => f.id === id)
    return file?.name || '未知文件'
  }).join('、')

  Modal.confirm({
    title: '确认批量删除',
    content: `确定要删除选中的 ${selectedFiles.value.length} 个文件吗？\n\n文件列表：${selectedFileNames}`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteSelectedFiles()
    },
  })
}

// 删除选中的文件
const deleteSelectedFiles = async () => {
  try {
    const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
    const deleteUrl = `${baseURL}/files/local/delete`
    
    console.log('删除URL:', deleteUrl)
    console.log('要删除的文件:', selectedFiles.value)
    
    for (const fileId of selectedFiles.value) {
      const file = fileList.value.find(f => f.id === fileId)
      if (file) {
        console.log('删除文件:', file.name, '路径:', file.path)
        
        const formData = new FormData()
        formData.append('file_path', file.path)
        
        const response = await fetch(deleteUrl, {
          method: 'POST',
          body: formData
        })
        
        console.log('删除响应状态:', response.status)
        
        if (!response.ok) {
          const errorText = await response.text()
          console.error('删除文件错误:', errorText)
          throw new Error(`删除文件 ${file.name} 失败: ${response.status} ${response.statusText}`)
        }
        
        const result = await response.json()
        console.log('删除结果:', result)
      }
    }
    
    message.success(`成功删除 ${selectedFiles.value.length} 个文件`)
    selectedFiles.value = []
    // 刷新当前目录
    refresh()
  } catch (error) {
    console.error('批量删除文件失败:', error)
    message.error(`删除失败: ${error instanceof Error ? error.message : '未知错误'}`)
  }
}

// 监听刷新事件
const handleRefreshEvent = () => {
  refresh()
}

// 监听刷新到根目录事件
const handleRefreshToRootEvent = () => {
  fetchFiles('.')
}

// 监听本地文件上传事件
const handleLocalFileUploadEvent = () => {
  openFileUploadDialog()
}

// 拖拽处理
const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
  e.stopPropagation()
}

const handleDragEnter = (e: DragEvent) => {
  e.preventDefault()
  e.stopPropagation()
  isDragOver.value = true
}

const handleDragLeave = (e: DragEvent) => {
  e.preventDefault()
  e.stopPropagation()
  isDragOver.value = false
}

const handleDrop = async (e: DragEvent) => {
  e.preventDefault()
  e.stopPropagation()
  isDragOver.value = false
  
  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length > 0) {
    await uploadFilesToCurrentDirectory(files)
  }
}

// 组件挂载时获取文件列表
onMounted(() => {
  fetchFiles()
  // 监听刷新事件
  window.addEventListener('refresh-local-files', handleRefreshEvent)
  window.addEventListener('refresh-local-files-to-root', handleRefreshToRootEvent)
  window.addEventListener('open-local-file-upload', handleLocalFileUploadEvent)
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('refresh-local-files', handleRefreshEvent)
  window.removeEventListener('refresh-local-files-to-root', handleRefreshToRootEvent)
  window.removeEventListener('open-local-file-upload', handleLocalFileUploadEvent)
})
</script>

<style scoped>
.local-file-browser {
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

.file-name-cell.clickable {
  cursor: pointer;
  transition: background-color 0.2s;
}

.file-name-cell.clickable:hover {
  background-color: #f5f5f5;
  border-radius: 4px;
  padding: 4px 8px;
  margin: -4px -8px;
}

.file-icon {
  font-size: 16px;
  color: #1890ff;
}

.directory-icon {
  color: #faad14;
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
