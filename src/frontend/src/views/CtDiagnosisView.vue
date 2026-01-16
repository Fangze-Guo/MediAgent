<template>
  <div class="ct-diagnosis-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2 class="page-title">
        <ReconciliationOutlined />
        {{ t('views_CtDiagnosisView.title') }}
      </h2>
      <a-button type="primary" @click="handleUploadCT">
        <template #icon>
          <UploadOutlined />
        </template>
        {{ t('views_CtDiagnosisView.uploadCT') }}
      </a-button>
    </div>

    <div class="content-layout">
      <!-- 左侧：目录树和患者信息 -->
      <div class="left-panel">
        <!-- 患者信息卡片 -->
        <a-card class="info-card" :title="t('views_CtDiagnosisView.patientInfo')">
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item :label="t('views_CtDiagnosisView.patientName')">
              {{ currentPatient?.name || '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_CtDiagnosisView.gender')">
              {{ currentPatient?.gender || '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_CtDiagnosisView.age')">
              {{ currentPatient?.age || '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_CtDiagnosisView.examDate')">
              {{ currentPatient?.examDate || '-' }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('views_CtDiagnosisView.examPart')">
              {{ currentPatient?.examPart || '-' }}
            </a-descriptions-item>
          </a-descriptions>
        </a-card>

        <!-- 目录树 -->
        <a-card class="tree-card" :title="t('views_CtDiagnosisView.fileTree')">
          <a-input-search
            v-model:value="treeSearchValue"
            :placeholder="t('views_CtDiagnosisView.searchTree')"
            allow-clear
            class="tree-search"
            @search="handleTreeSearch"
          />
          <a-tree
            v-if="treeData.length > 0"
            :tree-data="treeData"
            :expanded-keys="expandedKeys"
            :selected-keys="selectedKeys"
            :auto-expand-parent="autoExpandParent"
            :show-line="{ showLeafIcon: false }"
            :show-icon="true"
            @expand="onExpand"
            @select="onSelect"
            class="file-tree"
          >
            <template #icon="{ selected, expanded, dataRef }">
              <FolderOutlined v-if="dataRef.isLeaf === false" />
              <FileImageOutlined v-else />
            </template>
            <template #title="{ title, key, dataRef }">
              <span class="tree-node-title">
                {{ title }}
                <a-tag v-if="dataRef.isCurrent" color="blue" size="small" class="current-tag">
                  {{ t('views_CtDiagnosisView.current') }}
                </a-tag>
              </span>
            </template>
          </a-tree>
          <a-empty v-else :description="t('views_CtDiagnosisView.noData')" />
        </a-card>

        <!-- AI 诊断结果 -->
        <a-card class="diagnosis-card" :title="t('views_CtDiagnosisView.aiDiagnosis')">
          <div v-if="diagnosisResults.length > 0" class="diagnosis-results">
            <div
              v-for="(result, index) in diagnosisResults"
              :key="index"
              class="diagnosis-item"
              :class="getDiagnosisClass(result.type)"
            >
              <div class="diagnosis-header">
                <a-tag :color="getDiagnosisTagColor(result.type)" class="diagnosis-tag">
                  {{ getDiagnosisTypeText(result.type) }}
                </a-tag>
                <span v-if="result.confidence" class="confidence">
                  {{ t('views_CtDiagnosisView.confidence') }}: {{ result.confidence }}%
                </span>
              </div>
              <p class="diagnosis-text">{{ result.description }}</p>
            </div>
          </div>
          <a-empty v-else :description="t('views_CtDiagnosisView.noDiagnosis')" />
        </a-card>
      </div>

      <!-- 右侧：CT 图像查看器 -->
      <div class="right-panel">
        <a-card class="viewer-card">
          <!-- 工具栏 -->
          <div class="toolbar">
            <div class="toolbar-left">
              <a-button-group>
                <a-button @click="handlePreviousSlice">
                  <template #icon>
                    <LeftOutlined />
                  </template>
                  {{ t('views_CtDiagnosisView.previous') }}
                </a-button>
                <a-button @click="handleNextSlice">
                  {{ t('views_CtDiagnosisView.next') }}
                  <template #icon>
                    <RightOutlined />
                  </template>
                </a-button>
              </a-button-group>
              <span class="slice-info">
                {{ t('views_CtDiagnosisView.slice') }} {{ currentSlice + 1 }} / {{ totalSlices }}
              </span>
            </div>
            <div class="toolbar-center">
              <div class="window-control">
                <span class="control-label">{{ t('views_CtDiagnosisView.windowWidth') }}:</span>
                <a-slider
                  v-model:value="windowWidth"
                  :min="0"
                  :max="2000"
                  :step="10"
                  style="width: 150px"
                  @change="handleWindowChange"
                />
                <a-input-number
                  v-model:value="windowWidth"
                  :min="0"
                  :max="2000"
                  :step="10"
                  style="width: 80px"
                  @change="handleWindowChange"
                />
              </div>
              <div class="window-control">
                <span class="control-label">{{ t('views_CtDiagnosisView.windowLevel') }}:</span>
                <a-slider
                  v-model:value="windowLevel"
                  :min="-1000"
                  :max="1000"
                  :step="10"
                  style="width: 150px"
                  @change="handleWindowChange"
                />
                <a-input-number
                  v-model:value="windowLevel"
                  :min="-1000"
                  :max="1000"
                  :step="10"
                  style="width: 80px"
                  @change="handleWindowChange"
                />
              </div>
            </div>
            <div class="toolbar-right">
              <a-button @click="handleResetView">
                <template #icon>
                  <ReloadOutlined />
                </template>
                {{ t('views_CtDiagnosisView.reset') }}
              </a-button>
              <a-button @click="handleZoomIn">
                <template #icon>
                  <ZoomInOutlined />
                </template>
              </a-button>
              <a-button @click="handleZoomOut">
                <template #icon>
                  <ZoomOutOutlined />
                </template>
              </a-button>
            </div>
          </div>

          <!-- 图像显示区域 -->
          <div class="image-viewer" ref="imageViewerRef">
            <div v-if="!currentImage" class="image-placeholder">
              <FileImageOutlined class="placeholder-icon" />
              <p class="placeholder-text">{{ t('views_CtDiagnosisView.noImage') }}</p>
              <p class="placeholder-hint">{{ t('views_CtDiagnosisView.selectImageHint') }}</p>
            </div>
            <div v-else class="image-container">
              <!-- 这里可以集成实际的 DICOM 图像渲染库，如 cornerstone.js 或 vtk.js -->
              <div class="image-display">
                <div class="image-overlay">
                  <div class="image-info">
                    <span>{{ t('views_CtDiagnosisView.windowWidth') }}: {{ windowWidth }}</span>
                    <span>{{ t('views_CtDiagnosisView.windowLevel') }}: {{ windowLevel }}</span>
                    <span>{{ t('views_CtDiagnosisView.zoom') }}: {{ zoomLevel }}x</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 标注工具 -->
          <div class="annotation-toolbar">
            <span class="toolbar-label">{{ t('views_CtDiagnosisView.annotationTools') }}:</span>
            <a-radio-group v-model:value="annotationTool" button-style="solid" size="small">
              <a-radio-button value="none">
                <template #icon>
                  <CloseOutlined />
                </template>
                {{ t('views_CtDiagnosisView.none') }}
              </a-radio-button>
              <a-radio-button value="rectangle">
                <template #icon>
                  <BorderOutlined />
                </template>
                {{ t('views_CtDiagnosisView.rectangle') }}
              </a-radio-button>
              <a-radio-button value="circle">
                <template #icon>
                  <CheckCircleOutlined />
                </template>
                {{ t('views_CtDiagnosisView.circle') }}
              </a-radio-button>
              <a-radio-button value="arrow">
                <template #icon>
                  <ArrowRightOutlined />
                </template>
                {{ t('views_CtDiagnosisView.arrow') }}
              </a-radio-button>
              <a-radio-button value="text">
                <template #icon>
                  <FontSizeOutlined />
                </template>
                {{ t('views_CtDiagnosisView.text') }}
              </a-radio-button>
            </a-radio-group>
            <div class="toolbar-spacer"></div>
            <a-button type="primary" @click="handleSaveReport">
              <template #icon>
                <SaveOutlined />
              </template>
              {{ t('views_CtDiagnosisView.saveReport') }}
            </a-button>
          </div>
        </a-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ReconciliationOutlined,
  UploadOutlined,
  FolderOutlined,
  FileImageOutlined,
  LeftOutlined,
  RightOutlined,
  ReloadOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  CloseOutlined,
  BorderOutlined,
  CheckCircleOutlined,
  ArrowRightOutlined,
  FontSizeOutlined,
  SaveOutlined
} from '@ant-design/icons-vue'
import type { TreeProps } from 'ant-design-vue'

const { t } = useI18n()

// 树搜索
const treeSearchValue = ref('')

// 树数据
const expandedKeys = ref<string[]>([])
const selectedKeys = ref<string[]>([])
const autoExpandParent = ref(true)

// 当前患者信息
const currentPatient = ref({
  name: '张三',
  gender: '男',
  age: '45岁',
  examDate: '2024-01-15',
  examPart: '胸部'
})

// 树数据
const treeData = ref<TreeProps['treeData']>([
  {
    title: '患者_张三_20240115',
    key: '0',
    isLeaf: false,
    children: [
      {
        title: '序列_001',
        key: '0-0',
        isLeaf: false,
        isCurrent: true,
        children: [
          { title: 'slice_001.dcm', key: '0-0-0', isLeaf: true },
          { title: 'slice_002.dcm', key: '0-0-1', isLeaf: true },
          { title: 'slice_003.dcm', key: '0-0-2', isLeaf: true }
        ]
      },
      {
        title: '序列_002',
        key: '0-1',
        isLeaf: false,
        children: [
          { title: 'slice_001.dcm', key: '0-1-0', isLeaf: true },
          { title: 'slice_002.dcm', key: '0-1-1', isLeaf: true }
        ]
      }
    ]
  },
  {
    title: '患者_李四_20240114',
    key: '1',
    isLeaf: false,
    children: [
      {
        title: '序列_001',
        key: '1-0',
        isLeaf: false,
        children: [
          { title: 'slice_001.dcm', key: '1-0-0', isLeaf: true },
          { title: 'slice_002.dcm', key: '1-0-1', isLeaf: true }
        ]
      }
    ]
  }
])

// 图像查看器
const imageViewerRef = ref<HTMLElement>()
const currentImage = ref<string | null>('current')
const currentSlice = ref(0)
const totalSlices = ref(288)
const windowWidth = ref(400)
const windowLevel = ref(40)
const zoomLevel = ref(1.0)
const annotationTool = ref('none')

// 诊断结果
const diagnosisResults = ref([
  {
    type: 'suspicious',
    confidence: 85,
    description: '右肺上叶可见结节影，直径约8mm，边界清晰，建议进一步检查。'
  },
  {
    type: 'normal',
    confidence: 100,
    description: '左肺未见明显异常。'
  }
])

// 方法
const onExpand = (keys: string[]) => {
  expandedKeys.value = keys
  autoExpandParent.value = false
}

const onSelect = (keys: string[], info: any) => {
  selectedKeys.value = keys
  const node = info.node
  if (node.isLeaf) {
    // 加载图像
    currentImage.value = node.title as string
    currentSlice.value = 0
  }
}

const handleTreeSearch = () => {
  // 静态页面，仅展示
  console.log('搜索树:', treeSearchValue.value)
}

const handleUploadCT = () => {
  // 静态页面，仅展示
  console.log('上传CT影像')
}

const handlePreviousSlice = () => {
  if (currentSlice.value > 0) {
    currentSlice.value--
  }
}

const handleNextSlice = () => {
  if (currentSlice.value < totalSlices.value - 1) {
    currentSlice.value++
  }
}

const handleWindowChange = () => {
  // 静态页面，仅展示
  console.log('窗宽窗位变化:', windowWidth.value, windowLevel.value)
}

const handleResetView = () => {
  windowWidth.value = 400
  windowLevel.value = 40
  zoomLevel.value = 1.0
}

const handleZoomIn = () => {
  zoomLevel.value = Math.min(zoomLevel.value + 0.1, 5.0)
}

const handleZoomOut = () => {
  zoomLevel.value = Math.max(zoomLevel.value - 0.1, 0.5)
}

const handleSaveReport = () => {
  // 静态页面，仅展示
  console.log('保存诊断报告')
}

const getDiagnosisClass = (type: string) => {
  const classes: Record<string, string> = {
    suspicious: 'diagnosis-suspicious',
    normal: 'diagnosis-normal',
    abnormal: 'diagnosis-abnormal'
  }
  return classes[type] || ''
}

const getDiagnosisTagColor = (type: string) => {
  const colors: Record<string, string> = {
    suspicious: 'orange',
    normal: 'success',
    abnormal: 'error'
  }
  return colors[type] || 'default'
}

const getDiagnosisTypeText = (type: string) => {
  const texts: Record<string, string> = {
    suspicious: t('views_CtDiagnosisView.suspicious'),
    normal: t('views_CtDiagnosisView.normal'),
    abnormal: t('views_CtDiagnosisView.abnormal')
  }
  return texts[type] || type
}

onMounted(() => {
  // 默认展开第一个节点
  expandedKeys.value = ['0', '0-0']
  selectedKeys.value = ['0-0-0']
})
</script>

<style scoped>
.ct-diagnosis-container {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.content-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 24px;
  flex: 1;
  min-height: 0;
}

.left-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.right-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.info-card,
.tree-card,
.diagnosis-card {
  flex-shrink: 0;
}

.tree-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.tree-search {
  margin-bottom: 12px;
}

.file-tree {
  flex: 1;
  overflow-y: auto;
}

.tree-node-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-tag {
  margin-left: 8px;
}

.viewer-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 4px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slice-info {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.toolbar-center {
  display: flex;
  align-items: center;
  gap: 24px;
  flex: 1;
  justify-content: center;
}

.window-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-label {
  font-size: 14px;
  color: #666;
  min-width: 60px;
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.image-viewer {
  flex: 1;
  background: #000;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
  min-height: 500px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
  padding: 48px;
}

.placeholder-icon {
  font-size: 64px;
  margin-bottom: 16px;
  color: #666;
}

.placeholder-text {
  font-size: 18px;
  margin-bottom: 8px;
  color: #999;
}

.placeholder-hint {
  font-size: 14px;
  color: #999;
}

.image-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.image-display {
  width: 100%;
  height: 100%;
  background: linear-gradient(45deg, #1a1a1a 25%, transparent 25%),
    linear-gradient(-45deg, #1a1a1a 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #1a1a1a 75%),
    linear-gradient(-45deg, transparent 75%, #1a1a1a 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
  position: relative;
}

.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.image-info {
  position: absolute;
  bottom: 8px;
  left: 8px;
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #fff;
  background: rgba(0, 0, 0, 0.6);
  padding: 4px 8px;
  border-radius: 4px;
}

.annotation-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 4px;
  margin-top: 16px;
}

.toolbar-label {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.toolbar-spacer {
  flex: 1;
}

.diagnosis-results {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 300px;
  overflow-y: auto;
}

.diagnosis-item {
  padding: 12px;
  border-radius: 4px;
  border: 1px solid;
}

.diagnosis-suspicious {
  background: #fff7e6;
  border-color: #ffd591;
}

.diagnosis-normal {
  background: #f6ffed;
  border-color: #b7eb8f;
}

.diagnosis-abnormal {
  background: #fff1f0;
  border-color: #ffccc7;
}

.diagnosis-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.diagnosis-tag {
  margin: 0;
}

.confidence {
  font-size: 12px;
  color: #999;
}

.diagnosis-text {
  margin: 0;
  font-size: 14px;
  color: #333;
  line-height: 1.6;
}

/* 响应式设计 */
@media (max-width: 1400px) {
  .content-layout {
    grid-template-columns: 280px 1fr;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-center {
    flex-direction: column;
    gap: 12px;
  }
}

@media (max-width: 1024px) {
  .content-layout {
    grid-template-columns: 1fr;
  }

  .left-panel {
    max-height: 400px;
    overflow-y: auto;
  }
}
</style>
