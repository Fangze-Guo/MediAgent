<template>
  <div class="task-manage-container">
    <!-- 任务列表区域 -->
    <div class="task-list-section">
      <div class="section-header">
        <h2 class="section-title">
          <UnorderedListOutlined />
          任务列表
        </h2>
        <div class="section-actions">
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="搜索任务名称"
            style="width: 240px"
            @search="handleSearch"
            allow-clear
          />
          <a-radio-group v-model:value="statusFilter" button-style="solid" @change="handleFilterChange">
            <a-radio-button value="">全部</a-radio-button>
            <a-radio-button value="queued">排队中</a-radio-button>
            <a-radio-button value="running">执行中</a-radio-button>
            <a-radio-button value="succeeded">已完成</a-radio-button>
            <a-radio-button value="failed">已失败</a-radio-button>
          </a-radio-group>
          <a-button @click="loadTasks" :loading="loading">
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
        </div>
      </div>

      <!-- 任务表格 -->
      <a-table
        :columns="columns"
        :data-source="tasks"
        :loading="loading"
        :pagination="{
          current: currentPage,
          pageSize: pageSize,
          total: total,
          showSizeChanger: true,
          showTotal: (totalCount: number) => `共 ${totalCount} 条任务`,
          onChange: handlePageChange,
          onShowSizeChange: handlePageChange
        }"
        :row-key="(record: TaskInfo) => record.task_uid"
        :locale="{ emptyText: '暂无任务' }"
        class="task-table"
      >
        <!-- ID列 -->
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'id'">
            <span class="task-id-cell">{{ (currentPage - 1) * pageSize + index + 1 }}</span>
          </template>

          <!-- 任务名称列 -->
          <template v-else-if="column.key === 'name'">
            <div class="task-name-cell">
              <FileTextOutlined style="margin-right: 8px; color: #1890ff;" />
              <span>{{ record.task_name || record.task_uid }}</span>
              <a-button 
                type="link" 
                size="small"
                @click.stop="showEditNameModal(record)"
                class="edit-name-btn"
              >
                <template #icon><EditOutlined /></template>
              </a-button>
            </div>
          </template>

          <!-- 任务代码列 -->
          <template v-else-if="column.key === 'code'">
            <a-typography-text copyable :content="record.task_uid" class="task-code-cell">
              {{ record.task_uid }}
            </a-typography-text>
          </template>

          <!-- 任务类型列 -->
          <template v-else-if="column.key === 'type'">
            <a-tag color="blue">{{ getTaskType(record) }}</a-tag>
          </template>

          <!-- 任务状态列 -->
          <template v-else-if="column.key === 'status'">
            <a-tag :color="record.status_color">
              {{ record.status_text }}
            </a-tag>
          </template>

          <!-- 创建时间列 -->
          <template v-else-if="column.key === 'createTime'">
            <span class="time-cell">{{ record.create_time || '-' }}</span>
          </template>

          <!-- 更新时间列 -->
          <template v-else-if="column.key === 'updateTime'">
            <span class="time-cell">{{ record.update_time || '-' }}</span>
          </template>

          <!-- 操作列 -->
          <template v-else-if="column.key === 'action'">
            <div class="action-buttons">
              <a-button 
                type="link" 
                size="small"
                @click="showTaskDetail(record)"
                class="action-btn"
              >
                详情
              </a-button>
              <a-button 
                type="link" 
                danger
                size="small"
                @click="confirmDeleteTask(record)"
                :disabled="record.status === 'running'"
                class="action-btn"
              >
                删除
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 编辑任务名称模态框 -->
    <a-modal
      v-model:open="editNameVisible"
      title="编辑任务名称"
      @ok="handleUpdateTaskName"
      @cancel="editNameVisible = false"
    >
      <a-form layout="vertical">
        <a-form-item label="任务名称">
          <a-input 
            v-model:value="editingTaskName" 
            placeholder="请输入任务名称"
            :maxlength="100"
            allow-clear
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 任务详情模态框 -->
    <a-modal
      v-model:open="detailVisible"
      title="任务详情"
      width="900px"
      :footer="null"
      :destroy-on-close="true"
    >
      <div v-if="selectedTask" class="task-detail">
        <!-- 任务基本信息 -->
        <div class="detail-section">
          <h3 class="section-title">
            <FileTextOutlined />
            基本信息
          </h3>
          <a-descriptions bordered :column="2" size="small">
            <a-descriptions-item label="任务ID" :span="2">
              <a-typography-text copyable>{{ selectedTask.task_uid }}</a-typography-text>
            </a-descriptions-item>
            <a-descriptions-item label="任务状态">
              <a-tag :color="selectedTask.status_color">
                {{ selectedTask.status_text }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="用户ID">
              {{ selectedTask.user_uid }}
            </a-descriptions-item>
          </a-descriptions>
        </div>

        <!-- 进度信息 -->
        <div class="detail-section">
          <h3 class="section-title">
            <ClockCircleOutlined />
            执行进度
          </h3>
          <div class="progress-detail">
            <div class="progress-stats">
              <div class="stat-item">
                <div class="stat-label">总步骤</div>
                <div class="stat-value">{{ selectedTask.total_steps }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">已完成</div>
                <div class="stat-value success">{{ selectedTask.last_completed_step || 0 }}</div>
              </div>
              <div class="stat-item" v-if="selectedTask.current_step_number">
                <div class="stat-label">当前步骤</div>
                <div class="stat-value primary">{{ selectedTask.current_step_number }}</div>
              </div>
              <div class="stat-item" v-if="selectedTask.failed_step_number">
                <div class="stat-label">失败步骤</div>
                <div class="stat-value error">{{ selectedTask.failed_step_number }}</div>
              </div>
            </div>
            <a-progress
              :percent="selectedTask.progress_percentage"
              :status="getProgressStatus(selectedTask.status)"
              :stroke-color="getProgressColor(selectedTask.status)"
              :stroke-width="12"
            />
          </div>
        </div>

        <!-- 步骤列表 -->
        <div class="detail-section" v-if="taskSteps.length > 0">
          <h3 class="section-title">
            <UnorderedListOutlined />
            步骤详情
          </h3>
          <div class="steps-timeline">
            <div
              v-for="step in taskSteps"
              :key="step.step_number"
              class="step-item"
              :class="getStepClass(step, selectedTask)"
            >
              <div class="step-number">{{ step.step_number }}</div>
              <div class="step-content">
                <div class="step-header">
                  <span class="step-tool">{{ step.tool_name }}</span>
                  <a-tag 
                    v-if="getStepStatus(step, selectedTask)"
                    :color="getStepStatusColor(step, selectedTask)"
                    size="small"
                  >
                    {{ getStepStatus(step, selectedTask) }}
                  </a-tag>
                </div>
                <div class="step-info">
                  <div class="step-source">
                    <span class="label">数据源:</span>
                    <span class="value">{{ step.source_kind }} - {{ step.source || 'N/A' }}</span>
                  </div>
                  <div v-if="step.relative" class="step-relative">
                    <span class="label">相对路径:</span>
                    <span class="value">{{ step.relative }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="detail-actions">
          <div class="detail-actions-left">
            <a-button 
              danger 
              @click="confirmDeleteTask(selectedTask)"
              :disabled="selectedTask.status === 'running'"
            >
              <template #icon><DeleteOutlined /></template>
              删除任务
            </a-button>
          </div>
          <div class="detail-actions-right">
            <a-button @click="refreshTaskDetail" :loading="detailLoading">
              <template #icon><ReloadOutlined /></template>
              刷新
            </a-button>
            <a-switch 
              v-model:checked="autoRefreshEnabled" 
              checked-children="自动刷新" 
              un-checked-children="手动刷新"
            />
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { deleteTask, getTaskDetail, getTaskList, getTaskStatistics, updateTaskName, type TaskInfo, type TaskStatistics } from '@/apis/tasks'
import {
  ClockCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  FileTextOutlined,
  ReloadOutlined,
  UnorderedListOutlined
} from '@ant-design/icons-vue'
import { message, Modal } from 'ant-design-vue'
import { onMounted, onUnmounted, ref, watch } from 'vue'

// 表格列定义
const columns = [
  {
    title: 'ID',
    key: 'id',
    width: 80,
    align: 'center'
  },
  {
    title: '任务名称',
    key: 'name',
    width: 200,
  },
  {
    title: '任务代码',
    key: 'code',
    width: 180,
  },
  {
    title: '任务类型',
    key: 'type',
    width: 120,
    align: 'center'
  },
  {
    title: '任务状态',
    key: 'status',
    width: 120,
    align: 'center'
  },
  {
    title: '创建时间',
    key: 'createTime',
    width: 180,
  },
  {
    title: '更新时间',
    key: 'updateTime',
    width: 180,
  },
  {
    title: '操作',
    key: 'action',
    width: 150,
    align: 'center',
    fixed: 'right'
  }
]

// 响应式数据
const loading = ref(false)
const tasks = ref<TaskInfo[]>([])
const searchKeyword = ref('')
const statistics = ref<TaskStatistics>({
  total: 0,
  queued: 0,
  running: 0,
  succeeded: 0,
  failed: 0
})
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const detailVisible = ref(false)
const selectedTask = ref<TaskInfo | null>(null)
const taskSteps = ref<any[]>([])
const detailLoading = ref(false)
const autoRefreshEnabled = ref(false)
const refreshTimer = ref<number | null>(null)
const listRefreshTimer = ref<number | null>(null)
const editNameVisible = ref(false)
const editingTaskName = ref('')
const editingTask = ref<TaskInfo | null>(null)

// 处理搜索触发（用户点击搜索按钮/按回车时调用）
const handleSearch = () => {
  // 搜索时重置到第一页，避免“搜索后停留在原页码导致无结果”
  currentPage.value = 1
  // 调用加载任务列表方法，此时会携带搜索关键词
  loadTasks()
}

// 辅助函数：获取任务类型
const getTaskType = (task: TaskInfo): string => {
  try {
    const request = JSON.parse(task.request_json)
    if (request.steps && request.steps.length > 0) {
      const tools = request.steps.map((s: any) => s.tool_name).filter(Boolean)
      if (tools.length > 0) {
        return '机器学习'
      }
    }
  } catch (e) {
    // 解析失败
  }
  return '机器学习'
}

// 显示编辑任务名称模态框
const showEditNameModal = (task: TaskInfo) => {
  editingTask.value = task
  editingTaskName.value = task.task_name || task.task_uid
  editNameVisible.value = true
}

// 处理更新任务名称
const handleUpdateTaskName = async () => {
  if (!editingTask.value || !editingTaskName.value.trim()) {
    message.warning('请输入任务名称')
    return
  }

  try {
    const response = await updateTaskName(editingTask.value.task_uid, editingTaskName.value.trim())
    
    if (response.code === 200) {
      message.success('任务名称更新成功')
      editNameVisible.value = false
      // 刷新任务列表
      await loadTasks()
    } else {
      message.error(response.message || '更新任务名称失败')
    }
  } catch (error) {
    console.error('更新任务名称失败:', error)
    message.error(`更新任务名称失败: ${error instanceof Error ? error.message : String(error)}`)
  }
}

// 加载任务列表
const loadTasks = async () => {
  try {
    loading.value = true
    const offset = (currentPage.value - 1) * pageSize.value
    
    console.log('正在加载任务列表...', 
      { status: statusFilter.value, 
        keyword: searchKeyword.value, 
        limit: pageSize.value, 
        offset 
      }
    )
    
    const response = await getTaskList(
      statusFilter.value || undefined,
       pageSize.value, 
       offset, 
       searchKeyword.value || undefined
    )
    
    console.log('任务列表响应:', response)
    
    if (response.code === 200) {
      tasks.value = response.data || []
      console.log(`成功加载 ${tasks.value.length} 个任务`)
      
      // 如果没有任务，不显示错误，而是正常显示空状态
      if (tasks.value.length === 0) {
        console.log('当前没有任务数据')
      }
    } else {
      console.error('加载任务列表失败:', response)
      message.error(response.message || '加载任务列表失败')
    }
  } catch (error) {
    console.error('加载任务列表异常:', error)
    message.error(`加载任务列表失败: ${error instanceof Error ? error.message : String(error)}`)
  } finally {
    loading.value = false
  }
}

// 加载统计信息
const loadStatistics = async () => {
  try {
    console.log('正在加载任务统计信息...')
    
    const response = await getTaskStatistics()
    
    console.log('统计信息响应:', response)
    
    if (response.code === 200) {
      statistics.value = response.data
      // 更新total用于分页
      total.value = response.data.total
      console.log('统计信息加载成功:', statistics.value)
    } else {
      console.error('加载统计信息失败:', response)
      message.error(response.message || '加载统计信息失败')
    }
  } catch (error) {
    console.error('加载统计信息异常:', error)
    // 统计信息加载失败不影响主要功能，只在控制台输出错误
  }
}

// 处理过滤变化
const handleFilterChange = () => {
  currentPage.value = 1
  loadTasks()
}

// 处理分页变化
const handlePageChange = () => {
  loadTasks()
}

// 确认删除任务
const confirmDeleteTask = (task: TaskInfo) => {
  Modal.confirm({
    title: '确认删除任务',
    content: `确定要删除任务 ${task.task_uid} 吗？此操作不可恢复。`,
    okText: '确认删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await handleDeleteTask(task.task_uid)
    }
  })
}

// 删除任务
const handleDeleteTask = async (taskUid: string) => {
  try {
    const response = await deleteTask(taskUid)
    
    if (response.code === 200) {
      message.success('任务删除成功')
      // 刷新任务列表和统计信息
      await Promise.all([loadTasks(), loadStatistics()])
      // 如果当前详情窗口显示的是被删除的任务，关闭窗口
      if (selectedTask.value && selectedTask.value.task_uid === taskUid) {
        detailVisible.value = false
        selectedTask.value = null
      }
    } else {
      message.error(response.message || '删除任务失败')
    }
  } catch (error) {
    console.error('删除任务失败:', error)
    message.error(`删除任务失败: ${error instanceof Error ? error.message : String(error)}`)
  }
}

// 解析任务步骤
const parseTaskSteps = (requestJson: string): any[] => {
  try {
    const request = JSON.parse(requestJson)
    if (request.steps && Array.isArray(request.steps)) {
      return request.steps.sort((a: any, b: any) => 
        (a.step_number || a.stepNumber) - (b.step_number || b.stepNumber)
      )
    }
  } catch (error) {
    console.error('解析任务步骤失败:', error)
  }
  return []
}

// 显示任务详情
const showTaskDetail = async (task: TaskInfo) => {
  selectedTask.value = task
  taskSteps.value = parseTaskSteps(task.request_json)
  detailVisible.value = true
  
  // 如果任务正在运行，启动自动刷新
  if (task.status === 'running') {
    autoRefreshEnabled.value = true
  }
}

// 刷新任务详情
const refreshTaskDetail = async () => {
  if (!selectedTask.value) return
  
  try {
    detailLoading.value = true
    const response = await getTaskDetail(selectedTask.value.task_uid)
    
    if (response.code === 200) {
      selectedTask.value = response.data
      taskSteps.value = parseTaskSteps(response.data.request_json)
      console.log('任务详情已刷新')
      
      // 如果任务已完成，停止自动刷新
      if (response.data.status === 'succeeded' || response.data.status === 'failed') {
        autoRefreshEnabled.value = false
      }
    }
  } catch (error) {
    console.error('刷新任务详情失败:', error)
  } finally {
    detailLoading.value = false
  }
}

// 获取步骤状态
const getStepStatus = (step: any, task: TaskInfo): string => {
  const stepNumber = step.step_number || step.stepNumber
  const lastCompleted = task.last_completed_step || 0
  const currentStep = task.current_step_number
  const failedStep = task.failed_step_number
  
  if (failedStep === stepNumber) {
    return '失败'
  } else if (stepNumber <= lastCompleted) {
    return '已完成'
  } else if (stepNumber === currentStep) {
    return '执行中'
  } else if (stepNumber > lastCompleted) {
    return '等待中'
  }
  return ''
}

// 获取步骤状态颜色
const getStepStatusColor = (step: any, task: TaskInfo): string => {
  const status = getStepStatus(step, task)
  const colorMap: Record<string, string> = {
    '已完成': 'success',
    '执行中': 'processing',
    '等待中': 'default',
    '失败': 'error'
  }
  return colorMap[status] || 'default'
}

// 获取步骤样式类
const getStepClass = (step: any, task: TaskInfo): string => {
  const status = getStepStatus(step, task)
  const classMap: Record<string, string> = {
    '已完成': 'step-completed',
    '执行中': 'step-running',
    '等待中': 'step-pending',
    '失败': 'step-failed'
  }
  return classMap[status] || ''
}

// 获取进度条状态
const getProgressStatus = (status: string) => {
  switch (status) {
    case 'succeeded':
      return 'success'
    case 'failed':
      return 'exception'
    case 'running':
      return 'active'
    default:
      return 'normal'
  }
}

// 获取进度条颜色
const getProgressColor = (status: string) => {
  switch (status) {
    case 'succeeded':
      return '#52c41a'
    case 'failed':
      return '#ff4d4f'
    case 'running':
      return '#1890ff'
    case 'queued':
      return '#faad14'
    default:
      return '#d9d9d9'
  }
}

// 启动详情自动刷新
const startDetailAutoRefresh = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }
  refreshTimer.value = window.setInterval(() => {
    if (autoRefreshEnabled.value && detailVisible.value) {
      refreshTaskDetail()
    }
  }, 3000) // 每3秒刷新一次
}

// 停止详情自动刷新
const stopDetailAutoRefresh = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
    refreshTimer.value = null
  }
}

// 启动列表自动刷新（针对运行中的任务）
const startListAutoRefresh = () => {
  if (listRefreshTimer.value) {
    clearInterval(listRefreshTimer.value)
  }
  listRefreshTimer.value = window.setInterval(() => {
    // 如果有运行中的任务，自动刷新列表
    const hasRunningTasks = tasks.value.some(t => t.status === 'running')
    if (hasRunningTasks) {
      console.log('检测到运行中的任务，自动刷新列表')
      loadTasks()
      loadStatistics()
    }
  }, 5000) // 每5秒检查一次
}

// 停止列表自动刷新
const stopListAutoRefresh = () => {
  if (listRefreshTimer.value) {
    clearInterval(listRefreshTimer.value)
    listRefreshTimer.value = null
  }
}

// 监听自动刷新开关
watch(autoRefreshEnabled, (enabled) => {
  if (enabled) {
    startDetailAutoRefresh()
  } else {
    stopDetailAutoRefresh()
  }
})

// 监听详情窗口关闭
watch(detailVisible, (visible) => {
  if (!visible) {
    stopDetailAutoRefresh()
    autoRefreshEnabled.value = false
  }
})

// 组件挂载时加载数据
onMounted(() => {
  loadStatistics()
  loadTasks()
  startListAutoRefresh() // 启动列表自动刷新
})

// 组件卸载时清理定时器
onUnmounted(() => {
  stopDetailAutoRefresh()
  stopListAutoRefresh()
})
</script>

<style scoped>
.task-manage-container {
  padding: 24px;
  min-height: 100vh;
  background: #f0f2f5;
}

/* 统计卡片区域 */
.statistics-section {
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
  cursor: pointer;
}

.stat-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  transform: translateY(-2px);
}

.stat-icon {
  font-size: 32px;
  margin-right: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
}

.stat-card-total .stat-icon {
  background: #e6f7ff;
  color: #1890ff;
}

.stat-card-queued .stat-icon {
  background: #fff7e6;
  color: #faad14;
}

.stat-card-running .stat-icon {
  background: #e6f7ff;
  color: #1890ff;
}

.stat-card-succeeded .stat-icon {
  background: #f6ffed;
  color: #52c41a;
}

.stat-card-failed .stat-icon {
  background: #fff2f0;
  color: #ff4d4f;
}

.stat-content {
  flex: 1;
}

.stat-title {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

/* 任务列表区域 */
.task-list-section {
  background: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.section-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
}

.loading-container p {
  margin-top: 16px;
  color: #666;
}

/* 任务表格样式 */
.task-table {
  margin-top: 16px;
}

.task-table :deep(.ant-table) {
  background: white;
  border-radius: 8px;
}

.task-table :deep(.ant-table-thead > tr > th) {
  background: #fafafa;
  font-weight: 600;
  color: #333;
  border-bottom: 2px solid #f0f0f0;
}

.task-table :deep(.ant-table-tbody > tr) {
  transition: all 0.3s ease;
}

.task-table :deep(.ant-table-tbody > tr:hover) {
  background: #f5f9ff;
}

.task-table :deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #f0f0f0;
}

/* 单元格样式 */
.task-id-cell {
  font-weight: 500;
  color: #666;
}

.task-name-cell {
  display: flex;
  align-items: center;
  font-weight: 500;
  color: #333;
}

.edit-name-btn {
  margin-left: 8px;
  padding: 0 4px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.task-name-cell:hover .edit-name-btn {
  opacity: 1;
}

.task-code-cell {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #666;
}

.time-cell {
  font-size: 13px;
  color: #666;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.action-btn {
  padding: 0 8px;
}

/* 任务详情 */
.task-detail {
  padding: 16px 0;
}

.request-json {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
  max-height: 400px;
  overflow: auto;
  margin: 0;
}

/* 详情页样式 */
.detail-section {
  margin-bottom: 24px;
}

.detail-section .section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f0f0f0;
}

/* 进度详情样式 */
.progress-detail {
  background: #fafafa;
  padding: 20px;
  border-radius: 8px;
}

.progress-stats {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.stat-item {
  flex: 1;
  min-width: 100px;
  text-align: center;
  padding: 12px;
  background: white;
  border-radius: 6px;
  border: 1px solid #e8e8e8;
}

.stat-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.stat-value.success {
  color: #52c41a;
}

.stat-value.primary {
  color: #1890ff;
}

.stat-value.error {
  color: #ff4d4f;
}

/* 步骤时间线样式 */
.steps-timeline {
  position: relative;
  padding-left: 40px;
}

.steps-timeline::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #e8e8e8;
}

.step-item {
  position: relative;
  margin-bottom: 20px;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
  transition: all 0.3s ease;
}

.step-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border-color: #d9d9d9;
}

.step-item::before {
  content: '';
  position: absolute;
  left: -33px;
  top: 24px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #d9d9d9;
  border: 2px solid white;
  box-shadow: 0 0 0 2px #e8e8e8;
}

.step-completed {
  background: #f6ffed;
  border-color: #b7eb8f;
}

.step-completed::before {
  background: #52c41a;
  box-shadow: 0 0 0 2px #52c41a;
}

.step-running {
  background: #e6f7ff;
  border-color: #91d5ff;
  animation: pulse 2s infinite;
}

.step-running::before {
  background: #1890ff;
  box-shadow: 0 0 0 2px #1890ff;
  animation: blink 1.5s infinite;
}

.step-pending {
  background: #fafafa;
  border-color: #e8e8e8;
}

.step-pending::before {
  background: #d9d9d9;
  box-shadow: 0 0 0 2px #e8e8e8;
}

.step-failed {
  background: #fff2f0;
  border-color: #ffccc7;
}

.step-failed::before {
  background: #ff4d4f;
  box-shadow: 0 0 0 2px #ff4d4f;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.8;
  }
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.step-number {
  position: absolute;
  left: -40px;
  top: 16px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border: 2px solid #e8e8e8;
  border-radius: 50%;
  font-weight: bold;
  font-size: 14px;
  color: #666;
  z-index: 1;
}

.step-completed .step-number {
  background: #52c41a;
  border-color: #52c41a;
  color: white;
}

.step-running .step-number {
  background: #1890ff;
  border-color: #1890ff;
  color: white;
}

.step-failed .step-number {
  background: #ff4d4f;
  border-color: #ff4d4f;
  color: white;
}

.step-content {
  flex: 1;
}

.step-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.step-tool {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.step-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-source,
.step-relative {
  font-size: 13px;
  color: #666;
}

.step-source .label,
.step-relative .label {
  font-weight: 500;
  color: #888;
  margin-right: 8px;
}

.step-source .value,
.step-relative .value {
  color: #333;
  font-family: monospace;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
}

/* 详情操作按钮 */
.detail-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.detail-actions-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-actions-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .task-manage-container {
    padding: 16px;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .section-actions {
    width: 100%;
  }

  .section-actions .ant-radio-group {
    width: 100%;
  }

  .task-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .task-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>

