<template>
  <div class="progress-display">
    <!-- 进度模态框 -->
    <a-modal
      :open="visible"
      @update:open="emit('update:visible', $event)"
      :title="title"
      :width="600"
      :footer="null"
      :closable="false"
      :maskClosable="false"
    >
      <div class="progress-content">
        <!-- 任务信息 -->
        <div class="task-info">
          <div class="task-title">{{ taskTitle }}</div>
          <div class="task-description">{{ taskDescription }}</div>
        </div>

        <!-- 进度条 -->
        <div class="progress-section">
          <div class="progress-header">
            <span class="progress-label">处理进度</span>
            <span class="progress-percentage">{{ currentProgress }}%</span>
          </div>
          <a-progress 
            :percent="currentProgress" 
            :status="progressStatus"
            :stroke-color="progressColor"
            :show-info="false"
          />
        </div>

        <!-- 状态信息 -->
        <div class="status-section">
          <div class="status-item">
            <span class="status-label">当前状态：</span>
            <span class="status-value" :class="statusClass">{{ currentStatus }}</span>
          </div>
          <div v-if="currentMessage" class="status-item">
            <span class="status-label">详细信息：</span>
            <span class="status-value">{{ currentMessage }}</span>
          </div>
          <div v-if="estimatedTime" class="status-item">
            <span class="status-label">预计剩余时间：</span>
            <span class="status-value">{{ estimatedTime }}</span>
          </div>
        </div>

        <!-- 详细信息 -->
        <div v-if="details.length > 0" class="details-section">
          <div class="details-header">处理详情</div>
          <div class="details-list">
            <div 
              v-for="(detail, index) in details" 
              :key="index"
              class="detail-item"
              :class="{ 'active': index === currentDetailIndex }"
            >
              <div class="detail-icon">
                <CheckCircleOutlined v-if="detail.completed" />
                <LoadingOutlined v-else-if="index === currentDetailIndex" />
                <ClockCircleOutlined v-else />
              </div>
              <div class="detail-content">
                <div class="detail-text">{{ detail.text }}</div>
                <div v-if="detail.subText" class="detail-sub-text">{{ detail.subText }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="action-buttons">
          <a-button 
            v-if="canCancel" 
            @click="handleCancel"
            :loading="cancelling"
          >
            取消任务
          </a-button>
          <a-button 
            v-if="isCompleted" 
            type="primary" 
            @click="handleClose"
          >
            完成
          </a-button>
        </div>
      </div>
    </a-modal>

    <!-- 通知消息 -->
    <a-notification
      :open="notificationVisible"
      @update:open="notificationVisible = $event"
      :message="notificationMessage"
      :description="notificationDescription"
      :type="notificationType"
      placement="topRight"
      :duration="4.5"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { 
  CheckCircleOutlined, 
  LoadingOutlined, 
  ClockCircleOutlined 
} from '@ant-design/icons-vue'
import { getProgress, type ProgressResponse } from '@/apis/progress'

// Props
interface Props {
  visible: boolean
  title?: string
  taskTitle?: string
  taskDescription?: string
  progress?: number
  currentStatus?: string
  estimatedTime?: string
  details?: Array<{
    text: string
    subText?: string
    completed?: boolean
  }>
  canCancel?: boolean
  completed?: boolean
  taskId?: string  // 新增：任务ID，用于从后端获取真实进度
}

const props = withDefaults(defineProps<Props>(), {
  title: '处理进度',
  taskTitle: '',
  taskDescription: '',
  progress: 0,
  currentStatus: '准备中...',
  estimatedTime: '',
  details: () => [],
  canCancel: true,
  completed: false,
  taskId: ''
})

// Emits
const emit = defineEmits<{
  'update:visible': [value: boolean]
  'cancel': []
  'close': []
}>()

// 响应式数据
const cancelling = ref(false)
const notificationVisible = ref(false)
const notificationMessage = ref('')
const notificationDescription = ref('')
const notificationType = ref<'success' | 'error' | 'warning' | 'info'>('info')

// 真实进度数据
const realProgress = ref<ProgressResponse | null>(null)
const progressInterval = ref<NodeJS.Timeout | null>(null)

// 计算属性 - 优先使用真实进度
const currentProgress = computed(() => {
  return realProgress.value?.progress ?? props.progress
})

const currentStatus = computed(() => {
  return realProgress.value?.status ?? props.currentStatus
})

const currentMessage = computed(() => {
  return realProgress.value?.message ?? ''
})

const isCompleted = computed(() => {
  return realProgress.value?.completed ?? props.completed
})

const progressStatus = computed(() => {
  if (isCompleted.value) return 'success'
  if (currentProgress.value === 0) return 'normal'
  return 'active'
})

const progressColor = computed(() => {
  if (isCompleted.value) return '#52c41a'
  if (currentProgress.value < 30) return '#1890ff'
  if (currentProgress.value < 70) return '#faad14'
  return '#f5222d'
})

const statusClass = computed(() => {
  if (isCompleted.value) return 'status-success'
  if (currentProgress.value > 0) return 'status-processing'
  return 'status-waiting'
})

const currentDetailIndex = computed(() => {
  return props.details.findIndex(detail => !detail.completed)
})

// 进度轮询方法
const startProgressPolling = () => {
  if (!props.taskId) return
  
  progressInterval.value = setInterval(async () => {
    try {
      const response = await getProgress(props.taskId)
      if (response.success && response.data) {
        realProgress.value = response.data
        
        // 如果任务完成，停止轮询
        if (response.data.completed) {
          stopProgressPolling()
          showNotification('success', '任务完成', '处理任务已成功完成！')
        }
      }
    } catch (error) {
      console.error('获取进度失败:', error)
    }
  }, 1000) // 每秒轮询一次
}

const stopProgressPolling = () => {
  if (progressInterval.value) {
    clearInterval(progressInterval.value)
    progressInterval.value = null
  }
}

// 监听器
watch(() => props.visible, (newVal) => {
  if (newVal) {
    // 显示通知
    showNotification('info', '任务开始', '正在初始化处理任务...')
    
    // 开始轮询进度
    if (props.taskId) {
      startProgressPolling()
    }
  } else {
    // 停止轮询
    stopProgressPolling()
  }
})

watch(() => props.taskId, (newTaskId) => {
  if (newTaskId && props.visible) {
    startProgressPolling()
  }
})

watch(() => isCompleted.value, (newVal) => {
  if (newVal) {
    showNotification('success', '任务完成', '处理任务已成功完成！')
  }
})

// 方法
const handleCancel = async () => {
  cancelling.value = true
  try {
    emit('cancel')
    showNotification('warning', '任务取消', '正在取消处理任务...')
    // 延迟关闭，让用户看到取消状态
    setTimeout(() => {
      emit('update:visible', false)
      cancelling.value = false
    }, 1000)
  } catch (error) {
    cancelling.value = false
    showNotification('error', '取消失败', '取消任务时发生错误')
  }
}

const handleClose = () => {
  emit('close')
  emit('update:visible', false)
}

const showNotification = (
  type: 'success' | 'error' | 'warning' | 'info',
  message: string,
  description: string
) => {
  notificationType.value = type
  notificationMessage.value = message
  notificationDescription.value = description
  notificationVisible.value = true
}

// 生命周期钩子
onMounted(() => {
  if (props.visible && props.taskId) {
    startProgressPolling()
  }
})

onUnmounted(() => {
  stopProgressPolling()
})

// 暴露方法给父组件
defineExpose({
  showNotification,
  startProgressPolling,
  stopProgressPolling
})
</script>

<style scoped>
.progress-display {
  position: relative;
}

.progress-content {
  padding: 16px 0;
}

.task-info {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.task-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 8px;
}

.task-description {
  font-size: 14px;
  color: #666;
  line-height: 1.5;
}

.progress-section {
  margin-bottom: 24px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.progress-label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.progress-percentage {
  font-size: 16px;
  font-weight: 600;
  color: #1890ff;
}

.status-section {
  margin-bottom: 24px;
}

.status-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.status-label {
  font-size: 14px;
  color: #666;
  margin-right: 8px;
  min-width: 100px;
}

.status-value {
  font-size: 14px;
  font-weight: 500;
}

.status-waiting {
  color: #999;
}

.status-processing {
  color: #1890ff;
}

.status-success {
  color: #52c41a;
}

.details-section {
  margin-bottom: 24px;
}

.details-header {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

.details-list {
  max-height: 200px;
  overflow-y: auto;
}

.detail-item {
  display: flex;
  align-items: flex-start;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-item.active {
  background: #f0f9ff;
  margin: 0 -16px;
  padding: 8px 16px;
  border-radius: 6px;
}

.detail-icon {
  margin-right: 12px;
  margin-top: 2px;
  font-size: 16px;
}

.detail-icon .anticon-check-circle {
  color: #52c41a;
}

.detail-icon .anticon-loading {
  color: #1890ff;
}

.detail-icon .anticon-clock-circle {
  color: #d9d9d9;
}

.detail-content {
  flex: 1;
}

.detail-text {
  font-size: 14px;
  color: #333;
  margin-bottom: 4px;
}

.detail-sub-text {
  font-size: 12px;
  color: #666;
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

/* 滚动条样式 */
.details-list::-webkit-scrollbar {
  width: 6px;
}

.details-list::-webkit-scrollbar-track {
  background: #f5f5f5;
  border-radius: 3px;
}

.details-list::-webkit-scrollbar-thumb {
  background: #d9d9d9;
  border-radius: 3px;
}

.details-list::-webkit-scrollbar-thumb:hover {
  background: #bfbfbf;
}
</style>
