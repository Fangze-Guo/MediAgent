<template>
  <a-breadcrumb class="breadcrumb">
    <a-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
      <router-link v-if="item.path && !item.isLast" :to="item.path">
        {{ item.title }}
      </router-link>
      <span v-else>{{ item.title }}</span>
    </a-breadcrumb-item>
  </a-breadcrumb>
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const route = useRoute()
const { t } = useI18n()

interface Breadcrumb {
  title: string
  path?: string
  isLast: boolean
}

// 路由名称到 i18n key 的映射
const routeI18nMap: Record<string, string> = {
  'Home': 'breadcrumb.home',
  'Conversation': 'breadcrumb.conversation',
  'files': 'breadcrumb.files',
  'Tasks': 'breadcrumb.tasks',
  'Datasets': 'breadcrumb.datasets',
  'Settings': 'breadcrumb.settings',
  'SkillStore': 'breadcrumb.skillStore',
  'SkillDetail': 'breadcrumb.skillDetail',
  'ModelConfig': 'breadcrumb.modelConfig',
  'ClinicalTools': 'breadcrumb.clinicalTools',
  'NiceBcxAgent': 'breadcrumb.niceBcxAgent',
  'NiceBcxWorkflow': 'breadcrumb.niceBcxWorkflow',
  'NiceBcxKnowledgeBase': 'breadcrumb.niceBcxKnowledgeBase',
  'KnowledgeBaseDetail': 'breadcrumb.knowledgeBaseDetail',
  'DocumentDetail': 'breadcrumb.documentDetail'
}

const breadcrumbs = computed<Breadcrumb[]>(() => {
  const items: Breadcrumb[] = []

  // 添加首页
  if (route.name !== 'Home') {
    items.push({
      title: t('breadcrumb.home'),
      path: '/',
      isLast: false
    })
  }

  // 处理当前路由
  const i18nKey = routeI18nMap[route.name as string]
  const currentTitle = i18nKey ? t(i18nKey) : String(route.name)

  // 如果是详情页，添加父级路由
  if (route.name === 'SkillDetail') {
    items.push({
      title: t('breadcrumb.skillStore'),
      path: '/skill-store',
      isLast: false
    })
  } else if (route.name === 'KnowledgeBaseDetail') {
    items.push({
      title: t('breadcrumb.niceBcxKnowledgeBase'),
      path: '/nice-bcx-knowledge-base',
      isLast: false
    })
  } else if (route.name === 'DocumentDetail') {
    items.push({
      title: t('breadcrumb.niceBcxKnowledgeBase'),
      path: '/nice-bcx-knowledge-base',
      isLast: false
    })
    if (route.params.kbId) {
      items.push({
        title: t('breadcrumb.knowledgeBaseDetail'),
        path: `/knowledge-base/${route.params.kbId}`,
        isLast: false
      })
    }
  }

  // 添加当前页面
  items.push({
    title: currentTitle,
    isLast: true
  })

  return items
})
</script>

<style scoped>
.breadcrumb {
  margin: 0;
}

.breadcrumb :deep(.ant-breadcrumb-link) {
  color: inherit;
}

.breadcrumb :deep(.ant-breadcrumb-link):hover {
  color: #1890ff;
}
</style>
