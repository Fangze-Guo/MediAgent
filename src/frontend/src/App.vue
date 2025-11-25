<template>
  <a-config-provider :locale="antdLocale">
    <div id="app">
      <!-- 登录页面使用独立布局 -->
      <LoginView v-if="isLoginPage" />
      <!-- 其他页面使用主布局 -->
      <Layout v-else />
      <!-- 全局组件 -->
      <GlobalFileUpload />
    </div>
  </a-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import enUS from 'ant-design-vue/es/locale/en_US'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import Layout from '@/layout/Layout.vue'
import LoginView from '@/views/LoginView.vue'
import GlobalFileUpload from '@/components/file/GlobalFileUpload.vue'

const route = useRoute()
const { locale } = useI18n()

// Ant Design locale mapping
const localeMap = {
  'en-US': enUS,
  'zh-CN': zhCN
}

// 根据 i18n 的 locale 动态设置 Ant Design locale
const antdLocale = computed(() => {
  return localeMap[locale.value as keyof typeof localeMap] || enUS
})

// 判断是否为登录页面
const isLoginPage = computed(() => route.name === 'Login')
</script>

<style>
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  margin: 0;
  padding: 0;
  overflow: hidden;
  width: 100vw;
  height: 100vh;
}

* {
  box-sizing: border-box;
}
</style>