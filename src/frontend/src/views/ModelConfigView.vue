<template>
  <div class="model-config-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1>
            <SettingOutlined class="title-icon" />
            模型配置管理
          </h1>
          <p class="subtitle">管理系统中的AI模型配置，控制用户可用的模型选项</p>
        </div>
        <div class="action-section">
          <a-button type="primary" @click="showCreateModal" size="large">
            <template #icon>
              <PlusOutlined />
            </template>
            添加模型
          </a-button>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-cards">
      <a-row :gutter="24">
        <a-col :span="6">
          <a-card class="stat-card">
            <a-statistic
              title="总模型数"
              :value="totalModels"
              :value-style="{ color: '#1890ff' }"
            >
              <template #prefix>
                <RobotOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card class="stat-card">
            <a-statistic
              title="启用模型"
              :value="enabledModels"
              :value-style="{ color: '#52c41a' }"
            >
              <template #prefix>
                <CheckCircleOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card class="stat-card">
            <a-statistic
              title="模型提供商"
              :value="totalProviders"
              :value-style="{ color: '#722ed1' }"
            >
              <template #prefix>
                <CloudOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card class="stat-card">
            <a-statistic
              title="模型分类"
              :value="totalCategories"
              :value-style="{ color: '#fa8c16' }"
            >
              <template #prefix>
                <AppstoreOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 筛选和搜索 -->
    <div class="filter-section">
      <a-card>
        <a-row :gutter="16" align="middle">
          <a-col :span="8">
            <a-input-search
              v-model:value="searchText"
              placeholder="搜索模型名称或描述"
              @search="handleSearch"
              allow-clear
            />
          </a-col>
          <a-col :span="4">
            <a-select
              v-model:value="filterCategory"
              placeholder="选择分类"
              allow-clear
              style="width: 100%"
            >
              <a-select-option value="">全部分类</a-select-option>
              <a-select-option 
                v-for="(category, key) in categories" 
                :key="key" 
                :value="key"
              >
                {{ category.name }}
              </a-select-option>
            </a-select>
          </a-col>
          <a-col :span="4">
            <a-select
              v-model:value="filterProvider"
              placeholder="选择提供商"
              allow-clear
              style="width: 100%"
            >
              <a-select-option value="">全部提供商</a-select-option>
              <a-select-option 
                v-for="(provider, key) in providers" 
                :key="key" 
                :value="key"
              >
                {{ provider.name }}
              </a-select-option>
            </a-select>
          </a-col>
          <a-col :span="4">
            <a-select
              v-model:value="filterStatus"
              placeholder="选择状态"
              allow-clear
              style="width: 100%"
            >
              <a-select-option value="">全部状态</a-select-option>
              <a-select-option value="enabled">已启用</a-select-option>
              <a-select-option value="disabled">已禁用</a-select-option>
            </a-select>
          </a-col>
          <a-col :span="4">
            <a-button @click="resetFilters" style="width: 100%">
              重置筛选
            </a-button>
          </a-col>
        </a-row>
      </a-card>
    </div>

    <!-- 模型列表 -->
    <div class="models-section">
      <a-card title="模型列表">
        <template #extra>
          <a-radio-group v-model:value="viewMode" button-style="solid">
            <a-radio-button value="grid">
              <AppstoreOutlined />
              网格视图
            </a-radio-button>
            <a-radio-button value="table">
              <UnorderedListOutlined />
              表格视图
            </a-radio-button>
          </a-radio-group>
        </template>

        <!-- 网格视图 -->
        <div v-if="viewMode === 'grid'" class="models-grid">
          <a-row :gutter="[24, 24]">
            <a-col 
              v-for="model in filteredModels" 
              :key="model.id" 
              :xs="24" 
              :sm="12" 
              :md="8" 
              :lg="6"
            >
              <ModelCard
                :model="model"
                :category="categories[model.category]"
                :provider="providers[model.provider]"
                @edit="handleEditModel"
                @delete="handleDeleteModel"
                @toggle="handleToggleModel"
              />
            </a-col>
          </a-row>
        </div>

        <!-- 表格视图 -->
        <a-table
          v-else
          :columns="tableColumns"
          :data-source="filteredModels"
          :pagination="{ pageSize: 10, showSizeChanger: true }"
          :loading="loading"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <div class="model-name-cell">
                <a-avatar 
                  :src="providers[record.provider]?.avatar"
                  :style="!providers[record.provider]?.avatar ? { backgroundColor: getProviderColor(record.provider) } : {}" 
                  size="small"
                >
                  <template v-if="!providers[record.provider]?.avatar">
                    {{ record.provider.charAt(0) }}
                  </template>
                </a-avatar>
                <div class="model-info">
                  <div class="model-title">{{ record.name }}</div>
                  <div class="model-id">{{ record.id }}</div>
                </div>
              </div>
            </template>
            
            <template v-else-if="column.key === 'category'">
              <a-tag :color="getCategoryColor(record.category)">
                {{ categories[record.category]?.name || record.category }}
              </a-tag>
            </template>
            
            <template v-else-if="column.dataIndex === 'provider'">
              <div class="provider-cell">
                <div>{{ record.provider }}</div>
                <div v-if="providers[record.provider]" class="provider-links">
                  <a 
                    v-if="providers[record.provider].website" 
                    :href="providers[record.provider].website" 
                    target="_blank"
                    class="provider-link"
                  >
                    🌐
                  </a>
                  <a 
                    v-if="providers[record.provider].api_docs" 
                    :href="providers[record.provider].api_docs" 
                    target="_blank"
                    class="provider-link"
                  >
                    📚
                  </a>
                </div>
              </div>
            </template>
            
            <template v-else-if="column.key === 'capabilities'">
              <a-tag 
                v-for="capability in record.capabilities.slice(0, 2)" 
                :key="capability"
                size="small"
              >
                {{ capability }}
              </a-tag>
              <a-tag v-if="record.capabilities.length > 2" size="small">
                +{{ record.capabilities.length - 2 }}
              </a-tag>
            </template>
            
            <template v-else-if="column.key === 'cost'">
              <div class="cost-info">
                <div>输入: ${{ record.input_cost_per_1k }}/1K</div>
                <div>输出: ${{ record.output_cost_per_1k }}/1K</div>
              </div>
            </template>
            
            <template v-else-if="column.key === 'status'">
              <a-switch
                :checked="record.enabled"
                @change="() => handleToggleModel(record)"
                :loading="toggleLoading[record.id]"
              />
            </template>
            
            <template v-else-if="column.key === 'actions'">
              <a-space>
                <a-button 
                  type="text" 
                  size="small" 
                  @click="handleEditModel(record)"
                >
                  编辑
                </a-button>
                <a-button 
                  type="text" 
                  danger 
                  size="small" 
                  @click="handleDeleteModel(record)"
                >
                  删除
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- 创建/编辑模型弹窗 -->
    <ModelFormModal
      v-model:open="formModalVisible"
      :model="editingModel"
      :categories="categories"
      :providers="providers"
      @submit="handleFormSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  SettingOutlined,
  PlusOutlined,
  RobotOutlined,
  CheckCircleOutlined,
  CloudOutlined,
  AppstoreOutlined,
  UnorderedListOutlined
} from '@ant-design/icons-vue'
import type { ModelConfig, ModelCategory, ModelProvider } from '@/apis/modelConfig'
import {
  getAllModels, 
  createModel, 
  updateModel, 
  deleteModel, 
  toggleModelStatus,
  getCategories,
  getProviders
} from '@/apis/modelConfig'
import ModelCard from '@/components/model/ModelCard.vue'
import ModelFormModal from '@/components/model/ModelFormModal.vue'
import { getCategoryColor, getProviderColor } from '@/utils/colors'

// ==================== 响应式数据 ====================
const loading = ref(false)
const models = ref<ModelConfig[]>([])
const categories = ref<Record<string, ModelCategory>>({})
const providers = ref<Record<string, ModelProvider>>({})

// 筛选和搜索
const searchText = ref('')
const filterCategory = ref('')
const filterProvider = ref('')
const filterStatus = ref('')

// 视图模式
const viewMode = ref<'grid' | 'table'>('grid')

// 弹窗状态
const formModalVisible = ref(false)
const editingModel = ref<ModelConfig | null>(null)

// 切换状态加载
const toggleLoading = reactive<Record<string, boolean>>({})

// ==================== 计算属性 ====================
const totalModels = computed(() => models.value.length)
const enabledModels = computed(() => models.value.filter(m => m.enabled).length)
const totalProviders = computed(() => Object.keys(providers.value).length)
const totalCategories = computed(() => Object.keys(categories.value).length)

const filteredModels = computed(() => {
  let result = models.value

  // 搜索过滤
  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    result = result.filter(model => 
      model.name.toLowerCase().includes(search) ||
      model.description.toLowerCase().includes(search) ||
      model.id.toLowerCase().includes(search)
    )
  }

  // 分类过滤
  if (filterCategory.value) {
    result = result.filter(model => model.category === filterCategory.value)
  }

  // 提供商过滤
  if (filterProvider.value) {
    result = result.filter(model => model.provider === filterProvider.value)
  }

  // 状态过滤
  if (filterStatus.value) {
    const enabled = filterStatus.value === 'enabled'
    result = result.filter(model => model.enabled === enabled)
  }

  return result
})

// 表格列配置
const tableColumns = [
  {
    title: '模型名称',
    key: 'name',
    width: 200,
    fixed: 'left'
  },
  {
    title: '分类',
    key: 'category',
    width: 100
  },
  {
    title: '提供商',
    dataIndex: 'provider',
    width: 100
  },
  {
    title: '能力',
    key: 'capabilities',
    width: 150
  },
  {
    title: '最大Token',
    dataIndex: 'max_tokens',
    width: 100
  },
  {
    title: '成本',
    key: 'cost',
    width: 150
  },
  {
    title: '状态',
    key: 'status',
    width: 80
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    fixed: 'right'
  }
]

// ==================== 方法 ====================

/**
 * 加载模型数据
 */
const loadModels = async () => {
  try {
    loading.value = true
    
    // 并行获取模型、分类和提供商数据
    const [modelsResponse, categoriesResponse, providersResponse] = await Promise.all([
      getAllModels(),
      getCategories(),
      getProviders()
    ])
    
    // 处理模型数据
    if (modelsResponse.data && modelsResponse.data.models) {
      models.value = Object.values(modelsResponse.data.models)
    } else {
      models.value = []
    }
    
    // 使用真实的分类数据
    if (categoriesResponse.data) {
      categories.value = categoriesResponse.data as unknown as Record<string, ModelCategory>
    } else {
      categories.value = {}
    }
    
    // 使用真实的提供商数据
    if (providersResponse.data) {
      providers.value = providersResponse.data as unknown as Record<string, ModelProvider>
    } else {
      providers.value = {}
    }
  } catch (error) {
    message.error('加载模型数据失败')
    console.error('Load models error:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 搜索处理
 */
const handleSearch = () => {
  // 搜索逻辑已在 computed 中处理
}

/**
 * 重置筛选
 */
const resetFilters = () => {
  searchText.value = ''
  filterCategory.value = ''
  filterProvider.value = ''
  filterStatus.value = ''
}

/**
 * 显示创建模型弹窗
 */
const showCreateModal = () => {
  editingModel.value = null
  formModalVisible.value = true
}

/**
 * 编辑模型
 */
const handleEditModel = (model: ModelConfig) => {
  editingModel.value = { ...model }
  formModalVisible.value = true
}

/**
 * 删除模型
 */
const handleDeleteModel = (model: ModelConfig) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除模型 "${model.name}" 吗？此操作不可撤销。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await deleteModel(model.id)
        message.success('模型删除成功')
        await loadModels()
      } catch (error) {
        message.error('删除模型失败')
        console.error('Delete model error:', error)
      }
    }
  })
}

/**
 * 切换模型状态
 */
const handleToggleModel = async (model: ModelConfig) => {
  try {
    toggleLoading[model.id] = true
    await toggleModelStatus(model.id)
    message.success(`模型已${model.enabled ? '禁用' : '启用'}`)
    await loadModels()
  } catch (error) {
    message.error('切换模型状态失败')
    console.error('Toggle model status error:', error)
  } finally {
    toggleLoading[model.id] = false
  }
}

/**
 * 表单提交处理
 */
const handleFormSubmit = async (formData: any) => {
  try {
    if (editingModel.value) {
      // 更新模型
      await updateModel(editingModel.value.id, formData)
      message.success('模型更新成功')
    } else {
      // 创建模型
      await createModel(formData)
      message.success('模型创建成功')
    }
    
    formModalVisible.value = false
    await loadModels()
  } catch (error) {
    message.error(editingModel.value ? '更新模型失败' : '创建模型失败')
    console.error('Form submit error:', error)
  }
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadModels()
})
</script>

<style scoped>
.model-config-container {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
}

.page-header {
  margin-bottom: 24px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: white;
  padding: 24px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.title-section h1 {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 600;
  color: #262626;
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  color: #1890ff;
}

.subtitle {
  margin: 0;
  color: #8c8c8c;
  font-size: 16px;
}

.stats-cards {
  margin-bottom: 24px;
}

.stat-card {
  text-align: center;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.filter-section {
  margin-bottom: 24px;
}

.models-section {
  margin-bottom: 24px;
}

.models-grid {
  min-height: 400px;
}

.model-name-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.model-info {
  flex: 1;
}

.model-title {
  font-weight: 500;
  color: #262626;
}

.model-id {
  font-size: 12px;
  color: #8c8c8c;
}

.cost-info {
  font-size: 12px;
  color: #666;
}

.cost-info > div {
  line-height: 1.4;
}

:deep(.ant-table-thead > tr > th) {
  background: #fafafa;
  font-weight: 600;
}

:deep(.ant-card-head-title) {
  font-weight: 600;
}

/* 提供商单元格样式 */
.provider-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.provider-links {
  display: flex;
  gap: 8px;
}

.provider-link {
  font-size: 14px;
  text-decoration: none;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.provider-link:hover {
  opacity: 1;
}
</style>
