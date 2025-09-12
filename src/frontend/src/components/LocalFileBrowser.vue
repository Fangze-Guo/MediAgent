<template>
  <div class="local-file-browser">
    <!-- 路径导航 -->
    <div class="path-navigation">
      <a-breadcrumb>
        <a-breadcrumb-item>
          <a @click="navigateToPath('.')">根目录</a>
        </a-breadcrumb-item>
        <a-breadcrumb-item v-for="(part, index) in pathParts" :key="index">
          <a @click="navigateToPath(getPathUpTo(index))">{{ part }}</a>
        </a-breadcrumb-item>
      </a-breadcrumb>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <a-button @click="goUp" :disabled="!currentPath || currentPath === '.'">
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
      </div>
      <div class="toolbar-right">
        <span class="file-count">共 {{ fileList.length }} 个项目</span>
      </div>
    </div>

    <!-- 文件列表 -->
    <div class="file-list">
      <a-table
        :data-source="dataSource"
        :columns="columns"
        :pagination="false"
        :loading="loading"
        :scroll="{ y: 400 }"
        size="middle"
        class="file-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'name'">
            <div class="file-name-cell">
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
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ArrowUpOutlined,
  ReloadOutlined,
  DownloadOutlined,
  EyeOutlined,
  FileOutlined,
  FolderOutlined,
  PictureOutlined,
  FileExcelOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'
import { getLocalFiles, getLocalFileDownloadUrl, formatFileSize, type LocalFileInfo } from '@/apis/files'

// 响应式数据
const fileList = ref<LocalFileInfo[]>([])
const currentPath = ref('.')
const loading = ref(false)
const previewVisible = ref(false)
const previewFile = ref<LocalFileInfo | null>(null)

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
  if (currentPath.value && currentPath.value !== '.') {
    const parts = currentPath.value.split('/')
    parts.pop()
    const newPath = parts.length > 0 ? parts.join('/') : '.'
    fetchFiles(newPath)
  }
}

// 刷新当前目录
const refresh = () => {
  fetchFiles(currentPath.value)
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

// 组件挂载时获取文件列表
onMounted(() => {
  fetchFiles()
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
  overflow: hidden;
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
