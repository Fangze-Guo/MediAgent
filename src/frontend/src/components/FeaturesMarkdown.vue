<template>
  <div class="features-markdown">
    <!-- 编辑模式 -->
    <div v-if="isEditing && canEdit" class="edit-mode">
      <div class="edit-header">
        <h3>编辑功能特点</h3>
        <div class="edit-actions">
          <a-button @click="cancelEdit" style="margin-right: 8px">取消</a-button>
          <a-button type="primary" @click="saveFeatures" :loading="saving">保存</a-button>
        </div>
      </div>
      
      <div class="edit-content">
        <a-textarea
          v-model:value="editContent"
          placeholder="请输入功能特点的Markdown内容..."
          :rows="20"
          class="markdown-editor"
        />
        
        <div class="editor-toolbar">
          <a-space>
            <a-button size="small" @click="insertMarkdown('**', '**')">
              <BoldOutlined /> 粗体
            </a-button>
            <a-button size="small" @click="insertMarkdown('*', '*')">
              <ItalicOutlined /> 斜体
            </a-button>
            <a-button size="small" @click="insertMarkdown('`', '`')">
              <CodeOutlined /> 代码
            </a-button>
            <a-button size="small" @click="insertMarkdown('- ', '')">
              <UnorderedListOutlined /> 列表
            </a-button>
            <a-button size="small" @click="insertMarkdown('## ', '')">
              <FontSizeOutlined /> 标题
            </a-button>
            <a-button size="small" @click="insertMarkdown('[链接文本](', ')')">
              <LinkOutlined /> 链接
            </a-button>
          </a-space>
        </div>
        
        <div class="preview-section">
          <h4>预览效果</h4>
          <div class="preview-content">
            <MarkdownRenderer :content="editContent" />
          </div>
        </div>
      </div>
    </div>
    
    <!-- 显示模式 -->
    <div v-else class="display-mode">
      <div class="features-header">
        <h3 class="features-title">
          <AppstoreOutlined />
          功能特点
        </h3>
        <a-button 
          v-if="canEdit" 
          type="text" 
          size="small" 
          @click="startEdit"
          class="edit-btn"
        >
          <EditOutlined />
          编辑
        </a-button>
      </div>
      
      <div class="features-content">
        <div v-if="!features || features.trim() === ''" class="empty-features">
          <a-empty 
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
            description="暂无功能特点介绍"
          >
            <a-button v-if="canEdit" type="primary" @click="startEdit">
              <PlusOutlined />
              添加功能特点
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
  LinkOutlined
} from '@ant-design/icons-vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import { useAuthStore } from '@/store/auth'
import { isAdmin } from '@/utils/permission'

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

const authStore = useAuthStore()

// 编辑状态
const isEditing = ref(false)
const editContent = ref('')
const saving = ref(false)

// 计算是否可以编辑
const canEdit = computed(() => {
  const user = authStore.currentUser
  const propsCanEdit = props.canEdit
  const userIsAdmin = isAdmin(user)
  
  return propsCanEdit && userIsAdmin
})

// 开始编辑
const startEdit = () => {
  editContent.value = props.features || getDefaultFeatures()
  isEditing.value = true
}

// 取消编辑
const cancelEdit = () => {
  isEditing.value = false
  editContent.value = ''
}

// 保存功能特点
const saveFeatures = async () => {
  if (!editContent.value.trim()) {
    message.warning('请输入功能特点内容')
    return
  }
  
  try {
    saving.value = true
    emit('save', props.appId, editContent.value.trim())
    emit('update:features', editContent.value.trim())
    isEditing.value = false
    message.success('功能特点保存成功')
  } catch (error) {
    console.error('保存功能特点失败:', error)
    message.error('保存失败，请重试')
  } finally {
    saving.value = false
  }
}

// 插入Markdown语法
const insertMarkdown = (before: string, after: string) => {
  const textarea = document.querySelector('.markdown-editor textarea') as HTMLTextAreaElement
  if (!textarea) return
  
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const selectedText = editContent.value.substring(start, end)
  
  const newText = before + selectedText + after
  editContent.value = editContent.value.substring(0, start) + newText + editContent.value.substring(end)
  
  nextTick(() => {
    textarea.focus()
    textarea.setSelectionRange(start + before.length, start + before.length + selectedText.length)
  })
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

.markdown-editor {
  margin-bottom: 16px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 14px;
  line-height: 1.6;
}

.markdown-editor :deep(textarea) {
  border-radius: 6px;
  border: 1px solid #d9d9d9;
  transition: border-color 0.3s;
}

.markdown-editor :deep(textarea:focus) {
  border-color: #40a9ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
}

.editor-toolbar {
  margin-bottom: 20px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #e9ecef;
}

.editor-toolbar .ant-btn {
  margin-right: 8px;
  margin-bottom: 4px;
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
  
  .editor-toolbar .ant-space {
    flex-wrap: wrap;
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
