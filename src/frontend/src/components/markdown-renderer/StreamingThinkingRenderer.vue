<template>
  <div v-if="content" class="thinking-block" :class="{ collapsed: isCollapsed }">
    <div class="thinking-header" @click="toggleCollapse">
      <span class="think-dot-icon"></span>
      <span class="think-label">思考过程</span>
      <span class="think-chars">{{ displayContent.length }} 字</span>
      <span class="think-chevron" :class="{ expanded: !isCollapsed }">▼</span>
    </div>
    <Transition name="slide">
      <div v-if="!isCollapsed" class="thinking-body-wrapper">
        <div class="thinking-body">
          <span v-html="renderedContent"></span><span v-if="isStreaming" class="cursor-blink"></span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'

interface Props {
  content: string
  streaming?: boolean
  streamingSpeed?: number
  collapsed?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  streaming: false,
  streamingSpeed: 20,
  collapsed: true
})

const isCollapsed = ref(props.collapsed)
const displayContent = ref('')
const isStreaming = ref(false)
let currentCharIndex = 0
let streamingTimer: ReturnType<typeof setTimeout> | null = null

// 切换折叠状态
const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
}

// 清除流式处理
const clearStreaming = () => {
  if (streamingTimer) {
    clearTimeout(streamingTimer)
    streamingTimer = null
  }
}

// 启动流式输出 - 从当前位置继续
const animate = () => {
  if (currentCharIndex < props.content.length) {
    currentCharIndex++
    displayContent.value = props.content.substring(0, currentCharIndex)
    streamingTimer = setTimeout(animate, props.streamingSpeed)
  } else {
    isStreaming.value = false
    streamingTimer = null
  }
}

// 监听内容变化
watch(() => props.content, (newContent) => {
  if (!newContent) {
    clearStreaming()
    displayContent.value = ''
    currentCharIndex = 0
    isStreaming.value = false
    return
  }

  if (props.streaming) {
    if (newContent.length > displayContent.value.length) {
      // 内容变长：继续从当前位置流式输出，不重置 currentCharIndex
      if (!streamingTimer) {
        isStreaming.value = true
        animate()
      }
    } else if (newContent.length === displayContent.value.length) {
      // 内容相同，不做任何处理
      return
    } else {
      // 内容缩短 - 重置
      currentCharIndex = 0
      displayContent.value = ''
      isStreaming.value = true
      animate()
    }
  } else {
    clearStreaming()
    displayContent.value = newContent
    currentCharIndex = newContent.length
    isStreaming.value = false
  }
}, { immediate: true })

// 监听流式状态变化
watch(() => props.streaming, (streaming) => {
  if (streaming) {
    // 正在流式输出，自动展开
    isCollapsed.value = false
  } else {
    // 流式结束
    if (streamingTimer) {
      clearStreaming()
      displayContent.value = props.content
      currentCharIndex = props.content.length
      isStreaming.value = false
    }
  }
}, { immediate: true })

// 简单渲染：处理换行
const renderedContent = computed(() => {
  const content = displayContent.value || ''
  if (!content) return ''
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
})

// 清理定时器
onBeforeUnmount(() => {
  clearStreaming()
})
</script>

<style scoped>
.thinking-block {
  border: 0.5px solid #e8e8e8;
  border-radius: 8px;
  background: #fafbfc;
  margin-bottom: 8px;
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #888;
  user-select: none;
}

.thinking-header:hover {
  background: #f0f2f5;
}

.think-dot-icon {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #7F77DD;
  flex-shrink: 0;
}

.think-label {
  flex: 1;
  font-weight: 500;
}

.think-chars {
  font-size: 12px;
  color: #bbb;
}

.think-chevron {
  font-size: 10px;
  color: #bbb;
  transition: transform 0.2s ease;
}

.think-chevron.expanded {
  transform: rotate(180deg);
}

.thinking-body-wrapper {
  border-top: 0.5px solid #e8e8e8;
}

.thinking-body {
  padding: 10px 14px;
  font-size: 13px;
  color: #999;
  font-family: 'SFMono-Regular', Consolas, monospace;
  white-space: pre-wrap;
  line-height: 1.7;
  max-height: 200px;
  overflow-y: auto;
}

/* 打字机光标 */
.cursor-blink {
  display: inline-block;
  width: 2px;
  height: 1em;
  background-color: #7F77DD;
  margin-left: 1px;
  animation: blink-cursor 0.7s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  vertical-align: text-bottom;
  border-radius: 1px;
}

@keyframes blink-cursor {
  0%, 45% {
    opacity: 1;
    background-color: #7F77DD;
  }
  50%, 100% {
    opacity: 0.3;
    background-color: #7F77DD;
  }
}

/* 折叠动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 400px;
}
</style>
