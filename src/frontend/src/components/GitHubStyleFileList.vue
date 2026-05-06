<template>
  <div class="github-file-list">
    <a-spin v-if="loading" />
    <div v-else-if="fileTree.length === 0" class="empty-state">
      <InboxOutlined style="font-size: 32px; color: #ccc" />
      <p>暂无文件</p>
    </div>
    <div v-else class="file-list-container">
      <!-- 文件列表表格 -->
      <div class="file-table">
        <div
          v-for="item in flattenedFiles"
          :key="item.path"
          :class="['file-row', { 'is-directory': item.type === 'directory', 'is-expanded': item.expanded }]"
          @click="handleRowClick(item)"
        >
          <div class="file-cell file-name-cell" :style="{ paddingLeft: `${item.level * 20 + 12}px` }">
            <!-- 展开/收起图标 -->
            <span v-if="item.type === 'directory'" class="expand-icon">
              <RightOutlined v-if="!item.expanded" />
              <DownOutlined v-else />
            </span>

            <!-- 文件/文件夹图标 -->
            <span class="file-icon">
              <FolderFilled v-if="item.type === 'directory'" :style="{ color: '#54aeff' }" />
              <FileOutlined v-else :style="{ color: '#57606a' }" />
            </span>

            <!-- 文件名 -->
            <span class="file-name">{{ item.name }}</span>
          </div>

          <div class="file-cell file-size-cell">
            <span v-if="item.type === 'file' && item.size" class="file-size">
              {{ formatSize(item.size) }}
            </span>
          </div>
        </div>
      </div>

      <!-- 文件内容查看器 -->
      <div v-if="selectedFile" class="file-viewer">
        <div class="viewer-header">
          <div class="viewer-title">
            <FileOutlined />
            <span>{{ selectedFile.name }}</span>
            <span class="file-size-badge">{{ formatSize(selectedFile.size || 0) }}</span>
          </div>
          <a-button size="small" @click="copyContent">
            <CopyOutlined />
            复制
          </a-button>
        </div>
        <div class="viewer-body">
          <a-spin v-if="loadingContent" />
          <div v-else-if="fileContent?.is_binary" class="binary-file">
            <WarningOutlined style="font-size: 32px; color: #faad14" />
            <p>这是一个二进制文件，无法预览</p>
          </div>
          <pre v-else class="code-content"><code :class="getLanguageClass(selectedFile.name)">{{ fileContent?.content }}</code></pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  FolderFilled,
  FileOutlined,
  RightOutlined,
  DownOutlined,
  InboxOutlined,
  CopyOutlined,
  WarningOutlined
} from '@ant-design/icons-vue'
import { getSkillFiles, getSkillFileContent, type FileTreeNode, type FileContent } from '@/apis/skills'

const props = defineProps<{
  skillId: string
}>()

const loading = ref(true)
const loadingContent = ref(false)
const fileTree = ref<FileTreeNode[]>([])
const expandedPaths = ref<Set<string>>(new Set())
const selectedFile = ref<FileTreeNode | null>(null)
const fileContent = ref<FileContent | null>(null)

// 扁平化文件树用于显示
interface FlattenedItem extends FileTreeNode {
  level: number
  expanded?: boolean
}

const flattenedFiles = computed(() => {
  const result: FlattenedItem[] = []

  const flatten = (nodes: FileTreeNode[], level: number) => {
    for (const node of nodes) {
      const expanded = expandedPaths.value.has(node.path)
      result.push({ ...node, level, expanded })

      if (node.type === 'directory' && expanded && node.children) {
        flatten(node.children, level + 1)
      }
    }
  }

  flatten(fileTree.value, 0)
  return result
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

// 处理行点击
const handleRowClick = async (item: FlattenedItem) => {
  if (item.type === 'directory') {
    // 切换展开/收起
    if (expandedPaths.value.has(item.path)) {
      expandedPaths.value.delete(item.path)
    } else {
      expandedPaths.value.add(item.path)
    }
  } else {
    // 加载文件内容
    selectedFile.value = item
    await loadFileContent(item.path)
  }
}

// 加载文件内容
const loadFileContent = async (path: string) => {
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

// 复制文件内容
const copyContent = () => {
  if (fileContent.value?.content) {
    navigator.clipboard.writeText(fileContent.value.content)
    message.success('已复制到剪贴板')
  }
}

// 格式化文件大小
const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// 获取语言类名
const getLanguageClass = (filename: string) => {
  const ext = filename.split('.').pop()?.toLowerCase()
  const langMap: Record<string, string> = {
    'py': 'language-python',
    'js': 'language-javascript',
    'ts': 'language-typescript',
    'vue': 'language-vue',
    'html': 'language-html',
    'css': 'language-css',
    'json': 'language-json',
    'md': 'language-markdown',
    'yaml': 'language-yaml',
    'yml': 'language-yaml',
    'sh': 'language-bash',
  }
  return langMap[ext || ''] || 'language-text'
}

onMounted(() => {
  loadFileTree()
})
</script>

<style scoped>
.github-file-list {
  border: 1px solid #e1e4e8;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #6a737d;
}

.empty-state p {
  margin-top: 12px;
  font-size: 14px;
}

.file-list-container {
  display: flex;
  flex-direction: column;
}

/* 文件表格 */
.file-table {
  background: #fafbfc;
}

.file-row {
  display: flex;
  align-items: center;
  border-bottom: 1px solid #e1e4e8;
  cursor: pointer;
  transition: all 0.15s ease;
  background: #fff;
}

.file-row:last-child {
  border-bottom: none;
}

.file-row:hover {
  background-color: #f6f8fa;
  border-left: 3px solid #0366d6;
  padding-left: calc(var(--indent) - 3px);
}

.file-row.is-expanded {
  background-color: #f6f8fa;
}

.file-cell {
  padding: 10px 16px;
  font-size: 14px;
  color: #24292e;
}

.file-name-cell {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.expand-icon {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #6a737d;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.file-row:hover .expand-icon {
  color: #0366d6;
}

.file-icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.file-row:hover .file-icon {
  transform: scale(1.1);
}

.file-name {
  font-weight: 500;
  color: #0366d6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.15s ease;
}

.file-row:hover .file-name {
  color: #0366d6;
  text-decoration: underline;
}

.is-directory .file-name {
  color: #24292e;
  font-weight: 600;
}

.is-directory:hover .file-name {
  color: #0366d6;
}

.file-size-cell {
  width: 120px;
  text-align: right;
  flex-shrink: 0;
}

.file-size {
  font-size: 12px;
  color: #6a737d;
  font-family: 'SFMono-Regular', 'Consolas', monospace;
}

/* 文件查看器 */
.file-viewer {
  margin-top: 24px;
  border: 1px solid #e1e4e8;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: linear-gradient(180deg, #fafbfc 0%, #f6f8fa 100%);
  border-bottom: 1px solid #e1e4e8;
}

.viewer-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #24292e;
}

.viewer-title .anticon {
  color: #0366d6;
}

.file-size-badge {
  font-size: 11px;
  font-weight: 500;
  color: #6a737d;
  padding: 3px 10px;
  background: #fff;
  border: 1px solid #e1e4e8;
  border-radius: 16px;
  font-family: 'SFMono-Regular', 'Consolas', monospace;
}

.viewer-body {
  max-height: 600px;
  overflow: auto;
  background: #f6f8fa;
}

.viewer-body::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

.viewer-body::-webkit-scrollbar-track {
  background: #f6f8fa;
}

.viewer-body::-webkit-scrollbar-thumb {
  background: #d1d5da;
  border-radius: 5px;
}

.viewer-body::-webkit-scrollbar-thumb:hover {
  background: #959da5;
}

.binary-file {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 16px;
  color: #6a737d;
}

.binary-file p {
  font-size: 14px;
}

.code-content {
  margin: 0;
  padding: 20px;
  background: #fff;
  border: none;
  font-family: 'SFMono-Regular', 'Consolas', 'Liberation Mono', 'Menlo', monospace;
  font-size: 13px;
  line-height: 1.7;
  color: #24292e;
  overflow-x: auto;
  tab-size: 4;
}

.code-content::-webkit-scrollbar {
  height: 8px;
}

.code-content::-webkit-scrollbar-track {
  background: #f6f8fa;
}

.code-content::-webkit-scrollbar-thumb {
  background: #d1d5da;
  border-radius: 4px;
}

.code-content code {
  background: transparent;
  padding: 0;
  border: none;
  font-family: inherit;
}
</style>