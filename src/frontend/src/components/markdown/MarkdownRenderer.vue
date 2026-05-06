<template>
  <div class="markdown-content" :class="{ 'streaming-mode': streaming }" v-html="renderedMarkdown"></div>
  <span v-if="streaming" class="cursor-blink"></span>
</template>

<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import python from 'highlight.js/lib/languages/python'
import json from 'highlight.js/lib/languages/json'
import 'highlight.js/styles/github.css'

// 注册语言
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('json', json)

// Props
interface Props {
  /** 要渲染的 Markdown 内容 */
  content: string
  /** 是否启用代码高亮 */
  enableHighlight?: boolean
  /** 是否处于流式输出状态 */
  streaming?: boolean
  /** 流式输出速度（毫秒） */
  streamingSpeed?: number
}

const props = withDefaults(defineProps<Props>(), {
  enableHighlight: true,
  streaming: false,
  streamingSpeed: 20
})

const displayContent = ref('')
const lastRenderedContent = ref('')

// 配置 marked
marked.setOptions({
  breaks: true, // 支持换行
  gfm: true,    // 启用 GitHub 风格的 Markdown
})

// 自定义渲染器用于代码高亮
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

// 流式渲染动画处理
let animationFrameId: number | null = null
let charIndex = 0
let accumulatedTime = 0

const animateStreamingContent = () => {
  if (charIndex < props.content.length) {
    charIndex++
    displayContent.value = props.content.substring(0, charIndex)
    animationFrameId = requestAnimationFrame(animateStreamingContent)
  } else {
    // 完成后，使用完整内容
    lastRenderedContent.value = props.content
  }
}

// 监听内容变化，处理流式输出
watch(() => props.content, (newContent) => {
  if (!newContent) {
    displayContent.value = ''
    charIndex = 0
    if (animationFrameId !== null) {
      cancelAnimationFrame(animationFrameId)
      animationFrameId = null
    }
    return
  }

  if (props.streaming && newContent.length > lastRenderedContent.value.length) {
    // 流式模式，只处理新增的字符
    if (charIndex === 0) {
      charIndex = lastRenderedContent.value.length
    }
    if (animationFrameId === null) {
      animationFrameId = requestAnimationFrame(animateStreamingContent)
    }
  } else {
    // 非流式模式，直接显示
    lastRenderedContent.value = newContent
    displayContent.value = newContent
    charIndex = 0
    if (animationFrameId !== null) {
      cancelAnimationFrame(animationFrameId)
      animationFrameId = null
    }
  }
}, { immediate: true })

// 渲染 Markdown
const renderedMarkdown = computed(() => {
  const content = displayContent.value || ''
  if (!content) return ''
  
  try {
    return marked(content)
  } catch (error) {
    console.error('Markdown 渲染失败:', error)
    return content // 降级为纯文本
  }
})
</script>

<style scoped>
.markdown-content {
  line-height: 1.6;
  color: #333;
  word-break: break-word;
  overflow-wrap: break-word;
}

.markdown-content.streaming-mode {
  position: relative;
  display: inline-block;
  width: 100%;
}

/* 打字机光标 */
.cursor-blink {
  display: inline-block;
  width: 2px;
  height: 1em;
  background-color: #1890ff;
  margin-left: 2px;
  animation: cursor-blink 0.8s ease-in-out infinite;
  vertical-align: middle;
}

@keyframes cursor-blink {
  0%, 49% {
    opacity: 1;
    background-color: #1890ff;
  }
  50%, 100% {
    opacity: 0;
    background-color: transparent;
  }
}

/* 标题样式 */
.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  margin: 16px 0 8px 0;
  font-weight: 600;
  color: #1a1a1a;
  animation: fadeIn 0.3s ease-out;
}

.markdown-content :deep(h1) { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 8px; }
.markdown-content :deep(h2) { font-size: 1.3em; }
.markdown-content :deep(h3) { font-size: 1.1em; }

/* 段落样式 */
.markdown-content :deep(p) {
  margin: 8px 0;
  animation: fadeIn 0.3s ease-out;
}

/* 列表样式 */
.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
  animation: slideIn 0.3s ease-out;
}

.markdown-content :deep(li) {
  margin: 4px 0;
  animation: slideIn 0.3s ease-out;
}

/* 代码块样式 - 增强高亮效果 */
.markdown-content :deep(pre) {
  background: #f6f8fa;
  border: 1px solid #e1e4e8;
  border-radius: 6px;
  padding: 16px;
  margin: 12px 0;
  overflow-x: auto;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 14px;
  line-height: 1.45;
  animation: slideIn 0.3s ease-out;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.markdown-content :deep(code) {
  background: #f6f8fa;
  border-radius: 3px;
  padding: 2px 4px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
  color: #d73a49;
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
  color: inherit;
}

/* 引用样式 */
.markdown-content :deep(blockquote) {
  border-left: 4px solid #dfe2e5;
  padding-left: 16px;
  margin: 12px 0;
  color: #6a737d;
  font-style: italic;
  animation: slideIn 0.3s ease-out;
  background: #f8f9fa;
  padding-top: 8px;
  padding-bottom: 8px;
  border-radius: 0 4px 4px 0;
}

/* 表格样式 */
.markdown-content :deep(table) {
  border-collapse: collapse;
  margin: 12px 0;
  width: 100%;
  animation: slideIn 0.3s ease-out;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid #dfe2e5;
  padding: 8px 12px;
  text-align: left;
}

.markdown-content :deep(th) {
  background: #f6f8fa;
  font-weight: 600;
}

/* 链接样式 */
.markdown-content :deep(a) {
  color: #0366d6;
  text-decoration: none;
  transition: all 0.2s ease;
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
  color: #0256c7;
}

/* 分割线样式 */
.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid #eaecef;
  margin: 16px 0;
  animation: fadeIn 0.3s ease-out;
}

/* 强调样式 */
.markdown-content :deep(strong) {
  font-weight: 600;
  color: #1a1a1a;
}

.markdown-content :deep(em) {
  font-style: italic;
  color: #555;
}

/* 删除线样式 */
.markdown-content :deep(del) {
  text-decoration: line-through;
  color: #6a737d;
}

/* 动画效果 */
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
