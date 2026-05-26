<template>
  <div class="home-wrap">
    <div class="home-hero">
      <img src="/MedWiser.png" alt="MedWiser" class="hero-logo" />
      <h1 class="hero-title">{{ t('views_HomeView.welcome') }}</h1>
      <p class="hero-desc">{{ t('views_HomeView.description') }}</p>
    </div>

    <div class="nav-grid">
      <div
        v-for="card in navCards"
        :key="card.path"
        class="nav-card"
        @click="router.push(card.path)"
      >
        <div class="card-icon">{{ card.icon }}</div>
        <div class="card-body">
          <div class="card-title">{{ card.title }}</div>
          <div class="card-desc">{{ card.desc }}</div>
        </div>
        <span class="card-arrow">›</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { t } = useI18n()

const navCards = computed(() => [
  {
    path: '/conversation/new',
    icon: '💬',
    title: t('views_HomeView.nav.chat'),
    desc: t('views_HomeView.nav.chatDesc'),
  },
  {
    path: '/files',
    icon: '📁',
    title: t('views_HomeView.nav.files'),
    desc: t('views_HomeView.nav.filesDesc'),
  },
  {
    path: '/clinical-tools',
    icon: '🏥',
    title: t('views_HomeView.nav.clinicalTools'),
    desc: t('views_HomeView.nav.clinicalToolsDesc'),
  },
  {
    path: '/knowledge-base',
    icon: '📚',
    title: t('views_HomeView.nav.knowledgeBase'),
    desc: t('views_HomeView.nav.knowledgeBaseDesc'),
  },
  {
    path: '/skill-repository',
    icon: '🧩',
    title: t('views_HomeView.nav.skillStore'),
    desc: t('views_HomeView.nav.skillStoreDesc'),
  },
])
</script>

<style scoped>
.home-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--bg-primary);
  overflow-y: auto;
  padding: 48px 24px 40px;
  gap: 40px;
}

/* Hero 区 */
.home-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
}
.hero-logo {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  object-fit: contain;
}
.hero-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.4px;
}
.hero-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
  max-width: 560px;
}

/* 导航卡片网格 */
.nav-grid {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.nav-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-primary);
  cursor: pointer;
  transition: box-shadow 0.15s, border-color 0.15s;
}
.nav-card:hover {
  border-color: var(--link-color, #1890ff);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.07);
}
.card-icon {
  font-size: 22px;
  width: 36px;
  text-align: center;
  flex-shrink: 0;
}
.card-body {
  flex: 1;
  min-width: 0;
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
}
.card-desc {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-arrow {
  font-size: 18px;
  color: var(--text-tertiary, #9ca3af);
  flex-shrink: 0;
}


</style>


