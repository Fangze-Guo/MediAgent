<template>
  <a-layout class="root-layout">
    <a-layout-sider 
        :collapsed="collapsed" 
        :collapsible="true" 
        :trigger="null" 
        :width="300" 
        :collapsedWidth="0"
        theme="light" 
        class="app-sider">
      <Sidebar />
    </a-layout-sider>
    <a-layout class="site-layout">
      <a-layout-header style="background: #fff; padding: 0">
        <menu-unfold-outlined v-if="collapsed" class="trigger" @click="toggle()" />
        <menu-fold-outlined v-else class="trigger" @click="toggle()" />
      </a-layout-header>
      <a-layout-content class="app-content">
        <Suspense>
          <router-view />
          <template #fallback>
            <div class="loading-container">
              <a-spin size="large" />
              <p>加载中...</p>
            </div>
          </template>
        </Suspense>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script lang="ts" setup>
import { ref } from 'vue'
import Sidebar from '@/components/Sidebar.vue'
import { MenuUnfoldOutlined, MenuFoldOutlined } from '@ant-design/icons-vue'

const collapsed = ref(false)
const toggle = () => (collapsed.value = !collapsed.value)
</script>

<style>
.root-layout {
  width: 100%;
  height: 100vh;
  display: flex;
}

.app-sider {
  background: #ffffff;
  border-right: 1px solid #e5e7eb;
}

.site-layout {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  min-width: 0;
}

.trigger {
  font-size: 18px;
  cursor: pointer;
}

.app-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: #f5f5f5;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #666;
}

.loading-container p {
  margin-top: 16px;
  margin-bottom: 0;
}
</style>
  