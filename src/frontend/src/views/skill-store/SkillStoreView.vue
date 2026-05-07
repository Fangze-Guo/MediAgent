<template>
  <div class="skill-store">
    <!-- 顶部导航栏 -->
    <div class="store-header">
      <div class="header-container">
        <div class="store-logo">
          <span class="logo-icon">🛠️</span>
          <span class="logo-text">技能仓库</span>
        </div>
        
        <div class="search-box">
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="搜索技能名称或描述"
            size="large"
            @search="handleSearch"
            class="search-input"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input-search>
        </div>
      </div>
    </div>

    <!-- 分类标签栏 -->
    <div class="categories-bar">
      <div class="categories-container">
        <div
          v-for="cat in categories"
          :key="cat"
          :class="['category-tab', { active: selectedCategory === cat }]"
          @click="selectCategory(cat)"
        >
          {{ cat }}
        </div>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="store-main">
      <div class="main-container">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-state">
          <a-spin size="large" />
          <p>加载中...</p>
        </div>

        <!-- 空状态 -->
        <div v-else-if="skills.length === 0" class="empty-state">
          <InboxOutlined style="font-size: 64px; color: #dadce0" />
          <p class="empty-text">未找到匹配的技能</p>
          <p class="empty-hint">尝试调整搜索条件或选择其他分类</p>
        </div>

        <!-- 技能网格 -->
        <div v-else>
          <div class="section-header">
            <h2 class="section-title">
              {{ selectedCategory === '全部' ? '所有技能' : selectedCategory }}
            </h2>
            <span class="results-count">共 {{ skills.length }} 个技能</span>
          </div>
          
          <div class="skills-grid">
            <div
              v-for="skill in skills"
              :key="skill.id"
              class="skill-card"
              @click="goToSkillDetail(skill.id)"
            >
              <div class="card-header">
                <div class="skill-icon-wrapper">
                  <span class="skill-icon">{{ skill.icon }}</span>
                </div>
                <div class="skill-basic-info">
                  <h3 class="skill-name">{{ skill.name }}</h3>
                  <p class="skill-author">{{ skill.author }}</p>
                </div>
              </div>
              
              <p class="skill-description">{{ skill.description }}</p>
              
              <div class="card-footer">
                <span class="skill-category-badge">{{ skill.category }}</span>
                <a-button class="view-btn" size="small">
                  查看详情
                </a-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { SearchOutlined, InboxOutlined } from '@ant-design/icons-vue'
import { getSkills, getSkillCategories, type SkillInfo } from '@/apis/skills'

const router = useRouter()

// 响应式状态
const loading = ref(true)
const skills = ref<SkillInfo[]>([])
const categories = ref<string[]>([])
const selectedCategory = ref('全部')
const searchKeyword = ref('')

// 组件挂载时执行
onMounted(async () => {
  await loadCategories()
  await loadSkills()
})

// 加载分类列表
const loadCategories = async () => {
  try {
    const data = await getSkillCategories()
    categories.value = data
  } catch (error) {
    console.error('加载分类失败', error)
  }
}

// 加载技能列表
const loadSkills = async () => {
  loading.value = true
  try {
    const category = selectedCategory.value === '全部' ? undefined : selectedCategory.value
    const data = await getSkills(category, searchKeyword.value)
    skills.value = data
  } catch (error) {
    console.error('加载技能列表失败', error)
    message.error('加载技能列表失败')
  } finally {
    loading.value = false
  }
}

// 选择分类
const selectCategory = (category: string) => {
  selectedCategory.value = category
  searchKeyword.value = ''
  loadSkills()
}

// 处理搜索
const handleSearch = () => {
  loadSkills()
}

// 跳转到技能详情页
const goToSkillDetail = (id: string) => {
  router.push(`/skill-store/${id}`)
}
</script>

<style scoped>
.skill-store {
  min-height: 100vh;
  background: var(--bg-primary);
}

/* 顶部导航栏 */
.store-header {
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  gap: 40px;
}

.store-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}

.logo-icon {
  font-size: 28px;
}

.search-box {
  flex: 1;
  max-width: 720px;
}

.search-input {
  border-radius: 24px;
}

.search-input :deep(.ant-input) {
  border-radius: 24px;
}

.search-input :deep(.ant-input-group-addon) {
  border-radius: 0 24px 24px 0;
}

/* 分类标签栏 */
.categories-bar {
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 65px;
  z-index: 99;
}

.categories-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
}

.categories-container::-webkit-scrollbar {
  display: none;
}

.category-tab {
  padding: 14px 20px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  border-bottom: 3px solid transparent;
  transition: all 0.2s;
  white-space: nowrap;
  user-select: none;
}

.category-tab:hover {
  color: var(--link-color);
  background: var(--hover-bg);
}

.category-tab.active {
  color: var(--link-color);
  border-bottom-color: var(--link-color);
}

/* 主内容区 */
.store-main {
  background: var(--bg-primary);
  min-height: calc(100vh - 200px);
}

.main-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 32px 24px;
}

/* 加载和空状态 */
.loading-state,
.empty-state {
  text-align: center;
  padding: 80px 20px;
}

.loading-state p {
  margin-top: 16px;
  color: var(--text-secondary);
  font-size: 16px;
}

.empty-text {
  font-size: 20px;
  color: var(--text-secondary);
  margin: 16px 0 8px 0;
}

.empty-hint {
  font-size: 14px;
  color: var(--text-tertiary);
  margin: 0;
}

/* 区块标题 */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.section-title {
  font-size: 24px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
}

.results-count {
  font-size: 14px;
  color: var(--text-secondary);
}

/* 技能网格布局 */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
}

/* 技能卡片 */
.skill-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
}

.skill-card:hover {
  box-shadow: 0 1px 3px 1px rgba(60, 64, 67, 0.15);
  border-color: var(--border-color-light);
}

.card-header {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.skill-icon-wrapper {
  flex-shrink: 0;
}

.skill-icon {
  font-size: 48px;
  line-height: 1;
  display: block;
}

.skill-basic-info {
  flex: 1;
  min-width: 0;
}

.skill-name {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skill-author {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skill-description {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 16px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--bg-secondary);
}

.skill-category-badge {
  font-size: 11px;
  color: #1a73e8;
  background: #e8f0fe;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.view-btn {
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
}
</style>
