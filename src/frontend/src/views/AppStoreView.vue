<template>
  <div class="app-store">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">应用商店</h1>
          <p class="page-subtitle">探索和安装医疗AI应用工具</p>
        </div>
        <div class="search-section">
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="搜索应用..."
            size="large"
            @search="handleSearch"
            style="width: 300px"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input-search>
        </div>
      </div>
    </div>

    <div class="store-container">
      <!-- 分类导航 -->
      <div class="categories-sidebar">
        <div class="categories-title">分类</div>
        <div class="categories-list">
          <div
            v-for="cat in categories"
            :key="cat"
            :class="['category-item', { active: selectedCategory === cat }]"
            @click="selectCategory(cat)"
          >
            {{ cat }}
          </div>
        </div>
      </div>

      <!-- 应用列表 -->
      <div class="apps-main">
        <div v-if="loading" class="loading-state">
          <a-spin size="large" />
          <p>加载中...</p>
        </div>

        <div v-else-if="apps.length === 0" class="empty-state">
          <InboxOutlined style="font-size: 64px; color: #ccc" />
          <p>未找到相关应用</p>
        </div>

        <div v-else class="apps-grid">
          <div
            v-for="app in apps"
            :key="app.id"
            class="app-card"
            @click="showAppDetail(app)"
          >
            <div class="app-icon">{{ app.icon }}</div>
            <div class="app-info">
              <h3 class="app-name">{{ app.name }}</h3>
              <p class="app-description">{{ app.description }}</p>
              <div class="app-meta">
                <span class="app-category">{{ app.category }}</span>
                <span class="app-version">v{{ app.version }}</span>
              </div>
              <div class="app-stats">
                <span class="stat-item">
                  <StarFilled style="color: #faad14" />
                  {{ app.rating }}
                </span>
                <span class="stat-item">
                  <DownloadOutlined />
                  {{ formatNumber(app.downloads) }}
                </span>
              </div>
              <div class="app-tags">
                <a-tag v-for="tag in app.tags.slice(0, 3)" :key="tag" color="blue">
                  {{ tag }}
                </a-tag>
              </div>
            </div>
            <div class="app-action">
              <a-button
                v-if="app.installed"
                danger
                @click.stop="handleUninstall(app)"
              >
                卸载
              </a-button>
              <a-button
                v-else
                type="primary"
                @click.stop="handleInstall(app)"
              >
                安装
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 应用详情模态框 -->
    <a-modal
      v-model:open="detailVisible"
      :title="currentApp?.name"
      width="700px"
      :footer="null"
    >
      <div v-if="currentApp" class="app-detail">
        <div class="detail-header">
          <div class="detail-icon">{{ currentApp.icon }}</div>
          <div class="detail-info">
            <h2>{{ currentApp.name }}</h2>
            <div class="detail-meta">
              <span>版本: {{ currentApp.version }}</span>
              <span>作者: {{ currentApp.author }}</span>
              <span>分类: {{ currentApp.category }}</span>
            </div>
            <div class="detail-stats">
              <span>
                <StarFilled style="color: #faad14" />
                {{ currentApp.rating }} 评分
              </span>
              <span>
                <DownloadOutlined />
                {{ formatNumber(currentApp.downloads) }} 下载
              </span>
            </div>
          </div>
        </div>
        <div class="detail-description">
          <h3>应用简介</h3>
          <p>{{ currentApp.description }}</p>
        </div>
        <div class="detail-tags">
          <h3>标签</h3>
          <a-tag v-for="tag in currentApp.tags" :key="tag" color="blue">
            {{ tag }}
          </a-tag>
        </div>
        <div class="detail-actions">
          <a-button
            v-if="currentApp.installed"
            danger
            size="large"
            block
            @click="handleUninstall(currentApp)"
          >
            卸载应用
          </a-button>
          <a-button
            v-else
            type="primary"
            size="large"
            block
            @click="handleInstall(currentApp)"
          >
            安装应用
          </a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  SearchOutlined,
  InboxOutlined,
  StarFilled,
  DownloadOutlined
} from '@ant-design/icons-vue'
import { getApps, getCategories, installApp, uninstallApp, type AppInfo } from '@/apis/appStore'

const loading = ref(true)
const apps = ref<AppInfo[]>([])
const categories = ref<string[]>([])
const selectedCategory = ref('全部')
const searchKeyword = ref('')
const detailVisible = ref(false)
const currentApp = ref<AppInfo | null>(null)

onMounted(async () => {
  await loadCategories()
  await loadApps()
})

const loadCategories = async () => {
  try {
    const data = await getCategories()
    categories.value = data
  } catch (error) {
    console.error('加载分类失败', error)
  }
}

const loadApps = async () => {
  loading.value = true
  try {
    const category = selectedCategory.value === '全部' ? undefined : selectedCategory.value
    const data = await getApps(category, searchKeyword.value)
    apps.value = data
  } catch (error) {
    console.error('加载应用失败', error)
    message.error('加载应用失败')
  } finally {
    loading.value = false
  }
}

const selectCategory = (category: string) => {
  selectedCategory.value = category
  loadApps()
}

const handleSearch = () => {
  loadApps()
}

const showAppDetail = (app: AppInfo) => {
  currentApp.value = app
  detailVisible.value = true
}

const handleInstall = async (app: AppInfo) => {
  try {
    await installApp(app.id)
    message.success(`${app.name} 安装成功！`)
    app.installed = true
    if (currentApp.value?.id === app.id) {
      currentApp.value.installed = true
    }
  } catch (error) {
    console.error('安装失败', error)
    message.error('安装失败')
  }
}

const handleUninstall = async (app: AppInfo) => {
  try {
    await uninstallApp(app.id)
    message.success(`${app.name} 卸载成功！`)
    app.installed = false
    if (currentApp.value?.id === app.id) {
      currentApp.value.installed = false
    }
  } catch (error) {
    console.error('卸载失败', error)
    message.error('卸载失败')
  }
}

const formatNumber = (num: number | undefined) => {
  if (num === undefined || num === null) {
    return '0'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}
</script>

<style scoped>
.app-store {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}

.page-header {
  background: white;
  padding: 32px 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section {
  flex: 1;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  margin: 0 0 8px 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.page-subtitle {
  font-size: 16px;
  color: #666;
  margin: 0;
}

.store-container {
  max-width: 1400px;
  margin: 24px auto;
  display: flex;
  gap: 24px;
  padding: 0 24px;
}

.categories-sidebar {
  width: 200px;
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  height: fit-content;
  position: sticky;
  top: 24px;
}

.categories-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #1a1a1a;
}

.categories-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.category-item {
  padding: 10px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  color: #666;
}

.category-item:hover {
  background: #f5f5f5;
  color: #1677ff;
}

.category-item.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 500;
}

.apps-main {
  flex: 1;
}

.loading-state,
.empty-state {
  text-align: center;
  padding: 80px 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.loading-state p,
.empty-state p {
  margin-top: 16px;
  color: #999;
  font-size: 16px;
}

.apps-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
}

.app-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.app-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.app-icon {
  font-size: 64px;
  text-align: center;
  margin-bottom: 8px;
}

.app-info {
  flex: 1;
}

.app-name {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: #1a1a1a;
}

.app-description {
  font-size: 14px;
  color: #666;
  margin: 0 0 12px 0;
  line-height: 1.5;
}

.app-meta {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.app-category {
  font-size: 12px;
  color: #1677ff;
  background: #e6f4ff;
  padding: 2px 8px;
  border-radius: 4px;
}

.app-version {
  font-size: 12px;
  color: #666;
}

.app-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #666;
}

.app-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.app-action {
  margin-top: auto;
}

/* 应用详情 */
.app-detail {
  padding: 20px 0;
}

.detail-header {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid #f0f0f0;
}

.detail-icon {
  font-size: 80px;
}

.detail-info h2 {
  margin: 0 0 12px 0;
  font-size: 24px;
}

.detail-meta,
.detail-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
  color: #666;
  font-size: 14px;
}

.detail-description,
.detail-tags {
  margin-bottom: 24px;
}

.detail-description h3,
.detail-tags h3 {
  font-size: 16px;
  margin: 0 0 12px 0;
}

.detail-description p {
  color: #666;
  line-height: 1.6;
}

.detail-actions {
  margin-top: 32px;
}

@media (max-width: 768px) {
  .store-container {
    flex-direction: column;
  }

  .categories-sidebar {
    width: 100%;
    position: static;
  }

  .categories-list {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .apps-grid {
    grid-template-columns: 1fr;
  }

  .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .search-section {
    width: 100%;
  }

  .search-section .ant-input-search {
    width: 100% !important;
  }
}
</style>

