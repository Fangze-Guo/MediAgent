<template>
  <div id="app">
    <!-- 登录页面使用独立布局 -->
    <LoginView v-if="isLoginPage" />
    <!-- 其他页面使用主布局 -->
    <Layout v-else />
    <GlobalFileUpload />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Layout from '@/layout/Layout.vue'
import LoginView from '@/views/LoginView.vue'
import GlobalFileUpload from '@/components/file/GlobalFileUpload.vue'

const route = useRoute()

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