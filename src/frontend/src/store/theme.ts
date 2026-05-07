import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  // 从 localStorage 读取主题设置，默认为 light
  const savedTheme = localStorage.getItem('theme')
  const isDark = ref(savedTheme === 'dark')

  // 应用主题到 document
  const applyTheme = (dark: boolean) => {
    if (dark) {
      document.documentElement.classList.add('dark')
      document.documentElement.setAttribute('data-theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      document.documentElement.setAttribute('data-theme', 'light')
    }
  }

  // 初始化时应用主题
  applyTheme(isDark.value)

  // 切换主题
  const toggleTheme = () => {
    isDark.value = !isDark.value
  }

  // 监听主题变化并保存到 localStorage
  watch(isDark, (newValue) => {
    localStorage.setItem('theme', newValue ? 'dark' : 'light')
    applyTheme(newValue)
  })

  return {
    isDark,
    toggleTheme
  }
})
