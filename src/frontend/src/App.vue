<template>
  <div id="app">
    <Layout />
    <GlobalFileUpload />
  </div>
</template>

<script setup lang="ts">
import Layout from '@/layout/Layout.vue'
import GlobalFileUpload from '@/components/file/GlobalFileUpload.vue'
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