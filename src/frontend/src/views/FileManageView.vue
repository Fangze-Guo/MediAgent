<template>
  <div class="file-manage">
    <a-layout>
      <a-layout-content class="content">
        <!-- 上栏工具栏 -->
        <div class="top-toolbar">
          <h2 class="title">管理我的数据</h2>
          <div class="top-actions">
            <a-input-search
                v-model:value="fileStore.searchText"
                placeholder="搜索文件..."
                style="width: 200px; margin-right: 12px"
                @search="handleSearch"
                allow-clear
            />
            <a-button @click="handleRefresh"
                      :loading="fileStore.loading"
                      style="margin-right: 12px">
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
        </div>

        <!-- 下栏工具栏 -->
        <div class="bottom-toolbar">
          <div class="left-actions">
            <span class="file-count">共 {{ fileStore.fileList.length }} 个文件</span>
          </div>
          <div class="right-actions">
            <a-button
                :disabled="selectedCount === 0"
                danger
                @click="handleBatchDelete"
            >
              <template #icon>
                <DeleteOutlined />
              </template>
              批量删除 ({{ selectedCount }})
            </a-button>
          </div>
        </div>

        <!-- 文件列表容器 -->
        <div class="file-list-container">
          <a-tabs v-model:activeKey="activeTab" type="card">
            <a-tab-pane key="uploaded" tab="已上传文件">
              <a-table
                  :data-source="dataSource"
                  :columns="columns"
                  :pagination="false"
                  :scroll="{ y: 400 }"
                  :loading="fileStore.loading"
                  :row-selection="{ selectedRowKeys: fileStore.selectedFileIds, onChange: onSelectChange }"
                  size="middle"
                  class="file-table"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.dataIndex === 'originalName'">
                    <div class="file-name-cell">
                      <component
                          :is="record.type.startsWith('image/') ? PictureOutlined :
                          record.type.includes('csv') ? FileExcelOutlined : FileOutlined"
                          class="file-icon"
                      />
                      <span class="file-name" :title="record.originalName">{{ record.originalName }}</span>
                    </div>
                  </template>
                  <template v-else-if="column.dataIndex === 'type'">
                    <a-tag :color="record.type.startsWith('image/') ? 'blue' :
                              record.type.includes('csv') ? 'green' : 'default'">
                      {{
                        record.type.startsWith('image/') ? '图片' :
                            record.type.includes('csv') ? 'CSV' : '其他'
                      }}
                    </a-tag>
                  </template>
                  <template v-else-if="column.dataIndex === 'actions'">
                    <div class="actions">
                      <a-button
                          type="text"
                          size="small"
                          title="预览"
                          @click="handlePreviewFile(record)"
                      >
                        <EyeOutlined />
                      </a-button>
                      <a-button
                          type="text"
                          size="small"
                          title="下载"
                          @click="handleDownloadFile(record)"
                      >
                        <DownloadOutlined />
                      </a-button>
                      <a-button
                          type="text"
                          size="small"
                          danger
                          title="删除"
                          @click="handleDeleteFile(record)"
                      >
                        <DeleteOutlined />
                      </a-button>
                    </div>
                  </template>
                </template>
              </a-table>
            </a-tab-pane>
            <a-tab-pane key="local" tab="本地文件">
              <LocalFileBrowser />
            </a-tab-pane>
          </a-tabs>
        </div>

        <!-- 文件预览模态框 -->
        <a-modal
            v-model:open="previewVisible"
            title="文件预览"
            width="800px"
            :footer="null"
        >
          <div v-if="previewFile" class="file-preview">
            <div v-if="previewFile.type.startsWith('image/')" class="image-preview">
              <img
                  :src="getImageUrl(previewFile)"
                  :alt="previewFile.originalName"
                  style="max-width: 100%; max-height: 500px; object-fit: contain;"
              />
            </div>
            <div v-else class="file-info">
              <FileOutlined style="font-size: 48px; color: #1890ff; margin-bottom: 16px;" />
              <h3>{{ previewFile.originalName }}</h3>
              <p>文件大小: {{ formatFileSize(previewFile.size) }}</p>
              <p>文件类型: {{ previewFile.type }}</p>
              <p>上传时间: {{ new Date(previewFile.uploadTime).toLocaleString('zh-CN') }}</p>
            </div>
          </div>
        </a-modal>
      </a-layout-content>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  DeleteOutlined,
  DownloadOutlined,
  EyeOutlined,
  FileExcelOutlined,
  FileOutlined,
  PictureOutlined,
  ReloadOutlined,
  UploadOutlined
} from '@ant-design/icons-vue'
import { formatFileSize } from '@/apis/files'
import { useFileStore } from '@/store/files'
import LocalFileBrowser from '@/components/LocalFileBrowser.vue'

// 使用文件状态管理
const fileStore = useFileStore()

// 响应式数据
const activeTab = ref('uploaded')
const previewVisible = ref(false)
const previewFile = ref<any>(null)

// 表格列定义
const columns = [
  {
    title: '名称',
    dataIndex: 'originalName',
    key: 'originalName',
    sorter: (a: any, b: any) => a.originalName.localeCompare(b.originalName),
  },
  {
    title: '大小',
    dataIndex: 'size',
    key: 'size',
    width: 120,
    sorter: (a: any, b: any) => a.size - b.size,
  },
  {
    title: '类型',
    dataIndex: 'type',
    key: 'type',
    width: 120,
    filters: [
      {text: '图片', value: 'image'},
      {text: 'CSV', value: 'csv'},
      {text: '其他', value: 'other'},
    ],
    onFilter: (value: string, record: any) => {
      if (value === 'image') return record.type.startsWith('image/')
      if (value === 'csv') return record.type.includes('csv')
      return !record.type.startsWith('image/') && !record.type.includes('csv')
    },
  },
  {
    title: '上传时间',
    dataIndex: 'uploadTime',
    key: 'uploadTime',
    width: 180,
    sorter: (a: any, b: any) => new Date(a.uploadTime).getTime() - new Date(b.uploadTime).getTime(),
  },
  {
    title: '操作',
    dataIndex: 'actions',
    key: 'actions',
    width: 150,
  },
]

// 计算属性
const dataSource = computed(() => {
  return fileStore.filteredFiles.map(file => ({
    key: file.id,
    ...file,
    size: formatFileSize(file.size),
    uploadTime: new Date(file.uploadTime).toLocaleString('zh-CN'),
    icon: getFileIcon(file.type),
  }))
})

const selectedCount = computed(() => fileStore.selectedCount)

// 获取文件图标
const getFileIcon = (fileType: string) => {
  if (fileType.startsWith('image/')) {
    return 'picture'
  } else if (fileType.includes('csv')) {
    return 'file-excel'
  } else {
    return 'file'
  }
}

// 获取图片URL
const getImageUrl = (file: any) => {
  const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
  return `${baseURL}/files/serve/${file.id}`
}

// 获取文件列表
const fetchFileList = async () => {
  try {
    await fileStore.fetchFileList()
  } catch (error) {
    message.error('获取文件列表失败')
    console.error('获取文件列表失败:', error)
  }
}

// 删除文件
const handleDeleteFile = (file: any) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除文件 "${file.originalName}" 吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      const success = await fileStore.removeFile(file.id)
      if (success) {
        message.success('文件删除成功')
      } else {
        message.error(fileStore.error || '删除文件失败')
      }
    },
  })
}

// 下载文件
const handleDownloadFile = async (file: any) => {
  const result = await fileStore.downloadFileById(file.id)
  if (result.success && result.downloadUrl) {
    // 获取API基础URL
    const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
    const fullUrl = `${baseURL}${result.downloadUrl}`

    // 创建临时链接进行下载
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

// 预览文件
const handlePreviewFile = (file: any) => {
  previewFile.value = file
  previewVisible.value = true
}

// 批量删除
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
      if (result.success) {
        message.success(`成功删除 ${result.deletedCount} 个文件`)
      } else {
        message.error(fileStore.error || '批量删除失败')
      }
    },
  })
}

// 处理上传按钮点击
const handleUploadClick = () => {
  // 触发全局上传事件
  window.dispatchEvent(new CustomEvent('open-file-upload'))
}

// 行选择变化
const onSelectChange = (keys: string[]) => {
  fileStore.setSelectedFileIds(keys)
}

// 搜索
const handleSearch = () => {
  // 搜索逻辑在computed中处理
}

// 刷新文件列表
const handleRefresh = () => {
  if (activeTab.value === 'uploaded') {
    fetchFileList()
  } else if (activeTab.value === 'local') {
    // 刷新本地文件浏览器到根目录
    window.dispatchEvent(new CustomEvent('refresh-local-files-to-root'))
  }
}

// 监听文件列表刷新事件
const handleRefreshFileList = () => {
  fetchFileList()
}

// 组件挂载时获取文件列表
onMounted(() => {
  fetchFileList()
  // 监听文件列表刷新事件
  window.addEventListener('refresh-file-list', handleRefreshFileList)
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('refresh-file-list', handleRefreshFileList)
})
</script>

<style scoped>
.file-manage {
  background-color: #f0f2f5;
  border-radius: 8px;
  margin: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}

.content {
  background: white;
  padding: 0;
  border-radius: 8px;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 工具栏通用样式 */
.top-toolbar,
.bottom-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.top-toolbar {
  background: #fafafa;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.bottom-toolbar {
  background: #fff;
}

.title {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
  color: #333;
}

/* 左侧操作容器 */
.left-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-count {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

/* 右侧操作容器 */
.right-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* 文件列表容器 */
.file-list-container {
  padding: 0 20px 16px;
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.file-table {
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  flex: 1;
  overflow: hidden;
}

/* 文件名单元格 */
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
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 操作按钮 */
.actions {
  display: flex;
  gap: 8px;
}

/* 文件预览样式 */
.file-preview {
  text-align: center;
  padding: 20px;
}

.image-preview {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  max-height: 60vh;
  overflow: hidden;
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

/* 响应式设计 */
@media (max-width: 768px) {
  .file-manage {
    margin: 8px;
    padding: 12px;
    height: calc(100vh - 80px);
  }

  .top-toolbar,
  .bottom-toolbar {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
    padding: 12px 16px;
  }

  .right-actions {
    width: 100%;
    justify-content: space-between;
  }

  .file-list-container {
    padding: 0 16px 12px;
  }

  .file-name {
    max-width: 200px;
  }
}
</style>
