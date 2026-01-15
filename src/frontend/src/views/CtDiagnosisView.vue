<template>
  <div class="ct-diagnosis-container">
    <div class="page-header">
      <h2 class="page-title">
        <ReconciliationOutlined />
        {{ t('views_CtDiagnosisView.title') }}
      </h2>
    </div>
    <div class="page-content">
      <a-empty :description="t('views_CtDiagnosisView.placeholder')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ReconciliationOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<style scoped>
.ct-diagnosis-container {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.page-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
