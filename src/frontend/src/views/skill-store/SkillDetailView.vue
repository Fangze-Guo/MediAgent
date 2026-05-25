<template>
  <div class="skill-detail-page">
    <!-- 顶部导航栏 -->
    <div class="detail-header">
      <div class="header-container">
        <a-button type="text" @click="goBack" class="back-btn">
          <LeftOutlined />
          {{ t('views_SkillDetailView.backToStore') }}
        </a-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
      <p>{{ t('views_SkillDetailView.loading') }}</p>
    </div>

    <!-- 技能详情内容 -->
    <div v-else-if="skill" class="detail-content">
      <div class="content-container">
        <!-- 左侧主要内容 -->
        <div class="main-content">
          <!-- 技能头部信息 -->
          <div class="skill-header-section">
            <div v-if="isSvgIcon(getSkillIcon(skill.type))" class="skill-icon-large" v-html="getSkillIcon(skill.type)"></div>
            <div v-else class="skill-icon-large">{{ getSkillIcon(skill.type) }}</div>
            <div class="skill-header-info">
              <h1 class="skill-title">{{ skill.name }}</h1>
              <div class="skill-provider">{{ t('views_SkillDetailView.provider', { author: skill.author }) }}</div>
              <div class="skill-meta">
                <span class="meta-item">
                  <TagOutlined />
                  {{ skill.type }}
                </span>
                <span class="meta-item">
                  <FileTextOutlined />
                  {{ t('views_SkillDetailView.localSkill') }}
                </span>
              </div>
            </div>
          </div>

          <!-- 文件浏览器 -->
          <div class="section files-section">
            <h2 class="section-title">
              <FolderOpenOutlined style="margin-right: 8px" />
              {{ t('views_SkillDetailView.fileBrowser') }}
            </h2>
            <div class="files-content">
              <GitHubStyleFileList :skill-id="skillId" :project-id="projectId" />
            </div>
          </div>

          <!-- Skill 说明文档 -->
          <div class="section markdown-section">
            <h2 class="section-title">
              <FileTextOutlined style="margin-right: 8px" />
              README
            </h2>
            <div class="markdown-content">
              <MarkdownRenderer
                :content="skill.full_description || skill.features || ''"
                :enable-highlight="true"
              />
            </div>
          </div>
        </div>

        <!-- 右侧信息栏 -->
        <div class="sidebar-content">
          <div class="info-card">
            <h3 class="card-title">{{ t('views_SkillDetailView.skillInfo') }}</h3>
            <div class="info-list">
              <div class="info-item">
                <span class="info-label">ID</span>
                <span class="info-value">{{ skill.id }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">{{ t('views_SkillDetailView.type') }}</span>
                <span class="info-value">{{ skill.type }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">{{ t('views_SkillDetailView.version') }}</span>
                <span class="info-value">{{ skill.version }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">{{ t('views_SkillDetailView.author') }}</span>
                <span class="info-value">{{ skill.author }}</span>
              </div>
            </div>
          </div>

          <!-- 相关技能 -->
          <div v-if="relatedSkills.length > 0" class="info-card">
            <h3 class="card-title">{{ t('views_SkillDetailView.relatedSkills') }}</h3>
            <div class="related-skills">
              <div
                v-for="related in relatedSkills"
                :key="related.id"
                class="related-skill-item"
                @click="goToSkill(related.id)"
              >
                <span v-if="isSvgIcon(getSkillIcon(related.type))" class="related-icon" v-html="getSkillIcon(related.type)"></span>
                <span v-else class="related-icon">{{ getSkillIcon(related.type) }}</span>
                <span class="related-name">{{ related.name }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-else class="error-container">
      <InboxOutlined style="font-size: 64px; color: #dadce0" />
      <p class="error-text">{{ t('views_SkillDetailView.skillNotFound') }}</p>
      <a-button type="primary" @click="goBack">{{ t('views_SkillDetailView.back') }}</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  LeftOutlined,
  TagOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  InboxOutlined
} from '@ant-design/icons-vue'
import { getSkillDetail, getSkills, type SkillInfo } from '@/apis/skills'
import { getSkillIcon, isSvgIcon } from '@/utils/skillIcon'
import MarkdownRenderer from '@/components/markdown/MarkdownRenderer.vue'
import GitHubStyleFileList from '@/components/skill-store/GitHubStyleFileList.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// 从路由 query 读取 project_id
const projectId = computed(() => (route.query.project_id as string) || undefined)

// 响应式状态
const loading = ref(true)
const skill = ref<SkillInfo | null>(null)
const relatedSkills = ref<SkillInfo[]>([])

// 技能ID
const skillId = computed(() => route.params.id as string)

// 加载技能详情
const loadSkillDetail = async () => {
  loading.value = true
  try {
    const data = await getSkillDetail(skillId.value, projectId.value)
    skill.value = data

    // 加载相关技能（同项目，不按类别筛选）
    const allSkills = await getSkills(undefined, undefined, projectId.value)
    relatedSkills.value = allSkills.filter(s => s.id !== skillId.value).slice(0, 5)
  } catch (error) {
    console.error(t('views_SkillDetailView.loadDetailFailed'), error)
    message.error(t('views_SkillDetailView.loadDetailFailed'))
  } finally {
    loading.value = false
  }
}

// 返回技能仓库（保留 project_id）
const goBack = () => {
  const query = projectId.value ? { project_id: projectId.value } : {}
  router.push({ path: '/skill-repository', query })
}

// 跳转到其他技能（保留 project_id）
const goToSkill = (id: string) => {
  const query = projectId.value ? { project_id: projectId.value } : {}
  router.push({ path: `/skill-repository/${id}`, query })
}

// 监听路由变化，重新加载数据
watch(() => route.params.id, () => {
  if (route.params.id) {
    loadSkillDetail()
  }
}, { immediate: false })

// 组件挂载时加载数据
onMounted(() => {
  loadSkillDetail()
})
</script>

<style scoped>
/* 页面布局 */
.skill-detail-page {
  min-height: 100vh;
  background: var(--bg-primary);
}

/* 顶部导航 */
.detail-header {
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 12px 24px;
}

.back-btn {
  font-size: 14px;
  color: var(--text-secondary);
}

.back-btn:hover {
  color: var(--link-color, #1a73e8);
}

/* 加载和错误状态 */
.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  gap: 16px;
}

.loading-container p {
  color: var(--text-secondary);
  font-size: 16px;
}

.error-text {
  font-size: 20px;
  color: var(--text-secondary);
  margin: 0;
}

/* 详情内容 */
.detail-content {
  max-width: 1280px;
  margin: 0 auto;
  padding: 32px 24px;
}

.content-container {
  display: flex;
  gap: 32px;
}

/* 左侧主要内容 */
.main-content {
  flex: 1;
  min-width: 0;
}

/* 技能头部 */
.skill-header-section {
  display: flex;
  gap: 24px;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
}

.skill-icon-large {
  font-size: 96px;
  line-height: 1;
  flex-shrink: 0;
}

.skill-icon-large :deep(svg) {
  width: 96px;
  height: 96px;
}

.skill-header-info {
  flex: 1;
}

.skill-title {
  font-size: 32px;
  font-weight: 500;
  margin: 0 0 8px 0;
  color: var(--text-primary);
}

.skill-provider {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 16px;
}

.skill-meta {
  display: flex;
  gap: 16px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 12px;
  background: var(--bg-secondary);
  border-radius: 12px;
}

/* Section 样式 */
.section {
  margin-bottom: 32px;
}

.section-title {
  font-size: 20px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
}

/* Markdown 内容 */
.markdown-section {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 24px;
}

.markdown-section .section-title {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.markdown-content {
  color: var(--text-primary);
  line-height: 1.6;
}

/* 文件浏览器 */
.files-section {
  background: var(--bg-primary);
}

.files-content {
  margin-top: 0;
}

/* 右侧信息栏 */
.sidebar-content {
  width: 300px;
  flex-shrink: 0;
}

.info-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.info-value {
  font-size: 13px;
  color: var(--text-primary);
  text-align: right;
}

/* 相关技能 */
.related-skills {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.related-skill-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.related-skill-item:hover {
  background: var(--hover-bg, var(--bg-secondary));
}

.related-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.related-name {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
