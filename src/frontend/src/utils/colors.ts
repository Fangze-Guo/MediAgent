/**
 * 模型分类颜色配置
 */
export const getCategoryColor = (category: string): string => {
  const colors: Record<string, string> = {
    'text': 'blue',
    'multimodal': 'purple',
    'code': 'green',
    'reasoning': 'red',
    'chat': 'orange'
  }
  return colors[category] || 'default'
}

/**
 * 提供商颜色配置
 */
export const getProviderColor = (provider: string): string => {
  const colors: Record<string, string> = {
    'OpenAI': '#10a37f',
    'Anthropic': '#d97706',
    'AliCloud': '#ff6a00',
    'Alibaba': '#ff6a00',
    '阿里云': '#ff6a00',
    'DeepSeek': '#1890ff',
    'Google': '#4285f4',
    'Baidu': '#3385ff'
  }
  return colors[provider] || '#666666'
}
