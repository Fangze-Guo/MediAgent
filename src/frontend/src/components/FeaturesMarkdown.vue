<template>
  <div class="features-markdown">
    <!-- 编辑模式 -->
    <div v-if="isEditing && canEdit" class="edit-mode">
      <div class="edit-header">
        <h3>{{ t('components_FeaturesMarkdown.editTitle') }}</h3>
        <div class="edit-actions">
          <a-button @click="cancelEdit" style="margin-right: 8px">{{ t('components_FeaturesMarkdown.cancel') }}</a-button>
          <a-button type="primary" @click="saveFeatures" :loading="saving">{{ t('components_FeaturesMarkdown.save') }}</a-button>
        </div>
      </div>
      
      <div class="edit-content">
        <div class="editor-toolbar">
          <a-space wrap>
            <a-button 
              size="small" 
              @click="undo" 
              :disabled="historyIndex <= 0"
              title="撤销 (Ctrl+Z)"
            >
              <UndoOutlined /> {{ t('components_FeaturesMarkdown.undo') }}
            </a-button>
            <a-button 
              size="small" 
              @click="redo" 
              :disabled="historyIndex >= history.length - 1"
              title="重做 (Ctrl+Shift+Z)"
            >
              <RedoOutlined /> {{ t('components_FeaturesMarkdown.redo') }}
            </a-button>
            <a-divider type="vertical" />
            <a-button size="small" @click="insertMarkdown('**', '**')" title="粗体">
              <BoldOutlined /> {{ t('components_FeaturesMarkdown.bold') }}
            </a-button>
            <a-button size="small" @click="insertMarkdown('*', '*')" title="斜体">
              <ItalicOutlined /> {{ t('components_FeaturesMarkdown.italic') }}
            </a-button>
            <a-button size="small" @click="insertMarkdown('```', '```')" title="代码">
              <CodeOutlined /> {{ t('components_FeaturesMarkdown.code') }}
            </a-button>
            <a-button size="small" @click="insertMarkdown('- ', '')" title="无序列表">
              <UnorderedListOutlined /> {{ t('components_FeaturesMarkdown.list') }}
            </a-button>
            <a-button size="small" @click="insertMarkdown('## ', '')" title="标题">
              <FontSizeOutlined /> {{ t('components_FeaturesMarkdown.heading') }}
            </a-button>
            <a-button size="small" @click="insertMarkdown('[链接文本](', ')')" title="插入链接">
              <LinkOutlined /> {{ t('components_FeaturesMarkdown.link') }}
            </a-button>
            <a-button size="small" @click="triggerImageUpload" :loading="uploading" title="上传图片">
              <PictureOutlined /> {{ t('components_FeaturesMarkdown.image') }}
            </a-button>
          </a-space>
        </div>
        
        <!-- 隐藏的文件上传input -->
        <input
          ref="fileInputRef"
          type="file"
          accept="image/*"
          style="display: none"
          @change="onFileChange"
        />

        <div 
          class="editor-wrapper"
          :class="{ 'is-dragging': isDragging }"
          @dragover="handleDragOver"
          @dragleave="handleDragLeave"
          @drop="handleDrop"
        >
          <a-textarea
            ref="textareaRef"
            v-model:value="editContent"
            :placeholder="t('components_FeaturesMarkdown.placeholder')"
            :rows="20"
            class="markdown-editor"
            @paste="handlePaste"
            @keydown="handleKeyDown"
          />

          <div v-if="isDragging" class="drag-overlay">
            <PictureOutlined style="font-size: 48px; color: #1890ff;" />
            <p>{{ t('components_FeaturesMarkdown.dropImage') }}</p>
          </div>
        </div>
        
        <div class="preview-section">
          <h4>{{ t('components_FeaturesMarkdown.preview') }}</h4>
          <div class="preview-content">
            <MarkdownRenderer :content="previewContent" />
          </div>
        </div>
      </div>
    </div>
    
    <!-- 显示模式 -->
    <div v-else class="display-mode">
      <div class="features-header">
        <h3 class="features-title">
          <AppstoreOutlined />
          {{ t('components_FeaturesMarkdown.title') }}
        </h3>
        <a-button 
          v-if="canEdit" 
          type="text" 
          size="small" 
          @click="startEdit"
          class="edit-btn"
        >
          <EditOutlined />
          {{ t('components_FeaturesMarkdown.edit') }}
        </a-button>
      </div>
      
      <div class="features-content">
        <div v-if="!features || features.trim() === ''" class="empty-features">
          <a-empty 
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
            :description="t('components_FeaturesMarkdown.emptyDescription')"
          >
            <a-button v-if="canEdit" type="primary" @click="startEdit">
              <PlusOutlined />
              {{ t('components_FeaturesMarkdown.addFeatures') }}
            </a-button>
          </a-empty>
        </div>
        
        <div v-else class="markdown-wrapper">
          <MarkdownRenderer :content="features" :enable-highlight="true" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { message, Empty } from 'ant-design-vue'
import {
  EditOutlined,
  AppstoreOutlined,
  PlusOutlined,
  BoldOutlined,
  ItalicOutlined,
  CodeOutlined,
  UnorderedListOutlined,
  FontSizeOutlined,
  LinkOutlined,
  PictureOutlined,
  UndoOutlined,
  RedoOutlined
} from '@ant-design/icons-vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import { useAuthStore } from '@/store/auth'
import { isAdmin } from '@/utils/permission'
import { useI18n } from 'vue-i18n'

interface Props {
  /** 应用ID */
  appId: string
  /** 功能特点内容 */
  features: string
  /** 是否可编辑 */
  canEdit?: boolean
}

interface Emits {
  (e: 'update:features', features: string): void
  (e: 'save', appId: string, features: string): void
}

const props = withDefaults(defineProps<Props>(), {
  canEdit: false
})

const emit = defineEmits<Emits>()

const { t } = useI18n()
const authStore = useAuthStore()

// 编辑状态
const isEditing = ref(false)
const editContent = ref('')
const saving = ref(false)

// 预览内容（将占位符转换为 Base64）
const previewContent = computed(() => {
  return convertPlaceholderToBase64(editContent.value)
})

// 计算是否可以编辑
const canEdit = computed(() => {
  const user = authStore.currentUser
  const propsCanEdit = props.canEdit
  const userIsAdmin = isAdmin(user)
  
  return propsCanEdit && userIsAdmin
})

// 开始编辑
const startEdit = () => {
  const content = props.features || getDefaultFeatures()
  
  // 解析现有的 Base64 图片，转换为占位符
  editContent.value = parseBase64ToPlaceholder(content)
  isEditing.value = true
  
  // 初始化历史记录
  nextTick(() => {
    history.value = []
    historyIndex.value = -1
    saveHistory() // 保存初始状态
  })
}

// 将 Base64 图片转换为占位符（用于编辑）
const parseBase64ToPlaceholder = (content: string): string => {
  // 匹配 ![alt](data:image/...)
  const base64ImageRegex = /!\[([^\]]*)]\((data:image\/[^;]+;base64,[^)]+)\)/g
  
  return content.replace(base64ImageRegex, (_match, alt, base64) => {
    // 生成唯一ID
    const imageId = generateImageId()
    
    // 存储图片数据
    imageDataMap.value.set(imageId, base64)
    
    // 返回占位符
    return `![${alt}](image://${imageId})`
  })
}

// 将占位符转换回 Base64（用于保存）
const convertPlaceholderToBase64 = (content: string): string => {
  // 匹配 ![alt](image://img_xxx)
  const placeholderRegex = /!\[([^\]]*)]\(image:\/\/([^)]+)\)/g
  
  return content.replace(placeholderRegex, (match, alt, imageId) => {
    // 从映射中获取 Base64 数据
    const base64 = imageDataMap.value.get(imageId)
    
    if (base64) {
      return `![${alt}](${base64})`
    } else {
      // 如果找不到数据，保持原样
      console.warn(`${t('components_FeaturesMarkdown.imageDataLost')}: ${imageId}`)
      return match
    }
  })
}

// 取消编辑
const cancelEdit = () => {
  isEditing.value = false
  editContent.value = ''
  
  // 清空图片数据映射
  imageDataMap.value.clear()
  imageIdCounter = 0
}

// 保存功能特点
const saveFeatures = async () => {
  if (!editContent.value.trim()) {
    message.warning(t('components_FeaturesMarkdown.enterContent'))
    return
  }
  
  try {
    saving.value = true
    
    // 将占位符转换回 Base64
    const contentWithBase64 = convertPlaceholderToBase64(editContent.value.trim())
    
    emit('save', props.appId, contentWithBase64)
    emit('update:features', contentWithBase64)
    isEditing.value = false
    
    // 清空图片数据映射
    imageDataMap.value.clear()
    imageIdCounter = 0
    
    message.success(t('components_FeaturesMarkdown.saveSuccess'))
  } catch (error) {
    console.error('保存功能特点失败:', error)
    message.error(t('components_FeaturesMarkdown.saveFailed'))
  } finally {
    saving.value = false
  }
}

// 插入Markdown语法
const textareaRef = ref<any>(null)

const getTextarea = (): HTMLTextAreaElement | null => {
  let textarea: HTMLTextAreaElement | null = null
  
  // 方法1: 通过ref获取（Ant Design Vue组件需要访问内部元素）
  if (textareaRef.value) {
    textarea = textareaRef.value.$el?.querySelector('textarea') || textareaRef.value.$el
  }
  
  // 方法2: 直接查询DOM
  if (!textarea || !(textarea instanceof HTMLTextAreaElement)) {
    textarea = document.querySelector('.markdown-editor textarea') as HTMLTextAreaElement
  }
  
  // 方法3: 查找所有textarea
  if (!textarea) {
    const textareas = document.querySelectorAll('textarea')
    for (let i = 0; i < textareas.length; i++) {
      const ta = textareas[i] as HTMLTextAreaElement
      if (ta.placeholder?.includes('功能特点')) {
        textarea = ta
        break
      }
    }
  }
  
  return textarea
}

const insertMarkdown = (before: string, after: string) => {
  const textarea = getTextarea()
  
  if (!textarea) {
    console.error('未找到textarea元素，请确保编辑器已渲染')
    message.warning('编辑器未就绪，请稍后重试')
    return
  }
  
  // 保存历史记录
  saveHistory()
  
  // 保存当前滚动位置和光标位置
  const scrollTop = textarea.scrollTop
  const scrollLeft = textarea.scrollLeft
  
  const start = textarea.selectionStart || 0
  const end = textarea.selectionEnd || 0
  const selectedText = editContent.value.substring(start, end)
  
  // 构建新文本
  const newText = before + selectedText + after
  const beforeText = editContent.value.substring(0, start)
  const afterText = editContent.value.substring(end)
  
  // 更新内容
  editContent.value = beforeText + newText + afterText
  
  // 使用 requestAnimationFrame 确保 DOM 更新后再操作
  requestAnimationFrame(() => {
    nextTick(() => {
      if (textarea) {
        // 先设置光标位置
        if (selectedText) {
          const newStart = start + before.length
          const newEnd = newStart + selectedText.length
          textarea.setSelectionRange(newStart, newEnd)
        } else {
          // 将光标放在before和after之间
          const newPos = start + before.length
          textarea.setSelectionRange(newPos, newPos)
        }
        
        // 立即恢复滚动位置（在focus之前）
        textarea.scrollTop = scrollTop
        textarea.scrollLeft = scrollLeft
        
        // 最后focus，但不触发滚动
        textarea.focus({ preventScroll: true })
        
        // 再次确保滚动位置正确
        textarea.scrollTop = scrollTop
        textarea.scrollLeft = scrollLeft
      }
    })
  })
}

// 插入文本（用于图片等）
const insertText = (text: string, cursorOffset: number = 0) => {
  const textarea = getTextarea()
  
  if (!textarea) {
    console.error('未找到textarea元素')
    return
  }
  
  // 保存历史记录
  saveHistory()
  
  const scrollTop = textarea.scrollTop
  const scrollLeft = textarea.scrollLeft
  const start = textarea.selectionStart || 0
  const end = textarea.selectionEnd || 0
  
  const beforeText = editContent.value.substring(0, start)
  const afterText = editContent.value.substring(end)
  
  editContent.value = beforeText + text + afterText
  
  requestAnimationFrame(() => {
    nextTick(() => {
      if (textarea) {
        const newPos = start + text.length + cursorOffset
        textarea.setSelectionRange(newPos, newPos)
        
        textarea.scrollTop = scrollTop
        textarea.scrollLeft = scrollLeft
        
        textarea.focus({ preventScroll: true })
        
        textarea.scrollTop = scrollTop
        textarea.scrollLeft = scrollLeft
      }
    })
  })
}

// 撤销/重做功能
interface HistoryState {
  content: string
  cursorStart: number
  cursorEnd: number
  scrollTop: number
}

const history = ref<HistoryState[]>([])
const historyIndex = ref(-1)
const maxHistorySize = 50

// 保存历史记录
const saveHistory = () => {
  const textarea = getTextarea()
  if (!textarea) return
  
  const currentState: HistoryState = {
    content: editContent.value,
    cursorStart: textarea.selectionStart || 0,
    cursorEnd: textarea.selectionEnd || 0,
    scrollTop: textarea.scrollTop || 0
  }
  
  // 如果当前不在历史记录的末尾，删除后面的记录
  if (historyIndex.value < history.value.length - 1) {
    history.value = history.value.slice(0, historyIndex.value + 1)
  }
  
  // 添加新记录
  history.value.push(currentState)
  
  // 限制历史记录大小
  if (history.value.length > maxHistorySize) {
    history.value.shift()
  } else {
    historyIndex.value++
  }
}

// 撤销
const undo = () => {
  if (historyIndex.value <= 0) {
    message.info('没有可撤销的操作')
    return
  }
  
  const textarea = getTextarea()
  if (!textarea) return
  
  historyIndex.value--
  const state = history.value[historyIndex.value]
  
  editContent.value = state.content
  
  requestAnimationFrame(() => {
    nextTick(() => {
      if (textarea) {
        textarea.setSelectionRange(state.cursorStart, state.cursorEnd)
        textarea.scrollTop = state.scrollTop
        textarea.focus({ preventScroll: true })
        textarea.scrollTop = state.scrollTop
      }
    })
  })
}

// 重做
const redo = () => {
  if (historyIndex.value >= history.value.length - 1) {
    message.info('没有可重做的操作')
    return
  }
  
  const textarea = getTextarea()
  if (!textarea) return
  
  historyIndex.value++
  const state = history.value[historyIndex.value]
  
  editContent.value = state.content
  
  requestAnimationFrame(() => {
    nextTick(() => {
      if (textarea) {
        textarea.setSelectionRange(state.cursorStart, state.cursorEnd)
        textarea.scrollTop = state.scrollTop
        textarea.focus({ preventScroll: true })
        textarea.scrollTop = state.scrollTop
      }
    })
  })
}

// 处理键盘快捷键
const handleKeyDown = (event: KeyboardEvent) => {
  // Ctrl+Z 或 Cmd+Z: 撤销
  if ((event.ctrlKey || event.metaKey) && event.key === 'z' && !event.shiftKey) {
    event.preventDefault()
    undo()
    return
  }
  
  // Ctrl+Shift+Z 或 Cmd+Shift+Z 或 Ctrl+Y: 重做
  if (((event.ctrlKey || event.metaKey) && event.shiftKey && event.key === 'z') ||
      (event.ctrlKey && event.key === 'y')) {
    event.preventDefault()
    redo()
    return
  }
  
  // 记录普通输入（延迟保存，避免每个字符都保存）
  if (!event.ctrlKey && !event.metaKey && !event.altKey) {
    if (inputTimer.value !== null) {
      clearTimeout(inputTimer.value)
    }
    inputTimer.value = window.setTimeout(() => {
      saveHistory()
    }, 500) // 500ms 后保存
  }
}

const inputTimer = ref<number | null>(null)

// 处理图片上传
const uploading = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

// 图片数据存储（使用占位符ID映射到实际Base64数据）
const imageDataMap = ref<Map<string, string>>(new Map())
let imageIdCounter = 0

// 生成图片占位符ID
const generateImageId = () => {
  imageIdCounter++
  return `img_${Date.now()}_${imageIdCounter}`
}

const handleImageUpload = async (file: File) => {
  if (!file.type.startsWith('image/')) {
    message.error('请上传图片文件')
    return
  }
  
  // 检查文件大小（限制5MB）
  if (file.size > 5 * 1024 * 1024) {
    message.error('图片大小不能超过5MB')
    return
  }
  
  try {
    uploading.value = true
    
    const reader = new FileReader()
    reader.onload = (e) => {
      const base64 = e.target?.result as string
      
      // 生成唯一ID
      const imageId = generateImageId()
      
      // 存储图片数据
      imageDataMap.value.set(imageId, base64)
      
      // 使用简短的占位符
      const imageMarkdown = `![${file.name}](image://${imageId})\n`
      insertText(imageMarkdown, 0)
      
      message.success(`图片插入成功 (${(file.size / 1024).toFixed(1)}KB)`)
    }
    reader.onerror = () => {
      message.error('图片读取失败')
    }
    reader.readAsDataURL(file)
    
  } catch (error) {
    console.error('图片上传失败:', error)
    message.error('图片上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

const triggerImageUpload = () => {
  fileInputRef.value?.click()
}

const onFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    handleImageUpload(file)
  }
  // 清空input，允许重复上传同一文件
  target.value = ''
}

// 处理粘贴事件
const handlePaste = async (event: ClipboardEvent) => {
  const items = event.clipboardData?.items
  if (!items) return
  
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (item.type.startsWith('image/')) {
      event.preventDefault()
      const file = item.getAsFile()
      if (file) {
        await handleImageUpload(file)
      }
      break
    }
  }
}

// 处理拖拽上传
const isDragging = ref(false)

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = true
}

const handleDragLeave = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = false
}

const handleDrop = async (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = false
  
  const files = event.dataTransfer?.files
  if (!files || files.length === 0) return
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    if (file.type.startsWith('image/')) {
      await handleImageUpload(file)
    }
  }
}

// 获取默认功能特点模板
const getDefaultFeatures = () => {
  return `## 🚀 核心功能

### 主要特性
- **功能一**: 详细描述功能一的作用和优势
- **功能二**: 详细描述功能二的作用和优势
- **功能三**: 详细描述功能三的作用和优势

### 技术亮点
- 高性能处理能力
- 智能算法优化
- 用户友好的界面设计

### 使用场景
1. **场景一**: 适用于xxx情况下的数据处理
2. **场景二**: 适用于xxx情况下的分析需求
3. **场景三**: 适用于xxx情况下的工作流程

### 系统要求
- 操作系统: Windows 10+ / macOS 10.15+ / Linux
- 内存: 最低 4GB RAM，推荐 8GB+
- 存储空间: 至少 1GB 可用空间

### 更新日志
#### v1.0.0
- 初始版本发布
- 实现核心功能
- 支持基础数据处理

---

> 💡 **提示**: 如需更多帮助，请查看用户手册或联系技术支持。`
}
</script>

<style scoped>
.features-markdown {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

/* 显示模式样式 */
.display-mode {
  padding: 0;
}

.features-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
}

.features-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

.edit-btn {
  color: #1890ff;
}

.edit-btn:hover {
  color: #40a9ff;
  background: #f0f9ff;
}

.features-content {
  padding: 20px;
}

.empty-features {
  text-align: center;
  padding: 40px 20px;
}

.markdown-wrapper {
  max-width: none;
}

/* 编辑模式样式 */
.edit-mode {
  border: 1px solid #d9d9d9;
  border-radius: 8px;
}

.edit-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}

.edit-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.edit-content {
  padding: 20px;
}

.editor-wrapper {
  position: relative;
  margin-bottom: 16px;
}

.markdown-editor {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 14px;
  line-height: 1.6;
}

.markdown-editor :deep(textarea) {
  border-radius: 6px;
  border: 1px solid #d9d9d9;
  transition: border-color 0.3s, background-color 0.3s;
}

.markdown-editor :deep(textarea:focus) {
  border-color: #40a9ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
}

/* 拖拽上传样式 */
.editor-wrapper.is-dragging .markdown-editor :deep(textarea) {
  border-color: #1890ff;
  background-color: #f0f9ff;
}

.drag-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(24, 144, 255, 0.05);
  border: 2px dashed #1890ff;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 10;
}

.drag-overlay p {
  margin-top: 16px;
  font-size: 16px;
  color: #1890ff;
  font-weight: 500;
}

.editor-toolbar {
  margin-bottom: 20px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #e9ecef;
}

.preview-section {
  border-top: 1px solid #f0f0f0;
  padding-top: 20px;
}

.preview-section h4 {
  margin: 0 0 16px 0;
  font-size: 14px;
  font-weight: 600;
  color: #595959;
}

.preview-content {
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 16px;
  background: #fff;
  max-height: 400px;
  overflow-y: auto;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .edit-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .edit-actions {
    width: 100%;
    display: flex;
    justify-content: flex-end;
  }
  
  .editor-toolbar {
    padding: 8px;
  }

  .features-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}

/* 深色模式支持 */
@media (prefers-color-scheme: dark) {
  .features-markdown {
    background: #1f1f1f;
    color: #e8e8e8;
  }
  
  .features-header {
    background: #2a2a2a;
    border-bottom-color: #404040;
  }
  
  .edit-header {
    background: #2a2a2a;
    border-bottom-color: #404040;
  }
  
  .editor-toolbar {
    background: #2a2a2a;
    border-color: #404040;
  }
  
  .preview-content {
    background: #1f1f1f;
    border-color: #404040;
  }
}
</style>
