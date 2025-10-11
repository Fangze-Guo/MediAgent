<template>
  <div class="app-store">
    <!-- ==================== 顶部导航栏 ==================== -->
    <!-- 固定在页面顶部，包含 Logo 和搜索框，类似 Chrome Web Store 的顶部导航 -->
    <div class="store-header">
      <div class="header-container">
        <!-- 商店 Logo 区域 -->
        <div class="store-logo">
          <span class="logo-icon">🏪</span>
          <span class="logo-text">MediAgent 应用商店</span>
        </div>
        
        <!-- 搜索框区域：支持搜索应用名称、描述和标签 -->
        <div class="search-box">
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="搜索扩展程序、主题等"
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

    <!-- ==================== 分类标签栏 ==================== -->
    <!-- 水平滚动的分类标签，点击可切换不同分类，选中时显示蓝色下划线 -->
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

    <!-- ==================== 精选横幅轮播 ==================== -->
    <!-- 仅在"全部"分类时显示，展示评分最高的前3个应用 -->
    <div v-if="selectedCategory === '全部'" class="featured-banner">
      <div class="banner-container">
        <!-- Ant Design 轮播组件，自动播放 -->
        <a-carousel autoplay :dots="true" class="banner-carousel">
          <!-- 遍历精选应用，每个应用一张轮播图 -->
          <div v-for="featured in featuredApps" :key="featured.id" class="banner-slide">
            <div class="banner-content" @click="showAppDetail(featured)">
              <div class="banner-left">
                <!-- 应用图标 -->
                <div class="banner-icon">{{ featured.icon }}</div>
                <!-- 应用信息：名称、描述、评分和下载量 -->
                <div class="banner-info">
                  <h2 class="banner-title">{{ featured.name }}</h2>
                  <p class="banner-description">{{ featured.description }}</p>
                  <div class="banner-stats">
                    <span class="banner-rating">
                      <StarFilled style="color: #faad14; margin-right: 4px" />
                      {{ featured.rating }}
                    </span>
                    <span class="banner-downloads">
                      {{ formatNumber(featured.downloads) }} 位用户
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </a-carousel>
      </div>
    </div>

    <!-- ==================== 主内容区 ==================== -->
    <!-- 显示应用列表或加载/空状态 -->
    <div class="store-main">
      <div class="main-container">
        <!-- 加载状态：数据获取中时显示 -->
        <div v-if="loading" class="loading-state">
          <a-spin size="large" />
          <p>正在加载应用...</p>
        </div>

        <!-- 空状态：没有找到匹配的应用时显示 -->
        <div v-else-if="apps.length === 0" class="empty-state">
          <InboxOutlined style="font-size: 64px; color: #dadce0" />
          <p class="empty-text">未找到相关应用</p>
          <p class="empty-hint">请尝试其他搜索词或浏览其他分类</p>
        </div>

        <!-- 应用网格：正常展示应用列表 -->
        <div v-else>
          <!-- 区块标题：显示当前分类和应用数量 -->
          <div class="section-header">
            <h2 class="section-title">
              {{ selectedCategory === '全部' ? '推荐应用' : selectedCategory }}
            </h2>
            <span class="results-count">{{ apps.length }} 个应用</span>
          </div>
          
          <!-- 应用卡片网格：自适应布局 -->
          <div class="apps-grid">
            <!-- 遍历所有应用，每个应用一张卡片 -->
            <div
              v-for="app in apps"
              :key="app.id"
              class="app-card"
              @click="showAppDetail(app)"
            >
              <!-- 卡片头部：图标和基本信息 -->
              <div class="card-header">
                <div class="app-icon-wrapper">
                  <span class="app-icon">{{ app.icon }}</span>
                </div>
                <div class="app-basic-info">
                  <h3 class="app-name">{{ app.name }}</h3>
                  <p class="app-author">{{ app.author }}</p>
                  <!-- 评分和下载量 -->
                  <div class="app-rating">
                    <StarFilled class="star-icon" />
                    <span class="rating-value">{{ app.rating }}</span>
                    <span class="rating-count">({{ formatNumber(app.downloads) }})</span>
                  </div>
                </div>
              </div>
              
              <!-- 应用描述：最多显示2行，超出用省略号 -->
              <p class="app-description">{{ app.description }}</p>
              
              <!-- 卡片底部：分类标签和安装按钮 -->
              <div class="card-footer">
                <span class="app-category-badge">{{ app.category }}</span>
                <!-- 已安装状态：显示绿色按钮 -->
                <a-button
                  v-if="app.installed"
                  class="install-btn installed"
                  @click.stop="handleUninstall(app)"
                >
                  <CheckCircleFilled style="margin-right: 4px" />
                  已安装
                </a-button>
                <!-- 未安装状态：显示蓝色主按钮 -->
                <a-button
                  v-else
                  type="primary"
                  class="install-btn"
                  @click.stop="handleInstall(app)"
                >
                  添加至 MediAgent
                </a-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 应用详情模态框 ==================== -->
    <!-- 点击应用卡片时弹出，显示应用的完整信息 -->
    <a-modal
      v-model:open="detailVisible"
      width="900px"
      :footer="null"
      class="app-detail-modal"
    >
      <div v-if="currentApp" class="app-detail">
        <!-- 详情页头部：应用图标、名称、评分和操作按钮 -->
        <div class="detail-header">
          <div class="detail-left">
            <!-- 大尺寸应用图标 -->
            <div class="detail-icon-wrapper">
              <span class="detail-icon">{{ currentApp.icon }}</span>
            </div>
            <!-- 应用主要信息 -->
            <div class="detail-main-info">
              <h1 class="detail-title">{{ currentApp.name }}</h1>
              <p class="detail-author">由 {{ currentApp.author }} 提供</p>
              <!-- 评分展示区：大号数字评分 + 星星 + 用户数 -->
              <div class="detail-rating-section">
                <div class="rating-box">
                  <div class="rating-score">{{ currentApp.rating }}</div>
                  <div class="rating-stars">
                    <StarFilled v-for="i in 5" :key="i" class="star" />
                  </div>
                  <div class="rating-text">{{ formatNumber(currentApp.downloads) }} 位用户</div>
                </div>
              </div>
            </div>
          </div>
          <!-- 操作按钮区：安装或卸载 -->
          <div class="detail-actions">
            <a-button
              v-if="currentApp.installed"
              size="large"
              class="detail-action-btn installed-btn"
              @click="handleUninstall(currentApp)"
            >
              <CheckCircleFilled style="margin-right: 8px" />
              已添加到 MediAgent
            </a-button>
            <a-button
              v-else
              type="primary"
              size="large"
              class="detail-action-btn"
              @click="handleInstall(currentApp)"
            >
              添加至 MediAgent
            </a-button>
          </div>
        </div>

        <!-- 详情页主体：应用详细信息 -->
        <div class="detail-body">
          <!-- 概述区块 -->
          <div class="detail-section">
            <h3 class="section-subtitle">概述</h3>
            <p class="detail-description">{{ currentApp.description }}</p>
          </div>

          <!-- 详细信息区块：版本、更新日期、类别等 -->
          <div class="detail-section">
            <h3 class="section-subtitle">详细信息</h3>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">版本</span>
                <span class="info-value">{{ currentApp.version }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">更新日期</span>
                <span class="info-value">2024年10月11日</span>
              </div>
              <div class="info-item">
                <span class="info-label">类别</span>
                <span class="info-value">{{ currentApp.category }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">语言</span>
                <span class="info-value">中文</span>
              </div>
            </div>
          </div>

          <!-- 标签区块：显示应用相关的所有标签 -->
          <div class="detail-section">
            <h3 class="section-subtitle">标签</h3>
            <div class="detail-tags">
              <a-tag v-for="tag in currentApp.tags" :key="tag" class="detail-tag">
                {{ tag }}
              </a-tag>
            </div>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/**
 * 应用商店视图组件
 * 模仿 Chrome Web Store 的设计风格
 * 提供应用浏览、搜索、安装和卸载功能
 */

// ==================== 导入依赖 ====================
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
// 图标组件
import {
  SearchOutlined,     // 搜索图标
  InboxOutlined,      // 空状态图标
  StarFilled,         // 星星评分图标
  CheckCircleFilled   // 已安装勾选图标
} from '@ant-design/icons-vue'
// API 接口和类型定义
import { getApps, getCategories, installApp, uninstallApp, type AppInfo } from '@/apis/appStore'

// ==================== 响应式状态 ====================
const loading = ref(true)                          // 加载状态
const apps = ref<AppInfo[]>([])                    // 应用列表
const categories = ref<string[]>([])               // 分类列表
const selectedCategory = ref('全部')               // 当前选中的分类
const searchKeyword = ref('')                      // 搜索关键词
const detailVisible = ref(false)                   // 详情模态框显示状态
const currentApp = ref<AppInfo | null>(null)       // 当前查看的应用

// ==================== 计算属性 ====================
/**
 * 精选应用 - 按评分排序，取前3个
 * 用于首页横幅轮播展示
 */
const featuredApps = computed(() => {
  return [...apps.value]
    .sort((a, b) => b.rating - a.rating)  // 按评分从高到低排序
    .slice(0, 3)                          // 只取前3个
})

// ==================== 生命周期钩子 ====================
/**
 * 组件挂载时执行
 * 加载分类列表和应用列表
 */
onMounted(async () => {
  await loadCategories()
  await loadApps()
})

// ==================== 数据加载函数 ====================
/**
 * 加载分类列表
 * 从后端获取所有可用的应用分类
 */
const loadCategories = async () => {
  try {
    const data = await getCategories()
    categories.value = data
  } catch (error) {
    console.error('加载分类失败', error)
  }
}

/**
 * 加载应用列表
 * 根据当前选中的分类和搜索关键词获取应用
 */
const loadApps = async () => {
  loading.value = true
  try {
    // 如果选中"全部"，则不传分类参数
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

// ==================== 用户交互处理函数 ====================
/**
 * 选择分类
 * 点击分类标签时触发，重新加载对应分类的应用
 * @param category 分类名称
 */
const selectCategory = (category: string) => {
  selectedCategory.value = category
  searchKeyword.value = '' // 切换分类时清空搜索关键词
  loadApps()
}

/**
 * 处理搜索
 * 用户点击搜索按钮或按回车键时触发
 */
const handleSearch = () => {
  loadApps()
}

/**
 * 显示应用详情
 * 点击应用卡片时触发，打开详情模态框
 * @param app 要查看的应用信息
 */
const showAppDetail = (app: AppInfo) => {
  currentApp.value = app
  detailVisible.value = true
}

/**
 * 安装应用
 * 调用后端 API 安装应用，并更新 UI 状态
 * @param app 要安装的应用信息
 */
const handleInstall = async (app: AppInfo) => {
  try {
    await installApp(app.id)
    message.success(`${app.name} 已成功添加至 MediAgent`)
    // 更新应用的安装状态
    app.installed = true
    // 如果详情弹窗正在显示该应用，同步更新
    if (currentApp.value?.id === app.id) {
      currentApp.value.installed = true
    }
  } catch (error) {
    console.error('安装失败', error)
    message.error('安装失败，请稍后重试')
  }
}

/**
 * 卸载应用
 * 调用后端 API 卸载应用，并更新 UI 状态
 * @param app 要卸载的应用信息
 */
const handleUninstall = async (app: AppInfo) => {
  try {
    await uninstallApp(app.id)
    message.success(`${app.name} 已从 MediAgent 中移除`)
    // 更新应用的安装状态
    app.installed = false
    // 如果详情弹窗正在显示该应用，同步更新
    if (currentApp.value?.id === app.id) {
      currentApp.value.installed = false
    }
  } catch (error) {
    console.error('卸载失败', error)
    message.error('卸载失败，请稍后重试')
  }
}

// ==================== 工具函数 ====================
/**
 * 格式化数字显示
 * 将大数字转换为易读的格式（如 1.2K, 2.5M）
 * @param num 要格式化的数字
 * @returns 格式化后的字符串
 */
const formatNumber = (num: number | undefined) => {
  if (num === undefined || num === null) {
    return '0'
  }
  // 百万级别
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  // 千级别
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  // 小于1000直接显示
  return num.toString()
}
</script>

<style scoped>
/**
 * ==================== CSS 样式说明 ====================
 * 
 * 设计理念：模仿 Chrome Web Store 的简洁现代风格
 * 
 * 主要配色方案：
 * - 主色调：#1a73e8 (Google 蓝)
 * - 文字颜色：#202124 (深灰), #5f6368 (中灰), #80868b (浅灰)
 * - 边框颜色：#e8eaed, #dadce0
 * - 背景色：#ffffff (白色), #f1f3f4 (浅灰背景)
 * - 成功色：#2e7d32 (绿色) - 用于已安装状态
 * - 警告色：#faad14 (橙黄色) - 用于星星评分
 * 
 * 布局特点：
 * - 固定顶部导航栏和分类栏
 * - 最大宽度 1280px，居中显示
 * - 响应式网格布局，自适应不同屏幕尺寸
 * - 卡片式设计，悬浮时有微妙的阴影效果
 */

/* ==================== 全局容器 ==================== */
.app-store {
  min-height: 100vh;        /* 最小高度为视口高度 */
  background: #ffffff;      /* 纯白背景 */
}

/* ==================== 顶部导航栏 ==================== */
.store-header {
  background: #fff;
  border-bottom: 1px solid #e8eaed;   /* 底部细边框 */
  position: sticky;                    /* 滚动时固定在顶部 */
  top: 0;
  z-index: 100;                        /* 确保在其他内容之上 */
}

.header-container {
  max-width: 1280px;         /* 最大宽度限制 */
  margin: 0 auto;            /* 水平居中 */
  padding: 16px 24px;
  display: flex;
  align-items: center;
  gap: 40px;                 /* Logo 和搜索框之间的间距 */
}

/* Logo 区域 */
.store-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 500;
  color: #202124;
  cursor: pointer;
  white-space: nowrap;       /* 防止换行 */
}

.logo-icon {
  font-size: 28px;
}

.logo-text {
  font-weight: 500;
}

/* 搜索框区域 */
.search-box {
  flex: 1;                   /* 占据剩余空间 */
  max-width: 720px;          /* 最大宽度限制 */
}

.search-input {
  border-radius: 24px;       /* 圆角搜索框 */
}

/* 使用 :deep() 穿透 scoped 样式，修改 Ant Design 组件内部样式 */
.search-input :deep(.ant-input) {
  border-radius: 24px;
}

.search-input :deep(.ant-input-group-addon) {
  border-radius: 0 24px 24px 0;   /* 右侧按钮圆角 */
}

/* ==================== 分类标签栏 ==================== */
.categories-bar {
  background: #fff;
  border-bottom: 1px solid #e8eaed;
  position: sticky;          /* 固定在顶部导航栏下方 */
  top: 65px;                 /* 顶部导航栏的高度 */
  z-index: 99;
}

.categories-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  gap: 8px;
  overflow-x: auto;          /* 分类过多时支持水平滚动 */
  scrollbar-width: none;     /* Firefox 隐藏滚动条 */
}

/* Webkit 浏览器（Chrome, Safari）隐藏滚动条 */
.categories-container::-webkit-scrollbar {
  display: none;
}

/* 分类标签按钮 */
.category-tab {
  padding: 14px 20px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #5f6368;
  border-bottom: 3px solid transparent;   /* 默认透明底边框 */
  transition: all 0.2s;                   /* 平滑过渡效果 */
  white-space: nowrap;                    /* 文字不换行 */
  user-select: none;                      /* 防止文字被选中 */
}

/* 标签悬浮效果 */
.category-tab:hover {
  color: #1a73e8;           /* Google 蓝 */
  background: #f1f3f4;      /* 浅灰背景 */
}

/* 选中状态 */
.category-tab.active {
  color: #1a73e8;
  border-bottom-color: #1a73e8;   /* 蓝色下划线 */
}

/* ==================== 精选横幅轮播 ==================== */
.featured-banner {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);   /* 紫色渐变背景 */
  padding: 40px 0;
}

.banner-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 24px;
}

.banner-carousel :deep(.slick-slide) {
  padding: 0;
}

.banner-carousel :deep(.slick-dots) {
  bottom: -30px;
}

.banner-carousel :deep(.slick-dots li button) {
  background: rgba(255, 255, 255, 0.5);
}

.banner-carousel :deep(.slick-dots li.slick-active button) {
  background: #fff;
}

.banner-slide {
  outline: none;
}

.banner-content {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  padding: 40px;
  cursor: pointer;
  transition: all 0.3s;
  backdrop-filter: blur(10px);
}

.banner-content:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
}

.banner-left {
  display: flex;
  gap: 32px;
  align-items: center;
}

.banner-icon {
  font-size: 100px;
  line-height: 1;
}

.banner-info {
  flex: 1;
}

.banner-title {
  font-size: 32px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: #202124;
}

.banner-description {
  font-size: 16px;
  color: #5f6368;
  margin: 0 0 16px 0;
  line-height: 1.6;
}

.banner-stats {
  display: flex;
  gap: 24px;
  font-size: 14px;
}

.banner-rating,
.banner-downloads {
  display: flex;
  align-items: center;
  color: #5f6368;
  font-weight: 500;
}

/* 主内容区 */
.store-main {
  background: #fff;
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
  color: #5f6368;
  font-size: 16px;
}

.empty-text {
  font-size: 20px;
  color: #5f6368;
  margin: 16px 0 8px 0;
}

.empty-hint {
  font-size: 14px;
  color: #80868b;
  margin: 0;
}

/* 区块标题 */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e8eaed;
}

.section-title {
  font-size: 24px;
  font-weight: 500;
  color: #202124;
  margin: 0;
}

.results-count {
  font-size: 14px;
  color: #5f6368;
}

/* ==================== 应用网格布局 ==================== */
.apps-grid {
  display: grid;
  /* 自适应网格：每列最小 280px，自动填充，平分剩余空间 */
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;                  /* 卡片之间的间距 */
}

/* ==================== 应用卡片 ==================== */
.app-card {
  background: #fff;
  border: 1px solid #dadce0;      /* 细边框 */
  border-radius: 8px;             /* 圆角 */
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;           /* 平滑过渡 */
  display: flex;
  flex-direction: column;         /* 垂直布局 */
}

/* 卡片悬浮效果：轻微阴影 */
.app-card:hover {
  box-shadow: 0 1px 3px 1px rgba(60, 64, 67, 0.15);
  border-color: #dadce0;
}

/* 卡片头部：图标和基本信息 */
.card-header {
  display: flex;
  gap: 16px;                  /* 图标和信息之间的间距 */
  margin-bottom: 16px;
}

.app-icon-wrapper {
  flex-shrink: 0;             /* 图标不收缩 */
}

.app-icon {
  font-size: 48px;
  line-height: 1;
  display: block;
}

.app-basic-info {
  flex: 1;                    /* 占据剩余空间 */
  min-width: 0;               /* 允许内容收缩，配合 overflow 实现省略号 */
}

/* 应用名称 */
.app-name {
  font-size: 16px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 4px 0;
  overflow: hidden;           /* 隐藏溢出内容 */
  text-overflow: ellipsis;    /* 显示省略号 */
  white-space: nowrap;        /* 不换行 */
}

/* 应用作者 */
.app-author {
  font-size: 12px;
  color: #5f6368;
  margin: 0 0 8px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 评分区域 */
.app-rating {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.star-icon {
  color: #faad14;             /* 橙黄色星星 */
  font-size: 14px;
}

.rating-value {
  color: #202124;
  font-weight: 500;
}

.rating-count {
  color: #5f6368;             /* 灰色用户数 */
}

/* 应用描述 */
.app-description {
  font-size: 13px;
  color: #5f6368;
  line-height: 1.6;
  margin: 0 0 16px 0;
  /* Webkit 多行文本省略号 */
  display: -webkit-box;
  -webkit-line-clamp: 2;      /* 最多显示 2 行 */
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;                    /* 占据剩余空间 */
}

/* 卡片底部：分类和按钮 */
.card-footer {
  display: flex;
  justify-content: space-between;   /* 两端对齐 */
  align-items: center;
  margin-top: auto;                 /* 自动推到底部 */
  padding-top: 12px;
  border-top: 1px solid #f1f3f4;    /* 顶部分隔线 */
}

/* 分类标签 */
.app-category-badge {
  font-size: 11px;
  color: #1a73e8;               /* Google 蓝 */
  background: #e8f0fe;          /* 浅蓝背景 */
  padding: 4px 10px;
  border-radius: 12px;          /* 药丸形状 */
  font-weight: 500;
}

/* 安装按钮 */
.install-btn {
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  padding: 0 16px;
  height: 32px;
}

/* 已安装状态按钮：绿色主题 */
.install-btn.installed {
  background: #e8f5e9;          /* 浅绿背景 */
  border-color: #81c784;        /* 绿色边框 */
  color: #2e7d32;               /* 深绿文字 */
}

.install-btn.installed:hover {
  background: #c8e6c9;
  border-color: #66bb6a;
  color: #1b5e20;
}

/* 应用详情模态框 */
.app-detail-modal :deep(.ant-modal-content) {
  border-radius: 8px;
}

.app-detail-modal :deep(.ant-modal-header) {
  border-bottom: none;
  padding: 24px 24px 0;
}

.app-detail-modal :deep(.ant-modal-body) {
  padding: 24px;
}

.app-detail {
  color: #202124;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid #e8eaed;
}

.detail-left {
  display: flex;
  gap: 24px;
  flex: 1;
}

.detail-icon-wrapper {
  flex-shrink: 0;
}

.detail-icon {
  font-size: 96px;
  line-height: 1;
  display: block;
}

.detail-main-info {
  flex: 1;
}

.detail-title {
  font-size: 28px;
  font-weight: 500;
  margin: 0 0 8px 0;
  color: #202124;
}

.detail-author {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 16px 0;
}

.detail-rating-section {
  margin-top: 16px;
}

.rating-box {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.rating-score {
  font-size: 48px;
  font-weight: 400;
  color: #202124;
  line-height: 1;
}

.rating-stars {
  display: flex;
  gap: 2px;
}

.rating-stars .star {
  color: #faad14;
  font-size: 16px;
}

.rating-text {
  font-size: 12px;
  color: #5f6368;
}

.detail-actions {
  flex-shrink: 0;
}

.detail-action-btn {
  min-width: 200px;
  height: 40px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
}

.installed-btn {
  background: #e8f5e9;
  border-color: #81c784;
  color: #2e7d32;
}

.installed-btn:hover {
  background: #c8e6c9 !important;
  border-color: #66bb6a !important;
  color: #1b5e20 !important;
}

.detail-body {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-subtitle {
  font-size: 16px;
  font-weight: 500;
  color: #202124;
  margin: 0;
}

.detail-description {
  font-size: 14px;
  color: #5f6368;
  line-height: 1.6;
  margin: 0;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: #80868b;
  font-weight: 500;
  text-transform: uppercase;
}

.info-value {
  font-size: 14px;
  color: #202124;
}

.detail-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-tag {
  font-size: 13px;
  padding: 4px 12px;
  border-radius: 16px;
  background: #f1f3f4;
  border: 1px solid #e8eaed;
  color: #5f6368;
}

/* ==================== 响应式设计 ==================== */

/* 平板设备（宽度 ≤ 1024px） */
@media (max-width: 1024px) {
  .apps-grid {
    /* 缩小卡片最小宽度，适应平板屏幕 */
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  }
}

/* 移动设备（宽度 ≤ 768px） */
@media (max-width: 768px) {
  /* 头部改为垂直布局 */
  .header-container {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }

  /* 缩小 Logo 尺寸 */
  .store-logo {
    font-size: 18px;
  }

  .logo-icon {
    font-size: 24px;
  }

  /* 搜索框占满宽度 */
  .search-box {
    max-width: 100%;
  }

  /* 分类标签间距缩小 */
  .categories-container {
    gap: 4px;
  }

  .category-tab {
    padding: 12px 16px;
    font-size: 13px;
  }

  /* 横幅内边距减小 */
  .banner-content {
    padding: 24px;
  }

  /* 横幅改为垂直布局 */
  .banner-left {
    flex-direction: column;
    gap: 16px;
    text-align: center;
  }

  .banner-icon {
    font-size: 72px;
  }

  .banner-title {
    font-size: 24px;
  }

  /* 应用卡片改为单列 */
  .apps-grid {
    grid-template-columns: 1fr;
  }

  /* 详情页改为垂直布局 */
  .detail-header {
    flex-direction: column;
    gap: 24px;
  }

  .detail-left {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  /* 操作按钮占满宽度 */
  .detail-action-btn {
    width: 100%;
  }

  /* 信息网格改为单列 */
  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>

