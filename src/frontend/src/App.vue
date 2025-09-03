<template>
  <div id="app">
    <Layout />
  </div>
</template>

<script setup lang="ts">
import Layout from '@/layout/Layout.vue'
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

.root-layout {
  width: 100%;
  height: 100%;
  display: flex; /* 添加 Flex 布局 */
  flex-direction: row; /* 横向排列子元素 */
}

.app-sider {
  background: #ffffff;
  border-right: 1px solid #e5e7eb;
  position: relative;
  transition: width 0.3s ease;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.05);
  z-index: 10;
}

.app-content {
  flex: 1; /* 占满剩余空间 */
  height: 100%;
  overflow: hidden;
  background: #f5f5f5;
}

.toggle-btn {
  position: absolute;
  top: 20px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 11;
  transition: left 0.3s ease, transform 0.2s ease;
}

.toggle-btn:hover {
  transform: scale(1.1);
}
</style>