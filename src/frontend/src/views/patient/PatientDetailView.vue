<template>
  <div class="detail-page">
    <div class="detail-shell">
      <div class="detail-header">
        <a-button @click="goBack">
          <template #icon><ArrowLeftOutlined /></template>
          {{ t('common.back') }}
        </a-button>
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
              <div v-if="preCt.status === 'ready'" class="ct-ready">
                <template v-if="preCt.preview_url">
                  <img :src="withApiBase(preCt.preview_url)" :alt="preCt.file_name || 'Pre CT'" class="ct-preview-image" />
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
              </div>
              <div v-else class="scan-placeholder">
                <CameraOutlined />
                  <span>{{ t('views_PatientDetailView.pre.empty') }}</span>
                </div>
              <div class="ct-action-bar">
                <a-button class="ct-primary-action" :loading="uploadingPhase === 'pre'" @click="triggerCtUpload('pre')">
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
                  <a-button class="ct-icon-action" danger :loading="deletingPhase === 'pre'" :title="t('views_PatientDetailView.ct.delete')">
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
              <div v-if="postCt.status === 'ready'" class="ct-ready">
                <template v-if="postCt.preview_url">
                  <img :src="withApiBase(postCt.preview_url)" :alt="postCt.file_name || 'Post CT'" class="ct-preview-image" />
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
              </div>
              <div v-else class="scan-placeholder">
                <CameraOutlined />
                <span>{{ t('views_PatientDetailView.post.empty') }}</span>
              </div>
              <div class="ct-action-bar">
                <a-button class="ct-primary-action" :loading="uploadingPhase === 'post'" @click="triggerCtUpload('post')">
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
                  <a-button class="ct-icon-action" danger :loading="deletingPhase === 'post'" :title="t('views_PatientDetailView.ct.delete')">
                    <template #icon><DeleteOutlined /></template>
                  </a-button>
                </a-popconfirm>
              </div>
            </section>
          </div>

          <input
            ref="ctInputRef"
            type="file"
            class="hidden-file-input"
            accept=".nii,.gz,.dcm,.zip"
            @change="handleCtFileChange"
          />

          <div class="section-grid two">
            <section v-for="group in maskGroups" :key="group.key" class="panel feature-panel full-span">
              <div class="panel-header">
                <div>
                  <div class="panel-kicker">{{ group.title }}</div>
                </div>
              </div>
              <div class="mask-slot-grid">
                <div v-for="slot in group.slots" :key="slot.phase" class="mask-slot">
                  <div class="mask-slot-header">
                    <strong>{{ slot.label }}</strong>
                    <a-tag :color="maskStatusColor(slot.status.status)">{{ maskStatusLabel(slot.status.status) }}</a-tag>
                  </div>
                  <div v-if="slot.status.status === 'ready'" class="ct-ready">
                    <template v-if="slot.status.preview_url">
                      <img
                        :src="withApiBase(slot.status.preview_url)"
                        :alt="slot.status.file_name || `${group.title} ${slot.label}`"
                        class="ct-preview-image"
                      />
                      <div class="ct-image-caption">
                        <strong>{{ slot.status.file_name }}</strong>
                        <span>{{ formatFileSize(slot.status.file_size) }} · {{ formatDateTime(slot.status.uploaded_at) }}</span>
                      </div>
                    </template>
                    <div v-else class="ct-file-summary">
                      <component :is="group.icon" />
                      <div>
                        <strong>{{ slot.status.file_name }}</strong>
                        <span>{{ formatFileSize(slot.status.file_size) }} · {{ formatDateTime(slot.status.uploaded_at) }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else class="feature-window">
                    <component :is="group.icon" />
                    <span>{{ group.emptyText }}</span>
                  </div>
                  <div class="ct-action-bar">
                    <a-button
                      class="ct-primary-action"
                      :loading="uploadingMaskKey === maskKey(group.maskType, slot.phase)"
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
                        :loading="deletingMaskKey === maskKey(group.maskType, slot.phase)"
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

          <input
            ref="maskInputRef"
            type="file"
            class="hidden-file-input"
            accept=".nii,.gz"
            @change="handleMaskFileChange"
          />

          <div class="section-grid three">
            <section v-for="module in analysisModules" :key="module.key" class="panel module-panel">
              <div class="module-icon">
                <component :is="module.icon" />
              </div>
              <h2>{{ module.title }}</h2>
              <p>{{ module.desc }}</p>
              <a-button disabled>{{ t('views_PatientDetailView.notConfigured') }}</a-button>
            </section>
          </div>
        </template>

        <a-empty v-else-if="!loading" :description="t('views_PatientDetailView.notFound')" />
      </a-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  BarChartOutlined,
  CameraOutlined,
  DeleteOutlined,
  FileTextOutlined,
  FundProjectionScreenOutlined,
  UploadOutlined,
} from '@ant-design/icons-vue'
import {
  deletePatientCt,
  deletePatientMask,
  getPatient,
  getPatientCtStatus,
  getPatientMaskStatus,
  uploadPatientCt,
  uploadPatientMask,
  type CtPhase,
  type MaskType,
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
const emptyPreCt = (): PatientCtStatus => ({ phase: 'pre', status: 'empty', file_name: null, file_size: null, uploaded_at: null })
const emptyPostCt = (): PatientCtStatus => ({ phase: 'post', status: 'empty', file_name: null, file_size: null, uploaded_at: null })
const emptyMask = (maskType: MaskType, phase: CtPhase): PatientMaskStatus => ({
  mask_type: maskType,
  phase,
  status: 'empty',
  file_name: null,
  file_size: null,
  uploaded_at: null,
  preview_url: null,
})
const preCt = ref<PatientCtStatus>(emptyPreCt())
const postCt = ref<PatientCtStatus>(emptyPostCt())
const bodyPreMask = ref<PatientMaskStatus>(emptyMask('body-composition', 'pre'))
const bodyPostMask = ref<PatientMaskStatus>(emptyMask('body-composition', 'post'))
const spinePreMask = ref<PatientMaskStatus>(emptyMask('spine', 'pre'))
const spinePostMask = ref<PatientMaskStatus>(emptyMask('spine', 'post'))
const selectedUploadPhase = ref<CtPhase | null>(null)
const uploadingPhase = ref<CtPhase | null>(null)
const deletingPhase = ref<CtPhase | null>(null)
const ctInputRef = ref<HTMLInputElement | null>(null)
const selectedMaskTarget = ref<{ maskType: MaskType; phase: CtPhase } | null>(null)
const uploadingMaskKey = ref<string | null>(null)
const deletingMaskKey = ref<string | null>(null)
const maskInputRef = ref<HTMLInputElement | null>(null)

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
    key: 'body',
    index: '3',
    title: t('views_PatientDetailView.workflowSteps.body.title'),
    desc: t('views_PatientDetailView.workflowSteps.body.desc'),
  },
  {
    key: 'report',
    index: '4',
    title: t('views_PatientDetailView.workflowSteps.report.title'),
    desc: t('views_PatientDetailView.workflowSteps.report.desc'),
  },
])

const analysisModules = computed(() => [
  {
    key: 'bc',
    icon: BarChartOutlined,
    title: t('views_PatientDetailView.modules.bc.title'),
    desc: t('views_PatientDetailView.modules.bc.desc'),
  },
  {
    key: 'mpr',
    icon: FundProjectionScreenOutlined,
    title: t('views_PatientDetailView.modules.mpr.title'),
    desc: t('views_PatientDetailView.modules.mpr.desc'),
  },
  {
    key: 'report',
    icon: FileTextOutlined,
    title: t('views_PatientDetailView.modules.report.title'),
    desc: t('views_PatientDetailView.modules.report.desc'),
  },
])

const maskGroups = computed(() => [
  {
    key: 'body-composition',
    maskType: 'body-composition' as MaskType,
    title: 'BODY COMPOSITION',
    icon: BarChartOutlined,
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
    icon: FundProjectionScreenOutlined,
    emptyText: t('views_PatientDetailView.spine.empty'),
    slots: [
      { phase: 'pre' as CtPhase, label: t('views_PatientDetailView.mask.pre'), status: spinePreMask.value },
      { phase: 'post' as CtPhase, label: t('views_PatientDetailView.mask.post'), status: spinePostMask.value },
    ],
  },
])

onMounted(() => {
  fetchPatientDetail()
})

async function fetchPatientDetail() {
  loading.value = true
  try {
    const [patientInfo, preStatus, postStatus, bodyPreStatus, bodyPostStatus, spinePreStatus, spinePostStatus] = await Promise.all([
      getPatient(patientId.value),
      getPatientCtStatus(patientId.value, 'pre'),
      getPatientCtStatus(patientId.value, 'post'),
      getPatientMaskStatus(patientId.value, 'body-composition', 'pre'),
      getPatientMaskStatus(patientId.value, 'body-composition', 'post'),
      getPatientMaskStatus(patientId.value, 'spine', 'pre'),
      getPatientMaskStatus(patientId.value, 'spine', 'post'),
    ])
    patient.value = patientInfo
    preCt.value = preStatus
    postCt.value = postStatus
    bodyPreMask.value = bodyPreStatus
    bodyPostMask.value = bodyPostStatus
    spinePreMask.value = spinePreStatus
    spinePostMask.value = spinePostStatus
  } catch (error) {
    console.error('Load patient detail failed:', error)
    message.error(t('views_PatientDetailView.loadFailed'))
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/patients')
}

function triggerCtUpload(phase: CtPhase) {
  selectedUploadPhase.value = phase
  if (ctInputRef.value) {
    ctInputRef.value.value = ''
    ctInputRef.value.click()
  }
}

async function handleCtFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  const phase = selectedUploadPhase.value
  if (!file || !phase) return

  uploadingPhase.value = phase
  try {
    const status = await uploadPatientCt(patientId.value, phase, file)
    if (phase === 'pre') preCt.value = status
    else postCt.value = status
    message.success(t('views_PatientDetailView.ct.uploaded'))
  } catch (error: any) {
    console.error('Upload CT failed:', error)
    message.error(error?.message || t('views_PatientDetailView.ct.uploadFailed'))
  } finally {
    uploadingPhase.value = null
    selectedUploadPhase.value = null
    input.value = ''
  }
}

async function handleDeleteCt(phase: CtPhase) {
  deletingPhase.value = phase
  try {
    const status = await deletePatientCt(patientId.value, phase)
    if (phase === 'pre') preCt.value = status
    else postCt.value = status
    message.success(t('views_PatientDetailView.ct.deleted'))
  } catch (error: any) {
    console.error('Delete CT failed:', error)
    message.error(error?.message || t('views_PatientDetailView.ct.deleteFailed'))
  } finally {
    deletingPhase.value = null
  }
}

function maskKey(maskType: MaskType, phase: CtPhase) {
  return `${maskType}:${phase}`
}

function setMaskStatus(status: PatientMaskStatus) {
  if (status.mask_type === 'body-composition' && status.phase === 'pre') bodyPreMask.value = status
  else if (status.mask_type === 'body-composition' && status.phase === 'post') bodyPostMask.value = status
  else if (status.mask_type === 'spine' && status.phase === 'pre') spinePreMask.value = status
  else spinePostMask.value = status
}

function triggerMaskUpload(maskType: MaskType, phase: CtPhase) {
  selectedMaskTarget.value = { maskType, phase }
  if (maskInputRef.value) {
    maskInputRef.value.value = ''
    maskInputRef.value.click()
  }
}

async function handleMaskFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  const target = selectedMaskTarget.value
  if (!file || !target) return

  uploadingMaskKey.value = maskKey(target.maskType, target.phase)
  try {
    const status = await uploadPatientMask(patientId.value, target.maskType, target.phase, file)
    setMaskStatus(status)
    message.success(t('views_PatientDetailView.mask.uploaded'))
  } catch (error: any) {
    console.error('Upload mask failed:', error)
    message.error(error?.message || t('views_PatientDetailView.mask.uploadFailed'))
  } finally {
    uploadingMaskKey.value = null
    selectedMaskTarget.value = null
    input.value = ''
  }
}

async function handleDeleteMask(maskType: MaskType, phase: CtPhase) {
  deletingMaskKey.value = maskKey(maskType, phase)
  try {
    const status = await deletePatientMask(patientId.value, maskType, phase)
    setMaskStatus(status)
    message.success(t('views_PatientDetailView.mask.deleted'))
  } catch (error: any) {
    console.error('Delete mask failed:', error)
    message.error(error?.message || t('views_PatientDetailView.mask.deleteFailed'))
  } finally {
    deletingMaskKey.value = null
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

.section-grid.three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
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
  min-height: 340px;
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
  min-height: 340px;
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

.feature-window :deep(svg) {
  font-size: 30px;
  color: #0f766e;
}

.mask-slot-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
  min-height: 340px;
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

.ct-preview-image {
  width: 100%;
  height: 340px;
  display: block;
  object-fit: contain;
  background: #0b0f19;
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

.hidden-file-input {
  display: none;
}

.scan-placeholder :deep(svg) {
  font-size: 28px;
  color: #0f766e;
}

.module-panel {
  min-height: 210px;
}

.module-icon {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
  border-radius: 8px;
  background: #e8f3f1;
  color: #0f766e;
  font-size: 20px;
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
  .section-grid.three,
  .mask-slot-grid {
    grid-template-columns: 1fr;
  }

  .baseline-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
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

  .baseline-grid {
    grid-template-columns: 1fr;
  }
}
</style>
