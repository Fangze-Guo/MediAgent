<template>
  <a-modal
    :open="visible"
    title="模型配置管理"
    :width="900"
    :footer="null"
    @cancel="handleClose"
  >
    <div class="model-config-container">
      <!-- 当前模型状态 -->
      <div class="current-model-section">
        <h3 class="section-title">
          <RobotOutlined />
          当前模型
        </h3>
        <div class="current-model-card">
          <div class="model-info">
            <div class="model-name">{{ currentModel?.name }}</div>
            <div class="model-provider">{{ currentModel?.provider }}</div>
            <div class="model-description">{{ currentModel?.description }}</div>
            <div class="model-tags" v-if="currentModel?.tags">
              <a-tag 
                v-for="tag in currentModel.tags" 
                :key="tag"
                :color="getTagColor(tag)"
                size="small"
              >
                {{ tag }}
              </a-tag>
            </div>
          </div>
          <div class="model-status" :class="currentModel?.status">
            <div class="status-dot"></div>
            <span>{{ getStatusText(currentModel?.status) }}</span>
          </div>
        </div>
      </div>

      <!-- 模型列表 -->
      <div class="models-section">
        <div class="section-header">
          <h3 class="section-title">所有模型</h3>
          <div class="section-actions">
            <a-button type="primary" @click="showAddModal">
              <PlusOutlined />
              添加模型
            </a-button>
            <a-button @click="refreshModels">
              <ReloadOutlined />
              刷新
            </a-button>
          </div>
        </div>

        <div class="models-grid">
          <div 
            v-for="model in modelList" 
            :key="model.id"
            class="model-card"
            :class="{ 'active': model.id === currentModel?.id }"
            @click="selectModel(model)"
          >
            <div class="model-card-header">
              <div class="model-name">{{ model.name }}</div>
              <div class="model-provider">{{ model.provider }}</div>
            </div>
            <div class="model-description">{{ model.description }}</div>
            <div class="model-tags" v-if="model.tags">
              <a-tag 
                v-for="tag in model.tags" 
                :key="tag"
                :color="getTagColor(tag)"
                size="small"
              >
                {{ tag }}
              </a-tag>
            </div>
            <div class="model-card-footer">
              <div class="model-status" :class="model.status">
                <div class="status-dot"></div>
                <span>{{ getStatusText(model.status) }}</span>
              </div>
              <div class="model-actions">
                <a-button 
                  type="text" 
                  size="small"
                  @click.stop="editModel(model)"
                >
                  <EditOutlined />
                </a-button>
                <a-button 
                  type="text" 
                  size="small"
                  danger
                  @click.stop="deleteModel(model.id)"
                >
                  <DeleteOutlined />
                </a-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 模型配置编辑模态框 -->
      <a-modal
        :open="editModalVisible"
        :title="isEdit ? '编辑模型配置' : '添加模型配置'"
        @ok="handleSaveModel"
        @cancel="handleCloseEditModal"
        :confirm-loading="saving"
      >
        <a-form
          ref="editFormRef"
          :model="editFormData"
          :label-col="{ span: 6 }"
          :wrapper-col="{ span: 18 }"
        >
          <a-form-item label="模型ID" name="id" :rules="[{ required: true, message: '请输入模型ID' }]">
            <a-input v-model:value="editFormData.id" :disabled="isEdit" />
          </a-form-item>
          <a-form-item label="模型名称" name="name" :rules="[{ required: true, message: '请输入模型名称' }]">
            <a-input v-model:value="editFormData.name" />
          </a-form-item>
          <a-form-item label="描述">
            <a-textarea v-model:value="editFormData.description" :rows="2" />
          </a-form-item>
          <a-form-item label="提供商" name="provider" :rules="[{ required: true, message: '请选择提供商' }]">
            <a-select v-model:value="editFormData.provider">
              <a-select-option value="阿里云">阿里云</a-select-option>
              <a-select-option value="OpenAI">OpenAI</a-select-option>
              <a-select-option value="DeepSeek">DeepSeek</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="API基础URL" name="base_url" :rules="[{ required: true, message: '请输入API基础URL' }]">
            <a-input v-model:value="editFormData.base_url" />
          </a-form-item>
          <a-form-item label="API Key">
            <a-input-password v-model:value="editFormData.api_key" />
          </a-form-item>
          <a-form-item label="状态">
            <a-select v-model:value="editFormData.status">
              <a-select-option value="online">在线</a-select-option>
              <a-select-option value="maintenance">维护中</a-select-option>
              <a-select-option value="offline">离线</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="标签">
            <a-select
              v-model:value="editFormData.tags"
              mode="tags"
              placeholder="输入标签"
              style="width: 100%"
            >
              <a-select-option value="日常对话">日常对话</a-select-option>
              <a-select-option value="文本创作">文本创作</a-select-option>
              <a-select-option value="代码生成">代码生成</a-select-option>
              <a-select-option value="数学问题">数学问题</a-select-option>
              <a-select-option value="逻辑推理">逻辑推理</a-select-option>
              <a-select-option value="复杂分析">复杂分析</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>
      </a-modal>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { 
  RobotOutlined, 
  PlusOutlined, 
  ReloadOutlined, 
  EditOutlined, 
  DeleteOutlined 
} from '@ant-design/icons-vue'

// 类型定义
interface ModelInfo {
  id: string
  name: string
  description: string
  provider: string
  status: 'online' | 'maintenance' | 'offline'
  tags: string[]
  base_url?: string
  api_key?: string
  params?: Record<string, any>
}

interface Props {
  visible: boolean
}

interface Emits {
  'update:visible': [value: boolean]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 响应式数据
const modelList = ref<ModelInfo[]>([])
const currentModel = ref<ModelInfo | null>(null)
const editModalVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editFormRef = ref()

const editFormData = ref({
  id: '',
  name: '',
  description: '',
  provider: '阿里云',
  base_url: '',
  api_key: '',
  status: 'online',
  tags: [] as string[]
})

// 方法
const handleClose = () => {
  emit('update:visible', false)
}

const loadModels = async () => {
  try {
    const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
    
    // 获取模型列表
    const listResponse = await fetch(`${baseURL}/models/configs`)
    const listData = await listResponse.json()
    modelList.value = listData.data?.models ? Object.values(listData.data.models) : []
    
    // 获取当前模型
    const currentResponse = await fetch(`${baseURL}/models/current`)
    const currentData = await currentResponse.json()
    currentModel.value = currentData.data || []
    
  } catch (error) {
    console.error('加载模型列表失败:', error)
    message.error('加载模型列表失败')
  }
}

const selectModel = async (model: ModelInfo) => {
  try {
    const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
    
    const response = await fetch(`${baseURL}/models/current`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model_id: model.id
      })
    })
    
    if (response.ok) {
      const result = await response.json()
      if (result.code === 200) {
        currentModel.value = model
        message.success(`已切换到 ${model.name}`)
        // 触发全局事件，通知其他组件模型已切换
        window.dispatchEvent(new CustomEvent('model-changed', { 
          detail: { model } 
        }))
      } else {
        message.error(result.message || '切换模型失败')
      }
    } else {
      const errorData = await response.json()
      message.error(errorData.message || '切换模型失败')
    }
  } catch (error) {
    console.error('切换模型失败:', error)
    message.error('切换模型失败')
  }
}

const refreshModels = () => {
  loadModels()
}

const showAddModal = () => {
  isEdit.value = false
  editFormData.value = {
    id: '',
    name: '',
    description: '',
    provider: '阿里云',
    base_url: '',
    api_key: '',
    status: 'online',
    tags: []
  }
  editModalVisible.value = true
}

const editModel = (model: ModelInfo) => {
  isEdit.value = true
  editFormData.value = {
    id: model.id,
    name: model.name,
    description: model.description,
    provider: model.provider,
    base_url: model.base_url || '',
    api_key: model.api_key || '',
    status: model.status,
    tags: [...(model.tags || [])]
  }
  editModalVisible.value = true
}

const handleSaveModel = async () => {
  try {
    await editFormRef.value.validate()
    saving.value = true
    
    const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
    
    if (isEdit.value) {
      // 更新模型
      const response = await fetch(`${baseURL}/models/configs/${editFormData.value.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editFormData.value)
      })
      
      if (response.ok) {
        const result = await response.json()
        if (result.code === 200) {
          message.success('模型配置更新成功')
          // 触发全局事件，通知其他组件模型配置已更新
          window.dispatchEvent(new CustomEvent('model-config-updated', { 
            detail: { action: 'update', model: editFormData.value } 
          }))
        } else {
          throw new Error(result.message || '更新失败')
        }
      } else {
        const errorData = await response.json()
        throw new Error(errorData.message || '更新失败')
      }
    } else {
      // 添加模型
      const response = await fetch(`${baseURL}/models/configs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editFormData.value)
      })
      
      if (response.ok) {
        const result = await response.json()
        if (result.code === 200) {
          message.success('模型配置添加成功')
          // 触发全局事件，通知其他组件模型配置已添加
          window.dispatchEvent(new CustomEvent('model-config-updated', { 
            detail: { action: 'add', model: editFormData.value } 
          }))
        } else {
          throw new Error(result.message || '添加失败')
        }
      } else {
        const errorData = await response.json()
        throw new Error(errorData.message || '添加失败')
      }
    }
    
    editModalVisible.value = false
    loadModels()
    
  } catch (error) {
    console.error('保存失败:', error)
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleCloseEditModal = () => {
  editModalVisible.value = false
}

const deleteModel = (modelId: string) => {
  const model = modelList.value.find(m => m.id === modelId)
  
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除模型 "${model?.name}" 吗？`,
    onOk: async () => {
      try {
        const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
        
        const response = await fetch(`${baseURL}/models/configs/${modelId}`, {
          method: 'DELETE'
        })
        
        if (response.ok) {
          const result = await response.json()
          if (result.code === 200) {
            message.success('模型删除成功')
            // 触发全局事件，通知其他组件模型配置已删除
            window.dispatchEvent(new CustomEvent('model-config-updated', { 
              detail: { action: 'delete', modelId: modelId } 
            }))
            loadModels()
          } else {
            throw new Error(result.message || '删除失败')
          }
        } else {
          const errorData = await response.json()
          throw new Error(errorData.message || '删除失败')
        }
      } catch (error) {
        console.error('删除失败:', error)
        message.error('删除失败')
      }
    }
  })
}

const getTagColor = (tag: string) => {
  const colorMap: Record<string, string> = {
    '日常对话': 'blue',
    '文本创作': 'green',
    '代码生成': 'orange',
    '数学问题': 'red',
    '逻辑推理': 'cyan',
    '复杂分析': 'magenta',
  }
  return colorMap[tag] || 'default'
}

const getStatusText = (status?: string) => {
  const statusMap: Record<string, string> = {
    'online': '在线',
    'maintenance': '维护中',
    'offline': '离线'
  }
  return statusMap[status || 'offline']
}

onMounted(() => {
  if (props.visible) {
    loadModels()
  }
})

// 暴露方法给父组件
defineExpose({
  loadModels
})
</script>

<style scoped>
.model-config-container {
  padding: 16px 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

.section-title .anticon {
  color: #1890ff;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-actions {
  display: flex;
  gap: 8px;
}

.current-model-section {
  margin-bottom: 32px;
}

.current-model-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: white;
}

.model-name {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
}

.model-provider {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 8px;
}

.model-description {
  font-size: 13px;
  opacity: 0.8;
  margin-bottom: 12px;
}

.model-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

/* 标签选择框样式优化 */
:deep(.ant-select-selection-item) {
  border-radius: 12px !important;
  font-size: 12px !important;
  padding: 2px 8px !important;
  margin: 2px !important;
  transition: all 0.3s ease !important;
}

/* 选择框悬停效果 */
:deep(.ant-select-selection-item:hover) {
  transform: translateY(-1px) !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
}

.model-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online { background: #52c41a; }
.status-dot.maintenance { background: #faad14; }
.status-dot.offline { background: #ff4d4f; }

.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.model-card {
  border: 2px solid #f0f0f0;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  background: white;
}

.model-card:hover {
  border-color: #1890ff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.15);
}

.model-card.active {
  border-color: #1890ff;
  background: #f6ffed;
}

.model-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.model-card-header .model-name {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.model-card-header .model-provider {
  font-size: 12px;
  color: #666;
}

.model-card .model-description {
  color: #666;
  font-size: 12px;
  margin-bottom: 12px;
  line-height: 1.4;
}

.model-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.model-card-footer .model-status {
  font-size: 12px;
  color: #666;
}

.model-actions {
  display: flex;
  gap: 4px;
}

.model-card-footer .model-status .status-dot {
  margin-right: 4px;
}

/* 响应式 */
@media (max-width: 768px) {
  .models-grid {
    grid-template-columns: 1fr;
  }
  
  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .current-model-card {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .current-model-card .model-status {
    margin-top: 12px;
  }
}
</style>
