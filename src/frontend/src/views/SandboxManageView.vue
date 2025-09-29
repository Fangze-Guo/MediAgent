<template>
  <div class="sandbox-manage">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">沙盒文件管理</h1>
          <p class="page-subtitle">管理沙盒环境的输入文件和输出结果</p>
        </div>
      </div>
    </div>

    <div class="sandbox-grid">
      <!-- 目录结构显示 -->
      <div class="sandbox-section">
        <h2>📁 沙盒目录结构</h2>
        <div class="directory-tree">
          <div class="tree-item">
            <span class="folder">📁 src/data/sandbox/</span>
            <div class="tree-children">
              <div class="tree-item">
                <span class="folder">📁 dicom/</span>
                <div class="tree-child">
                  <span class="description">DICOM源文件</span>
                </div>
              </div>
              <div class="tree-item">
                <span class="folder">📁 input/</span>
                <div class="tree-child">
                  <span class="description">NII输入文件</span>
                </div>
              </div>
              <div class="tree-item">
                <span class="folder">📁 output/</span>
                <div class="tree-children">
                  <div class="tree-item">
                    <span class="folder">📁 dicom_to_nii/</span>
                    <div class="tree-child">
                      <span class="description">DICOM转换输出</span>
                    </div>
                  </div>
                  <div class="tree-item">
                    <span class="folder">📁 resample/</span>
                    <div class="tree-child">
                      <span class="description">重采样输出</span>
                    </div>
                  </div>
                  <div class="tree-item">
                    <span class="folder">📁 normalize/</span>
                    <div class="tree-child">
                      <span class="description">归一化输出</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 文件管理操作 -->
      <div class="sandbox-section">
        <h2>🛠️ 管理操作</h2>
        <div class="management-cards">
          <!-- DICOM文件管理 -->
          <div class="management-card">
            <div class="card-icon dicom">
              <FileImageOutlined />
            </div>
            <div class="card-content">
              <h3>DICOM文件</h3>
              <p>管理DICOM源文件</p>
              <div class="card-stats">
                <span>目录: dicom/</span>
                <span>文件数: {{ dicomFileCount }}</span>
              </div>
              <div class="card-actions">
                <a-button type="primary" @click="openDicomUpload">
                  <template #icon>
                    <UploadOutlined />
                  </template>
                  上传DICOM
                </a-button>
                <a-button @click="browseDicomFiles()">浏览文件</a-button>
              </div>
            </div>
          </div>

          <!-- NII输入文件管理 -->
          <div class="management-card">
            <div class="card-icon input">
              <FolderOpenOutlined />
            </div>
            <div class="card-content">
              <h3>NII输入文件</h3>
              <p>管理NII输入文件</p>
              <div class="card-stats">
                <span>目录: input/</span>
                <span>文件数: {{ niiFileCount }}</span>
              </div>
              <div class="card-actions">
                <a-button type="primary" @click="openNiiUpload">
                  <template #icon>
                    <UploadOutlined />
                  </template>
                  上传NII
                </a-button>
                <a-button @click="browseNiiFiles()">浏览文件</a-button>
              </div>
            </div>
          </div>

          <!-- 输出文件管理 -->
          <div class="management-card">
            <div class="card-icon output">
              <DownloadOutlined />
            </div>
            <div class="card-content">
              <h3>处理结果</h3>
              <p>查看处理输出</p>
              <div class="card-stats">
                <span>总计: {{ totalOutputFiles }}</span>
                <span>最新: {{ latestOutput }}</span>
              </div>
              <div class="card-actions">
                <a-button type="primary" @click="viewAllOutputs">查看所有输出</a-button>
                <a-button @click="clearOldOutputs">清理旧文件</a-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 快速沙盒操作 -->
      <div class="sandbox-section">
        <h2>⚡ 快速操作</h2>
        <div class="quick-actions">
          <div class="quick-card">
            <div class="quick-icon">
              <SwapOutlined />
            </div>
            <h4>DICOM转NII</h4>
            <p>将DICOM文件转换为NII格式</p>
            <a-button type="primary" block @click="quickConvert('dicom_to_nii')">
              开始转换
            </a-button>
          </div>

          <div class="quick-card">
            <div class="quick-icon">
              <ReloadOutlined />
            </div>
            <h4>图像重采样</h4>
            <p>对NII图像进行重采样</p>
            <a-button type="primary" block @click="quickConvert('resample')">
              开始重采样
            </a-button>
          </div>

          <div class="quick-card">
            <div class="quick-icon">
              <BarChartOutlined />
            </div>
            <h4>强度归一化</h4>
            <p>对NII图像进行归一化</p>
            <a-button type="primary" block @click="quickConvert('normalize')">
              开始归一化
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 文件浏览模态框 -->
    <a-modal
      v-model:open="fileBrowserVisible"
      :title="`浏览 ${currentBrowseType} 文件`"
      width="800px"
    >
      <div class="file-browser">
        <div class="file-list">
          <div v-if="currentFiles.length === 0" class="empty-state">
            <InboxOutlined />
            <p>该目录暂无文件</p>
          </div>
          <div v-else>
            <div 
              v-for="file in currentFiles" 
              :key="file.name"
              class="file-item">
              <div class="file-info">
                <FileOutlined />
                <span class="file-name">{{ file.name }}</span>
                <span class="file-size">{{ formatFileSize(file.size) }}</span>
              </div>
              <div class="file-actions">
                <a-button size="small" @click="downloadFile(file)">
                  下载
                </a-button>
                <a-button size="small" danger @click="deleteFile(file)">
                  删除
                </a-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </a-modal>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { 
  FileImageOutlined,
  FolderOpenOutlined,
  DownloadOutlined,
  UploadOutlined,
  SwapOutlined,
  ReloadOutlined,
  BarChartOutlined,
  FileOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const dicomFileCount = ref(0)
const niiFileCount = ref(0)
const totalOutputFiles = ref(0)
const latestOutput = ref('暂无')

const fileBrowserVisible = ref(false)
const currentBrowseType = ref('')
const currentFiles = ref<Array<{name: string, size: number}>>([])


// 响应式数据
// 文件列表状态管理

// 生命周期
onMounted(() => {
  loadFileStats()
  // 监听沙盒文件统计刷新事件
  window.addEventListener('refresh-sandbox-stats', loadFileStats)
})

onUnmounted(() => {
  // 移除事件监听
  window.removeEventListener('refresh-sandbox-stats', loadFileStats)
})

// 方法
const loadFileStats = async () => {
  try {
    // 这里应该调用API获取文件统计
    // 暂时使用模拟数据
    dicomFileCount.value = 0
    niiFileCount.value = 0
    totalOutputFiles.value = 0
  } catch (error) {
    console.error('加载文件统计失败:', error)
  }
}

const openDicomUpload = () => {
  // 发送全局沙盒上传事件
  window.dispatchEvent(new CustomEvent('open-sandbox-file-upload', {
    detail: { type: 'dicom' }
  }))
}

const openNiiUpload = () => {
  // 发送全局沙盒上传事件
  window.dispatchEvent(new CustomEvent('open-sandbox-file-upload', {
    detail: { type: 'nii' }
  }))
}

const browseDicomFiles = () => {
  currentBrowseType.value = 'DICOM'
  currentFiles.value = [] // 这里应该调用API获取文件列表
  fileBrowserVisible.value = true
}

const browseNiiFiles = () => {
  currentBrowseType.value = 'NII输入'
  currentFiles.value = [] // 这里应该调用API获取文件列表
  fileBrowserVisible.value = true
}

const viewAllOutputs = () => {
  currentBrowseType.value = '所有输出'
  currentFiles.value = [] // 这里应该调用API获取输出文件列表
  fileBrowserVisible.value = true
}

const clearOldOutputs = () => {
  message.info('清理功能开发中...')
}

const quickConvert = (sandboxType: string) => {
  message.info(`${sandboxType} 功能开发中，请使用专门的沙盒页面`)
}

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const downloadFile = (file: any) => {
  message.info(`下载 ${file.name} 功能开发中...`)
}

const deleteFile = (file: any) => {
  message.info(`删除 ${file.name} 功能开发中...`)
}

</script>

<style scoped>
.sandbox-manage {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  padding: 24px;
}

.page-header {
  margin-bottom: 32px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

.title-section {
  flex: 1;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0 0 8px 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.page-subtitle {
  font-size: 16px;
  color: #666;
  margin: 0;
}

.sandbox-grid {
  max-width: 1200px;
  margin: 0 auto;
}

.sandbox-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.sandbox-section h2 {
  margin: 0 0 20px 0;
  color: #1890ff;
  font-size: 20px;
}

/* 目录树样式 */
.directory-tree {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  font-family: 'Courier New', monospace;
  font-size: 14px;
}

.tree-item {
  margin-bottom: 8px;
}

.tree-children {
  margin-left: 16px;
}

.tree-child {
  margin-left: 16px;
  color: #6c757d;
}

.folder {
  color: #1890ff;
  font-weight: 500;
}

.description {
  color: #6c757d;
  font-style: italic;
  margin-left: 8px;
}

/* 管理卡片样式 */
.management-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.management-card {
  background: #fafafa;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  transition: all 0.3s ease;
}

.management-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.card-icon {
  width: 50px;
  height: 50px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
  margin-bottom: 16px;
}

.card-icon.dicom {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.card-icon.input {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.card-icon.output {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.card-content h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  color: #1a1a1a;
}

.card-content p {
  margin: 0 0 12px 0;
  color: #666;
  font-size: 14px;
}

.card-stats {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 16px;
}

.card-stats span {
  font-size: 12px;
  color: #666;
}

.card-actions {
  display: flex;
  gap: 8px;
}

/* 快速操作样式 */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
}

.quick-card {
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  transition: all 0.3s ease;
}

.quick-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.quick-icon {
  width: 60px;
  height: 60px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  margin: 0 auto 16px;
}

.quick-card h4 {
  margin: 0 0 8px 0;
  color: #1a1a1a;
  font-size: 16px;
}

.quick-card p {
  margin: 0 0 16px 0;
  color: #666;
  font-size: 14px;
}

/* 文件浏览器样式 */
.file-browser {
  max-height: 400px;
  overflow-y: auto;
}


.file-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #999;
}

.empty-state .anticon {
  font-size: 48px;
  margin-bottom: 16px;
}

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  background: white;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  font-weight: 500;
}

.file-size {
  color: #666;
  font-size: 12px;
}

.file-actions {
  display: flex;
  gap: 8px;
}

/* 上传区域样式 */
.upload-area {
  padding: 20px 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .management-cards,
  .quick-actions {
    grid-template-columns: 1fr;
  }
  
  .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
}
</style>
