<template>
  <div class="detail-page">
    <div class="detail-shell">
      <div class="detail-header">
        <div class="header-actions">
          <a-button class="header-action header-action-back" @click="goBack">
            <template #icon><ArrowLeftOutlined /></template>
            {{ t('common.back') }}
          </a-button>
          <a-button class="header-action header-action-export" type="primary" :loading="exportingReport" @click="handleExportReport">
            <template #icon><FileTextOutlined /></template>
            {{ t('views_PatientDetailView.report.exportPdf') }}
          </a-button>
          <a-button class="header-action header-action-outputs" :loading="loadingOutputs" @click="openOutputsModal">
            <template #icon><FolderOpenOutlined /></template>
            Outputs
          </a-button>
        </div>
        <div class="header-main">
          <span class="avatar">{{ initials(patient?.name || patientId) }}</span>
          <div>
            <div class="eyebrow">{{ t('views_PatientDetailView.eyebrow') }}</div>
            <h1>{{ patient?.name || patientId }}</h1>
            <p>{{ patientId }}</p>
          </div>
        </div>
      </div>

      <a-spin :spinning="loading">
        <template v-if="patient">
          <div class="info-grid">
            <section class="panel baseline-panel">
              <div class="panel-title">{{ t('views_PatientDetailView.baseline') }}</div>
              <div class="baseline-grid">
                <div v-for="item in baselineItems" :key="item.label" class="info-item">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>
            </section>

            <section class="panel action-panel">
              <div class="panel-title">{{ t('views_PatientDetailView.workflow') }}</div>
              <div class="workflow-list">
                <div v-for="step in workflowSteps" :key="step.key" class="workflow-item">
                  <span class="step-dot">{{ step.index }}</span>
                  <div>
                    <strong>{{ step.title }}</strong>
                    <p>{{ step.desc }}</p>
                  </div>
                </div>
              </div>
            </section>
          </div>

          <div class="section-grid two">
            <section class="panel ct-panel">
              <div class="panel-header">
                <div>
                  <div class="panel-kicker">PRE</div>
                </div>
                <a-tag :color="ctStatusColor(preCt.status)">{{ ctStatusLabel(preCt.status) }}</a-tag>
              </div>
              <div
                v-if="preCt.status === 'ready'"
                class="ct-ready preview-drop-zone"
                :class="{ 'drop-active': isPreviewDropActive(ctDropTarget('pre')) }"
                @dragenter.prevent="setPreviewDrag(ctDropTarget('pre'), $event)"
                @dragover.prevent="setPreviewDrag(ctDropTarget('pre'), $event)"
                @dragleave.self.prevent="clearPreviewDrag(ctDropTarget('pre'))"
                @drop.prevent="handleCtDrop('pre', $event)"
              >
                <div v-if="hasPreviewPlanes(preCt)" class="mpr-preview-grid">
                  <div v-for="plane in previewPlaneEntries(preCt)" :key="plane.key" class="mpr-preview-pane">
                    <img :src="previewSrc(plane.url, preCt)" :alt="`${plane.label} ${preCt.file_name || 'Pre CT'}`" />
                    <span>{{ plane.label }}</span>
                  </div>
                </div>
                <template v-else-if="preCt.preview_url">
                  <img :src="previewSrc(preCt.preview_url, preCt)" :alt="preCt.file_name || 'Pre CT'" class="ct-preview-image" />
                  <div class="ct-image-caption">
                    <strong>{{ preCt.file_name }}</strong>
                    <span>{{ formatFileSize(preCt.file_size) }} · {{ formatDateTime(preCt.uploaded_at) }}</span>
                  </div>
                </template>
                <div v-else class="ct-file-summary">
                  <CameraOutlined />
                  <div>
                    <strong>{{ preCt.file_name }}</strong>
                    <span>{{ formatFileSize(preCt.file_size) }} · {{ formatDateTime(preCt.uploaded_at) }}</span>
                  </div>
                </div>
                <a-button class="preview-zoom-action" :title="t('common.view')" @click="openCtViewer('pre')">
                  <template #icon><ZoomInOutlined /></template>
                </a-button>
                <div class="drop-overlay">
                  <UploadOutlined />
                  <span>{{ t('views_PatientDetailView.dragDrop.ct') }}</span>
                </div>
              </div>
              <div
                v-else
                class="scan-placeholder preview-drop-zone"
                :class="{ 'drop-active': isPreviewDropActive(ctDropTarget('pre')) }"
                @dragenter.prevent="setPreviewDrag(ctDropTarget('pre'), $event)"
                @dragover.prevent="setPreviewDrag(ctDropTarget('pre'), $event)"
                @dragleave.self.prevent="clearPreviewDrag(ctDropTarget('pre'))"
                @drop.prevent="handleCtDrop('pre', $event)"
              >
                <CameraOutlined />
                  <span>{{ t('views_PatientDetailView.pre.empty') }}</span>
                  <small>{{ t('views_PatientDetailView.dragDrop.ctHint') }}</small>
                  <div class="drop-overlay">
                    <UploadOutlined />
                    <span>{{ t('views_PatientDetailView.dragDrop.ct') }}</span>
                  </div>
                </div>
              <div class="ct-action-bar">
                <a-button class="ct-primary-action" :loading="uploadingPhase.pre" @click="triggerCtUpload('pre')">
                  <template #icon><UploadOutlined /></template>
                  {{ preCt.status === 'ready' ? t('views_PatientDetailView.ct.replace') : t('views_PatientDetailView.ct.uploadPre') }}
                </a-button>
                <a-popconfirm
                  v-if="preCt.status === 'ready'"
                  :title="t('views_PatientDetailView.ct.deleteConfirmPre')"
                  :ok-text="t('common.delete')"
                  :cancel-text="t('common.cancel')"
                  ok-type="danger"
                  @confirm="handleDeleteCt('pre')"
                >
                  <a-button class="ct-icon-action" danger :loading="deletingPhase.pre" :title="t('views_PatientDetailView.ct.delete')">
                    <template #icon><DeleteOutlined /></template>
                  </a-button>
                </a-popconfirm>
              </div>
            </section>

            <section class="panel ct-panel">
              <div class="panel-header">
                <div>
                  <div class="panel-kicker">POST</div>
                </div>
                <a-tag :color="ctStatusColor(postCt.status)">{{ ctStatusLabel(postCt.status) }}</a-tag>
              </div>
              <div
                v-if="postCt.status === 'ready'"
                class="ct-ready preview-drop-zone"
                :class="{ 'drop-active': isPreviewDropActive(ctDropTarget('post')) }"
                @dragenter.prevent="setPreviewDrag(ctDropTarget('post'), $event)"
                @dragover.prevent="setPreviewDrag(ctDropTarget('post'), $event)"
                @dragleave.self.prevent="clearPreviewDrag(ctDropTarget('post'))"
                @drop.prevent="handleCtDrop('post', $event)"
              >
                <div v-if="hasPreviewPlanes(postCt)" class="mpr-preview-grid">
                  <div v-for="plane in previewPlaneEntries(postCt)" :key="plane.key" class="mpr-preview-pane">
                    <img :src="previewSrc(plane.url, postCt)" :alt="`${plane.label} ${postCt.file_name || 'Post CT'}`" />
                    <span>{{ plane.label }}</span>
                  </div>
                </div>
                <template v-else-if="postCt.preview_url">
                  <img :src="previewSrc(postCt.preview_url, postCt)" :alt="postCt.file_name || 'Post CT'" class="ct-preview-image" />
                  <div class="ct-image-caption">
                    <strong>{{ postCt.file_name }}</strong>
                    <span>{{ formatFileSize(postCt.file_size) }} · {{ formatDateTime(postCt.uploaded_at) }}</span>
                  </div>
                </template>
                <div v-else class="ct-file-summary">
                  <CameraOutlined />
                  <div>
                    <strong>{{ postCt.file_name }}</strong>
                    <span>{{ formatFileSize(postCt.file_size) }} · {{ formatDateTime(postCt.uploaded_at) }}</span>
                  </div>
                </div>
                <a-button class="preview-zoom-action" :title="t('common.view')" @click="openCtViewer('post')">
                  <template #icon><ZoomInOutlined /></template>
                </a-button>
                <div class="drop-overlay">
                  <UploadOutlined />
                  <span>{{ t('views_PatientDetailView.dragDrop.ct') }}</span>
                </div>
              </div>
              <div
                v-else
                class="scan-placeholder preview-drop-zone"
                :class="{ 'drop-active': isPreviewDropActive(ctDropTarget('post')) }"
                @dragenter.prevent="setPreviewDrag(ctDropTarget('post'), $event)"
                @dragover.prevent="setPreviewDrag(ctDropTarget('post'), $event)"
                @dragleave.self.prevent="clearPreviewDrag(ctDropTarget('post'))"
                @drop.prevent="handleCtDrop('post', $event)"
              >
                <CameraOutlined />
                <span>{{ t('views_PatientDetailView.post.empty') }}</span>
                <small>{{ t('views_PatientDetailView.dragDrop.ctHint') }}</small>
                <div class="drop-overlay">
                  <UploadOutlined />
                  <span>{{ t('views_PatientDetailView.dragDrop.ct') }}</span>
                </div>
              </div>
              <div class="ct-action-bar">
                <a-button class="ct-primary-action" :loading="uploadingPhase.post" @click="triggerCtUpload('post')">
                  <template #icon><UploadOutlined /></template>
                  {{ postCt.status === 'ready' ? t('views_PatientDetailView.ct.replace') : t('views_PatientDetailView.ct.uploadPost') }}
                </a-button>
                <a-popconfirm
                  v-if="postCt.status === 'ready'"
                  :title="t('views_PatientDetailView.ct.deleteConfirmPost')"
                  :ok-text="t('common.delete')"
                  :cancel-text="t('common.cancel')"
                  ok-type="danger"
                  @confirm="handleDeleteCt('post')"
                >
                  <a-button class="ct-icon-action" danger :loading="deletingPhase.post" :title="t('views_PatientDetailView.ct.delete')">
                    <template #icon><DeleteOutlined /></template>
                  </a-button>
                </a-popconfirm>
              </div>
            </section>
          </div>

          <div class="section-grid two">
            <section v-for="group in maskGroups" :key="group.key" class="panel feature-panel full-span" :class="{ collapsed: !isMaskGroupExpanded(group) }">
              <div class="panel-header mask-group-header">
                <div>
                  <div class="panel-kicker">{{ group.title }}</div>
                </div>
                <div class="mask-group-actions">
                  <span class="mask-group-summary">{{ maskGroupSummary(group) }}</span>
                  <a-button class="mask-collapse-action" :title="isMaskGroupExpanded(group) ? t('common.collapse') : t('common.expand')" @click="toggleMaskGroup(group.key)">
                    <span class="mask-collapse-chevron" :class="{ expanded: isMaskGroupExpanded(group) }">⌄</span>
                  </a-button>
                </div>
              </div>
              <div v-if="isMaskGroupExpanded(group)" class="mask-slot-grid">
                <div v-for="slot in group.slots" :key="slot.phase" class="mask-slot">
                  <div class="mask-slot-header">
                    <strong>{{ slot.label }}</strong>
                    <a-tag :color="maskStatusColor(slot.status.status)">{{ maskStatusLabel(slot.status.status) }}</a-tag>
                  </div>
                  <div
                    v-if="slot.status.status === 'ready'"
                    class="ct-ready preview-drop-zone"
                    :class="{ 'drop-active': isPreviewDropActive(maskDropTarget(group.maskType, slot.phase)) }"
                    @dragenter.prevent="setPreviewDrag(maskDropTarget(group.maskType, slot.phase), $event)"
                    @dragover.prevent="setPreviewDrag(maskDropTarget(group.maskType, slot.phase), $event)"
                    @dragleave.self.prevent="clearPreviewDrag(maskDropTarget(group.maskType, slot.phase))"
                    @drop.prevent="handleMaskDrop(group.maskType, slot.phase, $event)"
                  >
                    <div v-if="hasPreviewPlanes(slot.status)" class="mpr-preview-grid">
                      <div v-for="plane in previewPlaneEntries(slot.status)" :key="plane.key" class="mpr-preview-pane">
                        <img :src="previewSrc(plane.url, slot.status)" :alt="`${plane.label} ${slot.status.file_name || group.title}`" />
                        <span>{{ plane.label }} mask</span>
                      </div>
                    </div>
                    <template v-else-if="slot.status.preview_url">
                      <img
                        :src="previewSrc(slot.status.preview_url, slot.status)"
                        :alt="slot.status.file_name || `${group.title} ${slot.label}`"
                        class="ct-preview-image"
                      />
                      <div class="ct-image-caption">
                        <strong>{{ slot.status.file_name }}</strong>
                        <span>{{ formatFileSize(slot.status.file_size) }} · {{ formatDateTime(slot.status.uploaded_at) }}</span>
                      </div>
                    </template>
                    <div v-else class="ct-file-summary">
                      <CameraOutlined />
                      <div>
                        <strong>{{ slot.status.file_name }}</strong>
                        <span>{{ formatFileSize(slot.status.file_size) }} · {{ formatDateTime(slot.status.uploaded_at) }}</span>
                      </div>
                    </div>
                    <a-button class="preview-zoom-action" :title="t('common.view')" @click="openMaskViewer(group.maskType, slot.phase)">
                      <template #icon><ZoomInOutlined /></template>
                    </a-button>
                    <div class="drop-overlay">
                      <UploadOutlined />
                      <span>{{ t('views_PatientDetailView.dragDrop.mask') }}</span>
                    </div>
                  </div>
                  <div
                    v-else
                    class="feature-window preview-drop-zone"
                    :class="{ 'drop-active': isPreviewDropActive(maskDropTarget(group.maskType, slot.phase)) }"
                    @dragenter.prevent="setPreviewDrag(maskDropTarget(group.maskType, slot.phase), $event)"
                    @dragover.prevent="setPreviewDrag(maskDropTarget(group.maskType, slot.phase), $event)"
                    @dragleave.self.prevent="clearPreviewDrag(maskDropTarget(group.maskType, slot.phase))"
                    @drop.prevent="handleMaskDrop(group.maskType, slot.phase, $event)"
                  >
                    <CameraOutlined />
                    <span>{{ group.emptyText }}</span>
                    <small>{{ t('views_PatientDetailView.dragDrop.maskHint') }}</small>
                    <div class="drop-overlay">
                      <UploadOutlined />
                      <span>{{ t('views_PatientDetailView.dragDrop.mask') }}</span>
                    </div>
                  </div>
                  <div class="ct-action-bar">
                    <a-button
                      class="ct-primary-action"
                      :loading="uploadingMaskKeys[maskKey(group.maskType, slot.phase)]"
                      @click="triggerMaskUpload(group.maskType, slot.phase)"
                    >
                      <template #icon><UploadOutlined /></template>
                      {{ slot.status.status === 'ready' ? t('views_PatientDetailView.mask.replace') : t('views_PatientDetailView.mask.upload') }}
                    </a-button>
                    <a-popconfirm
                      v-if="slot.status.status === 'ready'"
                      :title="t('views_PatientDetailView.mask.deleteConfirm')"
                      :ok-text="t('common.delete')"
                      :cancel-text="t('common.cancel')"
                      ok-type="danger"
                      @confirm="handleDeleteMask(group.maskType, slot.phase)"
                    >
                      <a-button
                        class="ct-icon-action"
                        danger
                        :loading="deletingMaskKeys[maskKey(group.maskType, slot.phase)]"
                        :title="t('views_PatientDetailView.mask.delete')"
                      >
                        <template #icon><DeleteOutlined /></template>
                      </a-button>
                    </a-popconfirm>
                  </div>
                </div>
              </div>
            </section>
          </div>

          <section class="panel body-results-panel">
            <div class="panel-header body-results-header">
              <div>
                <div class="panel-kicker">BODY COMPOSITION RESULTS</div>
                <h2>Metrics and Type</h2>
              </div>
              <a-button class="ct-icon-action" :loading="loadingBodyResults" title="Refresh body composition results" @click="fetchBodyCompositionResults">
                <template #icon><ReloadOutlined /></template>
              </a-button>
            </div>
            <a-spin :spinning="loadingBodyResults">
              <div class="body-results-grid">
                <div v-for="phase in bodyResultPhases" :key="phase" class="body-result-card">
                  <div class="body-result-card-header">
                    <strong>{{ phase.toUpperCase() }} metrics</strong>
                    <a-tag :color="metricResultForPhase(phase).csv ? 'green' : 'default'">
                      {{ metricResultForPhase(phase).csv ? metricResultSourceLabel(metricResultForPhase(phase).csv?.source) : 'Empty' }}
                    </a-tag>
                  </div>
                  <div v-if="metricResultForPhase(phase).summary" class="metric-mini-grid">
                    <div v-for="item in metricSummaryItems(metricResultForPhase(phase).summary)" :key="item.key" class="metric-mini-item">
                      <span>{{ item.label }}</span>
                      <strong>{{ item.value }}</strong>
                    </div>
                  </div>
                  <div v-else class="body-result-empty">No metrics table found</div>
                  <div class="body-result-actions">
                    <a-button size="small" :disabled="!metricResultForPhase(phase).csv" :loading="downloadingResultPath === metricResultForPhase(phase).csv?.relative_path" @click="downloadResultFile(metricResultForPhase(phase).csv)">
                      <template #icon><DownloadOutlined /></template>
                      CSV
                    </a-button>
                    <a-button size="small" :disabled="!metricResultForPhase(phase).xlsx" :loading="downloadingResultPath === metricResultForPhase(phase).xlsx?.relative_path" @click="downloadResultFile(metricResultForPhase(phase).xlsx)">
                      <template #icon><DownloadOutlined /></template>
                      XLSX
                    </a-button>
                    <a-button size="small" :loading="uploadingBodyMetricPhase === phase" @click="triggerBodyMetricUpload(phase)">
                      <template #icon><UploadOutlined /></template>
                      Upload
                    </a-button>
                  </div>
                </div>

                <div class="body-result-card type-result-card">
                  <div class="body-result-card-header">
                    <strong>Type classification</strong>
                    <a-tag :color="bodyCompositionResults?.type_classification.json ? 'green' : 'default'">
                      {{ bodyCompositionResults?.type_classification.json ? metricResultSourceLabel(bodyCompositionResults.type_classification.json.source) : 'Empty' }}
                    </a-tag>
                  </div>
                  <div v-if="bodyCompositionResults?.type_classification.summary?.metric_results" class="type-result-list">
                    <div v-for="item in typeSummaryItems" :key="item.metric" class="type-result-row">
                      <span>{{ item.metric }}</span>
                      <strong>{{ item.type }}</strong>
                      <small>{{ item.change }}</small>
                    </div>
                  </div>
                  <div v-else class="body-result-empty">No type classification JSON found</div>
                  <div class="body-result-actions">
                    <a-button size="small" :disabled="!bodyCompositionResults?.type_classification.json" :loading="downloadingResultPath === bodyCompositionResults?.type_classification.json?.relative_path" @click="downloadResultFile(bodyCompositionResults?.type_classification.json)">
                      <template #icon><DownloadOutlined /></template>
                      JSON
                    </a-button>
                    <a-button size="small" :loading="uploadingBodyType" @click="triggerBodyTypeUpload">
                      <template #icon><UploadOutlined /></template>
                      Upload
                    </a-button>
                  </div>
                </div>
              </div>
            </a-spin>
          </section>

          <div class="section-grid module-grid">
            <section v-for="module in analysisModules" :key="module.key" class="panel module-panel">
              <h2>{{ module.title }}</h2>
              <p>{{ module.desc }}</p>
              <a-button disabled>{{ t('views_PatientDetailView.notConfigured') }}</a-button>
            </section>
          </div>
        </template>

        <a-empty v-else-if="!loading" :description="t('views_PatientDetailView.notFound')" />
      </a-spin>
    </div>

    <a-modal
      v-model:open="viewerOpen"
      :title="viewerTitle"
      width="92vw"
      :footer="null"
      class="mpr-modal"
    >
      <MprViewer
        v-if="viewerTarget"
        :visible="viewerOpen"
        :metadata-url="viewerTarget.metadataUrl"
        :ct-slice-base-url="viewerTarget.ctSliceBaseUrl"
        :mask-slice-base-url="viewerTarget.maskSliceBaseUrl"
        :ct-volume-url="viewerTarget.ctVolumeUrl"
        :mask-volume-url="viewerTarget.maskVolumeUrl"
        :cache-key="viewerTarget.cacheKey"
      />
    </a-modal>

    <a-modal
      v-model:open="outputsOpen"
      title="Agent outputs"
      width="860px"
      :footer="null"
      class="outputs-modal"
    >
      <div v-if="outputRoot" class="output-root">{{ outputRoot }}</div>
      <div class="outputs-modal-toolbar">
        <span>{{ outputFiles.length }} files</span>
        <a-button class="ct-icon-action" :loading="loadingOutputs" title="Refresh outputs" @click="fetchPatientOutputs">
          <template #icon><ReloadOutlined /></template>
        </a-button>
      </div>
      <a-spin :spinning="loadingOutputs">
        <div v-if="visibleOutputTreeNodes.length" class="output-tree">
          <div
            v-for="node in visibleOutputTreeNodes"
            :key="node.id"
            class="output-tree-row"
            :class="node.kind"
            :style="{ '--tree-depth': node.depth }"
          >
            <button
              v-if="node.kind === 'folder'"
              class="output-tree-main output-tree-folder-button"
              type="button"
              @click="toggleOutputFolder(node.path)"
            >
              <span class="output-tree-chevron">
                <DownOutlined v-if="isOutputFolderExpanded(node.path)" />
                <RightOutlined v-else />
              </span>
              <span class="output-tree-icon"><FolderFilled /></span>
              <strong>{{ node.name }}</strong>
              <span>{{ node.fileCount }} files</span>
            </button>
            <template v-else-if="node.file">
              <div class="output-file-main">
                <span class="output-tree-spacer"></span>
                <span class="output-tree-icon"><FileOutlined /></span>
                <div>
                  <strong>{{ node.file.name }}</strong>
                </div>
              </div>
              <div class="output-file-meta">
                <span>{{ formatFileSize(node.file.size) }}</span>
                <span>{{ formatDateTime(node.file.modified_at) }}</span>
                <a-button
                  class="ct-icon-action"
                  :loading="downloadingOutputPath === node.file.path"
                  :title="`Download ${node.file.name}`"
                  @click="handleDownloadOutput(node.file)"
                >
                  <template #icon><DownloadOutlined /></template>
                </a-button>
              </div>
            </template>
          </div>
        </div>
        <div v-else class="outputs-empty">
          <FolderOpenOutlined />
          <span>No output files yet</span>
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  CameraOutlined,
  DeleteOutlined,
  DownloadOutlined,
  DownOutlined,
  FileOutlined,
  FileTextOutlined,
  FolderFilled,
  FolderOpenOutlined,
  ReloadOutlined,
  RightOutlined,
  UploadOutlined,
  ZoomInOutlined,
} from '@ant-design/icons-vue'
import MprViewer from '@/components/patient/MprViewer.vue'
import {
  deletePatientCt,
  deletePatientMask,
  downloadBodyCompositionResultFile,
  downloadPatientReport,
  downloadPatientOutput,
  getBodyCompositionResults,
  getPatient,
  getPatientCtStatus,
  getPatientMaskStatus,
  getPatientOutputs,
  uploadBodyCompositionMetricFile,
  uploadBodyCompositionTypeFile,
  uploadPatientCt,
  uploadPatientMask,
  type BodyCompositionMetricsSummary,
  type BodyCompositionResults,
  type CtPhase,
  type MaskType,
  type PatientOutputFile,
  type PatientResultFile,
  type PatientCtStatus,
  type PatientInfo,
  type PatientMaskStatus,
} from '@/apis/patients'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const patient = ref<PatientInfo | null>(null)
const patientId = computed(() => String(route.params.patientId || ''))
const emptyPreCt = (): PatientCtStatus => ({ phase: 'pre', status: 'empty', file_name: null, file_size: null, uploaded_at: null, preview_updated_at: null, preview_url: null, preview_planes: null, display_window: null })
const emptyPostCt = (): PatientCtStatus => ({ phase: 'post', status: 'empty', file_name: null, file_size: null, uploaded_at: null, preview_updated_at: null, preview_url: null, preview_planes: null, display_window: null })
const emptyMask = (maskType: MaskType, phase: CtPhase): PatientMaskStatus => ({
  mask_type: maskType,
  phase,
  status: 'empty',
  file_name: null,
  file_size: null,
  uploaded_at: null,
  preview_url: null,
  preview_planes: null,
})
const preCt = ref<PatientCtStatus>(emptyPreCt())
const postCt = ref<PatientCtStatus>(emptyPostCt())
const bodyPreMask = ref<PatientMaskStatus>(emptyMask('body-composition', 'pre'))
const bodyPostMask = ref<PatientMaskStatus>(emptyMask('body-composition', 'post'))
const spinePreMask = ref<PatientMaskStatus>(emptyMask('spine', 'pre'))
const spinePostMask = ref<PatientMaskStatus>(emptyMask('spine', 'post'))
const lungPreMask = ref<PatientMaskStatus>(emptyMask('lung', 'pre'))
const lungPostMask = ref<PatientMaskStatus>(emptyMask('lung', 'post'))
const tumorPreMask = ref<PatientMaskStatus>(emptyMask('tumor', 'pre'))
const tumorPostMask = ref<PatientMaskStatus>(emptyMask('tumor', 'post'))
const uploadingPhase = ref<Record<CtPhase, boolean>>({ pre: false, post: false })
const deletingPhase = ref<Record<CtPhase, boolean>>({ pre: false, post: false })
const uploadingMaskKeys = ref<Record<string, boolean>>({})
const deletingMaskKeys = ref<Record<string, boolean>>({})
const exportingReport = ref(false)
const loadingOutputs = ref(false)
const loadingBodyResults = ref(false)
const downloadingOutputPath = ref<string | null>(null)
const downloadingResultPath = ref<string | null>(null)
const uploadingBodyMetricPhase = ref<CtPhase | null>(null)
const uploadingBodyType = ref(false)
const outputsOpen = ref(false)
const outputRoot = ref('')
const outputFiles = ref<PatientOutputFile[]>([])
const bodyCompositionResults = ref<BodyCompositionResults | null>(null)
const expandedOutputFolders = ref<Record<string, boolean>>({})
const maskGroupOverrides = ref<Record<string, boolean>>({})
const viewerOpen = ref(false)
const viewerTitle = ref('')
const viewerTarget = ref<{
  metadataUrl: string
  ctSliceBaseUrl: string
  maskSliceBaseUrl?: string | null
  ctVolumeUrl: string
  maskVolumeUrl?: string | null
  cacheKey?: string | null
} | null>(null)
const activeDropTarget = ref<string | null>(null)

const baselineItems = computed(() => [
  { label: t('views_PatientManageView.fields.sex'), value: formatOption('sex', patient.value?.sex) },
  { label: t('views_PatientManageView.fields.age'), value: patient.value?.age ?? '-' },
  { label: t('views_PatientManageView.fields.phone'), value: patient.value?.phone || '-' },
  { label: t('views_PatientManageView.fields.height'), value: patient.value?.height_cm == null ? '-' : `${patient.value.height_cm} cm` },
  { label: t('views_PatientManageView.fields.smoking'), value: formatOption('smoking', patient.value?.smoking_status) },
  { label: t('views_PatientManageView.fields.pathology'), value: formatOption('pathology', patient.value?.pathology_type) },
  { label: t('views_PatientManageView.fields.pdL1'), value: formatOption('pdL1', patient.value?.pd_l1_status) },
])

const workflowSteps = computed(() => [
  {
    key: 'pre',
    index: '1',
    title: t('views_PatientDetailView.workflowSteps.pre.title'),
    desc: t('views_PatientDetailView.workflowSteps.pre.desc'),
  },
  {
    key: 'post',
    index: '2',
    title: t('views_PatientDetailView.workflowSteps.post.title'),
    desc: t('views_PatientDetailView.workflowSteps.post.desc'),
  },
  {
    key: 'masks',
    index: '3',
    title: t('views_PatientDetailView.workflowSteps.masks.title'),
    desc: t('views_PatientDetailView.workflowSteps.masks.desc'),
  },
  {
    key: 'preview',
    index: '4',
    title: t('views_PatientDetailView.workflowSteps.preview.title'),
    desc: t('views_PatientDetailView.workflowSteps.preview.desc'),
  },
  {
    key: 'report',
    index: '5',
    title: t('views_PatientDetailView.workflowSteps.report.title'),
    desc: t('views_PatientDetailView.workflowSteps.report.desc'),
  },
])

const analysisModules = computed(() => [
  {
    key: 'bc',
    title: t('views_PatientDetailView.modules.bc.title'),
    desc: t('views_PatientDetailView.modules.bc.desc'),
  },
  {
    key: 'mpr',
    title: t('views_PatientDetailView.modules.mpr.title'),
    desc: t('views_PatientDetailView.modules.mpr.desc'),
  },
])

const bodyResultPhases: CtPhase[] = ['pre', 'post']

const typeSummaryItems = computed(() => {
  const results = bodyCompositionResults.value?.type_classification.summary?.metric_results || {}
  return ['SMVI', 'VAVI', 'SAVI'].map((metric) => {
    const item = results[metric] || {}
    return {
      metric,
      type: item.type_label || '-',
      change: item.change_rate == null ? '-' : `${formatSignedNumber(item.change_rate)}% ${item.change_bucket || ''}`.trim(),
    }
  })
})

interface OutputTreeNode {
  id: string
  kind: 'folder' | 'file'
  name: string
  path: string
  depth: number
  fileCount?: number
  file?: PatientOutputFile
}

interface OutputTreeFolder {
  name: string
  path: string
  folders: Map<string, OutputTreeFolder>
  files: PatientOutputFile[]
}

function createOutputFolder(name: string, path: string): OutputTreeFolder {
  return { name, path, folders: new Map(), files: [] }
}

const outputTreeRoot = computed(() => {
  const root = createOutputFolder('agent_outputs', 'agent_outputs')
  for (const file of outputFiles.value) {
    const parts = file.path.split('/').filter(Boolean)
    let folder = root
    for (const part of parts.slice(0, -1)) {
      const childPath = `${folder.path}/${part}`
      let child = folder.folders.get(part)
      if (!child) {
        child = createOutputFolder(part, childPath)
        folder.folders.set(part, child)
      }
      folder = child
    }
    folder.files.push(file)
  }
  return root
})

function outputFolderFileCount(folder: OutputTreeFolder): number {
  let total = folder.files.length
  for (const child of folder.folders.values()) {
    total += outputFolderFileCount(child)
  }
  return total
}

function isOutputFolderExpanded(path: string) {
  return Boolean(expandedOutputFolders.value[path])
}

function toggleOutputFolder(path: string) {
  expandedOutputFolders.value = {
    ...expandedOutputFolders.value,
    [path]: !isOutputFolderExpanded(path),
  }
}

const visibleOutputTreeNodes = computed<OutputTreeNode[]>(() => {
  const nodes: OutputTreeNode[] = []
  const visit = (folder: OutputTreeFolder, depth: number) => {
    nodes.push({
      id: `folder:${folder.path}`,
      kind: 'folder',
      name: folder.name,
      path: folder.path,
      depth,
      fileCount: outputFolderFileCount(folder),
    })
    if (!isOutputFolderExpanded(folder.path)) return
    const folders = Array.from(folder.folders.values()).sort((left, right) => left.name.localeCompare(right.name))
    for (const child of folders) {
      visit(child, depth + 1)
    }
    const files = folder.files.slice().sort((left, right) => left.name.localeCompare(right.name))
    for (const file of files) {
      nodes.push({
        id: `file:${file.path}`,
        kind: 'file',
        name: file.name,
        path: file.path,
        depth: depth + 1,
        file,
      })
    }
  }
  if (outputFiles.value.length) {
    visit(outputTreeRoot.value, 0)
  }
  return nodes
})

const maskGroups = computed(() => [
  {
    key: 'body-composition',
    maskType: 'body-composition' as MaskType,
    title: 'BODY COMPOSITION',
    emptyText: t('views_PatientDetailView.bodyComposition.empty'),
    slots: [
      { phase: 'pre' as CtPhase, label: t('views_PatientDetailView.mask.pre'), status: bodyPreMask.value },
      { phase: 'post' as CtPhase, label: t('views_PatientDetailView.mask.post'), status: bodyPostMask.value },
    ],
  },
  {
    key: 'spine',
    maskType: 'spine' as MaskType,
    title: 'SPINE',
    emptyText: t('views_PatientDetailView.spine.empty'),
    slots: [
      { phase: 'pre' as CtPhase, label: t('views_PatientDetailView.mask.pre'), status: spinePreMask.value },
      { phase: 'post' as CtPhase, label: t('views_PatientDetailView.mask.post'), status: spinePostMask.value },
    ],
  },
  {
    key: 'lung',
    maskType: 'lung' as MaskType,
    title: 'LUNG',
    emptyText: t('views_PatientDetailView.lung.empty'),
    slots: [
      { phase: 'pre' as CtPhase, label: t('views_PatientDetailView.mask.pre'), status: lungPreMask.value },
      { phase: 'post' as CtPhase, label: t('views_PatientDetailView.mask.post'), status: lungPostMask.value },
    ],
  },
  {
    key: 'tumor',
    maskType: 'tumor' as MaskType,
    title: 'TUMOR',
    emptyText: t('views_PatientDetailView.tumor.empty'),
    slots: [
      { phase: 'pre' as CtPhase, label: t('views_PatientDetailView.mask.pre'), status: tumorPreMask.value },
      { phase: 'post' as CtPhase, label: t('views_PatientDetailView.mask.post'), status: tumorPostMask.value },
    ],
  },
])

type MaskGroup = (typeof maskGroups.value)[number]

function maskGroupHasData(group: MaskGroup) {
  return group.slots.some((slot) => slot.status.status === 'ready')
}

function isMaskGroupExpanded(group: MaskGroup) {
  return maskGroupOverrides.value[group.key] ?? maskGroupHasData(group)
}

function toggleMaskGroup(groupKey: string) {
  const group = maskGroups.value.find((item) => item.key === groupKey)
  if (!group) return
  maskGroupOverrides.value = {
    ...maskGroupOverrides.value,
    [groupKey]: !isMaskGroupExpanded(group),
  }
}

function maskGroupSummary(group: MaskGroup) {
  const readyCount = group.slots.filter((slot) => slot.status.status === 'ready').length
  return `${readyCount}/${group.slots.length} ${t('views_PatientDetailView.mask.ready')}`
}

function metricResultForPhase(phase: CtPhase) {
  return bodyCompositionResults.value?.metrics?.[phase] || { csv: null, xlsx: null, summary: null }
}

function metricResultSourceLabel(source?: string | null) {
  if (source === 'standard') return 'Uploaded'
  if (source === 'agent_output') return 'Agent'
  return source || 'Ready'
}

function formatMetricValue(value?: number | null, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(digits)
}

function formatSignedNumber(value?: number | null, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  const numberValue = Number(value)
  return `${numberValue > 0 ? '+' : ''}${numberValue.toFixed(digits)}`
}

function metricSummaryItems(summary?: BodyCompositionMetricsSummary | null) {
  if (!summary) return []
  return [
    { key: 'smvi', label: 'SMVI', value: formatMetricValue(summary.smvi) },
    { key: 'vavi', label: 'VAVI', value: formatMetricValue(summary.vavi) },
    { key: 'savi', label: 'SAVI', value: formatMetricValue(summary.savi) },
    { key: 'muscle', label: 'Muscle', value: `${formatMetricValue(summary.muscle_cm3, 0)} cm³` },
    { key: 'vat', label: 'VAT', value: `${formatMetricValue(summary.vat_cm3, 0)} cm³` },
    { key: 'sat', label: 'SAT', value: `${formatMetricValue(summary.sat_cm3, 0)} cm³` },
  ]
}

onMounted(() => {
  fetchPatientDetail()
})

async function fetchPatientDetail() {
  loading.value = true
  try {
    const [
      patientInfo,
      preStatus,
      postStatus,
      bodyPreStatus,
      bodyPostStatus,
      spinePreStatus,
      spinePostStatus,
      lungPreStatus,
      lungPostStatus,
      tumorPreStatus,
      tumorPostStatus,
      outputs,
      bodyResults,
    ] = await Promise.all([
      getPatient(patientId.value),
      getPatientCtStatus(patientId.value, 'pre'),
      getPatientCtStatus(patientId.value, 'post'),
      getPatientMaskStatus(patientId.value, 'body-composition', 'pre'),
      getPatientMaskStatus(patientId.value, 'body-composition', 'post'),
      getPatientMaskStatus(patientId.value, 'spine', 'pre'),
      getPatientMaskStatus(patientId.value, 'spine', 'post'),
      getPatientMaskStatus(patientId.value, 'lung', 'pre'),
      getPatientMaskStatus(patientId.value, 'lung', 'post'),
      getPatientMaskStatus(patientId.value, 'tumor', 'pre'),
      getPatientMaskStatus(patientId.value, 'tumor', 'post'),
      getPatientOutputs(patientId.value).catch((error) => {
        console.error('Load patient outputs failed:', error)
        return { patient_id: patientId.value, output_root: '', files: [] }
      }),
      getBodyCompositionResults(patientId.value).catch((error) => {
        console.error('Load body composition results failed:', error)
        return null
      }),
    ])
    patient.value = patientInfo
    preCt.value = preStatus
    postCt.value = postStatus
    bodyPreMask.value = bodyPreStatus
    bodyPostMask.value = bodyPostStatus
    spinePreMask.value = spinePreStatus
    spinePostMask.value = spinePostStatus
    lungPreMask.value = lungPreStatus
    lungPostMask.value = lungPostStatus
    tumorPreMask.value = tumorPreStatus
    tumorPostMask.value = tumorPostStatus
    outputRoot.value = outputs.output_root
    outputFiles.value = outputs.files
    bodyCompositionResults.value = bodyResults
  } catch (error) {
    console.error('Load patient detail failed:', error)
    message.error(t('views_PatientDetailView.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function fetchPatientOutputs() {
  loadingOutputs.value = true
  try {
    const outputs = await getPatientOutputs(patientId.value)
    outputRoot.value = outputs.output_root
    outputFiles.value = outputs.files
  } catch (error: any) {
    console.error('Load patient outputs failed:', error)
    message.error(error?.message || 'Failed to load output files')
  } finally {
    loadingOutputs.value = false
  }
}

async function fetchBodyCompositionResults() {
  loadingBodyResults.value = true
  try {
    bodyCompositionResults.value = await getBodyCompositionResults(patientId.value)
  } catch (error: any) {
    console.error('Load body composition results failed:', error)
    message.error(error?.message || 'Failed to load body composition results')
  } finally {
    loadingBodyResults.value = false
  }
}

function goBack() {
  router.push('/patients')
}

async function openOutputsModal() {
  outputsOpen.value = true
  await fetchPatientOutputs()
}

async function handleExportReport() {
  exportingReport.value = true
  try {
    const blob = await downloadPatientReport(patientId.value)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${patientId.value}_ct_report.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    console.error('Export patient report failed:', error)
    message.error(error?.message || t('views_PatientDetailView.report.exportFailed'))
  } finally {
    exportingReport.value = false
  }
}

async function handleDownloadOutput(file: PatientOutputFile) {
  downloadingOutputPath.value = file.path
  try {
    const blob = await downloadPatientOutput(patientId.value, file.path)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.name
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    console.error('Download patient output failed:', error)
    message.error(error?.message || 'Failed to download output file')
  } finally {
    downloadingOutputPath.value = null
  }
}

async function downloadResultFile(file?: PatientResultFile | null) {
  if (!file) return
  downloadingResultPath.value = file.relative_path
  try {
    const blob = await downloadBodyCompositionResultFile(file)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.name
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    console.error('Download body composition result failed:', error)
    message.error(error?.message || 'Failed to download result file')
  } finally {
    downloadingResultPath.value = null
  }
}

function triggerBodyMetricUpload(phase: CtPhase) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.csv,.xlsx'
  input.onchange = () => {
    const file = input.files?.[0]
    if (file) {
      void uploadBodyMetricFile(phase, file)
    }
  }
  input.click()
}

async function uploadBodyMetricFile(phase: CtPhase, file: File) {
  uploadingBodyMetricPhase.value = phase
  try {
    bodyCompositionResults.value = await uploadBodyCompositionMetricFile(patientId.value, phase, file)
    message.success('Metric file uploaded')
  } catch (error: any) {
    console.error('Upload metric file failed:', error)
    message.error(error?.message || 'Failed to upload metric file')
  } finally {
    uploadingBodyMetricPhase.value = null
  }
}

function triggerBodyTypeUpload() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = () => {
    const file = input.files?.[0]
    if (file) {
      void uploadBodyTypeFile(file)
    }
  }
  input.click()
}

async function uploadBodyTypeFile(file: File) {
  uploadingBodyType.value = true
  try {
    bodyCompositionResults.value = await uploadBodyCompositionTypeFile(patientId.value, file)
    message.success('Type classification file uploaded')
  } catch (error: any) {
    console.error('Upload type classification failed:', error)
    message.error(error?.message || 'Failed to upload type classification')
  } finally {
    uploadingBodyType.value = false
  }
}

function triggerCtUpload(phase: CtPhase) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.nii,.gz,.dcm,.zip'
  input.onchange = () => {
    const file = input.files?.[0]
    if (file) {
      void uploadCtFile(phase, file)
    }
  }
  input.click()
}

function ctDropTarget(phase: CtPhase) {
  return `ct:${phase}`
}

function maskDropTarget(maskType: MaskType, phase: CtPhase) {
  return `mask:${maskType}:${phase}`
}

function setPreviewDrag(target: string, event?: DragEvent) {
  if (event?.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
  activeDropTarget.value = target
}

function clearPreviewDrag(target?: string) {
  if (!target || activeDropTarget.value === target) {
    activeDropTarget.value = null
  }
}

function isPreviewDropActive(target: string) {
  return activeDropTarget.value === target
}

function firstDroppedFile(event: DragEvent) {
  const file = event.dataTransfer?.files?.[0]
  if (!file) {
    message.warning(t('views_PatientDetailView.dragDrop.noFile'))
  }
  return file
}

function handleCtDrop(phase: CtPhase, event: DragEvent) {
  clearPreviewDrag(ctDropTarget(phase))
  if (uploadingPhase.value[phase]) return
  const file = firstDroppedFile(event)
  if (file) {
    void uploadCtFile(phase, file)
  }
}

async function uploadCtFile(phase: CtPhase, file: File) {
  uploadingPhase.value[phase] = true
  try {
    const status = await uploadPatientCt(patientId.value, phase, file)
    if (phase === 'pre') preCt.value = status
    else postCt.value = status
    message.success(t('views_PatientDetailView.ct.uploaded'))
  } catch (error: any) {
    console.error('Upload CT failed:', error)
    message.error(error?.message || t('views_PatientDetailView.ct.uploadFailed'))
  } finally {
    uploadingPhase.value[phase] = false
  }
}

async function handleDeleteCt(phase: CtPhase) {
  deletingPhase.value[phase] = true
  try {
    const status = await deletePatientCt(patientId.value, phase)
    if (phase === 'pre') preCt.value = status
    else postCt.value = status
    message.success(t('views_PatientDetailView.ct.deleted'))
  } catch (error: any) {
    console.error('Delete CT failed:', error)
    message.error(error?.message || t('views_PatientDetailView.ct.deleteFailed'))
  } finally {
    deletingPhase.value[phase] = false
  }
}

function maskKey(maskType: MaskType, phase: CtPhase) {
  return `${maskType}:${phase}`
}

function getMaskStatusRef(maskType: MaskType, phase: CtPhase) {
  if (maskType === 'body-composition') return phase === 'pre' ? bodyPreMask : bodyPostMask
  if (maskType === 'spine') return phase === 'pre' ? spinePreMask : spinePostMask
  if (maskType === 'lung') return phase === 'pre' ? lungPreMask : lungPostMask
  return phase === 'pre' ? tumorPreMask : tumorPostMask
}

function maskDisplayName(maskType: MaskType) {
  if (maskType === 'body-composition') return 'Body Composition'
  if (maskType === 'spine') return 'Spine'
  if (maskType === 'lung') return 'Lung'
  return 'Tumor'
}

function setMaskStatus(status: PatientMaskStatus) {
  getMaskStatusRef(status.mask_type, status.phase).value = status
  if (status.status === 'ready') {
    maskGroupOverrides.value = {
      ...maskGroupOverrides.value,
      [status.mask_type]: true,
    }
  }
}

async function refreshCtStatus(phase: CtPhase) {
  const status = await getPatientCtStatus(patientId.value, phase)
  if (phase === 'pre') preCt.value = status
  else postCt.value = status
}

function triggerMaskUpload(maskType: MaskType, phase: CtPhase) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.nii,.gz'
  input.onchange = () => {
    const file = input.files?.[0]
    if (file) {
      void uploadMaskFile(maskType, phase, file)
    }
  }
  input.click()
}

function handleMaskDrop(maskType: MaskType, phase: CtPhase, event: DragEvent) {
  const key = maskKey(maskType, phase)
  clearPreviewDrag(maskDropTarget(maskType, phase))
  if (uploadingMaskKeys.value[key]) return
  const file = firstDroppedFile(event)
  if (file) {
    void uploadMaskFile(maskType, phase, file)
  }
}

async function uploadMaskFile(maskType: MaskType, phase: CtPhase, file: File) {
  const key = maskKey(maskType, phase)
  uploadingMaskKeys.value[key] = true
  try {
    const status = await uploadPatientMask(patientId.value, maskType, phase, file)
    setMaskStatus(status)
    if (maskType === 'tumor') {
      await refreshCtStatus(phase)
    }
    message.success(t('views_PatientDetailView.mask.uploaded'))
  } catch (error: any) {
    console.error('Upload mask failed:', error)
    message.error(error?.message || t('views_PatientDetailView.mask.uploadFailed'))
  } finally {
    uploadingMaskKeys.value[key] = false
  }
}

async function handleDeleteMask(maskType: MaskType, phase: CtPhase) {
  const key = maskKey(maskType, phase)
  deletingMaskKeys.value[key] = true
  try {
    const status = await deletePatientMask(patientId.value, maskType, phase)
    setMaskStatus(status)
    if (maskType === 'tumor') {
      await refreshCtStatus(phase)
    }
    message.success(t('views_PatientDetailView.mask.deleted'))
  } catch (error: any) {
    console.error('Delete mask failed:', error)
    message.error(error?.message || t('views_PatientDetailView.mask.deleteFailed'))
  } finally {
    deletingMaskKeys.value[key] = false
  }
}

function ctStatusLabel(status: PatientCtStatus['status']) {
  return status === 'ready'
    ? t('views_PatientDetailView.ct.ready')
    : t('views_PatientDetailView.ct.empty')
}

function ctStatusColor(status: PatientCtStatus['status']) {
  return status === 'ready' ? 'green' : 'default'
}

function maskStatusLabel(status: PatientMaskStatus['status']) {
  return status === 'ready'
    ? t('views_PatientDetailView.mask.ready')
    : t('views_PatientDetailView.mask.empty')
}

function maskStatusColor(status: PatientMaskStatus['status']) {
  return status === 'ready' ? 'green' : 'default'
}

function formatFileSize(value?: number | null) {
  if (!value) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function withApiBase(url: string) {
  if (!url || /^https?:\/\//.test(url)) return url
  const baseURL = (import.meta as any).env?.VITE_API_BASE || '/api'
  return `${baseURL}${url.startsWith('/') ? url : `/${url}`}`
}

function previewSrc(url: string, status: Pick<PatientCtStatus | PatientMaskStatus, 'uploaded_at' | 'file_size'> & { preview_updated_at?: string | null }) {
  const fullUrl = withApiBase(url)
  if (!fullUrl) return fullUrl
  const cacheKey = `${status.preview_updated_at || status.uploaded_at || ''}:${status.file_size || ''}`
  const separator = fullUrl.includes('?') ? '&' : '?'
  return `${fullUrl}${separator}v=${encodeURIComponent(cacheKey)}`
}

function ctViewerMetadataUrl(phase: CtPhase) {
  const status = phase === 'pre' ? preCt.value : postCt.value
  return previewSrc(`/patients/${encodeURIComponent(patientId.value)}/ct/${phase}/viewer-metadata`, status)
}

function ctSliceBaseUrl(phase: CtPhase) {
  return withApiBase(`/patients/${encodeURIComponent(patientId.value)}/ct/${phase}/slice`)
}

function ctVolumeUrl(phase: CtPhase, status: PatientCtStatus) {
  return previewSrc(`/patients/${encodeURIComponent(patientId.value)}/ct/${phase}/volume`, status)
}

function maskSliceBaseUrl(maskType: MaskType, phase: CtPhase, status: PatientMaskStatus) {
  void status
  return withApiBase(`/patients/${encodeURIComponent(patientId.value)}/mask/${maskType}/${phase}/slice`)
}

function maskVolumeUrl(maskType: MaskType, phase: CtPhase, status: PatientMaskStatus) {
  return previewSrc(`/patients/${encodeURIComponent(patientId.value)}/mask/${maskType}/${phase}/volume`, status)
}

function statusCacheKey(status: Pick<PatientCtStatus | PatientMaskStatus, 'uploaded_at' | 'file_size'> & { preview_updated_at?: string | null }) {
  return `${status.preview_updated_at || status.uploaded_at || ''}:${status.file_size || ''}`
}

function openCtViewer(phase: CtPhase) {
  const status = phase === 'pre' ? preCt.value : postCt.value
  viewerTitle.value = `${phase.toUpperCase()} CT - ${status.file_name || patientId.value}`
  viewerTarget.value = {
    metadataUrl: ctViewerMetadataUrl(phase),
    ctSliceBaseUrl: ctSliceBaseUrl(phase),
    maskSliceBaseUrl: null,
    ctVolumeUrl: ctVolumeUrl(phase, status),
    maskVolumeUrl: null,
    cacheKey: statusCacheKey(status),
  }
  viewerOpen.value = true
}

function openMaskViewer(maskType: MaskType, phase: CtPhase) {
  const maskStatus = getMaskStatusRef(maskType, phase).value
  const ctStatus = phase === 'pre' ? preCt.value : postCt.value
  if (ctStatus.status !== 'ready') {
    message.warning(t('views_PatientDetailView.ct.empty'))
    return
  }
  viewerTitle.value = `${maskDisplayName(maskType)} ${phase.toUpperCase()} - ${maskStatus.file_name || patientId.value}`
  viewerTarget.value = {
    metadataUrl: ctViewerMetadataUrl(phase),
    ctSliceBaseUrl: ctSliceBaseUrl(phase),
    maskSliceBaseUrl: maskSliceBaseUrl(maskType, phase, maskStatus),
    ctVolumeUrl: ctVolumeUrl(phase, ctStatus),
    maskVolumeUrl: maskVolumeUrl(maskType, phase, maskStatus),
    cacheKey: `${statusCacheKey(ctStatus)}:${statusCacheKey(maskStatus)}`,
  }
  viewerOpen.value = true
}

function hasPreviewPlanes(status: PatientCtStatus | PatientMaskStatus) {
  return previewPlaneEntries(status).length === 3
}

function previewPlaneEntries(status: PatientCtStatus | PatientMaskStatus) {
  const planes = status.preview_planes || {}
  return [
    { key: 'axial', label: 'Axial', url: planes.axial },
    { key: 'coronal', label: 'Coronal', url: planes.coronal },
    { key: 'sagittal', label: 'Sagittal', url: planes.sagittal },
  ].filter((plane): plane is { key: string; label: string; url: string } => Boolean(plane.url))
}

function initials(name: string) {
  const clean = (name || '').trim()
  if (!clean) return 'P'
  const parts = clean.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return clean.slice(0, 2).toUpperCase()
}

type OptionGroup = 'sex' | 'smoking' | 'pathology' | 'pdL1'

function formatOption(group: OptionGroup, value?: string | null) {
  if (!value) return '-'
  const groupKeys: Record<OptionGroup, Record<string, string>> = {
    sex: {
      Male: 'views_PatientManageView.options.sex.male',
      Female: 'views_PatientManageView.options.sex.female',
      Other: 'views_PatientManageView.options.sex.other',
    },
    smoking: {
      Never: 'views_PatientManageView.options.smoking.never',
      Former: 'views_PatientManageView.options.smoking.former',
      Current: 'views_PatientManageView.options.smoking.current',
      Unknown: 'views_PatientManageView.options.smoking.unknown',
    },
    pathology: {
      Adenocarcinoma: 'views_PatientManageView.options.pathology.adenocarcinoma',
      'Squamous cell carcinoma': 'views_PatientManageView.options.pathology.squamous',
      'Large cell carcinoma': 'views_PatientManageView.options.pathology.largeCell',
      'Small cell lung cancer': 'views_PatientManageView.options.pathology.smallCell',
      Other: 'views_PatientManageView.options.pathology.other',
      Unknown: 'views_PatientManageView.options.pathology.unknown',
    },
    pdL1: {
      'High expression': 'views_PatientManageView.options.pdL1.high',
      'Low expression': 'views_PatientManageView.options.pdL1.low',
      Negative: 'views_PatientManageView.options.pdL1.negative',
      Positive: 'views_PatientManageView.options.pdL1.positive',
      Unknown: 'views_PatientManageView.options.pdL1.unknown',
    },
  }
  const key = groupKeys[group][value]
  return key ? t(key) : value
}
</script>

<style scoped>
.detail-page {
  --patient-preview-height: 400px;
  min-height: 100%;
  padding: 28px;
  background: linear-gradient(180deg, #f5f7fb 0%, #eef3f8 100%);
}

.detail-shell {
  max-width: 1480px;
  margin: 0 auto;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
  padding: 22px 24px;
  background: #fff;
  border: 1px solid #e4e9f1;
  border-radius: 8px;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.07);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px;
  background: #f7fafc;
  border: 1px solid #e4e9f1;
  border-radius: 8px;
}

.header-action {
  height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  border-radius: 7px;
  font-weight: 700;
  letter-spacing: 0;
}

.header-action-back {
  color: #334155;
  border-color: transparent;
  background: transparent;
}

.header-action-back:hover,
.header-action-back:focus {
  color: #0f766e;
  border-color: #cfe7e2;
  background: #eef8f6;
}

.header-action-export {
  border-color: #0f766e;
  background: #0f766e;
  box-shadow: 0 8px 18px rgba(15, 118, 110, 0.22);
}

.header-action-export:hover,
.header-action-export:focus {
  border-color: #0b5f59;
  background: #0b5f59;
  box-shadow: 0 10px 22px rgba(15, 118, 110, 0.28);
}

.header-action-outputs {
  color: #334155;
  border-color: #d8e1ea;
  background: #fff;
}

.header-action-outputs:hover,
.header-action-outputs:focus {
  color: #0f766e;
  border-color: #cfe7e2;
  background: #eef8f6;
}

.header-main {
  display: flex;
  align-items: center;
  gap: 14px;
}

.avatar {
  display: inline-flex;
  width: 52px;
  height: 52px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #e8f3f1;
  color: #0f766e;
  font-size: 16px;
  font-weight: 800;
}

.eyebrow,
.panel-kicker {
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}

.detail-header h1 {
  margin: 2px 0;
  color: #111827;
  font-size: 26px;
  line-height: 1.2;
}

.detail-header p {
  margin: 0;
  color: #667085;
}

.info-grid,
.section-grid {
  display: grid;
  gap: 14px;
  margin-bottom: 14px;
}

.info-grid {
  grid-template-columns: 1.35fr .65fr;
}

.section-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.section-grid.module-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 14px;
}

.full-span {
  grid-column: 1 / -1;
}

.panel {
  background: #fff;
  border: 1px solid #e4e9f1;
  border-radius: 8px;
  padding: 18px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}

.panel-title {
  margin-bottom: 14px;
  color: #111827;
  font-size: 16px;
  font-weight: 700;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.feature-panel.collapsed {
  padding-bottom: 14px;
}

.feature-panel.collapsed .panel-header {
  margin-bottom: 0;
}

.mask-group-header {
  align-items: center;
}

.mask-group-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mask-group-summary {
  color: #667085;
  font-size: 12px;
  font-weight: 700;
}

.mask-collapse-action {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border-radius: 7px;
}

.mask-collapse-chevron {
  display: inline-block;
  color: #334155;
  font-size: 16px;
  line-height: 1;
  transform: rotate(-90deg);
  transition: transform 0.16s ease;
}

.mask-collapse-chevron.expanded {
  transform: rotate(0deg);
}

.panel-header h2,
.module-panel h2 {
  margin: 2px 0 0;
  color: #111827;
  font-size: 18px;
}

.baseline-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.info-item {
  min-height: 72px;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #edf0f5;
  border-radius: 8px;
}

.info-item span {
  display: block;
  margin-bottom: 8px;
  color: #697386;
  font-size: 12px;
}

.info-item strong {
  color: #111827;
  font-size: 14px;
}

.workflow-list {
  display: grid;
  gap: 10px;
}

.workflow-item {
  display: flex;
  gap: 10px;
}

.step-dot {
  display: inline-flex;
  width: 24px;
  height: 24px;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #0f766e;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}

.workflow-item strong {
  color: #111827;
  font-size: 13px;
}

.workflow-item p {
  margin: 2px 0 0;
  color: #667085;
  font-size: 12px;
  line-height: 1.5;
}

.scan-placeholder {
  position: relative;
  height: var(--patient-preview-height);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 10px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #667085;
}

.feature-window {
  position: relative;
  height: var(--patient-preview-height);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 10px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #667085;
}

.scan-placeholder small,
.feature-window small {
  color: #94a3b8;
  font-size: 12px;
}

.feature-window :deep(svg) {
  font-size: 30px;
  color: #0f766e;
}

.mask-slot-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

.mask-slot {
  min-width: 0;
}

.mask-slot-header {
  min-height: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.mask-slot-header strong {
  min-width: 0;
  overflow: hidden;
  color: #111827;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ct-ready {
  height: var(--patient-preview-height);
  box-sizing: border-box;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 0;
  overflow: hidden;
  background: #0b0f19;
  border: 1px solid #dbe5ef;
  border-radius: 8px;
  color: #0f766e;
}

.preview-drop-zone {
  transition: border-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
}

.preview-drop-zone.drop-active {
  border-color: #0f766e;
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.16);
}

.drop-overlay {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 10px;
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.16s ease;
}

.drop-overlay :deep(svg) {
  font-size: 28px;
}

.preview-drop-zone.drop-active .drop-overlay {
  opacity: 1;
}

.preview-zoom-action {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 2;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  background: rgba(15, 23, 42, 0.78);
  border-color: rgba(255, 255, 255, 0.2);
  color: #f9fafb;
}

.preview-zoom-action:hover,
.preview-zoom-action:focus {
  background: rgba(15, 23, 42, 0.94);
  color: #fff;
}

.ct-preview-image {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
  background: #0b0f19;
}

.mpr-preview-grid {
  width: 100%;
  height: 100%;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 10px;
  box-sizing: border-box;
}

.mpr-preview-pane {
  min-width: 0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #05070c;
  border-right: 1px solid rgba(148, 163, 184, 0.12);
}

.mpr-preview-pane:last-child {
  border-right: 0;
}

.mpr-preview-pane img {
  max-width: 100%;
  max-height: 100%;
  display: block;
  object-fit: contain;
}

.mpr-preview-pane span {
  position: absolute;
  left: 8px;
  bottom: 8px;
  color: #d1d5db;
  font-size: 10px;
  line-height: 1;
}

:global(.mpr-modal .ant-modal-content) {
  padding: 0;
  overflow: hidden;
}

:global(.mpr-modal .ant-modal-header) {
  margin: 0;
  padding: 14px 18px;
  background: #0b0f19;
  border-bottom: 1px solid #1f2937;
}

:global(.mpr-modal .ant-modal-title),
:global(.mpr-modal .ant-modal-close) {
  color: #f9fafb;
}

:global(.mpr-modal .ant-modal-body) {
  padding: 0;
  background: #05070c;
}

.ct-image-caption {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 11px;
  background: rgba(15, 23, 42, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  backdrop-filter: blur(4px);
}

.ct-image-caption strong {
  min-width: 0;
  overflow: hidden;
  color: #f9fafb;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ct-image-caption span {
  flex: 0 0 auto;
  color: #cbd5e1;
  font-size: 12px;
}

.ct-file-summary {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
}

.ct-file-summary :deep(svg) {
  flex: 0 0 auto;
  font-size: 30px;
}

.ct-file-summary strong {
  display: block;
  max-width: 100%;
  margin-bottom: 6px;
  overflow: hidden;
  color: #111827;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ct-file-summary span {
  color: #667085;
  font-size: 13px;
}

.ct-action-bar {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.ct-primary-action {
  flex: 1;
}

.ct-icon-action {
  width: 40px;
  flex: 0 0 auto;
}

.body-results-panel {
  margin-bottom: 14px;
}

.body-results-header {
  align-items: center;
}

.body-results-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.body-result-card {
  min-width: 0;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e4e9f1;
  border-radius: 8px;
}

.body-result-card-header {
  min-height: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.body-result-card-header strong {
  min-width: 0;
  overflow: hidden;
  color: #111827;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-mini-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 7px;
}

.metric-mini-item {
  min-width: 0;
  padding: 8px;
  background: #fff;
  border: 1px solid #edf0f5;
  border-radius: 7px;
}

.metric-mini-item span {
  display: block;
  margin-bottom: 4px;
  color: #667085;
  font-size: 11px;
}

.metric-mini-item strong {
  color: #111827;
  font-size: 13px;
}

.body-result-empty {
  min-height: 82px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border: 1px dashed #cbd5e1;
  border-radius: 7px;
  color: #667085;
  font-size: 12px;
}

.body-result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.type-result-list {
  display: grid;
  gap: 7px;
}

.type-result-row {
  min-height: 34px;
  display: grid;
  grid-template-columns: 52px 74px 1fr;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  background: #fff;
  border: 1px solid #edf0f5;
  border-radius: 7px;
}

.type-result-row span {
  color: #667085;
  font-size: 12px;
  font-weight: 700;
}

.type-result-row strong {
  color: #0f766e;
  font-size: 14px;
}

.type-result-row small {
  min-width: 0;
  overflow: hidden;
  color: #667085;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hidden-file-input {
  display: none;
}

.scan-placeholder :deep(svg) {
  font-size: 28px;
  color: #0f766e;
}

.output-root {
  margin: 0 0 10px;
  padding: 7px 9px;
  overflow: hidden;
  background: #f8fafc;
  border: 1px solid #edf0f5;
  border-radius: 6px;
  color: #667085;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.outputs-modal-toolbar {
  min-height: 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #667085;
  font-size: 12px;
  font-weight: 700;
}

.output-tree {
  max-height: min(62vh, 620px);
  overflow: auto;
  border: 1px solid var(--border-color, #d8dee4);
  border-radius: 8px;
  background: var(--bg-primary, #fff);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.output-tree-row {
  min-height: 40px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--border-color, #d8dee4);
  background: var(--bg-primary, #fff);
  cursor: default;
  transition: all 0.15s ease;
}

.output-tree-row:last-child {
  border-bottom: 0;
}

.output-tree-row.folder:hover,
.output-tree-row.file:hover {
  background: var(--hover-bg, #f6f8fa);
  border-left: 3px solid var(--link-color, #1a73e8);
}

.output-tree-row:hover .output-tree-main,
.output-tree-row:hover .output-file-main {
  padding-left: calc(var(--tree-depth) * 20px + 9px);
}

.output-tree-main,
.output-file-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 16px 9px calc(var(--tree-depth) * 20px + 12px);
}

.output-tree-folder-button {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.output-tree-chevron {
  display: inline-flex;
  width: 16px;
  height: 16px;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: var(--text-secondary, #57606a);
  font-size: 10px;
}

.output-tree-spacer {
  width: 16px;
  flex: 0 0 auto;
}

.output-tree-row:hover .output-tree-chevron {
  color: var(--link-color, #1a73e8);
}

.output-tree-icon {
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  font-size: 16px;
  transition: transform 0.2s ease;
}

.output-tree-row:hover .output-tree-icon {
  transform: scale(1.1);
}

.output-tree-row.folder .output-tree-icon {
  color: #54aeff;
  font-size: 15px;
}

.output-tree-row.file .output-tree-icon {
  color: #57606a;
  font-size: 16px;
}

.output-tree-main strong,
.output-file-main strong,
.output-file-main span {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.output-tree-main strong,
.output-file-main strong {
  color: var(--link-color, #1a73e8);
  font-size: 14px;
  font-weight: 500;
}

.output-tree-row:hover .output-tree-main strong,
.output-tree-row:hover .output-file-main strong {
  color: var(--link-hover, #0969da);
  text-decoration: underline;
}

.output-tree-row.folder .output-tree-main strong {
  color: var(--text-primary, #24292f);
  text-decoration: none;
}

.output-tree-main span,
.output-file-main span {
  color: var(--text-secondary, #57606a);
  font-size: 12px;
}

.output-file-meta {
  width: 220px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 6px 12px 6px 0;
  color: var(--text-secondary, #57606a);
  font-family: 'SFMono-Regular', 'Consolas', monospace;
  font-size: 12px;
  white-space: nowrap;
}

.output-file-meta .ct-icon-action {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.outputs-empty {
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 8px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #667085;
}

.outputs-empty :deep(svg) {
  color: #0f766e;
  font-size: 24px;
}

.module-panel {
  min-height: 210px;
}

.module-panel p {
  min-height: 48px;
  margin: 8px 0 18px;
  color: #667085;
  line-height: 1.6;
}

@media (max-width: 980px) {
  .info-grid,
  .section-grid.two,
  .section-grid.module-grid,
  .mask-slot-grid,
  .body-results-grid {
    grid-template-columns: 1fr;
  }

  .baseline-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .output-tree-row {
    grid-template-columns: 1fr;
  }

  .output-file-meta {
    justify-content: space-between;
  }

}

@media (max-width: 640px) {
  .detail-page {
    padding: 18px;
  }

  .detail-header {
    align-items: stretch;
    flex-direction: column;
  }

  .header-actions {
    flex-wrap: wrap;
    justify-content: space-between;
  }

  .header-action {
    flex: 1 1 120px;
    justify-content: center;
  }

  .baseline-grid {
    grid-template-columns: 1fr;
  }
}
</style>
