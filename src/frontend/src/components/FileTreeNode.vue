<template>
  <div class="tree-node">
    <div
      :class="['node-item', { 'is-selected': isSelected, 'is-directory': node.type === 'directory' }]"
      @click="handleClick"
    >
      <div class="node-content">
        <!-- 展开/收起图标 -->
        <span v-if="node.type === 'directory'" class="expand-icon">
          <RightOutlined v-if="!expanded" />
          <DownOutlined v-else />
        </span>
        <span v-else class="file-icon-placeholder"></span>

        <!-- 文件/文件夹图标 -->
        <span class="node-icon">
          <FolderOutlined v-if="node.type === 'directory'" :style="{ color: expanded ? '#faad14' : '#5f6368' }" />
          <FileOutlined v-else :style="{ color: getFileIconColor(node.name) }" />
        </span>

        <!-- 文件/文件夹名称 -->
        <span class="node-name">{{ node.name }}</span>

        <!-- 文件大小 -->
        <span v-if="node.type === 'file' && node.size" class="node-size">
          {{ formatSize(node.size) }}
        </span>
      </div>
    </div>

    <!-- 子节点（递归） -->
    <div v-if="node.type === 'directory' && expanded && node.children" class="node-children">
      <FileTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :selected-path="selectedPath"
        @select="$emit('select', $event.path, $event.type)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { FolderOutlined, FileOutlined, RightOutlined, DownOutlined } from '@ant-design/icons-vue'
import type { FileTreeNode as FileNode } from '@/apis/skills'

const props = defineProps<{
  node: FileNode
  selectedPath: string
}>()

const emit = defineEmits<{
  select: [{ path: string; type: string }]
}>()

const expanded = ref(false)

const isSelected = computed(() => props.selectedPath === props.node.path)

const handleClick = () => {
  if (props.node.type === 'directory') {
    expanded.value = !expanded.value
  } else {
    emit('select', { path: props.node.path, type: props.node.type })
  }
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

const getFileIconColor = (filename: string) => {
  const ext = filename.split('.').pop()?.toLowerCase()
  const colorMap: Record<string, string> = {
    'py': '#3776ab',
    'js': '#f7df1e',
    'ts': '#3178c6',
    'vue': '#42b883',
    'md': '#083fa1',
    'json': '#5f6368',
    'yaml': '#cb171e',
    'yml': '#cb171e',
    'sh': '#89e051',
  }
  return colorMap[ext || ''] || '#5f6368'
}
</script>

<style scoped>
.tree-node {
  user-select: none;
}

.node-item {
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.node-item:hover {
  background-color: #e8eaed;
}

.node-item.is-selected {
  background-color: #e3f2fd;
}

.node-content {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.expand-icon {
  width: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #5f6368;
}

.file-icon-placeholder {
  width: 16px;
}

.node-icon {
  font-size: 14px;
  display: flex;
  align-items: center;
}

.node-name {
  flex: 1;
  color: #202124;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-size {
  font-size: 11px;
  color: #5f6368;
}

.node-children {
  margin-left: 16px;
  margin-top: 2px;
}
</style>
