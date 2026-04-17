<template>
  <div class="streaming-wrapper">
    <div class="markdown-content" :class="{ 'streaming-active': isStreaming }" v-html="renderedMarkdown"></div>
    <span v-if="isStreaming" class="cursor-blink"></span>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, ref, onBeforeUnmount } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import python from 'highlight.js/lib/languages/python'
import json from 'highlight.js/lib/languages/json'
import 'highlight.js/styles/github.css'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('json', json)

interface Props {
  content: string
  enableHighlight?: boolean
  streaming?: boolean
  streamingSpeed?: number
}

const props = withDefaults(defineProps<Props>(), {
  enableHighlight: true,
  streaming: false,
  streamingSpeed: 15
})

const displayContent = ref('')
const isStreaming = ref(false)
let currentCharIndex = 0
let streamingTimer: ReturnType<typeof setTimeout> | null = null

// 配置 marked
const configureMarked = () => {
  marked.setOptions({
    breaks: true,
    gfm: true,
  })

  const renderer = new marked.Renderer()
  renderer.code = function(code: string, lang: string) {
    if (props.enableHighlight && lang && hljs.getLanguage(lang)) {
      try {
        const highlighted = hljs.highlight(code, { language: lang }).value
        return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>`
      } catch (err) {
        console.warn('代码高亮失败:', err)
      }
    }
    return `<pre><code>${code}</code></pre>`
  }

  marked.use({ renderer })
}

configureMarked()

// 启动流式输出 - 从当前位置继续
const animate = () => {
  if (currentCharIndex < props.content.length) {
    currentCharIndex++
    displayContent.value = props.content.substring(0, currentCharIndex)
    streamingTimer = setTimeout(animate, props.streamingSpeed)
  } else {
    // 输出完成
    isStreaming.value = false
    streamingTimer = null
  }
}

// 清除流式处理
const clearStreaming = () => {
  if (streamingTimer) {
    clearTimeout(streamingTimer)
    streamingTimer = null
  }
}

// 监听内容变化 - 核心逻辑修复
watch(() => props.content, (newContent) => {
  if (!newContent) {
    clearStreaming()
    displayContent.value = ''
    currentCharIndex = 0
    isStreaming.value = false
    return
  }

  // 如果是流式模式
  if (props.streaming) {
    // 内容是新增的（长度变长）
    if (newContent.length > displayContent.value.length) {
      // 继续从当前位置流式输出，不重置 currentCharIndex
      if (!streamingTimer) {
        isStreaming.value = true
        animate()
      }
    } else if (newContent.length === displayContent.value.length) {
      // 内容相同，不做任何处理
      return
    } else {
      // 内容缩短（不应该发生）- 重置
      currentCharIndex = 0
      displayContent.value = ''
      isStreaming.value = true
      animate()
    }
  } else {
    // 非流式模式 - 立即显示完整内容
    clearStreaming()
    displayContent.value = newContent
    currentCharIndex = newContent.length
    isStreaming.value = false
  }
}, { immediate: true })

// 监听流式状态变化 - 流式结束时完整显示
watch(() => props.streaming, (streaming) => {
  if (!streaming && streamingTimer) {
    // 流式输出结束，立即显示完整内容
    clearStreaming()
    displayContent.value = props.content
    currentCharIndex = props.content.length
    isStreaming.value = false
  }
})

// 渲染 Markdown
const renderedMarkdown = computed(() => {
  const content = displayContent.value || ''
  if (!content) return ''

  try {
    return marked(content)
  } catch (error) {
    console.error('Markdown 渲染失败:', error)
    return content
  }
})

// 清理定时器
onBeforeUnmount(() => {
  if (streamingTimer) {
    clearTimeout(streamingTimer)
    streamingTimer = null
  }
})
</script>

<style scoped>
.streaming-wrapper {
  position: relative;
  width: 100%;
}

.markdown-content {
  line-height: 1.6;
  color: #333;
  word-break: break-word;
  overflow-wrap: break-word;
  transition: all 0.2s ease;
}

.markdown-content.streaming-active {
  padding-right: 4px;
}

/* 打字机光标动画 */
.cursor-blink {
  display: inline-block;
  width: 2px;
  height: 1.2em;
  background-color: #1890ff;
  margin-left: 1px;
  animation: blink-cursor 0.7s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  vertical-align: text-bottom;
  border-radius: 1px;
}

@keyframes blink-cursor {
  0%, 45% {
    opacity: 1;
    background-color: #1890ff;
    box-shadow: 0 0 4px rgba(24, 144, 255, 0.4);
  }
  50%, 100% {
    opacity: 0.3;
    background-color: #1890ff;
    box-shadow: none;
  }
}

/* 标题样式 - 优雅的淡入 */
.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  margin: 16px 0 8px 0;
  font-weight: 600;
  color: #1a1a1a;
}

.markdown-content :deep(h1) {
  font-size: 1.5em;
  border-bottom: 2px solid #eaecef;
  padding-bottom: 8px;
}

.markdown-content :deep(h2) {
  font-size: 1.3em;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 4px;
}

.markdown-content :deep(h3) {
  font-size: 1.1em;
}

/* 段落 */
.markdown-content :deep(p) {
  margin: 8px 0;
  line-height: 1.8;
}

/* 列表 */
.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 12px 0;
  padding-left: 28px;
}

.markdown-content :deep(li) {
  margin: 6px 0;
  line-height: 1.6;
}

/* 代码块 - 美化展示 */
.markdown-content :deep(pre) {
  background: linear-gradient(135deg, #f5f7fa 0%, #f0f2f5 100%);
  border: 1px solid #e1e4e8;
  border-radius: 8px;
  padding: 16px;
  margin: 12px 0;
  overflow-x: auto;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.5;
  position: relative;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  scroll-behavior: smooth;
}

.markdown-content :deep(pre)::-webkit-scrollbar {
  height: 6px;
}

.markdown-content :deep(pre)::-webkit-scrollbar-track {
  background: #f0f0f0;
  border-radius: 3px;
}

.markdown-content :deep(pre)::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.markdown-content :deep(pre)::-webkit-scrollbar-thumb:hover {
  background: #999;
}

.markdown-content :deep(code) {
  background: #f6f8fa;
  border-radius: 3px;
  padding: 2px 6px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
  color: #d73a49;
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
  color: #24292e;
}

/* 引用块 */
.markdown-content :deep(blockquote) {
  border-left: 4px solid #1890ff;
  padding: 12px 16px;
  margin: 12px 0;
  background: #f5f7ff;
  border-radius: 0 4px 4px 0;
  color: #555;
}

.markdown-content :deep(blockquote p) {
  margin: 0;
}

/* 表格 */
.markdown-content :deep(table) {
  border-collapse: collapse;
  margin: 16px 0;
  width: 100%;
  background: white;
  border: 1px solid #dfe2e5;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.markdown-content :deep(thead) {
  background: #fafbfc;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid #dfe2e5;
  padding: 10px 12px;
  text-align: left;
}

.markdown-content :deep(th) {
  background: #f6f8fa;
  font-weight: 600;
  color: #24292e;
}

.markdown-content :deep(tbody tr:hover) {
  background: #f9f9f9;
}

/* 链接 */
.markdown-content :deep(a) {
  color: #0366d6;
  text-decoration: none;
  border-bottom: 1px solid rgba(3, 102, 214, 0);
  transition: all 0.2s ease;
}

.markdown-content :deep(a:hover) {
  color: #0256c7;
  border-bottom-color: #0256c7;
  text-decoration: none;
}

/* 分割线 */
.markdown-content :deep(hr) {
  border: none;
  height: 2px;
  background: linear-gradient(90deg, transparent, #eaecef 50%, transparent);
  margin: 20px 0;
}

/* 强调 */
.markdown-content :deep(strong) {
  font-weight: 600;
  color: #1a1a1a;
}

.markdown-content :deep(em) {
  font-style: italic;
  color: #555;
}

.markdown-content :deep(del) {
  text-decoration: line-through;
  color: #999;
  opacity: 0.7;
}

/* 图片 */
.markdown-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 12px 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}
</style>
