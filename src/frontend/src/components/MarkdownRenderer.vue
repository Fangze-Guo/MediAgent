<template>
  <div class="markdown-content" v-html="renderedMarkdown"></div>
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
}

const props = withDefaults(defineProps<Props>(), {
  enableHighlight: true
})

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

// 渲染 Markdown
const renderedMarkdown = computed(() => {
  if (!props.content) return ''
  
  try {
    return marked(props.content)
  } catch (error) {
    console.error('Markdown 渲染失败:', error)
    return props.content // 降级为纯文本
  }
})
</script>

<style scoped>
.markdown-content {
  line-height: 1.6;
  color: #333;
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
}

.markdown-content :deep(h1) { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 8px; }
.markdown-content :deep(h2) { font-size: 1.3em; }
.markdown-content :deep(h3) { font-size: 1.1em; }

/* 段落样式 */
.markdown-content :deep(p) {
  margin: 8px 0;
}

/* 列表样式 */
.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-content :deep(li) {
  margin: 4px 0;
}

/* 代码块样式 */
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
}

.markdown-content :deep(code) {
  background: #f6f8fa;
  border-radius: 3px;
  padding: 2px 4px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
}

/* 引用样式 */
.markdown-content :deep(blockquote) {
  border-left: 4px solid #dfe2e5;
  padding-left: 16px;
  margin: 12px 0;
  color: #6a737d;
  font-style: italic;
}

/* 表格样式 */
.markdown-content :deep(table) {
  border-collapse: collapse;
  margin: 12px 0;
  width: 100%;
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
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

/* 分割线样式 */
.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid #eaecef;
  margin: 16px 0;
}

/* 强调样式 */
.markdown-content :deep(strong) {
  font-weight: 600;
}

.markdown-content :deep(em) {
  font-style: italic;
}

/* 删除线样式 */
.markdown-content :deep(del) {
  text-decoration: line-through;
  color: #6a737d;
}
</style>
