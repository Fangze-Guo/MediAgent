<template>
  <a-modal
    :open="open"
    :title="isEdit ? '编辑模型' : '创建模型'"
    :width="800"
    :confirm-loading="loading"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      layout="vertical"
      class="model-form"
    >
      <a-row :gutter="16">
        <!-- 基本信息 -->
        <a-col :span="24">
          <h3 class="section-title">基本信息</h3>
        </a-col>
        
        <a-col :span="12">
          <a-form-item label="模型ID" name="id">
            <a-input 
              v-model:value="formData.id" 
              placeholder="例如: gpt-4o"
              :disabled="isEdit"
            />
          </a-form-item>
        </a-col>
        
        <a-col :span="12">
          <a-form-item label="模型名称" name="name">
            <a-input 
              v-model:value="formData.name" 
              placeholder="例如: GPT-4o"
            />
          </a-form-item>
        </a-col>
        
        <a-col :span="12">
          <a-form-item label="提供商" name="provider">
            <a-select 
              v-model:value="formData.provider" 
              placeholder="选择提供商"
              show-search
              allow-clear
            >
              <a-select-option 
                v-for="(provider, key) in providers" 
                :key="key" 
                :value="key"
              >
                {{ provider.name }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        
        <a-col :span="12">
          <a-form-item label="分类" name="category">
            <a-select 
              v-model:value="formData.category" 
              placeholder="选择分类"
            >
              <a-select-option 
                v-for="(category, key) in categories" 
                :key="key" 
                :value="key"
              >
                {{ category.name }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        
        <a-col :span="24">
          <a-form-item label="模型描述" name="description">
            <a-textarea 
              v-model:value="formData.description" 
              placeholder="请输入模型的详细描述"
              :rows="3"
            />
          </a-form-item>
        </a-col>

        <!-- 能力配置 -->
        <a-col :span="24">
          <h3 class="section-title">能力配置</h3>
        </a-col>
        
        <a-col :span="24">
          <a-form-item label="支持能力" name="capabilities">
            <a-select
              v-model:value="formData.capabilities"
              mode="tags"
              placeholder="选择或输入支持的能力"
              :options="capabilityOptions"
            />
          </a-form-item>
        </a-col>

        <!-- 技术规格 -->
        <a-col :span="24">
          <h3 class="section-title">技术规格</h3>
        </a-col>
        
        <a-col :span="8">
          <a-form-item label="最大Token数" name="max_tokens">
            <a-input-number 
              v-model:value="formData.max_tokens" 
              placeholder="128000"
              :min="1"
              :max="1000000"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        
        <a-col :span="8">
          <a-form-item label="输入成本(/1K)" name="input_cost_per_1k">
            <a-input-number 
              v-model:value="formData.input_cost_per_1k" 
              placeholder="0.005"
              :min="0"
              :step="0.001"
              :precision="6"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        
        <a-col :span="8">
          <a-form-item label="输出成本(/1K)" name="output_cost_per_1k">
            <a-input-number 
              v-model:value="formData.output_cost_per_1k" 
              placeholder="0.015"
              :min="0"
              :step="0.001"
              :precision="6"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>

        <!-- API配置 -->
        <a-col :span="24">
          <h3 class="section-title">API配置</h3>
        </a-col>
        
        <a-col :span="12">
          <a-form-item label="Base URL" name="base_url">
            <a-input 
              v-model:value="formData.config.base_url" 
              placeholder="https://api.openai.com/v1"
            />
          </a-form-item>
        </a-col>
        
        <a-col :span="12">
          <a-form-item label="模型标识" name="model">
            <a-input 
              v-model:value="formData.config.model" 
              placeholder="gpt-4o"
            />
          </a-form-item>
        </a-col>
        
        <a-col :span="8">
          <a-form-item label="Temperature" name="temperature">
            <a-input-number 
              v-model:value="formData.config.temperature" 
              placeholder="0.7"
              :min="0"
              :max="2"
              :step="0.1"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        
        <a-col :span="8">
          <a-form-item label="Max Tokens" name="max_tokens_config">
            <a-input-number 
              v-model:value="formData.config.max_tokens" 
              placeholder="4096"
              :min="1"
              :max="100000"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>

        <!-- 使用要求 -->
        <a-col :span="24">
          <h3 class="section-title">使用要求</h3>
        </a-col>
        
        <a-col :span="12">
          <a-form-item name="api_key_required">
            <a-checkbox v-model:checked="formData.requirements.api_key_required">
              需要API密钥
            </a-checkbox>
          </a-form-item>
        </a-col>
        
        <a-col :span="12">
          <a-form-item name="base_url_configurable">
            <a-checkbox v-model:checked="formData.requirements.base_url_configurable">
              可配置Base URL
            </a-checkbox>
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, reactive } from 'vue'
import type { FormInstance } from 'ant-design-vue'
import type { ModelConfig, ModelCategory, ModelProvider } from '@/apis/modelConfig'

// ==================== Props ====================
interface Props {
  open: boolean
  model?: ModelConfig | null
  categories: Record<string, ModelCategory>
  providers: Record<string, ModelProvider>
}

const props = defineProps<Props>()

// ==================== Emits ====================
const emit = defineEmits<{
  'update:open': [value: boolean]
  submit: [data: any]
}>()

// ==================== 响应式数据 ====================
const loading = ref(false)
const formRef = ref<FormInstance>()

// 判断是否为编辑模式
const isEdit = computed(() => !!props.model)

// 表单数据
const formData = reactive({
  id: '',
  name: '',
  provider: '',
  description: '',
  category: '',
  capabilities: [] as string[],
  max_tokens: 128000,
  input_cost_per_1k: 0.005,
  output_cost_per_1k: 0.015,
  config: {
    base_url: '',
    model: '',
    temperature: 0.7,
    max_tokens: 4096
  },
  requirements: {
    api_key_required: true,
    base_url_configurable: true
  }
})

// 能力选项
const capabilityOptions = [
  { label: '文本', value: 'text' },
  { label: '图像', value: 'image' },
  { label: '代码', value: 'code' },
  { label: '数学', value: 'math' },
  { label: '分析', value: 'analysis' },
  { label: '中文', value: 'chinese' },
  { label: '多模态', value: 'multimodal' }
]

// 表单验证规则
const rules = {
  id: [
    { required: true, message: '请输入模型ID' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: '模型ID只能包含字母、数字、下划线和连字符' }
  ],
  name: [
    { required: true, message: '请输入模型名称' }
  ],
  provider: [
    { required: true, message: '请选择提供商' }
  ],
  category: [
    { required: true, message: '请选择分类' }
  ],
  description: [
    { required: true, message: '请输入模型描述' }
  ],
  capabilities: [
    { required: true, message: '请选择至少一个能力' }
  ],
  max_tokens: [
    { required: true, message: '请输入最大Token数' },
    { type: 'number', min: 1, message: '最大Token数必须大于0' }
  ],
  input_cost_per_1k: [
    { required: true, message: '请输入输入成本' },
    { type: 'number', min: 0, message: '成本不能为负数' }
  ],
  output_cost_per_1k: [
    { required: true, message: '请输入输出成本' },
    { type: 'number', min: 0, message: '成本不能为负数' }
  ]
}

// ==================== 方法 ====================

/**
 * 重置表单
 */
const resetForm = () => {
  Object.assign(formData, {
    id: '',
    name: '',
    provider: '',
    description: '',
    category: '',
    capabilities: [],
    max_tokens: 128000,
    input_cost_per_1k: 0.005,
    output_cost_per_1k: 0.015,
    config: {
      base_url: '',
      model: '',
      temperature: 0.7,
      max_tokens: 4096
    },
    requirements: {
      api_key_required: true,
      base_url_configurable: true
    }
  })
  formRef.value?.clearValidate()
}

/**
 * 填充表单数据
 */
const fillForm = (model: ModelConfig) => {
  Object.assign(formData, {
    id: model.id,
    name: model.name,
    provider: model.provider,
    description: model.description,
    category: model.category,
    capabilities: [...model.capabilities],
    max_tokens: model.max_tokens,
    input_cost_per_1k: model.input_cost_per_1k,
    output_cost_per_1k: model.output_cost_per_1k,
    config: { ...model.config },
    requirements: { ...model.requirements }
  })
}

/**
 * 处理提交
 */
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    loading.value = true
    
    // 准备提交数据
    const submitData = {
      ...formData,
      config: { ...formData.config },
      requirements: { ...formData.requirements }
    }
    
    emit('submit', submitData)
  } catch (error) {
    console.error('Form validation failed:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 处理取消
 */
const handleCancel = () => {
  emit('update:open', false)
}

// ==================== 监听器 ====================

// 监听弹窗打开状态
watch(() => props.open, (newOpen) => {
  if (newOpen) {
    if (props.model) {
      fillForm(props.model)
    } else {
      resetForm()
    }
  }
})

// 监听模型数据变化
watch(() => props.model, (newModel) => {
  if (newModel && props.open) {
    fillForm(newModel)
  }
})
</script>

<style scoped>
.model-form {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 8px;
}

.section-title {
  margin: 24px 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 8px;
}

.section-title:first-child {
  margin-top: 0;
}

:deep(.ant-form-item-label > label) {
  font-weight: 500;
}

:deep(.ant-input-number) {
  width: 100%;
}

/* 滚动条样式 */
.model-form::-webkit-scrollbar {
  width: 6px;
}

.model-form::-webkit-scrollbar-track {
  background: transparent;
}

.model-form::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
}

.model-form::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}
</style>
