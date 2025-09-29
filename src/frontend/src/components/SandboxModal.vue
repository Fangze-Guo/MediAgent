<template>
  <a-modal
    :open="visible"
    :title="title"
    width="900px"
    :footer="null"
    :destroy-on-close="true"
    @update:open="handleVisibleChange"
  >
    <div class="sandbox-container">
      <!-- 目录结构显示 -->
      <div class="sandbox-section">
        <h4>📁 工作目录结构</h4>
        <div class="directory-tree">
          <div class="tree-item">
            <span class="folder">📁 src/data/sandbox/</span>
            <div class="tree-children">
              <div class="tree-item">
                <span class="folder">📁 dicom/</span>
                <div class="tree-child">
                  <span class="description">← DICOM源文件</span>
                </div>
              </div>
              <div class="tree-item">
                <span class="folder">📁 input/</span>
                <div class="tree-child">
                  <span class="description">← NII输入文件</span>
                </div>
              </div>
              <div class="tree-item">
                <span class="folder">📁 output/</span>
                <div class="tree-children">
                  <div class="tree-item">
                    <span class="folder">📁 dicom_to_nii/</span>
                    <div class="tree-child">
                      <span class="description">← DICOM转换输出</span>
                    </div>
                  </div>
                  <div class="tree-item">
                    <span class="folder">📁 resample/</span>
                    <div class="tree-child">
                      <span class="description">← 重采样输出</span>
                    </div>
                  </div>
                  <div class="tree-item">
                    <span class="folder">📁 normalize/</span>
                    <div class="tree-child">
                      <span class="description">← 归一化输出</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 配置表单 -->
      <div class="sandbox-section">
        <h4>⚙️ 配置</h4>
        <div class="config-form">
          <div class="form-item">
            <label>输出文件名:</label>
            <a-input 
              v-model:value="formData.output_filename" 
              placeholder="例如: result.nii.gz" 
              :disabled="processing" 
            />
            <span class="hint">留空自动生成</span>
          </div>
          <div class="form-item">
            <label>
              <a-checkbox v-model:checked="formData.compression" :disabled="processing">
                启用压缩
              </a-checkbox>
            </label>
            <span class="hint">输出 .nii.gz 格式</span>
          </div>
        </div>
      </div>

      <!-- 执行按钮 -->
      <div class="sandbox-section">
        <div class="action-buttons">
          <a-button 
            type="primary" 
            size="large" 
            :loading="processing"
            @click="handleExecute"
          >
            <template #icon>
              <PlayCircleOutlined />
            </template>
            {{ processing ? '处理中...' : '开始处理' }}
          </a-button>
          <a-button @click="handleClose" :disabled="processing">
            关闭
          </a-button>
        </div>
      </div>

      <!-- 执行日志 -->
      <div v-if="processing || logs.length > 0" class="sandbox-section">
        <h4>📋 执行日志</h4>
        <div class="log-container">
          <div 
            v-for="(log, index) in logs" 
            :key="index"
            class="log-entry"
            :class="log.type"
          >
            <span class="log-time">{{ log.time }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { PlayCircleOutlined } from '@ant-design/icons-vue'

// 类型定义
interface Props {
  visible: boolean
  processing: boolean
  logs: ConversionLog[]
  sandboxType?: 'dicom_to_nii' | 'resample' | 'normalize'
}

interface ConversionLog {
  time: string
  type: 'info' | 'success' | 'warning' | 'error'
  message: string
}

// Props
const props = withDefaults(defineProps<Props>(), {
  visible: false,
  processing: false,
  logs: () => [],
  sandboxType: 'dicom_to_nii'
})

// Emits
const emit = defineEmits<{
  'update:visible': [value: boolean]
  'execute': [params: ExecuteParams]
  'close': []
}>()

// 表单数据
const formData = ref({
  output_filename: '',
  compression: true,
  target_spacing: '1.0,1.0,1.0',
  interpolation: 'Linear' as 'Linear' | 'Nearest' | 'Cubic',
  batch_mode: false,
  method: 'z-score' as 'z-score' | 'min-max' | 'percentile',
  percentiles: '1,99',
  generate_stats: true
})

// 处理后的数据接口
interface ExecuteParams {
  output_filename?: string
  compression?: boolean
  target_spacing?: string
  interpolation?: 'Linear' | 'Nearest' | 'Cubic'
  batch_mode?: boolean
  method?: 'z-score' | 'min-max' | 'percentile'
  percentiles?: string
  generate_stats?: boolean
}

// 计算属性 - 标题
const title = computed(() => {
  const typeMap = {
    'dicom_to_nii': 'DICOM→NII转换',
    'resample': '图像重采样', 
    'normalize': '强度归一化'
  }
  return `${typeMap[props.sandboxType]} - 沙盒环境`
})

// 处理可见性变化
const handleVisibleChange = (value: boolean) => {
  emit('update:visible', value)
}

// 关闭模态框
const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

// 执行处理
const handleExecute = () => {
  let params: ExecuteParams = {}
  
  if (props.sandboxType === 'dicom_to_nii') {
    params = {
      output_filename: formData.value.output_filename.trim(),
      compression: formData.value.compression
    }
  } else if (props.sandboxType === 'resample') {
    params = {
      target_spacing: formData.value.target_spacing || '1.0,1.0,1.0',
      interpolation: formData.value.interpolation || 'Linear',
      batch_mode: formData.value.batch_mode || false
    }
  } else if (props.sandboxType === 'normalize') {
    params = {
      method: formData.value.method || 'z-score',
      percentiles: formData.value.percentiles || '1,99',
      generate_stats: formData.value.generate_stats !== false
    }
  }
  
  emit('execute', params)
}

// 监听visible变化，重置表单
watch(() => props.visible, (newVisible) => {
  if (newVisible) {
    // 重置默认值
    Object.assign(formData.value, {
      output_filename: '',
      compression: true,
      target_spacing: '1.0,1.0,1.0',
      interpolation: 'Linear' as 'Linear' | 'Nearest' | 'Cubic',
      batch_mode: false,
      method: 'z-score' as 'z-score' | 'min-max' | 'percentile',
      percentiles: '1,99',
      generate_stats: true
    })
  }
})
</script>

<style scoped>
.sandbox-container {
  padding: 20px 0;
}

.sandbox-section {
  margin-bottom: 24px;
}

.sandbox-section:last-child {
  margin-bottom: 0;
}

.sandbox-section h4 {
  margin: 0 0 12px 0;
  color: #1890ff;
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
}

.directory-tree {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 16px;
  font-family: 'Courier New', monospace;
  font-size: 14px;
}

.tree-item {
  margin-bottom: 8px;
}

.tree-children {
  margin-left: 16px;
}

.tree-child {
  margin-left: 16px;
  color: #6c757d;
}

.folder {
  color: #1890ff;
  font-weight: 500;
}

.file {
  color: #28a745;
  font-weight: 500;
}

.description {
  color: #6c757d;
  font-style: italic;
  margin-left: 8px;
}

.config-form {
  background: #fafafa;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
}

.form-item {
  margin-bottom: 16px;
}

.form-item:last-child {
  margin-bottom: 0;
}

.form-item label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #212529;
}

.form-item .hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #6c757d;
}

.action-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 24px;
}

.log-container {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  padding: 12px;
  max-height: 300px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.log-entry {
  margin-bottom: 4px;
  display: flex;
  gap: 8px;
}

.log-time {
  color: #6c757d;
  min-width: 70px;
}

.log-message {
  flex: 1;
}

.log-entry.info .log-message {
  color: #212529;
}

.log-entry.success .log-message {
  color: #198754;
}

.log-entry.warning .log-message {
  color: #fd7e14;
}

.log-entry.error .log-message {
  color: #dc3545;
}
</style>
