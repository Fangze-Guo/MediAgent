<template>
  <div class="task-manage-container">
    <!-- 任务列表区域 -->
    <div class="task-list-section">
      <div class="section-header">
          <h2 class="section-title">
          <UnorderedListOutlined />
          Task List
        </h2>
        <div class="section-actions">
          <a-input-search v-model:value="searchKeyword" placeholder="Search task name" style="width: 240px" @search="handleSearch"
            allow-clear />
          <a-radio-group v-model:value="statusFilter" button-style="solid" @change="handleFilterChange">
            <a-radio-button value="">All</a-radio-button>
            <a-radio-button value="queued">Queued</a-radio-button>
            <a-radio-button value="running">Running</a-radio-button>
            <a-radio-button value="succeeded">Succeeded</a-radio-button>
            <a-radio-button value="failed">Failed</a-radio-button>
          </a-radio-group>
          <a-button @click="loadTasks" :loading="loading">
            <template #icon>
              <ReloadOutlined />
            </template>
            Refresh
          </a-button>
        </div>
      </div>

      <!-- 任务表格 -->
      <a-table :columns="columns" :data-source="tasks" :loading="loading" :pagination="{
        current: currentPage,
        pageSize: pageSize,
        total: total,
        showSizeChanger: true,
        showTotal: (totalCount: number) => `${totalCount} tasks`,
        onChange: handlePageChange,
        onShowSizeChange: handlePageChange
      }" :row-key="(record: TaskInfo) => record.task_uid" :locale="{ emptyText: '暂无任务' }" class="task-table">
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
              <a-button type="link" size="small" @click.stop="showEditNameModal(record)" class="edit-name-btn">
                <template #icon>
                  <EditOutlined />
                </template>
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
              <a-button class="btn-icon" @click.stop="viewTaskFiles(record)" title="查看文件">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                  <circle cx="12" cy="12" r="3"></circle>
                </svg>
              </a-button>
              <a-button type="link" size="small" @click="showTaskDetail(record)" class="action-btn">
                详情
              </a-button>
              <a-button type="link" danger size="small" @click="confirmDeleteTask(record)"
                :disabled="record.status === 'running'" class="action-btn">
                删除
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 编辑任务名称模态框 -->
    <a-modal v-model:open="editNameVisible" title="编辑任务名称" @ok="handleUpdateTaskName" @cancel="editNameVisible = false">
      <a-form layout="vertical">
        <a-form-item label="任务名称">
          <a-input v-model:value="editingTaskName" placeholder="请输入任务名称" :maxlength="100" allow-clear />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 任务详情模态框 -->
    <a-modal v-model:open="detailVisible" title="任务详情" width="900px" :footer="null" :destroy-on-close="true">
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
            <a-progress :percent="selectedTask.progress_percentage" :status="getProgressStatus(selectedTask.status)"
              :stroke-color="getProgressColor(selectedTask.status)" :stroke-width="12" />
          </div>
        </div>

        <!-- 步骤列表 -->
        <div class="detail-section" v-if="taskSteps.length > 0">
          <h3 class="section-title">
            <UnorderedListOutlined />
            步骤详情
          </h3>
          <div class="steps-timeline">
            <div v-for="step in taskSteps" :key="step.step_number" class="step-item"
              :class="getStepClass(step, selectedTask)">
              <div class="step-number">{{ step.step_number }}</div>
              <div class="step-content">
                <div class="step-header">
                  <span class="step-tool">{{ step.tool_name }}</span>
                  <a-tag v-if="getStepStatus(step, selectedTask)" :color="getStepStatusColor(step, selectedTask)"
                    size="small">
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
            <a-button danger @click="confirmDeleteTask(selectedTask)" :disabled="selectedTask.status === 'running'">
              <template #icon>
                <DeleteOutlined />
              </template>
              删除任务
            </a-button>
          </div>
          <div class="detail-actions-right">
            <a-button @click="refreshTaskDetail" :loading="detailLoading">
              <template #icon>
                <ReloadOutlined />
              </template>
              刷新
            </a-button>
            <a-switch v-model:checked="autoRefreshEnabled" checked-children="自动刷新" un-checked-children="手动刷新" />
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 文件浏览模态框 -->
    <div class="modal" v-if="showFilesDialog" @click.self="showFilesDialog = false">
      <div class="modal-content modal-large">
        <div class="modal-header file-browser-header">
          <div class="header-title-wrapper">
            <div class="header-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
              </svg>
            </div>
            <div class="header-text">
              <h2>{{ selectedTask?.task_name }}</h2>
              <span class="header-subtitle">浏览任务文件</span>
            </div>
          </div>
          <button class="btn-close" @click="showFilesDialog = false">×</button>
        </div>
        <div class="modal-body">
          <!-- 当前路径 -->
          <div class="file-breadcrumb">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
            </svg>
            <span class="breadcrumb-path">{{ currentFilePath || "/" }}</span>
            <button v-if="currentFilePath && currentFilePath !== '.'" class="btn-back" @click="goBackFolder"
              title="返回上级">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2">
                <line x1="19" y1="12" x2="5" y2="12"></line>
                <polyline points="12 19 5 12 12 5"></polyline>
              </svg>
              返回上级
            </button>
          </div>

          <!-- 文件列表 -->
          <div v-if="filesLoading" class="files-loading">
            <div class="spinner"></div>
            <p>加载中...</p>
          </div>

          <div v-else-if="taskFiles.length === 0" class="empty-files">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="1">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
            </svg>
            <p>该文件夹为空</p>
          </div>

          <div v-else class="files-list-container">
            <!-- 表头 -->
            <div class="files-list-header">
              <div class="header-col col-name">名称</div>
              <div class="header-col col-size">大小</div>
              <div class="header-col col-time">修改时间</div>
            </div>

            <!-- 文件列表 -->
            <div class="files-list">
              <div v-for="file in taskFiles" :key="file.id" class="file-list-item"
                :class="{ 'is-directory': file.isDirectory, 'is-file': !file.isDirectory }"
                @click="file.isDirectory ? openFolder(file) : null">
                <div class="file-col col-name">
                  <div class="file-icon-wrapper">
                    <!-- 文件夹图标 -->
                    <svg v-if="file.isDirectory" xmlns="http://www.w3.org/2000/svg" width="20" height="20"
                      viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon-folder">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                    </svg>
                    <!-- 文件图标 -->
                    <svg v-else xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
                      fill="none" stroke="currentColor" stroke-width="2" class="icon-file">
                      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
                      <polyline points="13 2 13 9 20 9"></polyline>
                    </svg>
                  </div>
                  <span class="file-name-text" :title="file.name">{{ file.name }}</span>
                </div>
                <div class="file-col col-size">
                  <span v-if="!file.isDirectory">{{ formatFileSize(file.size) }}</span>
                  <span v-else class="folder-indicator">—</span>
                </div>
                <div class="file-col col-time">
                  {{ formatTime(file.modifiedTime) }}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showFilesDialog = false">
            关闭
          </button>
        </div>
      </div>
    </div>
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
import { getTaskFiles, type FileInfo } from "@/apis/files";
import { useAuthStore } from "@/store/auth"

const authStore = useAuthStore()

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
// 任务文件浏览
const viewingTask = ref<TaskInfo | null>(null)
const showFilesDialog = ref(false)
const currentFilePath = ref("")
const filesLoading = ref(false)
const taskFiles = ref<FileInfo[]>([])

// 处理搜索触发（用户点击搜索按钮/按回车时调用）
const handleSearch = () => {
  // 搜索时重置到第一页，避免“搜索后停留在原页码导致无结果”
  currentPage.value = 1
  // 调用加载任务列表方法，此时会携带搜索关键词
  loadTasks()
}

// 查看任务文件
const viewTaskFiles = async (currentTask: TaskInfo) => {
  viewingTask.value = currentTask;
  showFilesDialog.value = true;
  currentFilePath.value = `private/${authStore.currentUser?.uid}/workspace/${currentTask.task_uid}`;
  await loadTaskFiles();
};

// 返回上级文件夹
const goBackFolder = async () => {
  if (!currentFilePath.value || currentFilePath.value === ".") return;

  // 提取上级路径
  const pathParts = currentFilePath.value.split("/");
  pathParts.pop();
  currentFilePath.value = pathParts.length > 0 ? pathParts.join("/") : ".";

  await loadTaskFiles();
};

// 打开文件夹
const openFolder = async (file: FileInfo) => {
  if (!file.isDirectory) return;
  currentFilePath.value = file.path;
  await loadTaskFiles();
};

// 加载数据集文件
const loadTaskFiles = async () => {
  if (!currentFilePath.value) return;

  filesLoading.value = true;
  try {
    const response = await getTaskFiles(currentFilePath.value);
    if (response.code === 200) {
      taskFiles.value = response.data.files;
    }
  } catch (error) {
    console.error("加载文件列表失败:", error);
    alert("加载文件列表失败");
  } finally {
    filesLoading.value = false;
  }
};

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

// 格式化文件大小
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
};

// 格式化时间
const formatTime = (timeStr: string): string => {
  try {
    const date = new Date(timeStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      const hours = Math.floor(diff / (1000 * 60 * 60));
      if (hours === 0) {
        const minutes = Math.floor(diff / (1000 * 60));
        return minutes === 0 ? "刚刚" : `${minutes}分钟前`;
      }
      return `${hours}小时前`;
    } else if (days < 7) {
      return `${days}天前`;
    } else {
      return date.toLocaleDateString("zh-CN");
    }
  } catch {
    return timeStr;
  }
};

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
      {
        status: statusFilter.value,
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

.btn-icon {
  padding: 6px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
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

  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.8;
  }
}

@keyframes blink {

  0%,
  100% {
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

/* Modal样式 */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-large {
  max-width: 800px;
}

.modal-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 文件浏览器样式 */
.file-browser-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px 24px;
  border-bottom: none;
}

.file-browser-header .header-title-wrapper {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.file-browser-header .header-icon {
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
}

.file-browser-header .header-icon svg {
  color: white;
}

.file-browser-header .header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-browser-header h2 {
  color: white;
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.file-browser-header .header-subtitle {
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  font-weight: 400;
}

.btn-close {
  background: none;
  border: none;
  font-size: 28px;
  color: #9ca3af;
  cursor: pointer;
  line-height: 1;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.file-browser-header .btn-close {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  width: 36px;
  height: 36px;
  border-radius: 8px;
}

.file-browser-header .btn-close:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: scale(1.05);
}

.file-breadcrumb {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-radius: 12px;
  margin-bottom: 24px;
  border: 1px solid #bae6fd;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.file-breadcrumb svg {
  color: #0ea5e9;
  flex-shrink: 0;
}

.breadcrumb-path {
  flex: 1;
  font-size: 14px;
  color: #0c4a6e;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 6px;
  border: 1px solid rgba(14, 165, 233, 0.2);
}

.btn-back {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: white;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.files-loading {
  text-align: center;
  padding: 60px 20px;
  color: #9ca3af;
}

.empty-files {
  text-align: center;
  padding: 60px 20px;
  color: #9ca3af;
}

.empty-files svg {
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-files p {
  font-size: 14px;
  margin: 0;
}

/* 文件列表容器 */
.files-list-container {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
}

/* 表头 */
.files-list-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: linear-gradient(to bottom, #f9fafb, #f3f4f6);
  border-bottom: 2px solid #e5e7eb;
  font-weight: 600;
  font-size: 13px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.header-col {
  display: flex;
  align-items: center;
}

/* 文件列表 */
.files-list {
  max-height: 500px;
  overflow-y: auto;
}

.file-list-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f3f4f6;
  transition: all 0.2s;
  cursor: default;
}

.file-list-item:last-child {
  border-bottom: none;
}

.file-list-item:hover {
  background: #f9fafb;
}

.file-list-item.is-directory {
  cursor: pointer;
}

.file-list-item.is-directory:hover {
  background: linear-gradient(to right, #eff6ff, #f0f9ff);
  border-left: 3px solid #3b82f6;
  padding-left: 13px;
}

.file-list-item.is-directory:hover .icon-folder {
  color: #3b82f6;
  transform: scale(1.1);
}

.file-list-item.is-directory:hover .file-name-text {
  color: #2563eb;
  font-weight: 600;
}

.file-col {
  display: flex;
  align-items: center;
}

.col-name {
  flex: 1;
  min-width: 0;
}

/* 文件图标包装器 */
.file-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  margin-right: 12px;
  transition: all 0.2s;
}

.icon-folder {
  color: #60a5fa;
  transition: all 0.2s;
}

.icon-file {
  color: #9ca3af;
}

/* 文件名 */
.file-name-text {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: all 0.2s;
}

/* 文件夹指示器 */
.folder-indicator {
  color: #d1d5db;
  font-size: 18px;
  font-weight: 300;
}

/* 文件大小和时间 */
.col-size,
.col-time {
  font-size: 13px;
  color: #6b7280;
}

.col-size {
  width: 120px;
  justify-content: flex-end;
}

.col-time {
  width: 160px;
  justify-content: flex-end;
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  background: white;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}
</style>
