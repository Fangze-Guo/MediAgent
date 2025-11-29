<template>
  <div class="model-card" :class="{ 'disabled': !model.enabled }">
    <!-- 模型头部信息 -->
    <div class="model-header">
      <div class="model-avatar">
        <a-avatar 
          :src="getAvatarUrl(provider?.avatar)"
          :style="!provider?.avatar ? { backgroundColor: getProviderColor(model.provider) } : {}" 
          size="large"
        >
          <template v-if="!provider?.avatar">
            {{ model.provider.charAt(0) }}
          </template>
        </a-avatar>
      </div>
      
      <div class="model-info">
        <div class="model-title">
          <a-tooltip :title="model.name">
            <h3>{{ model.name }}</h3>
          </a-tooltip>
          <a-tag :color="getCategoryColor(model.category)">
            {{ category?.name || model.category }}
          </a-tag>
        </div>
        <a-tooltip :title="model.description">
          <p class="model-description">{{ model.description }}</p>
        </a-tooltip>
        
        <!-- 提供商链接 -->
        <div v-if="provider" class="provider-links">
          <a 
            v-if="provider.website" 
            :href="provider.website" 
            target="_blank"
            class="provider-link"
          >
            🌐 官网
          </a>
          <a 
            v-if="provider.api_docs" 
            :href="provider.api_docs" 
            target="_blank"
            class="provider-link"
          >
            📚 API文档
          </a>
        </div>
      </div>
      
      <div class="model-actions">
        <a-switch 
          :checked="model.enabled" 
          @change="$emit('toggle', model)"
          size="small"
        />
        <a-dropdown>
          <a-button type="text" size="small">
            <template #icon>
              <MoreOutlined />
            </template>
          </a-button>
          <template #overlay>
            <a-menu>
              <a-menu-item key="view" @click="showDetails = true">
                <EyeOutlined />
                {{ $t('model.card.details') }}
              </a-menu-item>
              <a-menu-item key="edit" @click="$emit('edit', model)">
                <EditOutlined />
                {{ $t('model.card.edit') }}
              </a-menu-item>
              <a-menu-item key="delete" @click="$emit('delete', model)" danger>
                <DeleteOutlined />
                {{ $t('model.card.delete') }}
              </a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </div>
    </div>

    <!-- 模型能力标签 -->
    <div class="model-capabilities">
      <a-tag 
        v-for="capability in model.capabilities" 
        :key="capability"
        size="small"
        class="capability-tag"
        :class="getTagClass(capability)"
      >
        {{ capability }}
      </a-tag>
    </div>

    <!-- 模型规格信息 -->
    <div class="model-specs">
      <div class="spec-item">
        <span class="spec-label">最大Token</span>
        <span class="spec-value">{{ formatNumber(model.max_tokens) }}</span>
      </div>
      <div class="spec-item">
        <span class="spec-label">输入成本</span>
        <span class="spec-value">${{ model.input_cost_per_1k }}/1K</span>
      </div>
      <div class="spec-item">
        <span class="spec-label">输出成本</span>
        <span class="spec-value">${{ model.output_cost_per_1k }}/1K</span>
      </div>
    </div>

    <!-- 提供商信息 -->
    <div class="model-footer">
      <div class="provider-info">
        <span class="provider-name">{{ provider?.name || model.provider }}</span>
        <a-tag v-if="model.enabled" color="success" size="small">启用</a-tag>
        <a-tag v-else color="default" size="small">禁用</a-tag>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <a-modal
      v-model:open="showDetails"
      :title="model.name + ' - ' + $t('model.card.details')"
      :width="600"
      :footer="null"
    >
      <div class="model-details">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item :label="$t('model.card.modelId')">{{ model.id }}</a-descriptions-item>
          <a-descriptions-item :label="$t('common.provider')">{{ model.provider }}</a-descriptions-item>
          <a-descriptions-item :label="$t('common.category')">{{ category?.name || model.category }}</a-descriptions-item>
          <a-descriptions-item :label="$t('common.status')">
            <a-tag v-if="model.enabled" color="success">{{ $t('model.card.enabled') }}</a-tag>
            <a-tag v-else color="default">{{ $t('model.card.disabled') }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="$t('model.card.maxTokens')" :span="2">{{ model.max_tokens.toLocaleString() }}</a-descriptions-item>
          <a-descriptions-item :label="$t('model.card.inputCost')">${{ model.input_cost_per_1k }}/1K tokens</a-descriptions-item>
          <a-descriptions-item :label="$t('model.card.outputCost')">${{ model.output_cost_per_1k }}/1K tokens</a-descriptions-item>
        </a-descriptions>
        
        <a-divider>{{ $t('model.card.capabilities') }}</a-divider>
        <div class="capabilities-list">
          <span 
            v-for="capability in model.capabilities" 
            :key="capability"
            class="model-tag"
            :class="getTagClass(capability)"
          >
            {{ capability }}
          </span>
        </div>
        
        <a-divider>{{ $t('model.card.apiConfig') }}</a-divider>
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item :label="$t('model.card.baseUrl')">{{ model.config.base_url }}</a-descriptions-item>
          <a-descriptions-item :label="$t('model.card.modelId')">{{ model.config.model }}</a-descriptions-item>
          <a-descriptions-item :label="$t('model.card.temperature')">{{ model.config.temperature }}</a-descriptions-item>
          <a-descriptions-item :label="$t('model.card.maxTokens')">{{ model.config.max_tokens }}</a-descriptions-item>
        </a-descriptions>
        
        <a-divider>{{ $t('model.card.requirements') }}</a-divider>
        <div class="requirements-list">
          <a-tag v-if="model.requirements.api_key_required" color="orange">{{ $t('model.card.apiKeyRequired') }}</a-tag>
          <a-tag v-if="model.requirements.base_url_configurable" color="blue">{{ $t('model.card.baseUrlConfigurable') }}</a-tag>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  MoreOutlined
} from '@ant-design/icons-vue'
import type { ModelConfig, ModelCategory, ModelProvider } from '@/apis/modelConfig'
import { getCategoryColor, getProviderColor } from '@/utils/colors'

// ==================== Props ====================
interface Props {
  model: ModelConfig
  category?: ModelCategory
  provider?: ModelProvider
}

defineProps<Props>()

// ==================== Emits ====================
defineEmits<{
  edit: [model: ModelConfig]
  delete: [model: ModelConfig]
  toggle: [model: ModelConfig]
}>()

// ==================== 响应式数据 ====================
const showDetails = ref(false)

// API基础URL
const API_BASE = 'http://localhost:8000'

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

// ==================== 方法 ====================

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

/**
 * 格式化数字
 */
const formatNumber = (num: number) => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}
</script>

<style scoped>
.model-card {
  border: 1px solid #f0f0f0;
  border-radius: 12px;
  padding: 20px;
  background: white;
  transition: all 0.3s ease;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.model-card:hover {
  border-color: #1890ff;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.15);
  transform: translateY(-2px);
}

.model-card.disabled {
  opacity: 0.6;
  background: #fafafa;
}

.model-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.model-avatar {
  flex-shrink: 0;
}

.model-info {
  flex: 1;
  min-width: 0;
}

.model-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.model-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-description {
  margin: 0;
  font-size: 13px;
  color: #8c8c8c;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.model-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.model-capabilities {
  margin-bottom: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.capability-tag {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}

.model-specs {
  margin-bottom: 16px;
  flex: 1;
}

.spec-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #f5f5f5;
}

.spec-item:last-child {
  border-bottom: none;
}

.spec-label {
  font-size: 12px;
  color: #8c8c8c;
}

.spec-value {
  font-size: 12px;
  color: #262626;
  font-weight: 500;
}

.model-footer {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid #f5f5f5;
}

.provider-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.provider-name {
  font-size: 12px;
  color: #595959;
  font-weight: 500;
}

.model-details {
  max-height: 60vh;
  overflow-y: auto;
}

.capabilities-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.requirements-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* 提供商链接样式 */
.provider-links {
  margin-top: 8px;
  display: flex;
  gap: 12px;
}

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

/* 标签样式 - 与 ModelSelector 保持一致 */
.model-tag {
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-right: 4px;
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

/* 响应式 */
@media (max-width: 768px) {
  .model-card {
    padding: 16px;
  }
  
  .model-title h3 {
    font-size: 14px;
  }
  
  .model-description {
    font-size: 12px;
  }
}
</style>
