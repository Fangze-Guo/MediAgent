<template>
  <div class="user-model-settings">
    <a-card :title="$t('model.settings.title')" class="settings-card">
      <template #extra>
        <a-space>
          <a-button type="primary" @click="showAddModal = true">
            <template #icon>
              <PlusOutlined />
            </template>
            {{ $t('model.settings.addModels') }}
          </a-button>
          <a-button type="link" @click="refreshModels" :loading="loading">
            <template #icon>
              <ReloadOutlined />
            </template>
            {{ $t('common.refresh') }}
          </a-button>
        </a-space>
      </template>

      <!-- 已配置的模型列表 -->
      <div class="configured-models-section">
        <div v-if="userModels.length === 0" class="empty-state">
          <a-empty :description="$t('common.noData')">
            <a-button type="primary" @click="showAddModal = true">
              {{ $t('model.settings.addModels') }}
            </a-button>
          </a-empty>
        </div>
        
        <div v-else class="models-grid">
          <div 
            v-for="model in userModels" 
            :key="model.id"
            class="model-card"
            :class="{ 'current': currentModelId === model.id }"
          >
            <div class="model-header">
              <a-avatar 
                :src="getAvatarUrl(providers[model.provider]?.avatar)"
                :style="!providers[model.provider]?.avatar ? { backgroundColor: getProviderColor(model.provider) } : {}" 
                size="large"
              >
                <template v-if="!providers[model.provider]?.avatar">
                  {{ model.provider.charAt(0) }}
                </template>
              </a-avatar>
              <div class="model-info">
                <h4>{{ model.name }}</h4>
                <p>{{ model.description }}</p>
                <div class="model-meta">
                  <a-tag color="default">{{ model.provider }}</a-tag>
                  <a-tag :color="(model as any).status === 'online' ? 'success' : 'error'">
                    {{ (model as any).status === 'online' ? '在线' : '离线' }}
                  </a-tag>
                  <a-tag v-if="currentModelId === model.id" color="blue">当前使用</a-tag>
                </div>
              </div>
            </div>
            
            <!-- 模型标签 -->
            <div class="model-features">
              <a-tag 
                v-for="tag in (model as any).tags" 
                :key="tag" 
                size="small"
                class="model-tag"
                :class="getTagClass(tag)"
              >
                {{ tag }}
              </a-tag>
            </div>
            
            <!-- 操作按钮 -->
            <div class="model-actions">
              <a-button 
                v-if="currentModelId !== model.id"
                type="primary" 
                size="small"
                @click="setCurrentModel(model.id)"
              >
                {{ $t('model.settings.switchTo') }}
              </a-button>
              <a-button 
                v-else
                type="primary" 
                size="small"
                disabled
              >
                {{ $t('model.settings.currentUsing') }}
              </a-button>
              <a-button 
                size="small"
                danger
                @click="removeModel(model.id)"
              >
                {{ $t('model.settings.remove') }}
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </a-card>

    <!-- 添加模型模态框 -->
    <a-modal
      v-model:open="showAddModal"
      :title="$t('model.settings.addModels')"
      :width="1000"
      :footer="null"
    >
      <div class="add-model-content">
        <!-- 搜索和筛选 -->
        <div class="model-filters">
          <a-row :gutter="16">
            <a-col :span="8">
              <a-input-search
                v-model:value="searchText"
                :placeholder="$t('model.settings.searchPlaceholder')"
                allow-clear
              />
            </a-col>
            <a-col :span="8">
              <a-select
                v-model:value="filterCategory"
                :placeholder="$t('model.settings.filterByCategory')"
                allow-clear
                style="width: 100%"
              >
                <a-select-option value="">{{ $t('model.settings.allCategories') }}</a-select-option>
                <a-select-option 
                  v-for="(category, key) in categories" 
                  :key="key" 
                  :value="key"
                >
                  {{ category.name }}
                </a-select-option>
              </a-select>
            </a-col>
            <a-col :span="8">
              <a-select
                v-model:value="filterProvider"
                :placeholder="$t('model.settings.filterByProvider')"
                allow-clear
                style="width: 100%"
              >
                <a-select-option value="">{{ $t('model.settings.allProviders') }}</a-select-option>
                <a-select-option 
                  v-for="(provider, key) in providers" 
                  :key="key" 
                  :value="key"
                >
                  {{ provider.name }}
                </a-select-option>
              </a-select>
            </a-col>
          </a-row>
        </div>

        <!-- 可添加的模型列表 -->
        <div class="available-models-grid">
          <div 
            v-for="model in filteredAvailableModels" 
            :key="model.id"
            class="model-card selectable"
            :class="{ 
              'selected': selectedModels.includes(model.id),
              'disabled': isModelAlreadyAdded(model.id)
            }"
            @click="toggleModelSelection(model.id)"
          >
            <div class="model-header">
              <a-avatar 
                :src="getAvatarUrl(providers[model.provider]?.avatar)"
                :style="!providers[model.provider]?.avatar ? { backgroundColor: getProviderColor(model.provider) } : {}" 
                size="large"
              >
                <template v-if="!providers[model.provider]?.avatar">
                  {{ model.provider.charAt(0) }}
                </template>
              </a-avatar>
              <div class="model-info">
                <h4>{{ model.name }}</h4>
                <p>{{ model.description }}</p>
                <div class="model-meta">
                  <a-tag :color="getCategoryColor(model.category)">
                    {{ model.category }}
                  </a-tag>
                  <a-tag color="default">{{ model.provider }}</a-tag>
                  <a-tag v-if="model.enabled" color="success">可用</a-tag>
                  <a-tag v-else color="error">不可用</a-tag>
                </div>
                
                <!-- 提供商链接 -->
                <div v-if="providers[model.provider]" class="provider-links">
                  <a 
                    v-if="providers[model.provider].website" 
                    :href="providers[model.provider].website" 
                    target="_blank"
                    class="provider-link"
                  >
                    🌐 官网
                  </a>
                  <a 
                    v-if="providers[model.provider].api_docs" 
                    :href="providers[model.provider].api_docs" 
                    target="_blank"
                    class="provider-link"
                  >
                    📚 API文档
                  </a>
                </div>
              </div>
              
              <!-- 选择状态 -->
              <div class="selection-indicator">
                <a-checkbox 
                  v-if="!isModelAlreadyAdded(model.id)"
                  :checked="selectedModels.includes(model.id)"
                />
                <a-tag v-else color="blue" size="small">已添加</a-tag>
              </div>
            </div>
            
            <!-- 模型特性 -->
            <div class="model-features">
              <span 
                v-for="capability in model.capabilities" 
                :key="capability" 
                class="model-tag"
                :class="getTagClass(capability)"
              >
                {{ capability }}
              </span>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="modal-actions">
          <a-space>
            <a-button @click="showAddModal = false">{{ $t('model.settings.cancel') }}</a-button>
            <a-button 
              type="primary" 
              :disabled="selectedModels.length === 0"
              :loading="adding"
              @click="addSelectedModels"
            >
              {{ $t('model.settings.addSelected') }} ({{ selectedModels.length }})
            </a-button>
          </a-space>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import {
  ReloadOutlined,
  PlusOutlined
} from '@ant-design/icons-vue'
import {
  getAvailableModels,
  getCurrentSelection,
  getAllModels,
  getProviders,
  getCategories,
  selectModel as selectUserModel,
  removeUserModel,
  checkModelStatus,
  type ModelConfig,
  type ModelCategory,
  type ModelProvider
} from '@/apis/modelConfig'
import { getCategoryColor, getProviderColor } from '@/utils/colors'

// ==================== 响应式数据 ====================
const loading = ref(false)
const adding = ref(false)
const isUnmounted = ref(false)
const showAddModal = ref(false)

// API基础URL
const API_BASE = 'http://localhost:8000'

// 用户已配置的模型
const userModels = ref<ModelConfig[]>([])
const currentModelId = ref('')

// 管理员预设的可用模型
const availableModels = ref<Record<string, ModelConfig>>({})
const categories = ref<Record<string, ModelCategory>>({})
const providers = ref<Record<string, ModelProvider>>({})

// 模态框中的选择状态
const selectedModels = ref<string[]>([])

// 筛选条件
const searchText = ref('')
const filterCategory = ref('')
const filterProvider = ref('')

// ==================== 辅助函数 ====================
/**
 * 获取完整的头像URL
 */
const getAvatarUrl = (avatar?: string) => {
  if (!avatar) return undefined
  
  // 如果已经是完整URL，直接返回
  if (avatar.startsWith('http://') || avatar.startsWith('https://')) {
    return avatar
  }
  
  // 如果是相对路径，拼接API基础URL
  if (avatar.startsWith('/')) {
    return `${API_BASE}${avatar}`
  }
  
  return avatar
}

/**
 * 获取标签样式类名
 */
const getTagClass = (tag: string) => {
  const { t } = useI18n()
  const classMap: Record<string, string> = {
    [t('model.capabilities.dailyChat')]: 'tag-blue',
    [t('model.capabilities.textCreation')]: 'tag-green', 
    [t('model.capabilities.codeGeneration')]: 'tag-orange',
    [t('model.capabilities.mathProblems')]: 'tag-red',
    [t('model.capabilities.logicalReasoning')]: 'tag-cyan',
    [t('model.capabilities.complexAnalysis')]: 'tag-magenta',
    // 兼容原有的中文标签
    '日常对话': 'tag-blue',
    '文本创作': 'tag-green',
    '代码生成': 'tag-orange',
    '数学问题': 'tag-red',
    '逻辑推理': 'tag-cyan',
    '复杂分析': 'tag-magenta',
  }
  return classMap[tag] || 'tag-default'
}

// ==================== 计算属性 ====================
const filteredAvailableModels = computed(() => {
  let models = Object.values(availableModels.value)

  // 搜索过滤
  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    models = models.filter(model => 
      model.name.toLowerCase().includes(search) ||
      model.description.toLowerCase().includes(search) ||
      model.provider.toLowerCase().includes(search)
    )
  }

  // 分类过滤
  if (filterCategory.value) {
    models = models.filter(model => model.category === filterCategory.value)
  }

  // 提供商过滤
  if (filterProvider.value) {
    models = models.filter(model => model.provider === filterProvider.value)
  }

  return models
})

// ==================== 方法 ====================

/**
 * 加载用户已配置的模型
 */
const loadUserModels = async () => {
  try {
    loading.value = true
    
    const [userResponse, currentResponse] = await Promise.all([
      getAvailableModels(),
      getCurrentSelection()
    ])
    
    // 检查组件是否已卸载
    if (isUnmounted.value) {
      return
    }
    
    // 处理用户配置的模型
    if (userResponse.data && userResponse.data.models) {
      userModels.value = Object.values(userResponse.data.models)
      currentModelId.value = userResponse.data.current_model_id || ''
    } else {
      userModels.value = []
      currentModelId.value = ''
    }
    
    // 检查当前模型状态并显示提示
    if (currentResponse.data && currentResponse.data.status_message) {
      message.warning(currentResponse.data.status_message, 5) // 显示5秒
    }
    
  } catch (error) {
    message.error('加载用户模型失败')
    console.error('Load user models error:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 加载管理员预设的可用模型
 */
const loadAvailableModels = async () => {
  try {
    const [allModelsResponse, providersResponse, categoriesResponse] = await Promise.all([
      getAllModels(),
      getProviders(),
      getCategories()
    ])
    
    // 检查组件是否已卸载
    if (isUnmounted.value) {
      return
    }
    
    // 处理管理员API数据结构
    if (allModelsResponse.data && allModelsResponse.data.models) {
      availableModels.value = allModelsResponse.data.models
    } else {
      availableModels.value = {}
    }
    
    // 使用真实的providers配置
    if (providersResponse.data) {
      providers.value = providersResponse.data as unknown as Record<string, ModelProvider>
    } else {
      providers.value = {}
    }
    
    // 使用真实的categories配置
    if (categoriesResponse.data) {
      categories.value = categoriesResponse.data as unknown as Record<string, ModelCategory>
    } else {
      categories.value = {}
    }
    
  } catch (error) {
    message.error('加载可用模型失败')
    console.error('Load available models error:', error)
  }
}

/**
 * 刷新模型列表
 */
const refreshModels = async () => {
  await Promise.all([
    loadUserModels(),
    loadAvailableModels()
  ])
}

/**
 * 设置当前使用的模型
 */
const setCurrentModel = async (modelId: string) => {
  try {
    const response = await selectUserModel({
      current_model_id: modelId
    })
    
    // 检查响应是否成功
    if (response.success) {
      currentModelId.value = modelId
      message.success('模型切换成功')
      
      // 触发全局事件通知其他组件
      window.dispatchEvent(new CustomEvent('model-changed', {
        detail: { modelId }
      }))
    } else {
      // 显示后端返回的友好错误信息
      message.error(response.message || '模型切换失败')
    }
    
  } catch (error: any) {
    console.error('Set current model error:', error)
    
    // 尝试从错误响应中获取友好的错误信息
    const errorMessage = error?.response?.data?.message || 
                        error?.response?.data?.detail || 
                        error?.message || 
                        '模型切换失败'
    
    message.error(errorMessage)
  }
}

/**
 * 移除模型
 */
const removeModel = async (modelId: string) => {
  // 找到要删除的模型信息
  const model = userModels.value.find(m => m.id === modelId)
  if (!model) {
    message.error('模型不存在')
    return
  }

  // 检查是否是当前使用的模型
  if (currentModelId.value === modelId) {
    message.error('无法移除当前正在使用的模型，请先切换到其他模型')
    return
  }

  Modal.confirm({
    title: '确认移除',
    content: `确定要移除模型 "${model.name}" 吗？此操作不可撤销。`,
    okText: '移除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await removeUserModel(modelId)
        message.success('模型移除成功')
        await loadUserModels()
      } catch (error) {
        message.error('移除模型失败')
        console.error('Remove model error:', error)
      }
    }
  })
}

/**
 * 检查模型是否已添加
 */
const isModelAlreadyAdded = (modelId: string) => {
  return userModels.value.some(model => model.id === modelId)
}

/**
 * 切换模型选择状态
 */
const toggleModelSelection = (modelId: string) => {
  if (isModelAlreadyAdded(modelId)) {
    return // 已添加的模型不能选择
  }
  
  const index = selectedModels.value.indexOf(modelId)
  if (index > -1) {
    selectedModels.value.splice(index, 1)
  } else {
    selectedModels.value.push(modelId)
  }
}

/**
 * 添加选中的模型
 */
const addSelectedModels = async () => {
  if (selectedModels.value.length === 0) {
    message.warning('请先选择要添加的模型')
    return
  }

  try {
    adding.value = true
    
    // 逐个添加选中的模型
    for (const modelId of selectedModels.value) {
      await selectUserModel({
        current_model_id: modelId
      })
    }
    
    message.success(`成功添加 ${selectedModels.value.length} 个模型`)
    
    // 清空选择并关闭模态框
    selectedModels.value = []
    showAddModal.value = false
    
    // 刷新用户模型列表
    await loadUserModels()
    
  } catch (error) {
    console.error('Add models error:', error)
    message.error('添加模型失败')
  } finally {
    adding.value = false
  }
}


// ==================== 生命周期 ====================
onMounted(() => {
  refreshModels()
})

onUnmounted(() => {
  isUnmounted.value = true
})
</script>

<style scoped>
.user-model-settings {
  max-width: 1200px;
}

.settings-card {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
}

.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.model-card {
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  padding: 16px;
  transition: all 0.3s;
}

.model-card:hover {
  border-color: #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.2);
}

.model-card.current {
  border-color: #1890ff;
  background-color: #f0f8ff;
}

.model-card.selectable {
  cursor: pointer;
}

.model-card.selected {
  border-color: #52c41a;
  background-color: #f6ffed;
}

.model-card.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.model-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
  position: relative;
}

.model-info {
  flex: 1;
}

.model-info h4 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
}

.model-info p {
  margin: 0 0 8px 0;
  color: #666;
  font-size: 14px;
}

.model-meta {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.model-features {
  margin-bottom: 12px;
}

.model-features .ant-tag {
  margin-bottom: 4px;
}

.model-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.selection-indicator {
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  align-items: center;
}

/* 模态框样式 */
.add-model-content {
  max-height: 70vh;
  overflow-y: auto;
}

.model-filters {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.available-models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
  max-height: 400px;
  overflow-y: auto;
}

.modal-actions {
  text-align: right;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

/* 提供商链接样式 */
.provider-links {
  margin-top: 8px;
  display: flex;
  gap: 12px;
}

/* 标签样式 - 与 ModelSelector 保持一致 */
.model-tag {
  padding: 5px 5px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-right: 20px;
  margin-bottom: 4px;
  display: inline-block;
}

.tag-blue { background: #e3f2fd; color: #1976d2; }
.tag-green { background: #e8f5e9; color: #388e3c; }
.tag-orange { background: #fff3e0; color: #f57c00; }
.tag-red { background: #ffebee; color: #c62828; }
.tag-cyan { background: #e0f7fa; color: #00acc1; }
.tag-magenta { background: #fce4ec; color: #c2185b; }
.tag-default { background: #f5f5f5; color: #666; }

.provider-link {
  font-size: 12px;
  color: #1890ff;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 4px;
}

.provider-link:hover {
  color: #40a9ff;
  text-decoration: underline;
}
</style>
