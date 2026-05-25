<template>
  <div class="clinical-tools">
    <!-- ==================== 顶部 Hero 横幅 ==================== -->
    <div class="tools-hero">
      <div class="hero-decor hero-decor-1"></div>
      <div class="hero-decor hero-decor-2"></div>
      <div class="hero-inner">
        <div class="hero-text">
          <div class="hero-icon-wrap">🏥</div>
          <div>
            <h1 class="hero-title">{{ t('views_ClinicalToolsView.logoText') }}</h1>
            <p class="hero-subtitle">{{ t('views_ClinicalToolsView.headerDescription') }}</p>
          </div>
        </div>
        <div class="hero-actions">
          <a-input-search
            v-model:value="searchKeyword"
            :placeholder="t('views_ClinicalToolsView.searchPlaceholder')"
            size="large"
            class="search-input"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input-search>
          <a-button class="create-agent-btn" @click="createModalVisible = true">
            <template #icon><PlusOutlined /></template>
            {{ t('views_ClinicalToolsView.createAgent') }}
          </a-button>
        </div>
      </div>
    </div>

    <!-- ==================== 主内容区 ==================== -->
    <div class="tools-main">
      <div class="main-container">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-state">
          <a-spin size="large" />
          <p>{{ t('views_ClinicalToolsView.loading') }}</p>
        </div>

        <!-- 空状态 -->
        <div v-else-if="filteredProjects.length === 0" class="empty-state">
          <InboxOutlined :style="{ fontSize: '64px', color: 'var(--border-color)' }" />
          <p class="empty-text">{{ t('views_ClinicalToolsView.emptyText') }}</p>
          <p class="empty-hint">{{ t('views_ClinicalToolsView.emptyHint') }}</p>
        </div>

        <!-- 项目网格 -->
        <div v-else>
          <!-- 区块标题 -->
          <div class="section-header">
            <h2 class="section-title">{{ t('views_ClinicalToolsView.sectionTitle') }}</h2>
            <span class="results-count">{{ t('views_ClinicalToolsView.resultsCount', { count: filteredProjects.length }) }}</span>
          </div>

          <div class="projects-grid">
            <div
              v-for="project in filteredProjects"
              :key="project.id"
              class="project-card"
            >
              <!-- 项目头部 -->
              <div class="project-header">
                <div class="project-avatar" :style="{ background: project.avatarColor }">
                  <span class="project-avatar-text">{{ project.avatarText }}</span>
                </div>
                <div class="project-info">
                  <h2 class="project-name">{{ project.name }}</h2>
                  <p class="project-description">{{ project.description }}</p>
                </div>
                <button class="card-edit-btn" :title="t('views_ClinicalToolsView.editBtnTitle')" @click.stop="openEditModal(project.id)">
                  <EditOutlined />
                </button>
                <a-popconfirm
                  v-if="isAdmin"
                  :title="t('views_ClinicalToolsView.deleteConfirmTitle')"
                  :ok-text="t('views_ClinicalToolsView.deleteOkText')"
                  :cancel-text="t('views_ClinicalToolsView.cancelBtn')"
                  ok-type="danger"
                  @confirm.stop="handleDeleteAgent(project.id)"
                  @click.stop
                >
                  <button class="card-delete-btn" :title="t('views_ClinicalToolsView.deleteBtnTitle')" @click.stop>
                    <DeleteOutlined />
                  </button>
                </a-popconfirm>
              </div>

              <!-- 工具列表 -->
              <div class="tools-list">
                <div
                  v-for="tool in project.tools"
                  :key="tool.id"
                  class="tool-item"
                  @click="navigateTo(tool.route)"
                >
                  <div class="tool-item-left">
                    <div class="tool-icon-wrapper" :style="{ background: tool.iconBg }">
                      <Icon :icon="tool.icon" class="tool-icon" :style="{ color: tool.iconColor }" />
                    </div>
                    <span class="tool-name">{{ tool.name }}</span>
                  </div>
                  <div class="tool-arrow">
                    <RightOutlined />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <!-- ==================== 新建智能体 Modal ==================== -->
  <a-modal
    v-model:open="createModalVisible"
    :title="t('views_ClinicalToolsView.createModalTitle')"
    :confirm-loading="createLoading"
    :ok-text="t('views_ClinicalToolsView.createBtn')"
    :cancel-text="t('views_ClinicalToolsView.cancelBtn')"
    :width="560"
    @ok="handleCreateSubmit"
    @cancel="createModalVisible = false"
  >
    <a-form layout="vertical" style="margin-top: 8px">
      <a-form-item :label="t('views_ClinicalToolsView.fieldName')" :required="true">
        <a-input v-model:value="createForm.name" :placeholder="t('views_ClinicalToolsView.fieldNamePlaceholder')" />
      </a-form-item>
      <a-form-item :label="t('views_ClinicalToolsView.fieldDesc')">
        <a-input v-model:value="createForm.description" :placeholder="t('views_ClinicalToolsView.fieldDescPlaceholder')" />
      </a-form-item>
      <a-form-item :label="t('views_ClinicalToolsView.fieldSystemPrompt')">
        <a-textarea
          v-model:value="createForm.system_prompt"
          :placeholder="t('views_ClinicalToolsView.fieldSystemPromptPlaceholder')"
          :rows="8"
          :style="{ fontFamily: 'monospace', fontSize: '13px' }"
        />
      </a-form-item>
    </a-form>
  </a-modal>
  <!-- ==================== 编辑智能体 Modal ==================== -->
  <a-modal
    v-model:open="editModalVisible"
    :title="t('views_ClinicalToolsView.editModalTitle')"
    :confirm-loading="editLoading"
    :ok-text="t('views_ClinicalToolsView.saveBtn')"
    :cancel-text="t('views_ClinicalToolsView.cancelBtn')"
    :width="560"
    @ok="handleEditSubmit"
    @cancel="editModalVisible = false"
  >
    <a-form layout="vertical" style="margin-top: 8px">
      <a-form-item :label="t('views_ClinicalToolsView.fieldName')">
        <a-input v-model:value="editForm.name" :placeholder="t('views_ClinicalToolsView.fieldNamePlaceholder')" />
      </a-form-item>
      <a-form-item :label="t('views_ClinicalToolsView.fieldDesc')">
        <a-input v-model:value="editForm.description" :placeholder="t('views_ClinicalToolsView.fieldDescPlaceholder')" />
      </a-form-item>
      <a-form-item :label="t('views_ClinicalToolsView.fieldSystemPrompt')">
        <a-textarea
          v-model:value="editForm.system_prompt"
          :placeholder="t('views_ClinicalToolsView.fieldSystemPromptEditPlaceholder')"
          :rows="8"
          :style="{ fontFamily: 'monospace', fontSize: '13px' }"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { SearchOutlined, RightOutlined, InboxOutlined, EditOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { Icon } from '@iconify/vue'
import { listClinicalAgents, createClinicalAgent, getAgent, updateAgent, deleteClinicalAgent, type ClinicalAgent, type UpdateAgentParams, type CreateAgentParams } from '@/apis/agents'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const { t } = useI18n()
const authStore = useAuthStore()
const isAdmin = computed(() => authStore.user?.role === 'admin')

// 工具数据接口
interface Tool {
  id: string
  name: string
  icon: string
  iconColor: string
  iconBg: string
  route: string
}

// 项目数据接口
interface Project {
  id: string
  name: string
  description: string
  avatarText: string
  avatarColor: string
  tools: Tool[]
}

// 头像颜色池
const avatarColors = [
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
  'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)',
  'linear-gradient(135deg, #fccb90 0%, #d57eeb 100%)',
  'linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)',
]

const getAvatarColor = (index: number) => avatarColors[index % avatarColors.length]

const getAvatarText = (name: string) => {
  if (!name) return '?'
  const trimmed = name.trim()
  // 取前两个字符（中文两字 or 英文首字母）
  return trimmed.slice(0, 2).toUpperCase()
}

// 状态
const searchKeyword = ref('')
const loading = ref(false)
const dynamicAgents = ref<ClinicalAgent[]>([])

// 删除智能体
const handleDeleteAgent = async (agentId: string) => {
  try {
    const res = await deleteClinicalAgent(agentId)
    if (res.code === 200) {
      dynamicAgents.value = dynamicAgents.value.filter(a => a.agent_id !== agentId)
      message.success(t('views_ClinicalToolsView.messages.deleteSuccess'))
    } else {
      message.error(res.message || t('views_ClinicalToolsView.messages.deleteFailed'))
    }
  } catch {
    message.error(t('views_ClinicalToolsView.messages.deleteError'))
  }
}

// 新建 Modal
const createModalVisible = ref(false)
const createLoading = ref(false)
const createForm = ref<CreateAgentParams>({ name: '', description: '', system_prompt: '' })

const handleCreateSubmit = async () => {
  if (!createForm.value.name?.trim()) {
    message.warning(t('views_ClinicalToolsView.messages.nameRequired'))
    return
  }
  createLoading.value = true
  try {
    const res = await createClinicalAgent(createForm.value)
    if (res.code === 200 && res.data) {
      dynamicAgents.value.unshift(res.data)
      message.success(t('views_ClinicalToolsView.messages.createSuccess'))
      createModalVisible.value = false
      createForm.value = { name: '', description: '', system_prompt: '' }
    } else {
      message.error(res.message || t('views_ClinicalToolsView.messages.createFailed'))
    }
  } catch {
    message.error(t('views_ClinicalToolsView.messages.createError'))
  } finally {
    createLoading.value = false
  }
}

// 编辑 Modal
const editModalVisible = ref(false)
const editLoading = ref(false)
const editingAgentId = ref('')
const editForm = ref<UpdateAgentParams>({ name: '', description: '', system_prompt: '' })

const openEditModal = async (agentId: string) => {
  editingAgentId.value = agentId
  editModalVisible.value = true
  editLoading.value = true
  try {
    const res = await getAgent(agentId)
    if (res.code === 200 && res.data) {
      editForm.value = {
        name: res.data.name,
        description: res.data.description,
        system_prompt: res.data.system_prompt,
      }
    }
  } catch {
    message.error(t('views_ClinicalToolsView.messages.loadAgentFailed'))
  } finally {
    editLoading.value = false
  }
}

const handleEditSubmit = async () => {
  if (!editForm.value.name?.trim()) {
    message.warning(t('views_ClinicalToolsView.messages.nameRequired'))
    return
  }
  editLoading.value = true
  try {
    const res = await updateAgent(editingAgentId.value, editForm.value)
    if (res.code === 200 && res.data) {
      const idx = dynamicAgents.value.findIndex(a => a.agent_id === editingAgentId.value)
      if (idx !== -1) dynamicAgents.value[idx] = res.data
      message.success(t('views_ClinicalToolsView.messages.saveSuccess'))
      editModalVisible.value = false
    } else {
      message.error(res.message || t('views_ClinicalToolsView.messages.saveFailed'))
    }
  } catch {
    message.error(t('views_ClinicalToolsView.messages.saveError'))
  } finally {
    editLoading.value = false
  }
}

// 项目列表 - 全部从接口动态拉取
const projects = computed<Project[]>(() =>
  dynamicAgents.value.map((agent, index) => ({
    id: agent.agent_id,
    name: agent.name,
    description: agent.description || '',
    avatarText: getAvatarText(agent.name),
    avatarColor: getAvatarColor(index),
    tools: [
      {
        id: `${agent.agent_id}-chat`,
        name: t('views_ClinicalToolsView.toolAgent'),
        icon: 'carbon:bot',
        iconColor: '#1677ff',
        iconBg: 'rgba(22,119,255,0.1)',
        route: `/clinical-agent/${agent.agent_id}?name=${encodeURIComponent(agent.name)}`
      },
      {
        id: `${agent.agent_id}-skills`,
        name: t('views_ClinicalToolsView.toolSkillManage'),
        icon: 'carbon:tools',
        iconColor: '#a0243e',
        iconBg: 'rgba(160,36,62,0.1)',
        route: `/clinical-agent/${agent.agent_id}/skills?name=${encodeURIComponent(agent.name)}`
      },
    ]
  }))
)

// 过滤后的项目列表
const filteredProjects = computed(() => {
  if (!searchKeyword.value.trim()) return projects.value
  const keyword = searchKeyword.value.toLowerCase().trim()
  return projects.value.filter(project =>
    project.name.toLowerCase().includes(keyword) ||
    project.description.toLowerCase().includes(keyword)
  )
})

// 导航到工具页面
const navigateTo = (path: string) => {
  router.push(path)
}

// 加载动态临床智能体
onMounted(async () => {
  try {
    loading.value = true
    const res = await listClinicalAgents()
    if (res.code === 200 && res.data) {
      dynamicAgents.value = res.data
    }
  } catch (e) {
    console.error('[ClinicalTools] Failed to load dynamic agents:', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* ==================== 整体布局 ==================== */
.clinical-tools {
  min-height: 100%;
  background: var(--bg-secondary);
}

/* ==================== Hero 横幅 ==================== */
.tools-hero {
  position: relative;
  background: linear-gradient(135deg, #0c1a3a 0%, #1a3a7c 55%, #0d6b8f 100%);
  padding: 44px 32px 40px;
  overflow: hidden;
}

.hero-decor {
  position: absolute;
  border-radius: 50%;
  opacity: 0.08;
  pointer-events: none;
}

.hero-decor-1 {
  width: 360px;
  height: 360px;
  background: #fff;
  top: -120px;
  right: 80px;
}

.hero-decor-2 {
  width: 220px;
  height: 220px;
  background: #60c8f5;
  bottom: -80px;
  left: 60px;
  opacity: 0.12;
}

.hero-inner {
  position: relative;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 40px;
  flex-wrap: wrap;
}

.hero-text {
  display: flex;
  align-items: center;
  gap: 18px;
  flex: 1;
  min-width: 0;
}

.hero-icon-wrap {
  font-size: 40px;
  width: 64px;
  height: 64px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.18);
}

.hero-title {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 6px 0;
  letter-spacing: -0.3px;
}

.hero-subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.65);
  margin: 0;
  line-height: 1.5;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 0 0 500px;
}

.hero-actions .search-input {
  flex: 1;
}

.create-agent-btn {
  white-space: nowrap;
  flex-shrink: 0;
  height: 40px;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
  color: #fff;
  border-radius: 10px;
}

.create-agent-btn:hover {
  background: rgba(255, 255, 255, 0.26) !important;
  border-color: rgba(255, 255, 255, 0.55) !important;
  color: #fff !important;
}

.hero-actions .search-input :deep(.ant-input-affix-wrapper) {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.25);
  border-radius: 10px 0 0 10px;
  color: #fff;
}

.hero-actions .search-input :deep(.ant-input-affix-wrapper:hover),
.hero-actions .search-input :deep(.ant-input-affix-wrapper-focused) {
  border-color: rgba(255, 255, 255, 0.55);
  background: rgba(255, 255, 255, 0.18);
}

.hero-actions .search-input :deep(.ant-input) {
  background: transparent;
  color: #fff;
}

.hero-actions .search-input :deep(.ant-input::placeholder) {
  color: rgba(255, 255, 255, 0.45);
}

.hero-actions .search-input :deep(.ant-input-prefix) {
  color: rgba(255, 255, 255, 0.55);
}

.hero-actions .search-input :deep(.ant-input-search-button) {
  border-radius: 0 10px 10px 0;
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.25);
  color: #fff;
}

.hero-actions .search-input :deep(.ant-input-search-button:hover) {
  background: rgba(255, 255, 255, 0.32);
  border-color: rgba(255, 255, 255, 0.5);
}

/* ==================== 主内容区 ==================== */
.tools-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 32px;
}

.main-container {
  width: 100%;
}

/* 加载和空状态 */
.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
}

.loading-state p,
.empty-text {
  font-size: 16px;
  color: var(--text-secondary);
  margin-top: 16px;
}

.empty-hint {
  font-size: 14px;
  color: var(--text-tertiary);
  margin-top: 8px;
}

/* 区块标题 */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.results-count {
  font-size: 14px;
  color: var(--text-secondary);
}

/* ==================== 项目网格 ==================== */
.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
}

/* ==================== 项目卡片 ==================== */
.project-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  overflow: hidden;
  transition: all 0.25s ease;
}

.project-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
  border-color: transparent;
}

/* 项目头部 */
.project-header {
  padding: 24px 24px 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}

/* 头像 */
.project-avatar {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.project-avatar-text {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.5px;
  line-height: 1;
}

.project-info {
  flex: 1;
  min-width: 0;
}

.project-name {
  font-size: 17px;
  font-weight: 600;
  margin: 0 0 6px 0;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-description {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ==================== 工具列表 ==================== */
.tools-list {
  padding: 0 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 工具项 */
.tool-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--bg-secondary);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.tool-item:hover {
  background: color-mix(in srgb, var(--link-color) 6%, var(--bg-primary));
  border-color: color-mix(in srgb, var(--link-color) 30%, transparent);
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.08);
}

.tool-item-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tool-icon-wrapper {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-icon {
  font-size: 18px;
}

.tool-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.tool-arrow {
  flex-shrink: 0;
  color: var(--border-color);
  font-size: 12px;
  transition: all 0.2s ease;
}

.tool-item:hover .tool-arrow {
  color: var(--link-color);
  transform: translateX(2px);
}

/* 卡片编辑按钮 */
.card-edit-btn {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border: none;
  background: transparent;
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.18s ease;
  align-self: flex-start;
  margin-top: 2px;
}

.card-edit-btn:hover {
  background: color-mix(in srgb, var(--link-color) 10%, transparent);
  color: var(--link-color);
}

.card-delete-btn {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border: none;
  background: transparent;
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.18s ease;
  align-self: flex-start;
  margin-top: 2px;
}

.card-delete-btn:hover {
  background: color-mix(in srgb, #ff4d4f 10%, transparent);
  color: #ff4d4f;
}

/* ==================== 响应式设计 ==================== */
@media (max-width: 1200px) {
  .projects-grid {
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  }
}

@media (max-width: 768px) {
  .tools-hero {
    padding: 32px 20px 28px;
  }

  .hero-inner {
    flex-direction: column;
    gap: 20px;
    align-items: flex-start;
  }

  .hero-actions {
    flex: 1;
    width: 100%;
  }

  .hero-icon-wrap {
    width: 52px;
    height: 52px;
    font-size: 32px;
    border-radius: 13px;
  }

  .hero-title {
    font-size: 22px;
  }

  .hero-subtitle {
    font-size: 13px;
  }

  .tools-main {
    padding: 24px 20px;
  }

  .projects-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .project-header {
    padding: 20px 20px 16px;
  }

  .project-avatar {
    width: 48px;
    height: 48px;
    border-radius: 12px;
  }

  .project-avatar-text {
    font-size: 16px;
  }

  .project-name {
    font-size: 16px;
  }
}

@media (max-width: 480px) {
  .tools-hero {
    padding: 24px 16px 22px;
  }

  .hero-text {
    gap: 12px;
  }

  .hero-icon-wrap {
    width: 44px;
    height: 44px;
    font-size: 26px;
  }

  .hero-title {
    font-size: 19px;
  }

  .tools-main {
    padding: 16px;
  }

  .tools-list {
    padding: 0 12px 12px;
  }
}
</style>
