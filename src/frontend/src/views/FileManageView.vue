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

        <!-- 文件列表容器 -->
        <div class="file-list-container">
          <a-tabs v-model:activeKey="activeTab" type="card">
            <a-tab-pane key="uploaded" tab="已上传文件">
              <UploadFileBrowser />
            </a-tab-pane>
            <a-tab-pane key="local" tab="本地文件">
              <LocalFileBrowser />
            </a-tab-pane>
            <a-tab-pane key="output" tab="输出文件">
              <OutputFileBrowser />
            </a-tab-pane>
          </a-tabs>
        </div>
      </a-layout-content>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined, UploadOutlined } from '@ant-design/icons-vue'
import { useFileStore } from '@/store/files'
import LocalFileBrowser from '@/components/file/LocalFileBrowser.vue'
import OutputFileBrowser from '@/components/file/OutputFileBrowser.vue'
import UploadFileBrowser from "@/components/file/UploadFileBrowser.vue";

// 使用文件状态管理
const fileStore = useFileStore()
// 响应式数据
const activeTab = ref('uploaded')

const fetchFileList = async () => {
  try {
    await fileStore.fetchFileList()
  } catch (error) {
    message.error('获取文件列表失败')
    console.error('获取文件列表失败:', error)
  }
}

// 处理上传按钮点击
const handleUploadClick = () => {
  if (activeTab.value === 'uploaded') {
    // 在已上传文件选项卡中，触发全局上传事件（上传到服务器存储）
    window.dispatchEvent(new CustomEvent('open-file-upload'))
  } else if (activeTab.value === 'local') {
    // 在本地文件选项卡中，触发本地文件上传事件（上传到当前目录）
    window.dispatchEvent(new CustomEvent('open-local-file-upload'))
  } else if (activeTab.value === 'output') {
    // 在输出文件选项卡中，触发输出文件上传事件（上传到当前目录）
    window.dispatchEvent(new CustomEvent('open-output-file-upload'))
  }
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
  } else if (activeTab.value === 'output') {
    // 刷新输出文件浏览器到根目录
    window.dispatchEvent(new CustomEvent('refresh-output-files-to-root'))
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
}

.content {
  background: white;
  padding: 0;
  border-radius: 8px;
}

/* 工具栏通用样式 */
.top-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #f0f0f0;
}

.top-toolbar {
  background: #fafafa;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.title {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
  color: #333;
}

/* 文件列表容器 */
.file-list-container {
  padding: 0 20px 16px;
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
  }

  .top-toolbar {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
    padding: 12px 16px;
  }

  .file-list-container {
    padding: 0 16px 12px;
  }
}
</style>
