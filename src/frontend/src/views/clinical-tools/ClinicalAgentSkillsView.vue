<template>
  <div class="agent-skills-view">
    <!-- ==================== Hero 横幅 ==================== -->
    <div class="skills-hero">
      <div class="hero-decor hero-decor-1"></div>
      <div class="hero-decor hero-decor-2"></div>
      <div class="hero-inner">
        <div class="hero-left">
          <button class="back-btn" @click="goBack" title="返回">
            <LeftOutlined />
          </button>
          <div class="hero-text">
            <div class="hero-icon-wrap">⚙️</div>
            <div>
              <h1 class="hero-title">Skill 管理</h1>
              <p class="hero-subtitle">{{ agentName }} · 管理该智能体可用的技能</p>
            </div>
          </div>
        </div>
        <div class="hero-stats">
          <div class="stat-item">
            <span class="stat-num">{{ installedIds.length }}</span>
            <span class="stat-label">已安装</span>
          </div>
          <span class="stat-sep">/</span>
          <div class="stat-item">
            <span class="stat-num">{{ allSkills.length }}</span>
            <span class="stat-label">全部</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 主内容区 ==================== -->
    <div class="skills-body">

      <!-- 筛选 & 搜索栏 -->
      <div class="filter-bar">
        <div class="filter-tabs">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            :class="['filter-tab', { active: activeTab === tab.key }]"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
            <span v-if="tab.key === 'installed'" class="tab-badge">{{ installedIds.length }}</span>
          </button>
        </div>
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="搜索 Skill 名称或描述"
          class="skill-search"
          allow-clear
        />
      </div>

      <!-- 加载态 -->
      <div v-if="loading" class="state-center">
        <a-spin size="large" />
        <p class="state-text">加载中...</p>
      </div>

      <!-- 空态 -->
      <div v-else-if="filteredSkills.length === 0" class="state-center">
        <InboxOutlined class="state-icon" />
        <p class="state-title">{{ activeTab === 'installed' ? '该智能体尚未安装任何 Skill' : '未找到匹配的 Skill' }}</p>
        <p class="state-hint">{{ activeTab === 'installed' ? '从「全部」标签页浏览并安装' : '尝试调整搜索条件' }}</p>
      </div>

      <!-- Skill 网格 -->
      <div v-else class="skills-grid">
        <div
          v-for="skill in filteredSkills"
          :key="skill.id"
          :class="['skill-card', { 'is-installed': isInstalled(skill.id) }]"
        >
          <!-- 卡片顶部 -->
          <div class="card-top">
            <div class="skill-icon-wrap">
              <span
                v-if="isSvgIcon(getSkillIcon(skill.type))"
                v-html="getSkillIcon(skill.type)"
                class="skill-emoji"
              />
              <span v-else class="skill-emoji">{{ getSkillIcon(skill.type) }}</span>
            </div>
            <div class="card-badges">
              <span class="type-badge">{{ skill.type }}</span>
              <span v-if="isInstalled(skill.id)" class="installed-badge">
                <CheckCircleFilled /> 已安装
              </span>
            </div>
          </div>

          <!-- 卡片内容 -->
          <h3 class="skill-name">{{ skill.name }}</h3>
          <p class="skill-desc">{{ skill.description }}</p>

          <!-- 卡片底部 -->
          <div class="card-footer">
            <div class="footer-left">
              <span class="skill-version">v{{ skill.version }}</span>
              <span class="skill-author">
                <UserOutlined /> {{ skill.author || 'Unknown' }}
              </span>
            </div>
            <a-button
              v-if="isInstalled(skill.id)"
              size="small"
              danger
              :loading="operatingId === skill.id"
              @click.stop="handleUninstall(skill)"
            >卸载</a-button>
            <a-button
              v-else
              size="small"
              type="primary"
              :loading="operatingId === skill.id"
              @click.stop="handleInstall(skill)"
            >安装</a-button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  LeftOutlined,
  InboxOutlined,
  UserOutlined,
  CheckCircleFilled
} from '@ant-design/icons-vue'
import { getSkills, type SkillInfo } from '@/apis/skills'
import { listInstalledSkills, installSkill, uninstallSkill } from '@/apis/agents'
import { getSkillIcon, isSvgIcon } from '@/utils/skillIcon'

const route = useRoute()
const router = useRouter()

const agentId = computed(() => route.params.agentId as string)
const agentName = computed(() => (route.query.name as string) || '智能体')

// ==================== 状态 ====================
const loading = ref(false)
const allSkills = ref<SkillInfo[]>([])
const installedIds = ref<string[]>([])
const operatingId = ref<string | null>(null)
const searchKeyword = ref('')
const activeTab = ref<'all' | 'installed'>('all')

const tabs: { key: 'all' | 'installed'; label: string }[] = [
  { key: 'all', label: '全部 Skill' },
  { key: 'installed', label: '已安装' },
]

// ==================== 计算 ====================
const isInstalled = (skillId: string) => installedIds.value.includes(skillId)

/**
 * 已安装列表：以 installedIds 为权威来源，从 allSkills 中取详情；
 * 若某个 slug 在全局列表中找不到（手动添加等情况），用 slug 生成占位对象保证显示。
 */
const installedSkillsList = computed<SkillInfo[]>(() =>
  installedIds.value.map(slug => {
    const found = allSkills.value.find(s => s.id === slug)
    if (found) return found
    return {
      id: slug,
      name: slug,
      type: 'installed',
      description: '',
      version: '-',
      author: '',
      downloads: 0,
      rating: 0,
      installed: true,
      featured: false,
      tags: [],
    }
  })
)

const filteredSkills = computed(() => {
  const base = activeTab.value === 'installed' ? installedSkillsList.value : allSkills.value
  const kw = searchKeyword.value.toLowerCase().trim()
  if (!kw) return base
  return base.filter(s =>
    s.name.toLowerCase().includes(kw) ||
    s.description.toLowerCase().includes(kw) ||
    s.type.toLowerCase().includes(kw)
  )
})

// ==================== 操作 ====================
const handleInstall = async (skill: SkillInfo) => {
  operatingId.value = skill.id
  try {
    await installSkill(agentId.value, skill.id)
    installedIds.value.push(skill.id)
    message.success(`已安装 ${skill.name}`)
  } catch {
    message.error(`安装 ${skill.name} 失败`)
  } finally {
    operatingId.value = null
  }
}

const handleUninstall = async (skill: SkillInfo) => {
  operatingId.value = skill.id
  try {
    await uninstallSkill(agentId.value, skill.id)
    installedIds.value = installedIds.value.filter(id => id !== skill.id)
    message.success(`已卸载 ${skill.name}`)
  } catch {
    message.error(`卸载 ${skill.name} 失败`)
  } finally {
    operatingId.value = null
  }
}

const goBack = () => router.push('/clinical-tools')

// ==================== 初始化 ====================
onMounted(async () => {
  loading.value = true
  try {
    const [skills, installed] = await Promise.all([
      getSkills(),
      listInstalledSkills(agentId.value)
    ])
    allSkills.value = skills
    if (installed.code === 200 && Array.isArray(installed.data)) {
      installedIds.value = installed.data
    }
  } catch {
    message.error('加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* ==================== 整体布局 ==================== */
.agent-skills-view {
  min-height: 100%;
  background: var(--bg-secondary);
}

/* ==================== Hero 横幅 ==================== */
.skills-hero {
  position: relative;
  background: linear-gradient(135deg, #2d0a14 0%, #6b1a2e 55%, #a0243e 100%);
  padding: 44px 32px 40px;
  overflow: hidden;
}

.hero-decor {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.hero-decor-1 {
  width: 340px;
  height: 340px;
  background: #fff;
  opacity: 0.07;
  top: -110px;
  right: 60px;
}

.hero-decor-2 {
  width: 220px;
  height: 220px;
  background: #ffb3c6;
  opacity: 0.1;
  bottom: -80px;
  left: 80px;
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

.hero-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
}

.back-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.22);
}

.hero-text {
  display: flex;
  align-items: center;
  gap: 18px;
  min-width: 0;
}

.hero-icon-wrap {
  font-size: 36px;
  width: 60px;
  height: 60px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.18);
}

.hero-title {
  font-size: 26px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 5px 0;
  letter-spacing: -0.3px;
}

.hero-subtitle {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.65);
  margin: 0;
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Stats */
.hero-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 14px;
  padding: 14px 24px;
  backdrop-filter: blur(4px);
  flex-shrink: 0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  line-height: 1;
}

.stat-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
  letter-spacing: 0.5px;
}

.stat-sep {
  font-size: 20px;
  color: rgba(255, 255, 255, 0.3);
  font-weight: 300;
}

/* ==================== 主内容区 ==================== */
.skills-body {
  max-width: 1400px;
  margin: 0 auto;
  padding: 32px;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.filter-tabs {
  display: flex;
  gap: 4px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 4px;
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  border: none;
  background: transparent;
  border-radius: 7px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
}

.filter-tab.active {
  background: var(--bg-secondary);
  color: var(--text-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.filter-tab:hover:not(.active) {
  color: var(--text-primary);
}

.tab-badge {
  font-size: 11px;
  font-weight: 600;
  background: #a0243e;
  color: #fff;
  border-radius: 10px;
  padding: 0 6px;
  min-width: 18px;
  text-align: center;
  line-height: 18px;
}

.skill-search {
  width: 280px;
}

/* ==================== 状态 ==================== */
.state-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 12px;
  text-align: center;
}

.state-icon {
  font-size: 56px;
  color: var(--border-color);
}

.state-text,
.state-title {
  font-size: 16px;
  color: var(--text-secondary);
  margin: 0;
}

.state-hint {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0;
}

/* ==================== Skill 网格 ==================== */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

/* ==================== Skill 卡片 ==================== */
.skill-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 20px 22px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: box-shadow 0.2s, border-color 0.2s, transform 0.15s;
}

.skill-card:hover {
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.skill-card.is-installed {
  border-color: rgba(160, 36, 62, 0.25);
  background: color-mix(in srgb, #a0243e 3%, var(--bg-primary));
}

.skill-card.is-installed:hover {
  border-color: rgba(160, 36, 62, 0.45);
}

/* 卡片顶部 */
.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.skill-icon-wrap {
  width: 46px;
  height: 46px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--link-color) 10%, var(--bg-secondary));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.skill-emoji {
  font-size: 24px;
  line-height: 1;
}

.card-badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.type-badge {
  font-size: 10px;
  font-weight: 600;
  color: var(--link-color);
  background: color-mix(in srgb, var(--link-color) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--link-color) 25%, transparent);
  padding: 2px 8px;
  border-radius: 20px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.installed-badge {
  font-size: 10px;
  font-weight: 600;
  color: #a0243e;
  background: rgba(160, 36, 62, 0.1);
  border: 1px solid rgba(160, 36, 62, 0.25);
  padding: 2px 8px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 卡片文字 */
.skill-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.skill-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 卡片底部 */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 10px;
  border-top: 1px solid var(--bg-secondary);
  margin-top: 2px;
}

.footer-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.skill-version {
  font-size: 11px;
  color: var(--text-tertiary);
}

.skill-author {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-tertiary);
}

/* ==================== 响应式 ==================== */
@media (max-width: 768px) {
  .skills-hero {
    padding: 32px 20px 28px;
  }

  .hero-inner {
    flex-direction: column;
    gap: 20px;
    align-items: flex-start;
  }

  .hero-stats {
    width: 100%;
    justify-content: center;
  }

  .skills-body {
    padding: 24px 16px;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .skill-search {
    width: 100%;
  }

  .skills-grid {
    grid-template-columns: 1fr;
  }
}
</style>
