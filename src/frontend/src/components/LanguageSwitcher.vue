<template>
  <div class="language-switcher">
    <a-select
      v-model:value="currentLocale"
      style="width: 100px"
      @change="handleLocaleChange"
    >
      <a-select-option value="en-US">English</a-select-option>
      <a-select-option value="zh-CN">中文</a-select-option>
    </a-select>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale, getLocale } from '@/i18n'

const { locale } = useI18n()
const currentLocale = ref<string>(getLocale())

const handleLocaleChange = (value: string) => {
  setLocale(value)
  locale.value = value
}

// 监听 locale 变化
watch(
  () => locale.value,
  (newLocale) => {
    currentLocale.value = newLocale
  }
)
</script>

<style scoped>
.language-switcher {
  display: flex;
  align-items: center;
}

.language-switcher :deep(.ant-select) {
  width: 100px;
}
</style>
