<template>
  <div class="workflow-container">
    <a-card>
      <template #title>
        <div style="display: flex; align-items: center; gap: 12px;">
          <ApartmentOutlined style="font-size: 24px;" />
          <span>NICE-BCX Workflow</span>
        </div>
      </template>
      
      <a-empty 
        :description="t('views_WorkflowView.comingSoon')"
        style="margin: 60px 0;"
      >
        <template #image>
          <ApartmentOutlined style="font-size: 64px; color: #d9d9d9;" />
        </template>
      </a-empty>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ApartmentOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<style scoped>
.workflow-container {
  padding: 24px;
  height: 100%;
  overflow: auto;
}
</style>
