<template>
  <div class="markdown-content" :class="{ 'streaming-mode': streaming }" v-html="renderedMarkdown"></div>
  <span v-if="streaming" class="cursor-blink"></span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
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

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
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

// 预处理：确保标题、列表、分隔线前有空行
function preprocessMarkdown(raw: string): string {
  raw = raw.replace(/([^\n])\n(#{1,6} )/g, '$1\n\n$2')
  raw = raw.replace(/([^\n])\n([-*+] |\d+\. )/g, '$1\n\n$2')
  raw = raw.replace(/([^\n])\n(---+|\*\*\*+|___+)(\n|$)/g, '$1\n\n$2\n\n')
  return raw
}

// 渲染 Markdown
const renderedMarkdown = computed(() => {
  const content = props.content || ''
  if (!content) return ''
  
  try {
    return marked(preprocessMarkdown(content))
  } catch (error) {
    console.error('Markdown 渲染失败:', error)
    return content // 降级为纯文本
  }
})
</script>

<style scoped>
.markdown-content {
  line-height: 1.6;
  color: var(--text-primary);
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
  0%, 49% { opacity: 1; background-color: #1890ff; }
  50%, 100% { opacity: 0; background-color: transparent; }
}

/* 流式期间禁用所有入场动画，避免 v-html 替换 DOM 时反复触发闪烁 */
.markdown-content.streaming-mode :deep(*) {
  animation: none !important;
}

/* 标题 */
.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  margin: 16px 0 8px 0;
  font-weight: 600;
  color: var(--text-primary);
  animation: fadeIn 0.3s ease-out;
}

.markdown-content :deep(h1) { font-size: 1.5em; border-bottom: 1px solid var(--border-color); padding-bottom: 8px; }
.markdown-content :deep(h2) { font-size: 1.3em; }
.markdown-content :deep(h3) { font-size: 1.1em; }

/* 段落 */
.markdown-content :deep(p) {
  margin: 8px 0;
  animation: fadeIn 0.3s ease-out;
}

/* 列表 */
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

/* 代码块 */
.markdown-content :deep(pre) {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
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
  background: var(--bg-secondary);
  border-radius: 3px;
  padding: 2px 4px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
  color: #d73a49;
}

/* 暗黑模式下行内代码颜色调亮 */
[data-theme='dark'] .markdown-content :deep(code) {
  color: #f97583;
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
  color: inherit;
}

/* 暗黑模式下覆盖 highlight.js github.css 的亮色背景 */
[data-theme='dark'] .markdown-content :deep(.hljs) {
  background: var(--bg-secondary);
  color: #abb2bf;
}

[data-theme='dark'] .markdown-content :deep(.hljs-keyword),
[data-theme='dark'] .markdown-content :deep(.hljs-selector-tag),
[data-theme='dark'] .markdown-content :deep(.hljs-built_in) { color: #c678dd; }

[data-theme='dark'] .markdown-content :deep(.hljs-string),
[data-theme='dark'] .markdown-content :deep(.hljs-attr) { color: #98c379; }

[data-theme='dark'] .markdown-content :deep(.hljs-number),
[data-theme='dark'] .markdown-content :deep(.hljs-literal) { color: #d19a66; }

[data-theme='dark'] .markdown-content :deep(.hljs-comment) { color: #5c6370; font-style: italic; }

[data-theme='dark'] .markdown-content :deep(.hljs-title),
[data-theme='dark'] .markdown-content :deep(.hljs-function) { color: #61afef; }

[data-theme='dark'] .markdown-content :deep(.hljs-variable),
[data-theme='dark'] .markdown-content :deep(.hljs-params) { color: #e06c75; }

/* 引用 */
.markdown-content :deep(blockquote) {
  border-left: 4px solid var(--border-color);
  padding: 8px 16px;
  margin: 12px 0;
  color: var(--text-secondary);
  font-style: italic;
  animation: slideIn 0.3s ease-out;
  background: var(--bg-secondary);
  border-radius: 0 4px 4px 0;
}

/* 表格 */
.markdown-content :deep(table) {
  border-collapse: collapse;
  margin: 12px 0;
  width: 100%;
  animation: slideIn 0.3s ease-out;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--border-color);
  padding: 8px 12px;
  text-align: left;
  color: var(--text-primary);
}

.markdown-content :deep(th) {
  background: var(--bg-secondary);
  font-weight: 600;
}

.markdown-content :deep(tbody tr:hover td) {
  background: var(--hover-bg, var(--bg-secondary));
}

/* 链接 */
.markdown-content :deep(a) {
  color: var(--link-color, #0366d6);
  text-decoration: none;
  transition: all 0.2s ease;
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

/* 分割线 */
.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 16px 0;
  animation: fadeIn 0.3s ease-out;
}

/* 强调 */
.markdown-content :deep(strong) {
  font-weight: 600;
  color: var(--text-primary);
}

.markdown-content :deep(em) {
  font-style: italic;
  color: var(--text-secondary);
}

/* 删除线 */
.markdown-content :deep(del) {
  text-decoration: line-through;
  color: var(--text-secondary);
}

/* 动画 */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
