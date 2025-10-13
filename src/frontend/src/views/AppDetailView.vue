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
              {{ app.full_description || app.description }}
            </div>
          </div>

          <!-- 功能特点 -->
          <div class="section features-section">
            <FeaturesMarkdown 
              :app-id="appId" 
              :features="app?.features || ''" 
              :can-edit="true"
              @save="handleSaveFeatures"
            />
          </div>

          <!-- 评论区 -->
          <div class="section reviews-section">
            <div class="reviews-header">
              <h2 class="section-title">用户评价 ({{ reviews.length }})</h2>
              <div class="review-controls">
                <a-select v-model:value="reviewSort" class="sort-select" @change="handleSortChange">
                  <a-select-option value="newest">最新</a-select-option>
                  <a-select-option value="oldest">最早</a-select-option>
                  <a-select-option value="highest">评分最高</a-select-option>
                  <a-select-option value="lowest">评分最低</a-select-option>
                  <a-select-option value="helpful">最有用</a-select-option>
                </a-select>
                <a-button type="primary" @click="handleWriteReview">
                  <template #icon><EditOutlined /></template>
                  {{ hasUserReviewed ? '修改评论' : '写评论' }}
                </a-button>
              </div>
            </div>
            
            <!-- 评分统计 -->
            <div class="rating-stats">
              <div class="stats-summary">
                <div class="average-rating">
                  <span class="big-rating">{{ reviewsData?.average_rating || 0 }}</span>
                  <div class="stars-small">
                    <StarFilled v-for="i in 5" :key="i" :style="{ color: i <= Math.round(reviewsData?.average_rating || 0) ? '#faad14' : '#e0e0e0' }" />
                  </div>
                  <span class="total-reviews">{{ reviewsData?.total || 0 }} 条评价</span>
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

            <!-- 添加评论表单 -->
            <div v-if="showAddReview" class="add-review-form">
              <div class="form-header">
                <h3>{{ isEditingReview ? '修改评论' : '写评论' }}</h3>
                <a-button type="text" @click="cancelAddReview">
                  <CloseOutlined />
                </a-button>
              </div>
              
              <!-- 用户信息提示 -->
              <div class="user-info-tip">
                <UserOutlined />
                <span>评论将以 <strong>{{ authStore.currentUser?.user_name || '未知用户' }}</strong> 的名义发布</span>
              </div>
              
              <a-form :model="reviewForm" layout="vertical" @finish="submitReview">
                <a-form-item label="您的评分" name="rating" :rules="[{ required: true, message: '请选择评分' }]">
                  <div class="rating-input">
                    <StarFilled 
                      v-for="i in 5" 
                      :key="i" 
                      :style="{ 
                        color: i <= reviewForm.rating ? '#faad14' : '#e0e0e0',
                        fontSize: '24px',
                        cursor: 'pointer',
                        marginRight: '4px'
                      }"
                      @click="reviewForm.rating = i"
                      @mouseenter="hoverRating = i"
                      @mouseleave="hoverRating = 0"
                    />
                    <span class="rating-text" v-if="reviewForm.rating > 0">
                      {{ getRatingText(reviewForm.rating) }}
                    </span>
                  </div>
                </a-form-item>
                <a-form-item label="评论内容" name="comment" :rules="[{ required: true, message: '请输入评论内容' }]">
                  <a-textarea 
                    v-model:value="reviewForm.comment" 
                    placeholder="请分享您的使用体验..." 
                    :rows="4"
                    :maxlength="500"
                    show-count
                  />
                </a-form-item>
                <a-form-item>
                  <div class="form-actions">
                    <a-button @click="cancelAddReview">取消</a-button>
                    <a-button type="primary" html-type="submit" :loading="submittingReview">
                      {{ isEditingReview ? '保存修改' : '发布评论' }}
                    </a-button>
                  </div>
                </a-form-item>
              </a-form>
            </div>

            <!-- 评论列表 -->
            <div class="reviews-list">
              <div v-if="sortedReviews.length === 0" class="no-reviews">
                <div class="no-reviews-icon">💬</div>
                <div class="no-reviews-text">暂无评论</div>
                <div class="no-reviews-desc">成为第一个评论此应用的用户吧！</div>
                <a-button type="primary" @click="handleWriteReview">
                  写第一条评论
                </a-button>
              </div>
              <div v-else class="reviews-container">
                <div v-for="(review, index) in sortedReviews" :key="review.id" class="review-item" :class="{ 'my-review': isCurrentUserReview(review) }">
                  <div class="review-card">
                    <div class="review-header">
                      <div class="reviewer-avatar" :style="{ background: getAvatarColor(review.user_name) }" :class="{ 'my-avatar': isCurrentUserReview(review) }">
                        {{ review.user_name.charAt(0).toUpperCase() }}
                      </div>
                      <div class="reviewer-info">
                        <div class="reviewer-name">
                          {{ review.user_name }}
                          <span v-if="isCurrentUserReview(review)" class="my-review-badge">
                            <UserOutlined />
                            我的评论
                          </span>
                        </div>
                        <div class="review-meta">
                          <span class="review-date">{{ formatDate(review.created_at) }}</span>
                          <span class="review-index">#{{ index + 1 }}</span>
                        </div>
                      </div>
                      <div class="review-rating">
                        <div class="stars-container">
                          <StarFilled v-for="i in review.rating" :key="i" class="star-filled" />
                          <StarFilled v-for="i in (5 - review.rating)" :key="i + review.rating" class="star-empty" />
                        </div>
                        <span class="rating-text">{{ review.rating }}.0 分</span>
                      </div>
                    </div>
                    
                    <div class="review-content">
                      <div class="content-text">{{ review.comment }}</div>
                      <div v-if="review.comment.length > 100" class="content-gradient"></div>
                    </div>
                    
                    <div class="review-footer">
                      <div class="review-actions">
                        <a-button 
                          type="text" 
                          size="small" 
                          @click="toggleHelpful(review.id)"
                          :class="{ active: review.isHelpful }"
                          class="action-btn helpful-btn"
                        >
                          <LikeOutlined />
                          <span class="count">({{ review.helpful_count }})</span>
                        </a-button>
                        
                        <!-- 只有用户自己的评论才显示删除按钮 -->
                        <a-button 
                          v-if="isCurrentUserReview(review)" 
                          type="text" 
                          size="small" 
                          class="action-btn delete-btn"
                          @click="handleDeleteReview(review.id)"
                        >
                          <DeleteOutlined />
                          <span>删除</span>
                        </a-button>
                      </div>
                      
                      <div class="review-stats">
                        <span class="helpful-stats" v-if="review.helpful_count > 0">
                          {{ review.helpful_count }} 人觉得有用
                        </span>
                      </div>
                    </div>
                  </div>
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
import { message, Modal } from 'ant-design-vue'
import {
  LeftOutlined,
  StarFilled,
  UserOutlined,
  CheckCircleFilled,
  ShareAltOutlined,
  LikeOutlined,
  InboxOutlined,
  EditOutlined,
  CloseOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import { getAppDetail, getApps, installApp, uninstallApp, getAppReviews, addAppReview, updateAppReview, deleteAppReview, toggleReviewHelpful, updateAppFeatures } from '@/apis/appStore'
import type { AppInfo, Review, ReviewsData, AddReviewRequest } from '@/apis/appStore'
import { useAuthStore } from '@/store/auth'
import FeaturesMarkdown from '@/components/FeaturesMarkdown.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

// 响应式状态
const loading = ref(true)
const app = ref<AppInfo | null>(null)
const relatedApps = ref<AppInfo[]>([])
const reviews = ref<Review[]>([])
const reviewsData = ref<ReviewsData | null>(null)

// 评论相关状态
const showAddReview = ref(false)
const submittingReview = ref(false)
const reviewSort = ref('newest')
const hoverRating = ref(0)
const isEditingReview = ref(false)  // 是否在编辑现有评论
const userExistingReview = ref<Review | null>(null)  // 用户的现有评论
const reviewForm = ref<AddReviewRequest>({
  user_name: '',  // 这个字段会在提交时自动填充当前用户名
  rating: 0,
  comment: ''
})

// 应用ID
const appId = computed(() => route.params.id as string)

// 检查当前用户是否已经评论过
const hasUserReviewed = computed(() => {
  if (!authStore.currentUser) return false
  return reviews.value.some(review => review.user_name === authStore.currentUser?.user_name)
})

// 获取当前用户的评论
const currentUserReview = computed(() => {
  if (!authStore.currentUser) return null
  return reviews.value.find(review => review.user_name === authStore.currentUser?.user_name) || null
})

// 判断评论是否属于当前用户
const isCurrentUserReview = (review: Review) => {
  if (!authStore.currentUser) return false
  return review.user_name === authStore.currentUser.user_name
}

// 保存功能特点
const handleSaveFeatures = async (appId: string, features: string) => {
  try {
    // 调用后端API保存功能特点
    await updateAppFeatures(appId, features)
    
    // 更新本地数据
    if (app.value) {
      app.value.features = features
    }
    
    message.success('功能特点保存成功')
  } catch (error) {
    console.error('保存功能特点失败:', error)
    message.error('保存失败，请重试')
  }
}

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

// 格式化日期
const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  if (days < 30) return `${Math.floor(days / 7)}周前`
  if (days < 365) return `${Math.floor(days / 30)}个月前`
  return `${Math.floor(days / 365)}年前`
}

// 获取评分文本
const getRatingText = (rating: number) => {
  const texts = ['', '很差', '一般', '还行', '不错', '很棒']
  return texts[rating] || ''
}

// 根据用户名生成头像颜色
const getAvatarColor = (userName: string) => {
  const colors = [
    'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
    'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
    'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
    'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
    'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
    'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)',
    'linear-gradient(135deg, #ff8a80 0%, #ea4c89 100%)',
    'linear-gradient(135deg, #8fd3f4 0%, #84fab0 100%)'
  ]
  
  // 根据用户名计算哈希值来选择颜色
  let hash = 0
  for (let i = 0; i < userName.length; i++) {
    hash = userName.charCodeAt(i) + ((hash << 5) - hash)
  }
  
  return colors[Math.abs(hash) % colors.length]
}

// 排序后的评论列表
const sortedReviews = computed(() => {
  const reviewsCopy = [...reviews.value]
  switch (reviewSort.value) {
    case 'newest':
      return reviewsCopy.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    case 'oldest':
      return reviewsCopy.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    case 'highest':
      return reviewsCopy.sort((a, b) => b.rating - a.rating)
    case 'lowest':
      return reviewsCopy.sort((a, b) => a.rating - b.rating)
    case 'helpful':
      return reviewsCopy.sort((a, b) => b.helpful_count - a.helpful_count)
    default:
      return reviewsCopy
  }
})

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
    
    // 加载评论数据，如果用户已登录则传递用户ID
    const userId = authStore.currentUser?.uid
    const reviewData = await getAppReviews(appId.value, userId)
    reviewsData.value = reviewData
    reviews.value = reviewData.reviews.map(review => ({
      ...review,
      isHelpful: review.user_liked || false  // 使用后端返回的点赞状态
    }))
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

// 评论相关函数
const handleWriteReview = () => {
  if (!authStore.currentUser) {
    message.error('请先登录后再发表评论')
    return
  }

  if (hasUserReviewed.value && currentUserReview.value) {
    // 用户已经评论过，进入编辑模式
    isEditingReview.value = true
    userExistingReview.value = currentUserReview.value
    reviewForm.value = {
      user_name: currentUserReview.value.user_name,
      rating: currentUserReview.value.rating,
      comment: currentUserReview.value.comment
    }
  } else {
    // 用户还没有评论，进入新建模式
    isEditingReview.value = false
    userExistingReview.value = null
    reviewForm.value = {
      user_name: '',
      rating: 0,
      comment: ''
    }
  }
  
  showAddReview.value = true
}

const submitReview = async () => {
  try {
    // 检查用户是否已登录
    if (!authStore.currentUser) {
      message.error('请先登录后再发表评论')
      return
    }

    submittingReview.value = true
    
    // 自动填充当前用户名
    const reviewData = {
      user_name: authStore.currentUser.user_name,
      rating: reviewForm.value.rating,
      comment: reviewForm.value.comment
    }
    
    if (isEditingReview.value && userExistingReview.value) {
      // 编辑模式：更新现有评论
      await updateAppReview(appId.value, userExistingReview.value.id, reviewData)
      message.success('评论修改成功！')
    } else {
      // 新建模式：添加新评论
      await addAppReview(appId.value, reviewData)
      message.success('评论发布成功！')
    }
    
    // 重置表单和状态
    reviewForm.value = {
      user_name: '',
      rating: 0,
      comment: ''
    }
    showAddReview.value = false
    isEditingReview.value = false
    userExistingReview.value = null
    
    // 重新加载评论
    const userId = authStore.currentUser?.uid
    const reviewData2 = await getAppReviews(appId.value, userId)
    reviewsData.value = reviewData2
    reviews.value = reviewData2.reviews.map(review => ({
      ...review,
      isHelpful: review.user_liked || false
    }))
  } catch (error) {
    console.error('提交评论失败', error)
    message.error(isEditingReview.value ? '评论修改失败，请重试' : '评论发布失败，请重试')
  } finally {
    submittingReview.value = false
  }
}

const cancelAddReview = () => {
  showAddReview.value = false
  isEditingReview.value = false
  userExistingReview.value = null
  reviewForm.value = {
    user_name: '',
    rating: 0,
    comment: ''
  }
}

const handleSortChange = () => {
  // 排序逻辑已在 computed 中处理
}

const toggleHelpful = async (reviewId: number) => {
  if (!authStore.currentUser) {
    message.error('请先登录后再点赞')
    return
  }

  const review = reviews.value.find(r => r.id === reviewId)
  if (!review) return

  try {
    // 调用后端API
    const result = await toggleReviewHelpful(appId.value, reviewId, authStore.currentUser.uid)
    
    // 更新前端状态
    review.helpful_count = result.helpful_count
    review.isHelpful = result.user_liked
    
    message.success(result.user_liked ? '已点赞' : '已取消点赞')
  } catch (error) {
    console.error('点赞操作失败', error)
    message.error('操作失败，请重试')
  }
}

// 删除评论
const handleDeleteReview = async (reviewId: number) => {
  if (!authStore.currentUser) {
    message.error('请先登录')
    return
  }

  try {
    // 显示确认对话框
    const confirmed = await new Promise((resolve) => {
      Modal.confirm({
        title: '确认删除评论',
        content: '删除后无法恢复，确定要删除这条评论吗？',
        okText: '删除',
        okType: 'danger',
        cancelText: '取消',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      })
    })

    if (!confirmed) return

    await deleteAppReview(appId.value, reviewId, authStore.currentUser.user_name)
    message.success('评论删除成功')
    
    // 重新加载评论数据
    const userId = authStore.currentUser?.uid
    const reviewData = await getAppReviews(appId.value, userId)
    reviewsData.value = reviewData
    reviews.value = reviewData.reviews.map(review => ({
      ...review,
      isHelpful: review.user_liked || false
    }))
  } catch (error) {
    console.error('删除评论失败', error)
    message.error('删除评论失败，请重试')
  }
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
.features-section {
  margin-bottom: 32px;
}

/* 评论区 */
.reviews-section {
  padding: 32px 0;
}

.reviews-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.review-controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.sort-select {
  width: 120px;
}

/* 添加评论表单样式 */
.add-review-form {
  background: #f8f9fa;
  border: 1px solid #e8eaed;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 32px;
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.form-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
  color: #202124;
}

/* 用户信息提示样式 */
.user-info-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f0f8ff;
  border: 1px solid #d6f1ff;
  border-radius: 8px;
  margin-bottom: 20px;
  font-size: 14px;
  color: #1890ff;
}

.user-info-tip strong {
  color: #1890ff;
  font-weight: 600;
}

.rating-input {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rating-text {
  font-size: 14px;
  color: #5f6368;
  font-weight: 500;
}

.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

/* 无评论状态样式 */
.no-reviews {
  text-align: center;
  padding: 60px 20px;
  color: #5f6368;
}

.no-reviews-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.no-reviews-text {
  font-size: 18px;
  font-weight: 500;
  margin-bottom: 8px;
  color: #202124;
}

.no-reviews-desc {
  font-size: 14px;
  margin-bottom: 24px;
}

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

/* 评论容器样式 */
.reviews-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 评论卡片样式 */
.review-item {
  position: relative;
  transition: all 0.3s ease;
}

.review-item:hover {
  transform: translateY(-2px);
}

.review-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #f0f0f0;
  overflow: hidden;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  padding: 24px;
}

.review-item:hover .review-card {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  border-color: #e6f7ff;
}


/* 评论头部样式 */
.review-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.reviewer-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 18px;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border: 3px solid #fff;
}

.reviewer-info {
  flex: 1;
  min-width: 0;
}

.reviewer-name {
  font-weight: 600;
  color: #1a1a1a;
  font-size: 16px;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}


.review-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #8c8c8c;
}

.review-date {
  font-weight: 500;
}

.review-index {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 8px;
  font-weight: 500;
}

/* 评分样式 */
.review-rating {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.stars-container {
  display: flex;
  gap: 2px;
}

.star-filled {
  color: #faad14;
  font-size: 16px;
  filter: drop-shadow(0 1px 2px rgba(250, 173, 20, 0.3));
}

.star-empty {
  color: #e8e8e8;
  font-size: 16px;
}

.rating-text {
  font-size: 12px;
  color: #8c8c8c;
  font-weight: 500;
}

/* 评论内容样式 */
.review-content {
  margin-bottom: 20px;
  position: relative;
}

.content-text {
  color: #262626;
  line-height: 1.7;
  font-size: 15px;
  word-break: break-word;
}

.content-gradient {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 20px;
  background: linear-gradient(transparent, rgba(255, 255, 255, 0.9));
  pointer-events: none;
}

/* 评论底部样式 */
.review-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid #f5f5f5;
}

.review-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background-color: #f5f5f5;
  transform: translateY(-1px);
}

.helpful-btn.active {
  background: linear-gradient(135deg, #1890ff, #40a9ff);
  color: white;
  border-color: transparent;
}

.helpful-btn.active:hover {
  background: linear-gradient(135deg, #096dd9, #1890ff);
  color: white;
}

.delete-btn:hover {
  background-color: #fff1f0;
  color: #ff4d4f;
  border-color: #ffccc7;
}


.count {
  background: rgba(255, 255, 255, 0.2);
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 11px;
}

.helpful-btn:not(.active) .count {
  background: #f0f0f0;
  color: #8c8c8c;
}

.review-stats {
  font-size: 12px;
  color: #8c8c8c;
}

.helpful-stats {
  font-weight: 500;
}

/* 用户自己的评论高亮样式 */
.my-review .review-card {
  background: #f6ffed;
  border-left: 4px solid #52c41a;
  box-shadow: 0 2px 8px rgba(82, 196, 26, 0.08);
}

.my-review:hover .review-card {
  box-shadow: 0 4px 12px rgba(82, 196, 26, 0.12);
}

/* 用户头像特殊样式 */
.my-avatar {
  border: 2px solid #52c41a !important;
}

/* 我的评论徽章 - 简约版 */
.my-review-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #52c41a;
  color: white;
  padding: 2px 6px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 500;
  margin-left: 8px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .review-card {
    padding: 16px;
  }
  
  .review-header {
    gap: 12px;
  }
  
  .reviewer-avatar {
    width: 40px;
    height: 40px;
    font-size: 16px;
  }
  
  .reviewer-name {
    font-size: 14px;
  }
  
  .content-text {
    font-size: 14px;
  }
  
  .review-footer {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
  
  .review-actions {
    width: 100%;
    justify-content: space-between;
  }
}

/* 动画效果 */
@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.review-item {
  animation: slideInUp 0.3s ease-out;
}

.review-item:nth-child(1) { animation-delay: 0.1s; }
.review-item:nth-child(2) { animation-delay: 0.2s; }
.review-item:nth-child(3) { animation-delay: 0.3s; }
.review-item:nth-child(4) { animation-delay: 0.4s; }
.review-item:nth-child(5) { animation-delay: 0.5s; }

/* 加载动画 */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.review-item.loading {
  animation: pulse 1.5s ease-in-out infinite;
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

