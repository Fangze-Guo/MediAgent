<template>
  <div>
    <a-dropdown 
      :trigger="['click']" 
      placement="topLeft"
      v-model:open="dropdownVisible"
    >
      <div class="model-select-trigger" @click="handleTriggerClick" :class="{ 'loading': loading }">
        <a-spin v-if="loading" size="small" class="trigger-spin" />
        <span class="trigger-name">{{ selectedModelInfo.name }}</span>
        <DownOutlined class="trigger-chevron" :class="{ 'rotated': dropdownVisible }" />
      </div>
      
      <template #overlay>
        <div class="model-dropdown">
          <div class="model-groups">
            <div
              v-for="provider in modelProviders"
              :key="provider.name"
              class="model-group"
            >
              <div class="provider-label">{{ provider.name }}</div>
              <div
                v-for="model in provider.models"
                :key="model.id"
                class="model-option"
                :class="{ 'selected': model.id === modelId }"
                @click="selectModel(model)"
              >
                <span class="model-name">{{ model.name }}</span>
                <CheckOutlined v-if="model.id === modelId" class="model-check-icon" />
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
import { DownOutlined, CheckOutlined } from '@ant-design/icons-vue'
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
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
  user-select: none;
}

.model-select-trigger:hover {
  background: var(--hover-bg, rgba(255,255,255,0.08));
}

.model-select-trigger.loading {
  opacity: 0.5;
  cursor: not-allowed;
}

.trigger-spin {
  font-size: 12px;
}

.trigger-name {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
}

.trigger-chevron {
  color: var(--text-tertiary, rgba(255,255,255,0.35));
  font-size: 10px;
  transition: transform 0.2s ease;
}

.trigger-chevron.rotated {
  transform: rotate(180deg);
}

.model-dropdown {
  background: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  overflow: hidden;
  min-width: 200px;
  max-width: 300px;
}

.model-groups {
  padding: 8px 0;
  max-height: 360px;
  overflow-y: auto;
}

.model-group + .model-group {
  margin-top: 4px;
  border-top: 1px solid var(--border-color);
  padding-top: 4px;
}

.provider-label {
  padding: 4px 14px 2px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 14px;
  cursor: pointer;
  transition: background 0.12s;
}

.model-option:hover {
  background: var(--hover-bg, rgba(255,255,255,0.06));
}

.model-option.selected .model-name {
  color: var(--link-color, #4da6ff);
  font-weight: 500;
}

.model-name {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.4;
}

.model-check-icon {
  font-size: 11px;
  color: var(--link-color, #4da6ff);
  flex-shrink: 0;
}

/* 滚动条样式 */
.model-groups::-webkit-scrollbar {
  width: 6px;
}

.model-groups::-webkit-scrollbar-track {
  background: var(--bg-secondary);
}

.model-groups::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.model-groups::-webkit-scrollbar-thumb:hover {
  background: var(--text-tertiary);
}

/* 响应式 */
@media (max-width: 768px) {
  .model-dropdown {
    min-width: 280px;
  }

  .model-name {
    font-size: 12px;
  }
}
</style>
