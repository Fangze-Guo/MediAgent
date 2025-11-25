<template>
  <div>
    <a-dropdown 
      :trigger="['click']" 
      placement="topLeft"
      v-model:open="dropdownVisible"
    >
      <div class="model-select-trigger" @click="handleTriggerClick" :class="{ 'loading': loading }">
        <div class="model-icon">
          <RobotOutlined v-if="!loading" />
          <a-spin v-else size="small" />
        </div>
        <div class="model-info">
          <span class="model-name">{{ selectedModelInfo.name }}</span>
          <span class="model-provider">{{ selectedModelInfo.provider }}</span>
          <span v-if="error" class="error-text">{{ error }}</span>
        </div>
        <DownOutlined class="dropdown-icon" :class="{ 'rotated': dropdownVisible }" />
      </div>
      
      <template #overlay>
        <div class="model-dropdown">
          <div class="dropdown-header">
            <span class="header-text">选择模型</span>
            <a-button type="link" size="small" @click="showModelConfig">
              <SettingOutlined />
            </a-button>
          </div>
          
          <div class="model-groups">
            <div 
              v-for="provider in modelProviders" 
              :key="provider.name"
              class="model-group"
            >
              <div class="provider-header">
                <span class="provider-name">{{ provider.name }}</span>
                <span class="provider-count">{{ provider.models.length }}个模型</span>
              </div>
              
              <div class="model-list">
                <div
                  v-for="model in provider.models"
                  :key="model.id"
                  class="model-option"
                  :class="{ 'selected': model.id === modelId }"
                  @click="selectModel(model)"
                >
                  <div class="model-option-content">
                    <div class="model-check">
                      <a-radio :checked="model.id === modelId" />
                    </div>
                    <div class="model-details">
                      <div class="model-name">{{ model.name }}</div>
                      <div class="model-description">{{ model.description }}</div>
                      <div class="model-tags">
                        <span 
                          v-for="tag in (model.tags || [])" 
                          :key="tag"
                          class="model-tag"
                          :class="getTagClass(tag)"
                        >
                          {{ tag }}
                        </span>
                      </div>
                    </div>
                    <div class="model-status" :class="model.status">
                      <div class="status-dot"></div>
                      <span class="status-text">{{ getStatusText(model.status || 'online') }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </a-dropdown>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { RobotOutlined, DownOutlined, SettingOutlined } from '@ant-design/icons-vue'
import { 
  getAvailableModels, 
  selectModel as selectUserModel,
  type ModelConfig 
} from '@/apis/modelConfig'

// 类型定义
interface ModelInfo extends ModelConfig {
  // 继承 ModelConfig 的所有属性
  tags?: string[]
  status?: 'online' | 'maintenance' | 'offline'
}

interface ModelProvider {
  name: string
  models: ModelInfo[]
}

// Props
interface Props {
  value: string
}

// Emits
interface Emits {
  'update:value': [value: string]
  'model-change': [model: ModelInfo]
}

const props = withDefaults(defineProps<Props>(), {
  value: 'qwen-plus'
})

const emit = defineEmits<Emits>()

// 响应式数据
const dropdownVisible = ref(false)
const modelId = ref(props.value)
const loading = ref(false)
const error = ref<string | null>(null)

// 模型数据
const modelProviders = ref<ModelProvider[]>([])

// 组件是否已卸载的标志
const isUnmounted = ref(false)

// 从API加载模型配置
const loadModelConfigs = async () => {
  try {
    loading.value = true
    error.value = null
    
    console.log('开始加载模型配置...')
    
    // 获取可用模型和当前选择
    const availableResponse = await getAvailableModels()
    
    // 检查组件是否已卸载
    if (isUnmounted.value) {
      return
    }
    
    console.log('API 响应:', { availableResponse })
    
    // 检查响应数据是否有效
    if (!availableResponse || !availableResponse.data || !availableResponse.data.models) {
      console.warn('API 返回的模型数据为空:', availableResponse)
      modelProviders.value = []
      return
    }
    
    // 将模型配置转换为按提供商分组的格式
    const providersMap = new Map<string, ModelInfo[]>()
    
    Object.values(availableResponse.data.models).forEach(modelData => {
      if (!modelData) return // 跳过空值
      
      const model = modelData as any
      
      // 转换为 ModelInfo 格式，使用新的数据结构
      const modelInfo: ModelInfo = {
        id: model.id,
        name: model.name,
        provider: model.provider,
        description: model.description,
        category: model.provider, // 使用provider作为category
        capabilities: model.tags || [],
        max_tokens: model.max_tokens,
        input_cost_per_1k: model.input_cost_per_1k,
        output_cost_per_1k: model.output_cost_per_1k,
        enabled: model.enabled,
        config: model.config,
        requirements: model.requirements,
        tags: model.tags || [],
        status: model.status || 'online' as const
      }
      
      const provider = model.provider
      if (!providersMap.has(provider)) {
        providersMap.set(provider, [])
      }
      providersMap.get(provider)!.push(modelInfo)
    })
    
    // 转换为 ModelProvider 数组
    modelProviders.value = Array.from(providersMap.entries()).map(([name, models]) => ({
      name,
      models
    }))
    
    console.log('加载的模型配置:', {
      current_model_id: availableResponse.data.current_model_id,
      providers_count: modelProviders.value.length,
      total_models: modelProviders.value.reduce((sum, p) => sum + p.models.length, 0)
    })
    
    // 再次检查组件是否已卸载
    if (isUnmounted.value) {
      return
    }
    
    // 设置当前模型ID
    if (availableResponse.data.current_model_id) {
      modelId.value = availableResponse.data.current_model_id
    } else if (modelProviders.value.length > 0 && modelProviders.value[0].models.length > 0) {
      // 如果没有设置当前模型，使用第一个可用模型
      modelId.value = modelProviders.value[0].models[0].id
    }
    
  } catch (err) {
    console.error('加载模型配置失败:', err)
    error.value = err instanceof Error ? err.message : '加载模型配置失败'
    
    // 如果API失败，清空模型列表，不显示默认配置
    modelProviders.value = []
  } finally {
    loading.value = false
  }
}


// 计算属性
const selectedModelInfo = computed(() => {
  const allModels = modelProviders.value.flatMap(p => p.models)
  const foundModel = allModels.find(m => m.id === modelId.value)
  
  // 如果找到匹配的模型，返回它；否则返回第一个可用模型，如果都没有则返回默认模型
  if (foundModel) {
    return foundModel
  }
  
  if (allModels.length > 0) {
    return allModels[0]
  }
  
  // 返回默认模型信息，避免 undefined 错误
  return {
    id: 'default',
    name: '加载中...',
    description: '正在加载模型配置',
    provider: '系统',
    status: 'online' as const,
    tags: [],
    base_url: '',
    api_key: '',
    params: {}
  }
})

// 方法
const handleTriggerClick = () => {
  dropdownVisible.value = !dropdownVisible.value
}

const selectModel = async (model: ModelInfo) => {
  try {
    loading.value = true
    error.value = null
    
    // 调用API设置当前模型
    await selectUserModel({
      current_model_id: model.id
    })
    
    modelId.value = model.id
    emit('update:value', model.id)
    emit('model-change', model)
    dropdownVisible.value = false
    error.value = null  // 清除错误信息
    
  } catch (err) {
    console.error('切换模型失败:', err)
    error.value = err instanceof Error ? err.message : '切换模型失败'
  } finally {
    loading.value = false
  }
}

const router = useRouter()

const showModelConfig = () => {
  // 跳转到设置页面的模型配置部分
  router.push('/settings')
}


const getTagClass = (tag: string) => {
  const classMap: Record<string, string> = {
    '日常对话': 'tag-blue',
    '文本创作': 'tag-green',
    '代码生成': 'tag-orange',
    '数学问题': 'tag-red',
    '逻辑推理': 'tag-cyan',
    '复杂分析': 'tag-magenta',
  }
  return classMap[tag] || 'tag-default'
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    'online': '在线',
    'maintenance': '维护中',
    'offline': '离线'
  }
  return statusMap[status] || '未知'
}

// 监听props变化
watch(() => props.value, (newValue) => {
  modelId.value = newValue
})

// 组件挂载时加载数据
onMounted(() => {
  loadModelConfigs()
  
  // 监听全局模型切换事件
  window.addEventListener('model-changed', handleGlobalModelChange)
  // 监听模型配置更新事件
  window.addEventListener('model-config-updated', handleModelConfigUpdated)
})

// 组件卸载时清理事件监听
onUnmounted(() => {
  isUnmounted.value = true
  window.removeEventListener('model-changed', handleGlobalModelChange)
  window.removeEventListener('model-config-updated', handleModelConfigUpdated)
})

// 处理全局模型切换事件
const handleGlobalModelChange = (event: Event) => {
  const customEvent = event as CustomEvent
  const { model } = customEvent.detail
  if (model && model.id !== modelId.value) {
    modelId.value = model.id
    emit('update:value', model.id)
    emit('model-change', model)
  }
}

// 处理模型配置更新事件
const handleModelConfigUpdated = (event: Event) => {
  const customEvent = event as CustomEvent
  const { action, modelId: deletedModelId } = customEvent.detail
  
  console.log('收到模型配置更新事件:', { action, deletedModelId })
  
  // 重新加载模型配置
  loadModelConfigs()
  
  // 如果是删除操作且删除的是当前选中的模型，需要切换到其他模型
  if (action === 'delete' && deletedModelId === modelId.value) {
    // 延迟执行，确保模型列表已更新
    setTimeout(() => {
      const allModels = modelProviders.value.flatMap(p => p.models)
      console.log('删除后可用模型数量:', allModels.length)
      if (allModels.length > 0) {
        const firstModel = allModels[0]
        selectModel(firstModel)
      }
    }, 100)
  }
}

// 暴露方法给父组件
defineExpose({
  selectModel,
  getSelectedModel: () => selectedModelInfo.value
})
</script>

<style scoped>
.model-select-trigger {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
  min-width: 180px;
}

.model-select-trigger:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.model-select-trigger.loading {
  opacity: 0.7;
  cursor: not-allowed;
}

.model-icon {
  margin-right: 8px;
}

.model-icon .anticon {
  color: white;
  font-size: 16px;
}

.model-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-right: 8px;
}

.model-name {
  color: white;
  font-weight: 600;
  font-size: 13px;
  line-height: 1.2;
}

.model-provider {
  color: rgba(255, 255, 255, 0.8);
  font-size: 11px;
  line-height: 1;
}

.error-text {
  color: #ff4d4f;
  font-size: 10px;
  line-height: 1;
  margin-top: 2px;
}

.dropdown-icon {
  color: white;
  font-size: 12px;
  transition: transform 0.3s ease;
}

.rotated {
  transform: rotate(180deg);
}

.model-dropdown {
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  overflow: hidden;
  min-width: 320px;
  max-width: 480px;
}

.dropdown-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.header-text {
  font-weight: 600;
  color: #343a40;
  font-size: 14px;
}

.model-groups {
  max-height: 400px;
  overflow-y: auto;
}

.model-group {
  border-bottom: 1px solid #f0f0f0;
}

.model-group:last-child {
  border-bottom: none;
}

.provider-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px 8px;
  background: #fafbfc;
}

.provider-name {
  font-weight: 500;
  color: #495057;
  font-size: 13px;
}

.provider-count {
  color: #6c757d;
  font-size: 11px;
}

.model-list {
  padding: 0 20px 16px;
}

.model-option {
  margin-bottom: 8px;
  border-radius: 8px;
  transition: all 0.2s ease;
  cursor: pointer;
}

.model-option:hover {
  background: #f8f9ff;
}

.model-option.selected {
  background: #e6f3ff;
  border: 1px solid #1890ff;
}

.model-option-content {
  display: flex;
  align-items: center;
  padding: 12px;
}

.model-check {
  margin-right: 12px;
}

.model-details {
  flex: 1;
  margin-right: 12px;
}

.model-details .model-name {
  color: #343a40;
  font-weight: 500;
  font-size: 14px;
  margin-bottom: 2px;
}

.model-description {
  color: #6c757d;
  font-size: 12px;
  margin-bottom: 6px;
}

.model-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.model-tag {
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tag-blue { background: #e3f2fd; color: #1976d2; }
.tag-green { background: #e8f5e9; color: #388e3c; }
.tag-purple { background: #f3e5f5; color: #7b1fa2; }
.tag-orange { background: #fff3e0; color: #f57c00; }
.tag-red { background: #ffebee; color: #c62828; }
.tag-cyan { background: #e0f7fa; color: #00acc1; }
.tag-magenta { background: #fce4ec; color: #c2185b; }
.tag-default { background: #f5f5f5; color: #666; }

.model-status {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online { background: #52c41a; }
.status-dot.maintenance { background: #faad14; }
.status-dot.offline { background: #ff4d4f; }

.status-text {
  font-size: 11px;
  color: #6c757d;
}

/* 滚动条样式 */
.model-groups::-webkit-scrollbar {
  width: 6px;
}

.model-groups::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.model-groups::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.model-groups::-webkit-scrollbar-thumb:hover {
  background: #a1a1a1;
}

/* 响应式 */
@media (max-width: 768px) {
  .model-dropdown {
    min-width: 280px;
  }
  
  .model-select-trigger {
    min-width: 150px;
  }
  
  .model-name {
    font-size: 12px;
  }
  
  .model-provider {
    font-size: 10px;
  }
}
</style>
