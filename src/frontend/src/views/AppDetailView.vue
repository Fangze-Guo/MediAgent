<template>
  <div class="app-detail-page">
    <!-- ==================== 顶部导航栏 ==================== -->
    <div class="detail-header">
      <div class="header-container">
        <a-button type="text" @click="goBack" class="back-btn">
          <LeftOutlined />
          返回应用商店
        </a-button>
      </div>
    </div>

    <!-- ==================== 加载状态 ==================== -->
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
      <p>正在加载应用信息...</p>
    </div>

    <!-- ==================== 应用详情内容 ==================== -->
    <div v-else-if="app" class="detail-content">
      <div class="content-container">
        <!-- 左侧主要内容 -->
        <div class="main-content">
          <!-- 应用头部信息 -->
          <div class="app-header-section">
            <div class="app-icon-large">{{ app.icon }}</div>
            <div class="app-header-info">
              <h1 class="app-title">{{ app.name }}</h1>
              <div class="app-provider">由 {{ app.author }} 提供</div>
              
              <!-- 评分和用户数 -->
              <div class="rating-section">
                <div class="rating-display">
                  <div class="rating-number">{{ app.rating }}</div>
                  <div class="rating-stars">
                    <StarFilled v-for="i in 5" :key="i" :style="{ color: i <= Math.round(app.rating) ? '#faad14' : '#e0e0e0' }" />
                  </div>
                  <div class="rating-text">({{ formatNumber(app.downloads) }} 个评分)</div>
                </div>
                <div class="user-count">
                  <UserOutlined />
                  {{ formatNumber(app.downloads) }} 位用户
                </div>
              </div>

              <!-- 操作按钮 -->
              <div class="action-buttons">
                <a-button
                  v-if="app.installed"
                  size="large"
                  class="primary-action-btn installed"
                  @click="handleUninstall"
                >
                  <CheckCircleFilled style="margin-right: 8px" />
                  已添加到 MediAgent
                </a-button>
                <a-button
                  v-else
                  type="primary"
                  size="large"
                  class="primary-action-btn"
                  @click="handleInstall"
                >
                  添加至 MediAgent
                </a-button>
                <a-button size="large" class="share-btn">
                  <ShareAltOutlined />
                  分享
                </a-button>
              </div>
            </div>
          </div>

          <!-- 概述部分 -->
          <div class="section overview-section">
            <h2 class="section-title">概述</h2>
            <div class="overview-content">
              {{ app.fullDescription || app.description }}
            </div>
          </div>

          <!-- 功能特点 -->
          <div class="section features-section">
            <h2 class="section-title">功能特点</h2>
            <ul class="features-list">
              <li v-for="(feature, index) in features" :key="index">{{ feature }}</li>
            </ul>
          </div>

          <!-- 评论区 -->
          <div class="section reviews-section">
            <h2 class="section-title">用户评价 ({{ reviews.length }})</h2>
            
            <!-- 评分统计 -->
            <div class="rating-stats">
              <div class="stats-summary">
                <div class="average-rating">
                  <span class="big-rating">{{ app.rating }}</span>
                  <div class="stars-small">
                    <StarFilled v-for="i in 5" :key="i" :style="{ color: i <= Math.round(app.rating) ? '#faad14' : '#e0e0e0' }" />
                  </div>
                  <span class="total-reviews">{{ reviews.length }} 条评价</span>
                </div>
              </div>
              <div class="stats-bars">
                <div v-for="star in [5, 4, 3, 2, 1]" :key="star" class="stat-bar">
                  <span class="star-label">{{ star }} 星</span>
                  <div class="bar-container">
                    <div class="bar-fill" :style="{ width: getStarPercentage(star) + '%' }"></div>
                  </div>
                  <span class="star-count">{{ getStarCount(star) }}</span>
                </div>
              </div>
            </div>

            <!-- 评论列表 -->
            <div class="reviews-list">
              <div v-for="review in reviews" :key="review.id" class="review-item">
                <div class="review-header">
                  <div class="reviewer-avatar">{{ review.user_name.charAt(0) }}</div>
                  <div class="reviewer-info">
                    <div class="reviewer-name">{{ review.user_name }}</div>
                    <div class="review-date">{{ review.date }}</div>
                  </div>
                  <div class="review-rating">
                    <StarFilled v-for="i in review.rating" :key="i" style="color: #faad14" />
                  </div>
                </div>
                <div class="review-content">
                  {{ review.comment }}
                </div>
                <div class="review-actions">
                  <a-button type="text" size="small">
                    <LikeOutlined />
                    有用 ({{ review.helpful_count }})
                  </a-button>
                  <a-button type="text" size="small">
                    <DislikeOutlined />
                  </a-button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧信息栏 -->
        <div class="sidebar-content">
          <!-- 详细信息 -->
          <div class="info-card">
            <h3 class="info-card-title">详情</h3>
            <div class="info-items">
              <div class="info-row">
                <span class="info-label">版本</span>
                <span class="info-value">{{ app.version }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">上次更新日期</span>
                <span class="info-value">2025年10月11日</span>
              </div>
              <div class="info-row">
                <span class="info-label">大小</span>
                <span class="info-value">2.5MB</span>
              </div>
              <div class="info-row">
                <span class="info-label">语言</span>
                <span class="info-value">中文</span>
              </div>
              <div class="info-row">
                <span class="info-label">分类</span>
                <span class="info-value">{{ app.category }}</span>
              </div>
            </div>
          </div>

          <!-- 标签 -->
          <div class="info-card">
            <h3 class="info-card-title">标签</h3>
            <div class="tags-container">
              <a-tag v-for="tag in app.tags" :key="tag" class="app-tag">{{ tag }}</a-tag>
            </div>
          </div>

          <!-- 相关应用 -->
          <div class="info-card">
            <h3 class="info-card-title">相关应用</h3>
            <div class="related-apps">
              <div v-for="relatedApp in relatedApps" :key="relatedApp.id" class="related-app-item" @click="goToApp(relatedApp.id)">
                <div class="related-app-icon">{{ relatedApp.icon }}</div>
                <div class="related-app-info">
                  <div class="related-app-name">{{ relatedApp.name }}</div>
                  <div class="related-app-rating">
                    <StarFilled style="color: #faad14; font-size: 12px" />
                    {{ relatedApp.rating }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 错误状态 ==================== -->
    <div v-else class="error-container">
      <InboxOutlined style="font-size: 64px; color: #dadce0" />
      <p class="error-text">未找到该应用</p>
      <a-button type="primary" @click="goBack">返回应用商店</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  LeftOutlined,
  StarFilled,
  UserOutlined,
  CheckCircleFilled,
  ShareAltOutlined,
  LikeOutlined,
  DislikeOutlined,
  InboxOutlined
} from '@ant-design/icons-vue'
import { getAppDetail, getApps, installApp, uninstallApp, getAppReviews } from '@/apis/appStore'
import type { AppInfo, Review, ReviewsData } from '@/apis/appStore'

const route = useRoute()
const router = useRouter()

// 响应式状态
const loading = ref(true)
const app = ref<AppInfo | null>(null)
const relatedApps = ref<AppInfo[]>([])
const reviews = ref<Review[]>([])
const reviewsData = ref<ReviewsData | null>(null)

// 应用ID
const appId = computed(() => route.params.id as string)

// 功能特点（可以从后端获取）
const features = computed(() => {
  if (!app.value) return []
  return [
    '支持 DICOM 格式转换',
    '批量处理功能',
    '高效的图像处理算法',
    '支持多种输出格式',
    '用户友好的界面设计'
  ]
})

// 计算评分统计（从后端获取的数据）
const getStarCount = (star: number) => {
  if (!reviewsData.value) return 0
  return reviewsData.value.rating_distribution[star.toString()] || 0
}

const getStarPercentage = (star: number) => {
  if (!reviewsData.value || reviewsData.value.total === 0) return 0
  const count = getStarCount(star)
  return (count / reviewsData.value.total) * 100
}

// 格式化数字
const formatNumber = (num: number | undefined) => {
  if (num === undefined || num === null) return '0'
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

// 加载应用详情
const loadAppDetail = async () => {
  loading.value = true
  try {
    // 加载应用详情
    const data = await getAppDetail(appId.value)
    app.value = data
    
    // 加载相关应用（同类别）
    if (data.category) {
      const allApps = await getApps(data.category)
      relatedApps.value = allApps.filter(a => a.id !== appId.value).slice(0, 5)
    }
    
    // 加载评论数据
    const reviewData = await getAppReviews(appId.value)
    reviewsData.value = reviewData
    reviews.value = reviewData.reviews
  } catch (error) {
    console.error('加载应用详情失败', error)
    message.error('加载应用详情失败')
  } finally {
    loading.value = false
  }
}

// 安装应用
const handleInstall = async () => {
  if (!app.value) return
  try {
    await installApp(app.value.id)
    message.success(`${app.value.name} 已成功添加至 MediAgent`)
    app.value.installed = true
  } catch (error) {
    console.error('安装失败', error)
    message.error('安装失败，请稍后重试')
  }
}

// 卸载应用
const handleUninstall = async () => {
  if (!app.value) return
  try {
    await uninstallApp(app.value.id)
    message.success(`${app.value.name} 已从 MediAgent 中移除`)
    app.value.installed = false
  } catch (error) {
    console.error('卸载失败', error)
    message.error('卸载失败，请稍后重试')
  }
}

// 返回应用商店
const goBack = () => {
  router.push('/app-store')
}

// 跳转到其他应用
const goToApp = (id: string) => {
  router.push(`/app-store/${id}`)
}

// 监听路由变化，重新加载数据
watch(() => route.params.id, () => {
  if (route.params.id) {
    loadAppDetail()
  }
}, { immediate: false })

// 组件挂载时加载数据
onMounted(() => {
  loadAppDetail()
})
</script>

<style scoped>
/* ==================== 页面布局 ==================== */
.app-detail-page {
  min-height: 100vh;
  background: #fff;
}

/* 顶部导航 */
.detail-header {
  background: #fff;
  border-bottom: 1px solid #e8eaed;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 16px 24px;
}

.back-btn {
  font-size: 14px;
  color: #5f6368;
  padding: 8px 16px;
}

.back-btn:hover {
  color: #1a73e8;
}

/* 加载和错误状态 */
.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 40px;
}

.loading-container p,
.error-text {
  margin-top: 16px;
  color: #5f6368;
  font-size: 16px;
}

/* 主内容区 */
.detail-content {
  max-width: 1280px;
  margin: 0 auto;
  padding: 40px 24px;
}

.content-container {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 40px;
}

/* 左侧主要内容 */
.main-content {
  display: flex;
  flex-direction: column;
  gap: 40px;
}

/* 应用头部 */
.app-header-section {
  display: flex;
  gap: 24px;
  padding-bottom: 32px;
  border-bottom: 1px solid #e8eaed;
}

.app-icon-large {
  font-size: 96px;
  line-height: 1;
  width: 128px;
  height: 128px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.app-header-info {
  flex: 1;
}

.app-title {
  font-size: 32px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 8px 0;
}

.app-provider {
  font-size: 14px;
  color: #5f6368;
  margin-bottom: 16px;
}

/* 评分展示 */
.rating-section {
  display: flex;
  align-items: center;
  gap: 32px;
  margin-bottom: 24px;
}

.rating-display {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rating-number {
  font-size: 48px;
  font-weight: 400;
  color: #202124;
  line-height: 1;
}

.rating-stars {
  display: flex;
  gap: 2px;
  font-size: 20px;
}

.rating-text {
  font-size: 14px;
  color: #5f6368;
}

.user-count {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #5f6368;
}

/* 操作按钮 */
.action-buttons {
  display: flex;
  gap: 12px;
}

.primary-action-btn {
  min-width: 200px;
  height: 48px;
  font-size: 16px;
  font-weight: 500;
  border-radius: 4px;
}

.primary-action-btn.installed {
  background: #e8f5e9;
  border-color: #81c784;
  color: #2e7d32;
}

.primary-action-btn.installed:hover {
  background: #c8e6c9;
  border-color: #66bb6a;
  color: #1b5e20;
}

.share-btn {
  height: 48px;
  border-radius: 4px;
}

/* 区块样式 */
.section {
  padding: 0;
}

.section-title {
  font-size: 20px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 16px 0;
}

/* 概述 */
.overview-content {
  font-size: 14px;
  color: #5f6368;
  line-height: 1.8;
}

/* 功能特点 */
.features-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.features-list li {
  padding: 12px 0;
  padding-left: 24px;
  position: relative;
  font-size: 14px;
  color: #5f6368;
  line-height: 1.6;
}

.features-list li::before {
  content: '✓';
  position: absolute;
  left: 0;
  color: #1a73e8;
  font-weight: bold;
}

/* 评论区 */
.rating-stats {
  display: flex;
  gap: 40px;
  margin-bottom: 32px;
  padding: 24px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stats-summary {
  flex-shrink: 0;
}

.average-rating {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.big-rating {
  font-size: 48px;
  font-weight: 400;
  color: #202124;
}

.stars-small {
  display: flex;
  gap: 2px;
  font-size: 16px;
}

.total-reviews {
  font-size: 12px;
  color: #5f6368;
}

.stats-bars {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.star-label {
  font-size: 12px;
  color: #5f6368;
  width: 40px;
}

.bar-container {
  flex: 1;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: #faad14;
  transition: width 0.3s;
}

.star-count {
  font-size: 12px;
  color: #5f6368;
  width: 30px;
  text-align: right;
}

/* 评论列表 */
.reviews-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.review-item {
  padding: 20px;
  border: 1px solid #e8eaed;
  border-radius: 8px;
}

.review-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.reviewer-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 18px;
}

.reviewer-info {
  flex: 1;
}

.reviewer-name {
  font-weight: 500;
  color: #202124;
  font-size: 14px;
}

.review-date {
  font-size: 12px;
  color: #5f6368;
}

.review-rating {
  display: flex;
  gap: 2px;
  font-size: 14px;
}

.review-content {
  font-size: 14px;
  color: #5f6368;
  line-height: 1.6;
  margin-bottom: 12px;
}

.review-actions {
  display: flex;
  gap: 8px;
}

/* 右侧信息栏 */
.sidebar-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.info-card {
  background: #fff;
  border: 1px solid #e8eaed;
  border-radius: 8px;
  padding: 20px;
}

.info-card-title {
  font-size: 16px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 16px 0;
}

.info-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.info-label {
  color: #5f6368;
}

.info-value {
  color: #202124;
  font-weight: 500;
}

/* 标签 */
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.app-tag {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 16px;
  background: #f1f3f4;
  border: 1px solid #e8eaed;
  color: #5f6368;
}

/* 相关应用 */
.related-apps {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.related-app-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.related-app-item:hover {
  background: #f8f9fa;
}

.related-app-icon {
  font-size: 32px;
  line-height: 1;
}

.related-app-info {
  flex: 1;
}

.related-app-name {
  font-size: 13px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 4px;
}

.related-app-rating {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #5f6368;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .content-container {
    grid-template-columns: 1fr;
  }

  .sidebar-content {
    order: -1;
  }
}

@media (max-width: 768px) {
  .app-header-section {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .rating-section {
    flex-direction: column;
    align-items: center;
  }

  .rating-stats {
    flex-direction: column;
  }

  .action-buttons {
    flex-direction: column;
  }

  .primary-action-btn {
    width: 100%;
  }
}
</style>

