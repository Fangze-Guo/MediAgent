import { createI18n } from 'vue-i18n'
import enUS from './locales/en-US.json'
import zhCN from './locales/zh-CN.json'

// 定义语言类型
export type MessageSchema = typeof enUS

// 获取浏览器语言或本地存储的语言，默认为英文
const getDefaultLocale = (): string => {
  const stored = localStorage.getItem('locale')
  if (stored) return stored

  const browserLang = navigator.language.toLowerCase()
  if (browserLang.startsWith('zh')) {
    return 'zh-CN'
  }
  return 'en-US'
}

const defaultLocale = getDefaultLocale()

const options = {
  legacy: false, // 使用 Composition API
  locale: defaultLocale,
  fallbackLocale: 'en-US',
  messages: {
    'en-US': enUS,
    'zh-CN': zhCN
  }
}

const i18n = createI18n(options)

// 导出语言切换函数
export const setLocale = (locale: string) => {
  localStorage.setItem('locale', locale)
  ;(i18n.global.locale as any).value = locale
}

// 导出当前语言获取函数
export const getLocale = (): string => {
  const locale = i18n.global.locale as any
  return typeof locale === 'string' ? locale : locale.value
}

export default i18n
