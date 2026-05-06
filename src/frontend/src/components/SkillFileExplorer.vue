<template>
  <div class="file-explorer">
    <!-- 左侧文件树 -->
    <div class="file-tree-panel">
      <div class="panel-header">
        <FolderOutlined />
        <span>文件结构</span>
      </div>
      <div class="tree-content">
        <a-spin v-if="loading" />
        <div v-else-if="fileTree.length === 0" class="empty-state">
          <InboxOutlined style="font-size: 32px; color: #ccc" />
          <p>暂无文件</p>
        </div>
        <div v-else class="tree-nodes">
          <FileTreeNode
            v-for="node in fileTree"
            :key="node.path"
            :node="node"
            :selected-path="selectedFilePath"
            @select="handleFileSelect"
          />
        </div>
      </div>
    </div>

    <!-- 右侧文件内容 -->
    <div class="file-content-panel">
      <div v-if="!selectedFilePath" class="empty-content">
        <FileTextOutlined style="font-size: 48px; color: #ccc" />
        <p>选择一个文件查看内容</p>
      </div>
      <div v-else class="content-viewer">
        <!-- 文件头部 -->
        <div class="file-header">
          <div class="file-info">
            <FileOutlined />
            <span class="file-name">{{ selectedFileName }}</span>
            <span class="file-size">{{ formatFileSize(fileContent?.size) }}</span>
          </div>
          <a-button size="small" @click="copyContent">
            <CopyOutlined />
            复制
          </a-button>
        </div>

        <!-- 文件内容 -->
        <div class="file-body">
          <a-spin v-if="loadingContent" />
          <div v-else-if="fileContent?.is_binary" class="binary-file">
            <WarningOutlined style="font-size: 32px; color: #faad14" />
            <p>这是一个二进制文件，无法预览</p>
          </div>
          <pre v-else class="code-content"><code :class="getLanguageClass(selectedFileName)">{{ fileContent?.content }}</code></pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  FolderOutlined,
  FileTextOutlined,
  FileOutlined,
  InboxOutlined,
  CopyOutlined,
  WarningOutlined
} from '@ant-design/icons-vue'
import { getSkillFiles, getSkillFileContent, type FileTreeNode as FileNode, type FileContent } from '@/apis/skills'
import FileTreeNode from './FileTreeNode.vue'

const props = defineProps<{
  skillId: string
}>()

const loading = ref(true)
const loadingContent = ref(false)
const fileTree = ref<FileNode[]>([])
const selectedFilePath = ref<string>('')
const fileContent = ref<FileContent | null>(null)

const selectedFileName = computed(() => {
  if (!selectedFilePath.value) return ''
  return selectedFilePath.value.split('/').pop() || ''
})

// 加载文件树
const loadFileTree = async () => {
  loading.value = true
  try {
    const files = await getSkillFiles(props.skillId)
    fileTree.value = files
  } catch (error) {
    console.error('加载文件树失败', error)
    message.error('加载文件树失败')
  } finally {
    loading.value = false
  }
}

// 选择文件
const handleFileSelect = async (path: string, type: string) => {
  if (type === 'directory') return
  
  selectedFilePath.value = path
  loadingContent.value = true
  
  try {
    const content = await getSkillFileContent(props.skillId, path)
    fileContent.value = content
  } catch (error) {
    console.error('加载文件内容失败', error)
    message.error('加载文件内容失败')
  } finally {
    loadingContent.value = false
  }
}

// 复制内容
const copyContent = () => {
  if (!fileContent.value?.content) return
  navigator.clipboard.writeText(fileContent.value.content)
  message.success('已复制到剪贴板')
}

// 格式化文件大小
const formatFileSize = (bytes?: number) => {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// 获取语言类名（用于语法高亮）
const getLanguageClass = (filename: string) => {
  const ext = filename.split('.').pop()?.toLowerCase()
  const langMap: Record<string, string> = {
    'py': 'language-python',
    'js': 'language-javascript',
    'ts': 'language-typescript',
    'vue': 'language-vue',
    'md': 'language-markdown',
    'json': 'language-json',
    'yaml': 'language-yaml',
    'yml': 'language-yaml',
    'sh': 'language-bash',
  }
  return langMap[ext || ''] || 'language-plaintext'
}

onMounted(() => {
  loadFileTree()
})
</script>

<style scoped>
.file-explorer {
  display: flex;
  height: 600px;
  border: 1px solid #e8eaed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

/* 左侧文件树 */
.file-tree-panel {
  width: 300px;
  border-right: 1px solid #e8eaed;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}

.panel-header {
  padding: 12px 16px;
  border-bottom: 1px solid #e8eaed;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
}

.tree-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.tree-nodes {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* 右侧内容区 */
.file-content-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.empty-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
  gap: 16px;
}

.content-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.file-header {
  padding: 12px 16px;
  border-bottom: 1px solid #e8eaed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fafafa;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  font-weight: 500;
  color: #202124;
}

.file-size {
  font-size: 12px;
  color: #5f6368;
}

.file-body {
  flex: 1;
  overflow: auto;
  background: #f8f9fa;
}

.binary-file {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  color: #666;
}

.code-content {
  margin: 0;
  padding: 16px;
  background: #f8f9fa;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #202124;
  overflow-x: auto;
}

.code-content code {
  display: block;
  white-space: pre;
}

/* 滚动条样式 */
.tree-content::-webkit-scrollbar,
.file-body::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.tree-content::-webkit-scrollbar-track,
.file-body::-webkit-scrollbar-track {
  background: transparent;
}

.tree-content::-webkit-scrollbar-thumb,
.file-body::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.tree-content::-webkit-scrollbar-thumb:hover,
.file-body::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}
</style>
