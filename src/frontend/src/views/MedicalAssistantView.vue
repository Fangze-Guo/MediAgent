<template>
  <div class="medical-assistant">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">医学图像处理助手</h1>
          <p class="page-subtitle">DICOM到NII格式转换工具</p>
        </div>
        <div class="header-actions">
          <a-button type="primary" size="large" @click="startNewTask">
            <template #icon>
              <PlusOutlined />
            </template>
            新建任务
          </a-button>
        </div>
      </div>
    </div>

    <!-- 功能卡片网格 -->
    <div class="tools-grid">
      <div class="tools-section">
        <h2 class="section-title">推荐工具</h2>
        <div class="tools-container">
          <div 
            v-for="tool in medicalTools" 
            :key="tool.id"
            class="tool-card"
            :class="{ 'featured': tool.featured }"
            @click="selectTool(tool)"
          >
            <div class="tool-icon" :style="{ background: tool.gradient }">
              <component :is="tool.icon" />
            </div>
            <div class="tool-content">
              <h3 class="tool-title">{{ tool.name }}</h3>
              <p class="tool-description">{{ tool.description }}</p>
              <div class="tool-tags">
                <span class="tag" :class="tool.category">{{ tool.categoryText }}</span>
                <span class="status" :class="tool.status">{{ tool.statusText }}</span>
              </div>
            </div>
            <div class="tool-actions">
              <a-button type="text" size="small" @click.stop="viewDetails(tool)">
                详情
              </a-button>
              <a-button type="primary" size="small" @click.stop="startChatWithTool(tool)">
                开始对话
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 工具详情模态框 -->
    <a-modal
      v-model:open="detailModalVisible"
      :title="selectedTool?.name"
      width="600px"
      :footer="null"
    >
      <div v-if="selectedTool" class="tool-detail">
        <div class="detail-header">
          <div class="detail-icon" :style="{ background: selectedTool.gradient }">
            <component :is="selectedTool.icon" />
          </div>
          <div class="detail-info">
            <h3>{{ selectedTool.name }}</h3>
            <p>{{ selectedTool.description }}</p>
            <div class="detail-tags">
              <span class="tag" :class="selectedTool.category">{{ selectedTool.categoryText }}</span>
              <span class="status" :class="selectedTool.status">{{ selectedTool.statusText }}</span>
            </div>
          </div>
        </div>
        
        <div class="detail-content">
          <div class="detail-section">
            <h4>功能特点</h4>
            <ul>
              <li v-for="feature in selectedTool.features" :key="feature">{{ feature }}</li>
            </ul>
          </div>
          
          <div class="detail-section">
            <h4>使用方法</h4>
            <div class="usage-content">
              <MarkdownRenderer :content="selectedTool.usage" />
            </div>
          </div>
          
          <div class="detail-section">
            <h4>参数说明</h4>
            <div class="params-list">
              <div v-for="param in selectedTool.params" :key="param.name" class="param-item">
                <div class="param-name">{{ param.name }}</div>
                <div class="param-type">{{ param.type }}</div>
                <div class="param-desc">{{ param.description }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 进度显示组件 -->
    <ProgressDisplay
      :visible="progressVisible"
      :title="progressTitle"
      :task-title="progressTaskTitle"
      :progress="progressValue"
      :status="progressStatus"
      :details="progressDetails"
      :completed="progressCompleted"
      @update:visible="progressVisible = $event"
      @cancel="handleProgressCancel"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { useConversationsStore } from '@/store/conversations'
import { 
  PlusOutlined,
  FileImageOutlined,
  SwapOutlined
} from '@ant-design/icons-vue'
import ProgressDisplay from '@/components/ProgressDisplay.vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'

// 状态管理
const conversationsStore = useConversationsStore()

// 类型定义
interface MedicalTool {
  id: string
  name: string
  description: string
  icon: any
  gradient: string
  category: string
  categoryText: string
  status: string
  statusText: string
  featured: boolean
  features: string[]
  usage: string
  params: Array<{
    name: string
    type: string
    description: string
  }>
}

interface ProgressDetail {
  text: string
  subText?: string
  completed?: boolean
}

// 响应式数据
const detailModalVisible = ref(false)
const selectedTool = ref<MedicalTool | null>(null)
const currentTool = ref<MedicalTool | null>(null)

// 进度相关
const progressVisible = ref(false)
const progressTitle = ref('处理进度')
const progressTaskTitle = ref('')
const progressValue = ref(0)
const progressStatus = ref('处理中...')
const progressDetails = ref<ProgressDetail[]>([])
const progressCompleted = ref(false)

// 医学工具数据 - 严格对齐后端实现
const medicalTools = ref<MedicalTool[]>([
  {
    id: 'convert_dicom_series',
    name: '单序列DICOM转换',
    description: '将单个DICOM序列转换为NII文件，适用于精确控制单个序列的转换',
    icon: FileImageOutlined,
    gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    category: 'conversion',
    categoryText: '单序列转换',
    status: 'available',
    statusText: '可用',
    featured: true,
    features: [
      '精确控制输出文件名',
      '支持单个序列转换',
      '保持原始空间信息',
      '适合测试和验证',
      '使用SimpleITK确保转换质量',
      '返回详细的图像信息（尺寸、间距等）'
    ],
    usage: `**使用步骤：**
1. 将单个DICOM序列放在 \`data/\` 目录中
2. 在对话中告诉AI："请帮我将data/dicom文件夹转换为output/series1.nii.gz"
3. AI会自动调用单序列转换工具
4. 转换后的文件保存在指定路径

**适用场景：**
- 单个患者的单个序列转换
- 需要精确控制输出文件名
- 测试和验证转换效果

**目录结构示例：**
\`\`\`
data/
└── dicom_series/
    ├── IM-0001-0001.dcm
    ├── IM-0001-0002.dcm
    └── ...
\`\`\`

**输出结果：**
\`\`\`
output/
└── series1.nii.gz  # 指定文件名
\`\`\``,
    params: [
      {
        name: 'dicom_directory',
        type: 'string',
        description: 'DICOM文件目录路径（必需）'
      },
      {
        name: 'output_file',
        type: 'string',
        description: '输出NII文件路径（包含文件名，必需）'
      },
      {
        name: 'compression',
        type: 'boolean',
        description: '是否压缩输出文件（默认：true，推荐启用）'
      }
    ]
  },
  {
    id: 'batch_convert_patients',
    name: '多患者批量转换',
    description: '批量转换多个患者的DICOM数据，自动识别C0/C2序列，适合大规模数据处理',
    icon: SwapOutlined,
    gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    category: 'batch',
    categoryText: '批量处理',
    status: 'available',
    statusText: '可用',
    featured: true,
    features: [
      '自动识别C0/C2序列',
      '按患者组织输出文件',
      '支持多患者批量处理',
      '详细的处理结果报告',
      '适合工作流编排',
      '错误自动跳过，继续处理其他数据'
    ],
    usage: `**使用步骤：**
1. 按照患者目录结构组织DICOM文件
2. 在对话中告诉AI："请帮我批量转换data目录下所有患者的DICOM数据"
3. AI会自动调用多患者批量转换工具
4. 转换后的文件按患者分别保存

**适用场景：**
- 多患者批量处理
- 大规模数据转换
- 自动化工作流

**输入目录结构：**
\`\`\`
data/
├── patient001/
│   ├── C0/          # 对比前序列
│   │   ├── IM-0001-0001.dcm
│   │   └── ...
│   └── C2/          # 对比后序列
│       ├── IM-0002-0001.dcm
│       └── ...
├── patient002/
│   ├── C0/
│   └── C2/
└── ...
\`\`\`

**输出目录结构：**
\`\`\`
output/
├── patient001/
│   ├── C0.nii.gz
│   └── C2.nii.gz
├── patient002/
│   ├── C0.nii.gz
│   └── C2.nii.gz
└── ...
\`\`\``,
    params: [
      {
        name: 'patients_directory',
        type: 'string',
        description: '患者文件夹目录（每个子文件夹为一个患者）（必需）'
      },
      {
        name: 'output_directory',
        type: 'string',
        description: '输出目录（必需）'
      },
      {
        name: 'compression',
        type: 'boolean',
        description: '是否压缩输出文件（默认：true，推荐启用）'
      }
    ]
  }
])

// 工具相关方法
const selectTool = (tool: MedicalTool) => {
  selectedTool.value = tool
}

const startNewTask = () => {
  message.info('请选择要使用的工具')
}

const viewDetails = (tool: MedicalTool) => {
  selectTool(tool)
}

// 对话相关方法
const startChatWithTool = (tool: MedicalTool) => {
  currentTool.value = tool
  
  // 创建医学助手专用会话
  const conversationId = `medical-${tool.id}-${Date.now()}`
  
  // 创建会话，传递工具信息
  conversationsStore.createConversation(conversationId, 'medical', {
    toolId: tool.id,
    toolName: tool.name,
    toolIcon: tool.icon,
    toolGradient: tool.gradient
  })
  
  // 根据工具类型生成不同的欢迎消息
  const welcomeMessage = generateWelcomeMessage(tool)
  
  conversationsStore.appendMessage(conversationId, welcomeMessage)
  
  // 跳转到聊天页面
  window.location.href = `/chat/${conversationId}`
}

// 根据工具生成欢迎消息
const generateWelcomeMessage = (tool: MedicalTool) => {
  const baseMessage = {
    role: 'assistant' as const,
    assistantType: 'medical' as const
  }
  
  if (tool.id === 'convert_dicom_series') {
    return {
      ...baseMessage,
      content: `您好！我是**单序列DICOM转换专家**，专门处理单个DICOM序列的精确转换。

**我的专业能力：**
• 🎯 精确控制输出文件名和路径
• 🔍 单个序列的详细分析和转换
• ⚙️ 专业的参数配置建议
• 📊 详细的图像信息分析

**适用场景：**
• 单个患者的单个序列转换
• 需要精确控制输出文件名
• 测试和验证转换效果
• 小规模数据处理

**快速开始：**
1. 将单个DICOM序列放在 \`data/\` 目录中
2. 告诉我您想要的输出文件名和路径
3. 我会为您提供精确的转换方案

请告诉我您想要转换哪个DICOM序列，以及您希望的输出文件名？`
    }
  } else if (tool.id === 'batch_convert_patients') {
    return {
      ...baseMessage,
      content: `您好！我是**多患者批量转换专家**，专门处理大规模DICOM数据的批量转换。

**我的专业能力：**
• 🚀 多患者批量处理
• 🔄 自动识别C0/C2序列
• 📁 按患者组织输出文件
• 📈 详细的处理结果报告

**适用场景：**
• 多患者批量处理
• 大规模数据转换
• 自动化工作流
• 临床研究数据处理

**目录结构要求：**
\`\`\`
data/
├── patient001/
│   ├── C0/          # 对比前序列
│   └── C2/          # 对比后序列
├── patient002/
│   ├── C0/
│   └── C2/
└── ...
\`\`\`

**快速开始：**
1. 按照患者目录结构组织DICOM文件
2. 告诉我您要处理的患者范围
3. 我会为您提供批量转换方案

请告诉我您要批量转换哪些患者的数据？`
    }
  }
  
  // 默认欢迎消息
  return {
    ...baseMessage,
    content: `您好！我是专业的医学图像处理专家。

**我可以为您提供：**
• 🔄 DICOM到NII格式转换
• 📁 批量多患者数据处理
• ⚙️ 专业的参数配置建议
• 📊 详细的技术解释和指导

请告诉我您想要处理什么类型的医学图像数据？`
  }
}

// 进度相关方法
const handleProgressCancel = () => {
  message.warning('任务已取消')
  progressVisible.value = false
}
</script>

<style scoped>
.medical-assistant {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  padding: 24px;
}

.page-header {
  margin-bottom: 32px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

.title-section {
  flex: 1;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0 0 8px 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.page-subtitle {
  font-size: 16px;
  color: #666;
  margin: 0;
}

.tools-grid {
  max-width: 1200px;
  margin: 0 auto;
}

.tools-section {
  margin-bottom: 32px;
}

.section-title {
  font-size: 24px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 20px;
}

.tools-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
}

.tool-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  cursor: pointer;
  border: 2px solid transparent;
}

.tool-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
  border-color: #667eea;
}

.tool-card.featured {
  border-color: #667eea;
  background: linear-gradient(135deg, #f8f9ff 0%, #ffffff 100%);
}

.tool-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
  margin-bottom: 16px;
}

.tool-content {
  margin-bottom: 20px;
}

.tool-title {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.tool-description {
  font-size: 14px;
  color: #666;
  line-height: 1.5;
  margin: 0 0 16px 0;
}

.tool-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.tag.conversion {
  background: #e3f2fd;
  color: #1976d2;
}

.tag.batch {
  background: #fce4ec;
  color: #c2185b;
}

.status {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status.available {
  background: #e8f5e8;
  color: #2e7d32;
}

.tool-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.tool-detail {
  padding: 20px 0;
}

.detail-header {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e8e8e8;
}

.detail-icon {
  width: 80px;
  height: 80px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 32px;
  margin-right: 20px;
}

.detail-info h3 {
  font-size: 24px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.detail-info p {
  font-size: 14px;
  color: #666;
  margin: 0 0 12px 0;
}

.detail-tags {
  display: flex;
  gap: 8px;
}

.detail-content {
  margin-top: 20px;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section h4 {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 12px 0;
}

.detail-section ul {
  margin: 0;
  padding-left: 20px;
}

.detail-section li {
  font-size: 14px;
  color: #666;
  margin-bottom: 4px;
}

.params-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.param-item {
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 4px solid #667eea;
}

.param-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 4px;
}

.param-type {
  font-size: 12px;
  color: #667eea;
  font-weight: 500;
  margin-bottom: 4px;
}

.param-desc {
  font-size: 13px;
  color: #666;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .tools-container {
    grid-template-columns: 1fr;
  }
  
  .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .detail-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .detail-icon {
    margin-right: 0;
    margin-bottom: 16px;
  }
}
</style>