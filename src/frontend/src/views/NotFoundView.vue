<template>
  <div class="not-found-page">
    <div class="not-found-content">
      <h1>404</h1>
      <h2>{{ t('views_NotFoundView.title') }}</h2>
      <p>{{ t('views_NotFoundView.message') }}</p>
      <router-link to="/" class="back-home">{{ t('views_NotFoundView.backHome') }}</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<style scoped>
.not-found-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  text-align: center;
}

.not-found-content h1 {
  font-size: 120px;
  margin: 0;
  font-weight: 700;
  opacity: 0.8;
}

.not-found-content h2 {
  font-size: 32px;
  margin: 0 0 16px 0;
  font-weight: 600;
}

.not-found-content p {
  font-size: 18px;
  margin: 0 0 32px 0;
  opacity: 0.9;
}

.back-home {
  display: inline-block;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  text-decoration: none;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  transition: all 0.3s ease;
}

.back-home:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .not-found-content h1 {
    font-size: 80px;
  }
  
  .not-found-content h2 {
    font-size: 24px;
  }
  
  .not-found-content p {
    font-size: 16px;
  }
}
</style>
