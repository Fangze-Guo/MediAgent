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
        :style="{ '--card-accent': card.color }"
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
    color: '#3b82f6',
  },
  {
    path: '/files',
    icon: '📁',
    title: t('views_HomeView.nav.files'),
    desc: t('views_HomeView.nav.filesDesc'),
    color: '#10b981',
  },
  {
    path: '/clinical-tools',
    icon: '🏥',
    title: t('views_HomeView.nav.clinicalTools'),
    desc: t('views_HomeView.nav.clinicalToolsDesc'),
    color: '#f59e0b',
  },
  {
    path: '/knowledge-base',
    icon: '📚',
    title: t('views_HomeView.nav.knowledgeBase'),
    desc: t('views_HomeView.nav.knowledgeBaseDesc'),
    color: '#8b5cf6',
  },
  {
    path: '/skill-repository',
    icon: '🧩',
    title: t('views_HomeView.nav.skillStore'),
    desc: t('views_HomeView.nav.skillStoreDesc'),
    color: '#ec4899',
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
  background: var(--bg-secondary);
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
  border: 1px solid color-mix(in srgb, var(--card-accent) 25%, transparent);
  background: color-mix(in srgb, var(--card-accent) 8%, var(--bg-primary));
  cursor: pointer;
  transition: box-shadow 0.15s, border-color 0.15s, transform 0.1s, background 0.15s;
  user-select: none;
}
.nav-card:hover {
  border-color: color-mix(in srgb, var(--card-accent) 55%, transparent);
  background: color-mix(in srgb, var(--card-accent) 13%, var(--bg-primary));
  box-shadow: 0 2px 12px color-mix(in srgb, var(--card-accent) 20%, transparent);
}
.nav-card:active {
  transform: scale(0.975);
  background: color-mix(in srgb, var(--card-accent) 18%, var(--bg-primary));
  border-color: color-mix(in srgb, var(--card-accent) 70%, transparent);
  box-shadow: 0 1px 4px color-mix(in srgb, var(--card-accent) 25%, transparent);
}
.card-icon {
  font-size: 22px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: color-mix(in srgb, var(--card-accent) 15%, transparent);
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


