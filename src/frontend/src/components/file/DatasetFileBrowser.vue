<template>
  <div class="dataset-file-browser">
    <!-- 路径导航 -->
    <div class="path-navigation">
      <a-breadcrumb>
        <a-breadcrumb-item>
          <a @click="navigateToPath('.')">
            <HomeOutlined style="margin-right: 4px;" />
            {{ t('components_DatasetFileBrowser.pathNavigation.datasetDir') }}
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
          {{ t('components_DatasetFileBrowser.pathNavigation.parentDir') }}
        </a-button>
        <a-button @click="refresh" :loading="fileStore.loading">
          <template #icon>
            <ReloadOutlined />
          </template>
          {{ t('components_DatasetFileBrowser.pathNavigation.refresh') }}
        </a-button>
        <a-button v-if="canWrite" type="primary" @click="handleUploadClick">
          <template #icon>
            <UploadOutlined />
          </template>
          {{ t('components_DatasetFileBrowser.pathNavigation.uploadToCurrent') }}
        </a-button>
        <a-button v-if="canWrite" @click="showCreateFolderModal">
          <template #icon>
            <FolderAddOutlined />
          </template>
          {{ t('components_DatasetFileBrowser.pathNavigation.createFolder') }}
        </a-button>
      </div>
      <div class="toolbar-right">
        <span class="file-count">{{ t('components_DatasetFileBrowser.pathNavigation.totalFiles', {
          count:
            fileStore.fileList.length
        }) }}</span>
        <a-button v-if="canDelete && fileStore.selectedCount > 0" danger @click="handleBatchDelete">
          <template #icon>
            <DeleteOutlined />
          </template>
          {{ t('components_DatasetFileBrowser.pathNavigation.batchDelete', { count: fileStore.selectedCount }) }}
        </a-button>
      </div>
    </div>

    <div class="file-list" @drop="handleDrop" @dragover="handleDragOver" @dragenter="handleDragEnter"
      @dragleave="handleDragLeave" :class="{ 'drag-over': isDragOver }">
      <a-table :data-source="dataSource" :columns="columns" :pagination="false" :loading="fileStore.loading"
        :row-selection="{ selectedRowKeys: fileStore.selectedFileIds, onChange: onSelectChange }" size="middle"
        class="file-table">
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'name'">
            <div class="file-name-cell" :class="{ 'clickable': record.isDirectory }" @click="handleItemClick(record)">
              <component :is="getFileIcon(record.type)" class="file-icon"
                :class="{ 'directory-icon': record.isDirectory }" />
              <span class="file-name" :title="record.name">{{ record.name }}</span>
            </div>
          </template>
          <template v-else-if="column.dataIndex === 'type'">
            <a-tag :color="getTypeColor(record.type)">
              {{ getTypeName(record.type) }}
            </a-tag>
          </template>
          <template v-else-if="column.dataIndex === 'size'">
            <span v-if="record.isDirectory">-</span>
            <span v-else>{{ formatFileSize(record.size) }}</span>
          </template>
          <template v-else-if="column.dataIndex === 'modifiedTime'">
            {{ new Date(record.modifiedTime).toLocaleString('zh-CN') }}
          </template>
          <template v-else-if="column.dataIndex === 'actions'">
            <div class="actions">
              <a-button v-if="!record.isDirectory" type="text" size="small"
                :title="t('components_DatasetFileBrowser.fileList.preview')" @click="previewFileHandler(record)">
                <EyeOutlined />
              </a-button>
              <a-button v-if="canDeleteFile(record)" type="text" size="small"
                :title="t('components_DatasetFileBrowser.fileList.delete')" danger
                @click="deleteFileHandler(record)">
                <DeleteOutlined />
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 文件预览模态框 -->
    <a-modal v-model:open="previewVisible" :title="t('components_DatasetFileBrowser.previewModal.title')"
      width="800px" :footer="null">
      <div v-if="previewFile" class="file-preview">
        <div v-if="isImageFile(previewFile)" class="image-preview">
          <img :src="getImageUrl(previewFile)" :alt="previewFile.name"
            style="max-width: 100%; max-height: 500px; object-fit: contain;" />
        </div>
        <div v-else class="file-info">
          <FileOutlined style="font-size: 48px; color: #1890ff; margin-bottom: 16px;" />
          <h3>{{ previewFile.name }}</h3>
          <p>{{ t('components_DatasetFileBrowser.previewModal.fileSize') }}: {{ formatFileSize(previewFile.size) }}
          </p>
          <p>{{ t('components_DatasetFileBrowser.previewModal.fileType') }}: {{ previewFile.type }}</p>
          <p>{{ t('components_DatasetFileBrowser.previewModal.modifiedTime') }}: {{ new
            Date(previewFile.modifiedTime).toLocaleString('zh-CN') }}</p>
        </div>
      </div>
    </a-modal>

    <!-- 创建文件夹模态框 -->
    <a-modal v-model:open="createFolderVisible"
      :title="t('components_DatasetFileBrowser.createFolderModal.title')"
      :okText="t('components_DatasetFileBrowser.createFolderModal.create')"
      :cancelText="t('components_DatasetFileBrowser.createFolderModal.cancel')" @ok="handleCreateFolder"
      :confirm-loading="createFolderLoading">
      <a-form :model="createFolderForm" :rules="createFolderRules" ref="createFolderFormRef">
        <a-form-item :label="t('components_DatasetFileBrowser.createFolderModal.label')" name="folderName">
          <a-input v-model:value="createFolderForm.folderName"
            :placeholder="t('components_DatasetFileBrowser.createFolderModal.placeholder')" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  ArrowUpOutlined,
  DeleteOutlined,
  EyeOutlined,
  FileExcelOutlined,
  FileOutlined,
  FolderAddOutlined,
  FolderOutlined,
  HomeOutlined,
  PictureOutlined,
  ReloadOutlined,
  UploadOutlined,
} from '@ant-design/icons-vue'
import { formatFileSize, uploadFile, createFolder } from '@/apis/files'
import { useFileStore } from '@/store/files'
import { useAuthStore } from '@/store/auth'
import { useI18n } from 'vue-i18n'

// 国际化
const { t } = useI18n()

const fileStore = useFileStore()
const authStore = useAuthStore()

const previewVisible = ref(false)
const previewFile = ref<any>(null)
const isDragOver = ref(false)
const currentPath = ref('.')
const parentPath = ref<string | null>(null)

// 创建文件夹相关状态
const createFolderVisible = ref(false)
const createFolderLoading = ref(false)
const createFolderForm = ref({
  folderName: ''
})
const createFolderFormRef = ref()
const createFolderRules = {
  folderName: [
    { required: true, message: t('components_DatasetFileBrowser.createFolderRules.required'), trigger: 'blur' },
    { min: 1, max: 50, message: t('components_DatasetFileBrowser.createFolderRules.length'), trigger: 'blur' },
    { pattern: /^[^<>:"/\\|?*]+$/, message: t('components_DatasetFileBrowser.createFolderRules.pattern'), trigger: 'blur' }
  ]
}

// 列定义
const columns = computed(() => [
  {
    title: t('components_DatasetFileBrowser.fileList.name'),
    dataIndex: 'name',
    key: 'name',
    sorter: (a: any, b: any) => a.name.localeCompare(b.name),
  },
  {
    title: t('components_DatasetFileBrowser.fileList.type'),
    dataIndex: 'type',
    key: 'type',
    width: 120,
  },
  {
    title: t('components_DatasetFileBrowser.fileList.size'),
    dataIndex: 'size',
    key: 'size',
    width: 120,
    sorter: (a: any, b: any) => a.size - b.size,
  },
  {
    title: t('components_DatasetFileBrowser.fileList.modifiedTime'),
    dataIndex: 'modifiedTime',
    key: 'modifiedTime',
    width: 180,
    sorter: (a: any, b: any) => new Date(a.modifiedTime).getTime() - new Date(b.modifiedTime).getTime(),
  },
  { title: t('components_DatasetFileBrowser.fileList.actions'), dataIndex: 'actions', key: 'actions', width: 150 },
])

// 数据源
const dataSource = computed(() => fileStore.filteredFiles.map(f => ({
  key: f.id,
  id: f.id,
  name: f.name,
  size: f.size,
  type: f.type,
  modifiedTime: f.modifiedTime,
  isDirectory: f.isDirectory,
  path: f.path,
})))

// 路径导航相关
const pathParts = computed(() => {
  if (!currentPath.value || currentPath.value === '.') return []
  return currentPath.value.split('/').filter(part => part)
})

const canGoUp = computed(() => {
  return parentPath.value !== null && parentPath.value !== undefined
})

// 权限判断：是否可以写入（上传、创建文件夹）
const canWrite = computed(() => {
  const user = authStore.currentUser
  if (!user) return false

  // 管理员可以写入任何位置
  if (user.role === 'admin') return true

  const path = currentPath.value
  if (!path || path === '.') return false

  const parts = path.split('/').filter(p => p)
  if (parts.length === 0) return false

  // 在public目录下不允许普通用户写入
  if (parts[0] === 'public') return false

  // 在private目录下，只能写入自己的文件夹
  if (parts[0] === 'private') {
    if (parts.length < 2) return false
    const folderUserId = parseInt(parts[1])
    return folderUserId === user.uid
  }

  return false
})

// 权限判断：是否可以删除
const canDelete = computed(() => {
  const user = authStore.currentUser
  if (!user) return false

  // 管理员可以删除（除了根目录）
  if (user.role === 'admin') return true

  const path = currentPath.value
  if (!path || path === '.') return false

  const parts = path.split('/').filter(p => p)
  if (parts.length === 0) return false

  // 禁止删除private和public根目录
  if (parts.length === 1 && (parts[0] === 'private' || parts[0] === 'public')) {
    return false
  }

  // 在public目录下不允许普通用户删除
  if (parts[0] === 'public') return false

  // 在private目录下，只能删除自己的文件夹下的内容
  if (parts[0] === 'private') {
    if (parts.length < 2) return false
    const folderUserId = parseInt(parts[1])
    return folderUserId === user.uid
  }

  return false
})

// 判断单个文件是否可删除
const canDeleteFile = (file: any) => {
  const user = authStore.currentUser
  if (!user) return false

  // 管理员可以删除大部分文件（除了根目录）
  if (user.role === 'admin') {
    // 禁止删除private和public根目录
    if (file.path === 'private' || file.path === 'public') {
      return false
    }
    return true
  }

  // 使用canDelete的基础权限判断
  if (!canDelete.value) return false

  // 额外检查：禁止删除private和public根目录
  if (file.path === 'private' || file.path === 'public') {
    return false
  }

  return true
}

const getPathUpTo = (index: number) => {
  const parts = pathParts.value.slice(0, index + 1)
  return parts.length > 0 ? parts.join('/') : '.'
}

const navigateToPath = (path: string) => {
  fetchFiles(path)
}

const goUp = () => {
  if (!canGoUp.value || !parentPath.value) return
  fetchFiles(parentPath.value)
}

const onSelectChange = (keys: string[]) => {
  fileStore.setSelectedFileIds(keys)
}

const fetchFiles = async (path: string = '.') => {
  try {
    await fileStore.fetchFileList(path)
    // 更新路径信息
    if (fileStore.currentPath !== undefined) {
      currentPath.value = fileStore.currentPath
    }
    if (fileStore.parentPath !== undefined) {
      parentPath.value = fileStore.parentPath
    }
  } catch (e) {
    message.error(t('components_DatasetFileBrowser.messages.loadFailed'))
  }
}

const refresh = async () => {
  await fetchFiles(currentPath.value)
}

// 显示创建文件夹模态框
const showCreateFolderModal = () => {
  createFolderForm.value.folderName = ''
  createFolderVisible.value = true
}

// 创建文件夹
const handleCreateFolder = async () => {
  try {
    await createFolderFormRef.value?.validate()
    createFolderLoading.value = true

    const result = await createFolder(createFolderForm.value.folderName, currentPath.value)
    if (result.code === 200) {
      message.success(t('components_DatasetFileBrowser.messages.createSuccess'))
      createFolderVisible.value = false
      await refresh()
    } else {
      message.error(result.message || t('components_DatasetFileBrowser.messages.createFailed'))
    }
  } catch (error) {
    message.error(t('components_DatasetFileBrowser.messages.createFailed'))
  } finally {
    createFolderLoading.value = false
  }
}

// 处理文件/目录点击
const handleItemClick = (item: any) => {
  if (item.isDirectory) {
    // 进入目录
    const newPath = currentPath.value === '.' ? item.name : `${currentPath.value}/${item.name}`
    fetchFiles(newPath)
  } else {
    // 预览文件
    previewFileHandler(item)
  }
}

// 获取文件图标
const getFileIcon = (fileType: string) => {
  if (fileType === 'directory') {
    return FolderOutlined
  } else if (fileType.startsWith('image/')) {
    return PictureOutlined
  } else if (fileType.includes('csv') || fileType.includes('excel')) {
    return FileExcelOutlined
  } else if (fileType.includes('dicom') || fileType.includes('application/dicom')) {
    return PictureOutlined // 使用图片图标表示DICOM医学图像
  } else {
    return FileOutlined
  }
}

// 获取类型颜色
const getTypeColor = (fileType: string) => {
  if (fileType === 'directory') return 'blue'
  if (fileType.startsWith('image/')) return 'blue'
  if (fileType.includes('csv') || fileType.includes('excel')) return 'green'
  if (fileType.includes('dicom') || fileType.includes('application/dicom')) return 'purple'
  if (fileType.includes('text')) return 'orange'
  return 'default'
}

// 获取类型名称
const getTypeName = (fileType: string) => {
  if (fileType === 'directory') return t('components_DatasetFileBrowser.fileList.typeDirectory')
  if (fileType.startsWith('image/')) return t('components_DatasetFileBrowser.fileList.typeImage')
  if (fileType.includes('csv')) return 'CSV'
  if (fileType.includes('excel')) return 'Excel'
  if (fileType.includes('dicom') || fileType.includes('application/dicom')) return 'DICOM'
  if (fileType.includes('text')) return t('components_DatasetFileBrowser.fileList.typeText')
  return t('components_DatasetFileBrowser.fileList.typeOthers')
}

const deleteFileHandler = (file: any) => {
  Modal.confirm({
    title: t('components_DatasetFileBrowser.deleteFile.confirmTitle'),
    content: file.isDirectory
      ? t('components_DatasetFileBrowser.deleteFile.confirmDirMessage', { fileName: file.name })
      : t('components_DatasetFileBrowser.deleteFile.confirmFileMessage', { fileName: file.name }),
    okText: t('components_DatasetFileBrowser.deleteFile.confirmTitle'),
    okType: 'danger',
    cancelText: t('components_DatasetFileBrowser.deleteFile.cancel'),
    onOk: async () => {
      const ok = await fileStore.removeFile(file.id)
      if (ok) message.success(`${file.isDirectory ? t('components_DatasetFileBrowser.deleteFile.dirDeleteSuccess') : t('components_DatasetFileBrowser.deleteFile.fileDeleteSuccess')}`)
      else message.error(fileStore.error || t('components_DatasetFileBrowser.deleteFile.deleteFailed'))
    }
  })
}

const handleBatchDelete = () => {
  if (fileStore.selectedCount === 0) {
    message.warning(t('components_DatasetFileBrowser.batchDelete.selectPrompt'))
    return
  }
  Modal.confirm({
    title: t('components_DatasetFileBrowser.batchDelete.confirmTitle'),
    content: t('components_DatasetFileBrowser.batchDelete.confirmMessage', { count: fileStore.selectedCount }),
    okText: t('components_DatasetFileBrowser.batchDelete.delete'),
    okType: 'danger',
    cancelText: t('components_DatasetFileBrowser.batchDelete.cancel'),
    onOk: async () => {
      const result = await fileStore.removeFiles(fileStore.selectedFileIds)
      if (result.success) message.success(t('components_DatasetFileBrowser.batchDelete.success', { count: result.deletedCount }))
      else message.error(fileStore.error || t('components_DatasetFileBrowser.batchDelete.failed'))
    }
  })
}

const previewFileHandler = (file: any) => {
  previewFile.value = file
  previewVisible.value = true
}

const isImageFile = (file: any) => {
  return file ? file.type.startsWith('image/') : false
}

const getImageUrl = (file: any) => {
  const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
  // 正确编码文件路径（file.id 是相对路径，可能包含斜杠和特殊字符）
  const encodedPath = file.id.split('/').map((part: string) => encodeURIComponent(part)).join('/')
  return `${baseURL}/files/serve/${encodedPath}`
}

const handleUploadClick = () => {
  // 触发全局文件上传事件，传递当前路径
  window.dispatchEvent(new CustomEvent('open-dataset-file-upload', {
    detail: { currentPath: currentPath.value }
  }))
}

const uploadSelectedFiles = async (files: File[]) => {
  try {
    for (const file of files) {
      const result = await uploadFile(file, currentPath.value)
      if (result.code === 200) {
        await refresh()
      } else {
        throw new Error(result.message || t('components_DatasetFileBrowser.uploadSelectedFiles.1'))
      }
    }
    message.success(t('components_DatasetFileBrowser.uploadSelectedFiles.2', { count: files.length }))
  } catch (error) {
    message.error(t('components_DatasetFileBrowser.uploadSelectedFiles.3', {
      message: (error as Error).message || t('components_DatasetFileBrowser.uploadSelectedFiles.4')
    }))
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

const handleRefreshEvent = () => {
  refresh()
}

onMounted(() => {
  fetchFiles('.')
  window.addEventListener('refresh-file-list', handleRefreshEvent)
})

onUnmounted(() => {
  window.removeEventListener('refresh-file-list', handleRefreshEvent)
})
</script>

<style scoped>
.dataset-file-browser {
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

.directory-icon {
  color: #faad14;
}
</style>
