<template>
  <div class="clinical-tools">
    <!-- ==================== 顶部导航栏 ==================== -->
    <div class="tools-header">
      <div class="header-container">
        <div class="header-content">
          <div class="header-left">
            <div class="logo-wrapper">
              <div class="logo-icon">🏥</div>
              <div class="logo-info">
                <h1 class="logo-title">{{ t('views_ClinicalToolsView.logoText') }}</h1>
                <p class="logo-subtitle">{{ t('views_ClinicalToolsView.headerDescription') }}</p>
              </div>
            </div>
          </div>
          <div class="header-right">
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
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 分类标签栏 ==================== -->
    <div class="categories-bar">
      <div class="categories-container">
        <div
          v-for="cat in categories"
          :key="cat.key"
          :class="['category-tab', { active: selectedCategory === cat.key }]"
          @click="selectCategory(cat.key)"
        >
          {{ cat.label }}
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
          <InboxOutlined style="font-size: 64px; color: #dadce0" />
          <p class="empty-text">{{ t('views_ClinicalToolsView.emptyText') }}</p>
          <p class="empty-hint">{{ t('views_ClinicalToolsView.emptyHint') }}</p>
        </div>

        <!-- 项目网格 -->
        <div v-else>
          <!-- 区块标题 -->
          <div class="section-header">
            <h2 class="section-title">
              {{ selectedCategory === 'all'
                ? t('views_ClinicalToolsView.sectionTitle')
                : categories.find(c => c.key === selectedCategory)?.label }}
            </h2>
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
                <div class="project-icon-wrapper">
                  <Icon :icon="project.icon" class="project-icon" />
                </div>
                <div class="project-info">
                  <h2 class="project-name">{{ project.name }}</h2>
                  <p class="project-description">{{ project.description }}</p>
                </div>
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
                    <div class="tool-icon-wrapper">
                      <Icon :icon="tool.icon" class="tool-icon" :style="{ color: tool.iconColor }" />
                    </div>
                    <div class="tool-info">
                      <h3 class="tool-name">{{ tool.name }}</h3>
                      <p class="tool-description">{{ tool.description }}</p>
                    </div>
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
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { SearchOutlined, RightOutlined, InboxOutlined } from '@ant-design/icons-vue'
import { Icon } from '@iconify/vue'

const router = useRouter()
const { t } = useI18n()

// 工具数据接口
interface Tool {
  id: string
  name: string
  description: string
  icon: string
  iconColor: string
  route: string
}

// 项目数据接口
interface Project {
  id: string
  name: string
  description: string
  icon: string
  category: string
  tools: Tool[]
}

// 分类接口
interface Category {
  key: string
  label: string
}

// 状态
const searchKeyword = ref('')
const selectedCategory = ref('all')
const loading = ref(false)

// 分类列表
const categories = computed<Category[]>(() => [
  { key: 'all', label: t('views_ClinicalToolsView.categories.all') },
  { key: 'segmentation', label: t('views_ClinicalToolsView.categories.segmentation') },
  { key: 'neoadjuvant', label: t('views_ClinicalToolsView.categories.neoadjuvant') }
])

// 项目数据
const projects = computed<Project[]>(() => [
  {
    id: 'gl-nict',
    name: t('views_ClinicalToolsView.projects.glNict.name'),
    description: t('views_ClinicalToolsView.projects.glNict.description'),
    icon: 'healthicons:medical-records',
    category: 'neoadjuvant',
    tools: [
      {
        id: 'gl-nict-agent',
        name: t('views_ClinicalToolsView.tools.glNictAgent.name'),
        description: t('views_ClinicalToolsView.tools.glNictAgent.description'),
        icon: 'carbon:bot',
        iconColor: '#52c41a',
        route: '/gl-nict-agent'
      },
      {
        id: 'gl-nict-knowledge-base',
        name: t('views_ClinicalToolsView.tools.glNictKnowledgeBase.name'),
        description: t('views_ClinicalToolsView.tools.glNictKnowledgeBase.description'),
        icon: 'healthicons:i-documents-accepted',
        iconColor: '#faad14',
        route: '/gl-nict-knowledge-base'
      }
    ]
  }
])

// 过滤后的项目列表
const filteredProjects = computed(() => {
  let result = projects.value

  // 按分类筛选
  if (selectedCategory.value !== 'all') {
    result = result.filter(project => project.category === selectedCategory.value)
  }

  // 按搜索关键词筛选
  if (searchKeyword.value.trim()) {
    const keyword = searchKeyword.value.toLowerCase().trim()
    result = result.filter(project => {
      // 搜索项目名称和描述
      const projectMatch = project.name.toLowerCase().includes(keyword) ||
                          project.description.toLowerCase().includes(keyword)

      // 搜索工具名称和描述
      const toolMatch = project.tools.some(tool =>
        tool.name.toLowerCase().includes(keyword) ||
        tool.description.toLowerCase().includes(keyword)
      )

      return projectMatch || toolMatch
    })
  }

  return result
})

// 选择分类
const selectCategory = (category: string) => {
  selectedCategory.value = category
}

// 导航到工具页面
const navigateTo = (path: string) => {
  router.push(path)
}
</script>

<style scoped>
/* ==================== 整体布局 ==================== */
.clinical-tools {
  min-height: 100vh;
  background: #f5f7fa;
}

/* ==================== 顶部导航栏 ==================== */
.tools-header {
  background: white;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.header-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px 32px;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
}

.header-left {
  flex: 1;
  min-width: 0;
}

.logo-wrapper {
  display: flex;
  align-items: center;
  gap: 16px;
}

.logo-icon {
  width: 48px;
  height: 48px;
  font-size: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  flex-shrink: 0;
}

.logo-info {
  flex: 1;
  min-width: 0;
}

.logo-title {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 4px 0;
}

.logo-subtitle {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
  line-height: 1.5;
}

.header-right {
  flex: 0 0 400px;
}

.search-input {
  border-radius: 8px;
}

/* ==================== 分类标签栏 ==================== */
.categories-bar {
  background: white;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 89px;
  z-index: 99;
}

.categories-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 32px;
  display: flex;
  gap: 32px;
  overflow-x: auto;
  scrollbar-width: none;
}

.categories-container::-webkit-scrollbar {
  display: none;
}

.category-tab {
  padding: 16px 0;
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
  cursor: pointer;
  white-space: nowrap;
  border-bottom: 2px solid transparent;
  transition: all 0.2s ease;
}

.category-tab:hover {
  color: #1890ff;
}

.category-tab.active {
  color: #1890ff;
  border-bottom-color: #1890ff;
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
  color: #6b7280;
  margin-top: 16px;
}

.empty-hint {
  font-size: 14px;
  color: #9ca3af;
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
  color: #1f2937;
  margin: 0;
}

.results-count {
  font-size: 14px;
  color: #6b7280;
}

/* ==================== 项目网格 ==================== */
.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
  gap: 24px;
}

/* ==================== 项目卡片 ==================== */
.project-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.2s ease;
}

.project-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: #d1d5db;
}

/* 项目头部 */
.project-header {
  padding: 24px;
  border-bottom: 1px solid #f3f4f6;
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.project-icon-wrapper {
  width: 56px;
  height: 56px;
  background: #eff6ff;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.project-icon {
  font-size: 32px;
  color: #1890ff;
}

.project-info {
  flex: 1;
  min-width: 0;
}

.project-name {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: #1f2937;
}

.project-description {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
  line-height: 1.6;
}

/* ==================== 工具列表 ==================== */
.tools-list {
  padding: 20px;
}

/* 工具项 */
.tool-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  margin-bottom: 12px;
  background: #f9fafb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.tool-item:last-child {
  margin-bottom: 0;
}

.tool-item:hover {
  background: white;
  border-color: #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.1);
}

.tool-item-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.tool-icon-wrapper {
  width: 40px;
  height: 40px;
  background: white;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-icon {
  font-size: 24px;
}

.tool-info {
  flex: 1;
  min-width: 0;
}

.tool-name {
  font-size: 15px;
  font-weight: 500;
  color: #1f2937;
  margin: 0 0 4px 0;
}

.tool-description {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
  line-height: 1.5;
}

.tool-arrow {
  flex-shrink: 0;
  color: #d1d5db;
  font-size: 14px;
  transition: all 0.2s ease;
}

.tool-item:hover .tool-arrow {
  color: #1890ff;
}

/* ==================== 响应式设计 ==================== */
@media (max-width: 1200px) {
  .projects-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .header-container {
    padding: 16px 20px;
  }

  .header-content {
    flex-direction: column;
    gap: 16px;
  }

  .header-right {
    flex: 1;
    width: 100%;
  }

  .logo-icon {
    width: 40px;
    height: 40px;
    font-size: 28px;
    border-radius: 10px;
  }

  .logo-title {
    font-size: 20px;
  }

  .logo-subtitle {
    font-size: 13px;
  }

  .categories-bar {
    top: 120px;
  }

  .categories-container {
    padding: 0 20px;
    gap: 24px;
  }

  .tools-main {
    padding: 24px 20px;
  }

  .projects-grid {
    gap: 20px;
  }

  .project-header {
    padding: 20px;
  }

  .project-icon-wrapper {
    width: 48px;
    height: 48px;
  }

  .project-icon {
    font-size: 28px;
  }

  .project-name {
    font-size: 18px;
  }

  .project-description {
    font-size: 13px;
  }

  .tools-list {
    padding: 16px;
  }

  .tool-item {
    padding: 14px;
  }

  .tool-icon-wrapper {
    width: 36px;
    height: 36px;
  }

  .tool-icon {
    font-size: 20px;
  }

  .tool-name {
    font-size: 14px;
  }

  .tool-description {
    font-size: 12px;
  }
}

@media (max-width: 480px) {
  .header-container {
    padding: 12px 16px;
  }

  .logo-wrapper {
    gap: 12px;
  }

  .logo-icon {
    width: 36px;
    height: 36px;
    font-size: 24px;
  }

  .logo-title {
    font-size: 18px;
  }

  .tools-main {
    padding: 20px 16px;
  }

  .project-header {
    padding: 16px;
    flex-direction: column;
  }

  .project-icon-wrapper {
    width: 44px;
    height: 44px;
  }

  .project-icon {
    font-size: 24px;
  }

  .project-name {
    font-size: 16px;
  }

  .tools-list {
    padding: 12px;
  }

  .tool-item {
    padding: 12px;
    margin-bottom: 10px;
  }

  .tool-item-left {
    gap: 10px;
  }
}
</style>
