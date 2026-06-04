<template>
  <div class="patient-page">
    <div class="patient-shell">
      <div class="page-header">
        <div>
          <div class="eyebrow">{{ t('views_PatientManageView.eyebrow') }}</div>
          <h1>{{ t('views_PatientManageView.title') }}</h1>
          <p>{{ t('views_PatientManageView.subtitle') }}</p>
        </div>
        <a-button type="primary" size="large" @click="openCreateModal">
          <template #icon><PlusOutlined /></template>
          {{ t('views_PatientManageView.createPatient') }}
        </a-button>
      </div>

      <div class="table-panel">
        <div class="toolbar">
          <a-input-search
            v-model:value="keyword"
            :placeholder="t('views_PatientManageView.searchPlaceholder')"
            allow-clear
            class="search"
            @search="handleSearch"
            @change="handleSearchInputChange"
          />
          <a-button @click="fetchPatients">
            <template #icon><ReloadOutlined /></template>
            {{ t('common.refresh') }}
          </a-button>
        </div>

        <a-table
          :columns="columns"
          :data-source="patients"
          :loading="loading"
          :row-key="getRowKey"
          :pagination="pagination"
          :scroll="{ x: 1180 }"
          size="middle"
          class="patient-table"
          @change="handleTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'identity'">
              <div class="patient-identity">
                <span class="patient-avatar">{{ initials(record.name) }}</span>
                <span class="patient-main">
                  <span class="patient-name">{{ record.name }}</span>
                  <span class="patient-id">{{ record.patient_id }}</span>
                </span>
              </div>
            </template>
            <template v-else-if="column.key === 'sex'">
              <a-tag v-if="record.sex" :color="sexColor(record.sex)">{{ formatOption('sex', record.sex) }}</a-tag>
              <span v-else class="muted">-</span>
            </template>
            <template v-else-if="column.key === 'age'">
              <span>{{ record.age ?? '-' }}</span>
            </template>
            <template v-else-if="column.key === 'phone'">
              <span :class="{ muted: !record.phone }">{{ record.phone || '-' }}</span>
            </template>
            <template v-else-if="column.key === 'height_cm'">
              <span>{{ record.height_cm == null ? '-' : `${record.height_cm} cm` }}</span>
            </template>
            <template v-else-if="column.key === 'smoking_status'">
              <span :class="{ muted: !record.smoking_status }">{{ formatOption('smoking', record.smoking_status) }}</span>
            </template>
            <template v-else-if="column.key === 'pathology_type'">
              <span class="truncate-cell" :title="formatOption('pathology', record.pathology_type)">
                {{ formatOption('pathology', record.pathology_type) }}
              </span>
            </template>
            <template v-else-if="column.key === 'pd_l1_status'">
              <a-tag v-if="record.pd_l1_status" color="gold">{{ formatOption('pdL1', record.pd_l1_status) }}</a-tag>
              <span v-else class="muted">-</span>
            </template>
            <template v-else-if="column.key === 'updated_at'">
              <span class="date-text">{{ formatDateTime(record.updated_at) }}</span>
            </template>
            <template v-else-if="column.key === 'actions'">
              <div class="actions">
                <a-button type="text" size="small" :title="t('common.edit')" @click="openEditModal(record)">
                  <template #icon><EditOutlined /></template>
                </a-button>
                <a-popconfirm
                  :title="t('views_PatientManageView.deleteConfirm')"
                  :ok-text="t('common.delete')"
                  :cancel-text="t('common.cancel')"
                  ok-type="danger"
                  @confirm="handleDelete(record.patient_id)"
                >
                  <a-button type="text" size="small" danger :title="t('common.delete')">
                    <template #icon><DeleteOutlined /></template>
                  </a-button>
                </a-popconfirm>
              </div>
            </template>
          </template>
        </a-table>
      </div>
    </div>

    <a-modal
      v-model:open="modalOpen"
      :title="editingPatient ? t('views_PatientManageView.editPatient') : t('views_PatientManageView.createPatient')"
      :confirm-loading="saving"
      :ok-text="editingPatient ? t('views_PatientManageView.save') : t('views_PatientManageView.create')"
      :cancel-text="t('common.cancel')"
      :width="720"
      @ok="handleSubmit"
      @cancel="closeModal"
    >
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical" class="patient-form">
        <div class="form-section-title">{{ t('views_PatientManageView.identityInfo') }}</div>
        <div class="form-grid">
          <a-form-item :label="t('views_PatientManageView.fields.patientId')" name="patient_id">
            <a-input
              v-model:value="form.patient_id"
              :disabled="Boolean(editingPatient)"
              :placeholder="t('views_PatientManageView.placeholders.patientId')"
            />
          </a-form-item>
          <a-form-item :label="t('views_PatientManageView.fields.name')" name="name">
            <a-input v-model:value="form.name" :placeholder="t('views_PatientManageView.placeholders.name')" />
          </a-form-item>
          <a-form-item :label="t('views_PatientManageView.fields.sex')" name="sex">
            <a-select v-model:value="form.sex" allow-clear :placeholder="t('views_PatientManageView.placeholders.sex')">
              <a-select-option v-for="option in sexOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item :label="t('views_PatientManageView.fields.age')" name="age">
            <a-input-number v-model:value="form.age" :min="0" :max="130" class="full-input" />
          </a-form-item>
          <a-form-item :label="t('views_PatientManageView.fields.phone')" name="phone">
            <a-input v-model:value="form.phone" placeholder="+8612345678901" />
          </a-form-item>
          <a-form-item :label="t('views_PatientManageView.fields.height')" name="height_cm">
            <a-input-number v-model:value="form.height_cm" :min="0" :max="300" class="full-input" />
          </a-form-item>
        </div>

        <div class="form-section-title">{{ t('views_PatientManageView.clinicalInfo') }}</div>
        <div class="form-grid">
          <a-form-item :label="t('views_PatientManageView.fields.smoking')" name="smoking_status">
            <a-select v-model:value="form.smoking_status" allow-clear :placeholder="t('views_PatientManageView.placeholders.smoking')">
              <a-select-option v-for="option in smokingOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item :label="t('views_PatientManageView.fields.pathology')" name="pathology_type">
            <a-select v-model:value="form.pathology_type" allow-clear :placeholder="t('views_PatientManageView.placeholders.pathology')">
              <a-select-option v-for="option in pathologyOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item :label="t('views_PatientManageView.fields.pdL1')" name="pd_l1_status" class="wide">
            <a-select v-model:value="form.pd_l1_status" allow-clear :placeholder="t('views_PatientManageView.placeholders.pdL1')">
              <a-select-option v-for="option in pdL1Options" :key="option.value" :value="option.value">
                {{ option.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </div>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TablePaginationConfig } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import {
  createPatient,
  deletePatient,
  listPatients,
  updatePatient,
  type PatientInfo,
  type PatientPayload,
} from '@/apis/patients'

type PatientForm = PatientPayload & { patient_id?: string }
type OptionGroup = 'sex' | 'smoking' | 'pathology' | 'pdL1'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const patients = ref<PatientInfo[]>([])
const editingPatient = ref<PatientInfo | null>(null)
const keyword = ref('')
const page = ref(1)
const size = ref(20)
const total = ref(0)
const formRef = ref()
const form = reactive<PatientForm>({
  patient_id: '',
  name: '',
  sex: undefined,
  age: undefined,
  phone: '',
  height_cm: undefined,
  smoking_status: '',
  pathology_type: '',
  pd_l1_status: '',
})

const columns = computed(() => [
  { title: t('views_PatientManageView.columns.patient'), key: 'identity', width: 190 },
  { title: t('views_PatientManageView.columns.sex'), dataIndex: 'sex', key: 'sex', width: 90 },
  { title: t('views_PatientManageView.columns.age'), dataIndex: 'age', key: 'age', width: 80 },
  { title: t('views_PatientManageView.columns.phone'), dataIndex: 'phone', key: 'phone', width: 160 },
  { title: t('views_PatientManageView.columns.height'), key: 'height_cm', width: 100 },
  { title: t('views_PatientManageView.columns.smoking'), dataIndex: 'smoking_status', key: 'smoking_status', width: 130 },
  { title: t('views_PatientManageView.columns.pathology'), dataIndex: 'pathology_type', key: 'pathology_type', width: 170 },
  { title: t('views_PatientManageView.columns.pdL1'), dataIndex: 'pd_l1_status', key: 'pd_l1_status', width: 150 },
  { title: t('views_PatientManageView.columns.updatedAt'), key: 'updated_at', width: 170 },
  { title: t('views_PatientManageView.columns.actions'), key: 'actions', width: 100, fixed: 'right' as const },
])

const sexOptions = computed(() => [
  { value: 'Male', label: t('views_PatientManageView.options.sex.male') },
  { value: 'Female', label: t('views_PatientManageView.options.sex.female') },
  { value: 'Other', label: t('views_PatientManageView.options.sex.other') },
])

const smokingOptions = computed(() => [
  { value: 'Never', label: t('views_PatientManageView.options.smoking.never') },
  { value: 'Former', label: t('views_PatientManageView.options.smoking.former') },
  { value: 'Current', label: t('views_PatientManageView.options.smoking.current') },
  { value: 'Unknown', label: t('views_PatientManageView.options.smoking.unknown') },
])

const pathologyOptions = computed(() => [
  { value: 'Adenocarcinoma', label: t('views_PatientManageView.options.pathology.adenocarcinoma') },
  { value: 'Squamous cell carcinoma', label: t('views_PatientManageView.options.pathology.squamous') },
  { value: 'Large cell carcinoma', label: t('views_PatientManageView.options.pathology.largeCell') },
  { value: 'Small cell lung cancer', label: t('views_PatientManageView.options.pathology.smallCell') },
  { value: 'Other', label: t('views_PatientManageView.options.pathology.other') },
  { value: 'Unknown', label: t('views_PatientManageView.options.pathology.unknown') },
])

const pdL1Options = computed(() => [
  { value: 'High expression', label: t('views_PatientManageView.options.pdL1.high') },
  { value: 'Low expression', label: t('views_PatientManageView.options.pdL1.low') },
  { value: 'Negative', label: t('views_PatientManageView.options.pdL1.negative') },
  { value: 'Positive', label: t('views_PatientManageView.options.pdL1.positive') },
  { value: 'Unknown', label: t('views_PatientManageView.options.pdL1.unknown') },
])

const rules = {
  patient_id: [
    { required: true, message: t('views_PatientManageView.validation.patientIdRequired'), trigger: 'blur' },
    {
      pattern: /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/,
      message: t('views_PatientManageView.validation.patientIdPattern'),
      trigger: 'blur',
    },
  ],
  name: [{ required: true, message: t('views_PatientManageView.validation.nameRequired'), trigger: 'blur' }],
}

const getRowKey = (record: PatientInfo) => record.patient_id

const pagination = computed<TablePaginationConfig>(() => ({
  current: page.value,
  pageSize: size.value,
  total: total.value,
  showSizeChanger: true,
  showTotal: count => t('views_PatientManageView.totalPatients', { count }),
}))

onMounted(() => {
  fetchPatients()
})

async function fetchPatients() {
  loading.value = true
  try {
    const result = await listPatients({
      keyword: keyword.value.trim() || undefined,
      page: page.value,
      size: size.value,
    })
    patients.value = result.items
    total.value = result.total
  } catch (error) {
    console.error('Load patients failed:', error)
    message.error(t('views_PatientManageView.messages.loadFailed'))
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.patient_id = ''
  form.name = ''
  form.sex = undefined
  form.age = undefined
  form.phone = ''
  form.height_cm = undefined
  form.smoking_status = ''
  form.pathology_type = ''
  form.pd_l1_status = ''
  formRef.value?.clearValidate?.()
}

function openCreateModal() {
  editingPatient.value = null
  resetForm()
  modalOpen.value = true
}

function openEditModal(patient: PatientInfo) {
  editingPatient.value = patient
  form.patient_id = patient.patient_id
  form.name = patient.name
  form.sex = patient.sex ?? undefined
  form.age = patient.age ?? undefined
  form.phone = patient.phone ?? ''
  form.height_cm = patient.height_cm ?? undefined
  form.smoking_status = patient.smoking_status ?? ''
  form.pathology_type = patient.pathology_type ?? ''
  form.pd_l1_status = patient.pd_l1_status ?? ''
  formRef.value?.clearValidate?.()
  modalOpen.value = true
}

function closeModal() {
  modalOpen.value = false
}

function normalizedPayload(): PatientPayload {
  return {
    patient_id: form.patient_id?.trim(),
    name: form.name.trim(),
    sex: form.sex || null,
    age: form.age ?? null,
    phone: form.phone?.trim() || null,
    height_cm: form.height_cm ?? null,
    smoking_status: form.smoking_status?.trim() || null,
    pathology_type: form.pathology_type?.trim() || null,
    pd_l1_status: form.pd_l1_status?.trim() || null,
  }
}

async function handleSubmit() {
  await formRef.value?.validate()
  saving.value = true
  try {
    const payload = normalizedPayload()
    if (editingPatient.value) {
      await updatePatient(editingPatient.value.patient_id, payload)
      message.success(t('views_PatientManageView.messages.updated'))
    } else {
      await createPatient(payload)
      message.success(t('views_PatientManageView.messages.created'))
    }
    modalOpen.value = false
    await fetchPatients()
  } catch (error: any) {
    console.error('Save patient failed:', error)
    message.error(error?.message || t('views_PatientManageView.messages.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function handleDelete(patientId: string) {
  loading.value = true
  try {
    await deletePatient(patientId)
    message.success(t('views_PatientManageView.messages.deleted'))
    if (patients.value.length === 1 && page.value > 1) page.value -= 1
    await fetchPatients()
  } catch (error: any) {
    console.error('Delete patient failed:', error)
    message.error(error?.message || t('views_PatientManageView.messages.deleteFailed'))
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchPatients()
}

function handleSearchInputChange() {
  if (!keyword.value) handleSearch()
}

function handleTableChange(nextPagination: TablePaginationConfig) {
  page.value = nextPagination.current || 1
  size.value = nextPagination.pageSize || 20
  fetchPatients()
}

function formatDateTime(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function initials(name: string) {
  const clean = (name || '').trim()
  if (!clean) return 'P'
  const parts = clean.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return clean.slice(0, 2).toUpperCase()
}

function sexColor(sex?: string | null) {
  if (sex === 'Male') return 'blue'
  if (sex === 'Female') return 'magenta'
  return 'default'
}

function optionList(group: OptionGroup) {
  if (group === 'sex') return sexOptions.value
  if (group === 'smoking') return smokingOptions.value
  if (group === 'pathology') return pathologyOptions.value
  return pdL1Options.value
}

function formatOption(group: OptionGroup, value?: string | null) {
  if (!value) return '-'
  return optionList(group).find(option => option.value === value)?.label || value
}
</script>

<style scoped>
.patient-page {
  min-height: 100%;
  padding: 28px;
  background:
    linear-gradient(180deg, #f5f7fb 0%, #eef3f8 100%);
}

.patient-shell {
  max-width: 1480px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 24px 26px;
  background: #ffffff;
  border: 1px solid #e4e9f1;
  border-radius: 8px;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.07);
}

.eyebrow {
  margin-bottom: 8px;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}

.page-header h1 {
  margin: 0;
  color: #111827;
  font-size: 26px;
  line-height: 1.2;
  font-weight: 700;
}

.page-header p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 14px;
  line-height: 1.6;
}

.table-panel {
  padding: 16px;
  background: #ffffff;
  border: 1px solid #e4e9f1;
  border-radius: 8px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.search {
  width: min(420px, 100%);
}

.patient-table {
  background: #fff;
}

.patient-table :deep(.ant-table) {
  color: #1f2937;
}

.patient-table :deep(.ant-table-container) {
  border: 1px solid #edf0f5;
  border-radius: 8px;
}

.patient-table :deep(.ant-table-thead > tr > th) {
  background: #f7f9fc;
  color: #475467;
  font-size: 12px;
  font-weight: 700;
}

.patient-table :deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #edf0f5;
}

.patient-table :deep(.ant-table-tbody > tr:hover > td) {
  background: #f8fbff;
}

.patient-identity {
  display: flex;
  align-items: center;
  gap: 10px;
}

.patient-avatar {
  display: inline-flex;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 8px;
  background: #e8f3f1;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.patient-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.patient-name {
  color: #111827;
  font-weight: 600;
  line-height: 1.35;
}

.patient-id {
  color: #667085;
  font-size: 12px;
}

.muted {
  color: #98a2b3;
}

.date-text {
  color: #667085;
  font-size: 12px;
}

.truncate-cell {
  display: inline-block;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
  white-space: nowrap;
}

.actions {
  display: flex;
  gap: 4px;
}

.patient-form {
  margin-top: 8px;
}

.form-section-title {
  margin: 4px 0 14px;
  padding-left: 10px;
  border-left: 3px solid #0f766e;
  color: #111827;
  font-size: 14px;
  font-weight: 700;
}

.form-section-title + .form-grid {
  margin-bottom: 8px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
}

.wide {
  grid-column: span 2;
}

.full-input {
  width: 100%;
}

@media (max-width: 760px) {
  .patient-page {
    padding: 18px;
  }

  .page-header {
    flex-direction: column;
    align-items: stretch;
    padding: 20px;
  }

  .toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .search {
    width: 100%;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .wide {
    grid-column: span 1;
  }
}
</style>
