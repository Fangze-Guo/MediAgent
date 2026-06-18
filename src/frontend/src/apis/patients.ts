import { api, del, get, post, put } from '@/utils/request'

export interface BaseResponse<T = any> {
  code: number
  data: T
  message: string
}

export interface PatientInfo {
  id: number
  patient_id: string
  name: string
  sex?: string | null
  age?: number | null
  phone?: string | null
  height_cm?: number | null
  smoking_status?: string | null
  pathology_type?: string | null
  pd_l1_status?: string | null
  created_at: string
  updated_at: string
}

export interface PatientPayload {
  patient_id?: string
  name: string
  sex?: string | null
  age?: number | null
  phone?: string | null
  height_cm?: number | null
  smoking_status?: string | null
  pathology_type?: string | null
  pd_l1_status?: string | null
}

export interface PatientListResult {
  items: PatientInfo[]
  total: number
  page: number
  size: number
}

export type CtPhase = 'pre' | 'post'
export type MaskType = 'body-composition' | 'spine' | 'lung' | 'tumor'
export type LungPredictionResultType = 'tumor-radiomics-mpr' | 'mpr-dfs'

export interface PatientCtStatus {
  phase: CtPhase
  status: 'empty' | 'ready'
  file_name?: string | null
  file_size?: number | null
  uploaded_at?: string | null
  preview_updated_at?: string | null
  preview_url?: string | null
  preview_planes?: PreviewPlanes | null
  display_window?: DisplayWindow | null
}

export interface PatientMaskStatus {
  mask_type: MaskType
  phase: CtPhase
  status: 'empty' | 'ready'
  file_name?: string | null
  file_size?: number | null
  uploaded_at?: string | null
  preview_url?: string | null
  preview_planes?: PreviewPlanes | null
}

export type PreviewPlane = 'axial' | 'coronal' | 'sagittal'
export type PreviewPlanes = Partial<Record<PreviewPlane, string>>
export interface DisplayWindow {
  min: number
  max: number
}

export interface PatientOutputFile {
  path: string
  name: string
  size: number
  modified_at: string
  media_type: string
  download_url: string
}

export interface PatientOutputsResult {
  patient_id: string
  output_root: string
  files: PatientOutputFile[]
}

export interface PatientResultFile {
  path: string
  relative_path: string
  name: string
  size: number
  modified_at: string
  media_type: string
  download_url: string
  source: 'standard' | 'agent_output' | string
}

export interface BodyCompositionMetricsSummary {
  file_name?: string | null
  muscle_cm3?: number | null
  vat_cm3?: number | null
  sat_cm3?: number | null
  smvi?: number | null
  vavi?: number | null
  savi?: number | null
  thoracic_start?: string | null
  thoracic_end?: string | null
}

export interface BodyCompositionTypeSummary {
  status?: string | null
  message?: string | null
  metric_results?: Record<string, {
    status?: string
    type_label?: string | null
    type_code?: string | null
    baseline_group?: string | null
    change_rate?: number | null
    change_bucket?: string | null
  }>
}

export interface TumorRadiomicsMprSummary {
  status?: string | null
  mode?: string | null
  requested_mode?: string | null
  probability?: number | null
  selected_model?: string | null
  pre_available?: boolean | null
  post_available?: boolean | null
  fusion_eligible?: boolean | null
  result_level?: string | null
  result_level_label?: string | null
  usable_for_main_mpr?: boolean | null
  can_export_tumor_radiomics_score?: boolean | null
  downgraded?: boolean | null
  missing_input_labels?: string[]
  message?: string | null
}

export interface MprDfsPredictionSummary {
  status?: string | null
  probability?: number | null
  selected_model?: string | null
  selected_feature_groups?: string | null
  prediction_scope?: string | null
  prediction_scope_label?: string | null
  dfs_available?: boolean | null
  dfs_risk_score?: number | null
  dfs_risk_group?: string | null
  dfs_cutpoint?: number | null
  tumor_radiomics_score?: number | null
  downgraded?: boolean | null
  downgrade_reason?: string | null
  unavailable_features?: string[]
  next_required_field_labels?: string[]
  used_information_category_labels?: string[]
  can_start_prediction?: boolean | null
  can_be_more_complete?: boolean | null
  message?: string | null
}

export interface BodyCompositionResults {
  patient_id: string
  standard_roots: {
    metrics: string
    type_classification: string
  }
  metrics: Record<CtPhase, {
    csv?: PatientResultFile | null
    xlsx?: PatientResultFile | null
    summary?: BodyCompositionMetricsSummary | null
  }>
  type_classification: {
    json?: PatientResultFile | null
    summary?: BodyCompositionTypeSummary | null
  }
  lung_predictions?: {
    tumor_radiomics_mpr: {
      json?: PatientResultFile | null
      summary?: TumorRadiomicsMprSummary | null
      default_path_rule?: string | null
    }
    mpr_dfs: {
      json?: PatientResultFile | null
      summary?: MprDfsPredictionSummary | null
      default_path_rule?: string | null
    }
  }
}

export async function listPatients(params: {
  keyword?: string
  page?: number
  size?: number
}): Promise<PatientListResult> {
  const query = new URLSearchParams()
  if (params.keyword) query.set('keyword', params.keyword)
  if (params.page) query.set('page', String(params.page))
  if (params.size) query.set('size', String(params.size))
  const response = await get<BaseResponse<PatientListResult>>(`/patients?${query.toString()}`)
  return response.data.data
}

export async function createPatient(payload: PatientPayload): Promise<PatientInfo> {
  const response = await post<BaseResponse<PatientInfo>>('/patients', payload)
  return response.data.data
}

export async function getPatient(patientId: string): Promise<PatientInfo> {
  const response = await get<BaseResponse<PatientInfo>>(`/patients/${encodeURIComponent(patientId)}`)
  return response.data.data
}

export async function updatePatient(patientId: string, payload: PatientPayload): Promise<PatientInfo> {
  const response = await put<BaseResponse<PatientInfo>>(`/patients/${encodeURIComponent(patientId)}`, payload)
  return response.data.data
}

export async function deletePatient(patientId: string): Promise<{ patient_id: string; directory_deleted: boolean }> {
  const response = await del<BaseResponse<{ patient_id: string; directory_deleted: boolean }>>(
    `/patients/${encodeURIComponent(patientId)}`
  )
  return response.data.data
}

export async function getPatientCtStatus(patientId: string, phase: CtPhase): Promise<PatientCtStatus> {
  const response = await get<BaseResponse<PatientCtStatus>>(
    `/patients/${encodeURIComponent(patientId)}/ct/${phase}`
  )
  return response.data.data
}

export async function uploadPatientCt(patientId: string, phase: CtPhase, file: File): Promise<PatientCtStatus> {
  const formData = new FormData()
  formData.append('ct_file', file)
  const response = await post<BaseResponse<PatientCtStatus>>(
    `/patients/${encodeURIComponent(patientId)}/ct/${phase}`,
    formData
  )
  return response.data.data
}

export async function importPatientCtFromOutput(patientId: string, phase: CtPhase, sourcePath: string): Promise<PatientCtStatus> {
  const response = await post<BaseResponse<PatientCtStatus>>(
    `/patients/${encodeURIComponent(patientId)}/ct/${phase}/import-output`,
    { source_path: sourcePath }
  )
  return response.data.data
}

export async function deletePatientCt(patientId: string, phase: CtPhase): Promise<PatientCtStatus> {
  const response = await del<BaseResponse<PatientCtStatus>>(
    `/patients/${encodeURIComponent(patientId)}/ct/${phase}`
  )
  return response.data.data
}

export async function getPatientMaskStatus(patientId: string, maskType: MaskType, phase: CtPhase): Promise<PatientMaskStatus> {
  const response = await get<BaseResponse<PatientMaskStatus>>(
    `/patients/${encodeURIComponent(patientId)}/mask/${maskType}/${phase}`
  )
  return response.data.data
}

export async function uploadPatientMask(patientId: string, maskType: MaskType, phase: CtPhase, file: File): Promise<PatientMaskStatus> {
  const formData = new FormData()
  formData.append('mask_file', file)
  const response = await post<BaseResponse<PatientMaskStatus>>(
    `/patients/${encodeURIComponent(patientId)}/mask/${maskType}/${phase}`,
    formData
  )
  return response.data.data
}

export async function importPatientMaskFromOutput(
  patientId: string,
  maskType: MaskType,
  phase: CtPhase,
  sourcePath: string
): Promise<PatientMaskStatus> {
  const response = await post<BaseResponse<PatientMaskStatus>>(
    `/patients/${encodeURIComponent(patientId)}/mask/${maskType}/${phase}/import-output`,
    { source_path: sourcePath }
  )
  return response.data.data
}

export async function deletePatientMask(patientId: string, maskType: MaskType, phase: CtPhase): Promise<PatientMaskStatus> {
  const response = await del<BaseResponse<PatientMaskStatus>>(
    `/patients/${encodeURIComponent(patientId)}/mask/${maskType}/${phase}`
  )
  return response.data.data
}

export async function downloadPatientReport(patientId: string): Promise<Blob> {
  const response = await api.get(`/patients/${encodeURIComponent(patientId)}/report`, {
    responseType: 'blob',
  })
  return response.data
}

export async function getPatientOutputs(patientId: string): Promise<PatientOutputsResult> {
  const response = await get<BaseResponse<PatientOutputsResult>>(
    `/patients/${encodeURIComponent(patientId)}/outputs`
  )
  return response.data.data
}

export async function downloadPatientOutput(patientId: string, filePath: string): Promise<Blob> {
  const encodedPath = filePath.split('/').map(encodeURIComponent).join('/')
  const response = await api.get(
    `/patients/${encodeURIComponent(patientId)}/outputs/serve/${encodedPath}`,
    { responseType: 'blob' }
  )
  return response.data
}

export async function deletePatientOutputDirectory(
  patientId: string,
  dirPath: string
): Promise<{ patient_id: string; deleted_path: string }> {
  const encodedPath = dirPath.split('/').map(encodeURIComponent).join('/')
  const response = await del<BaseResponse<{ patient_id: string; deleted_path: string }>>(
    `/patients/${encodeURIComponent(patientId)}/outputs/directories/${encodedPath}`
  )
  return response.data.data
}

export async function getBodyCompositionResults(patientId: string): Promise<BodyCompositionResults> {
  const response = await get<BaseResponse<BodyCompositionResults>>(
    `/patients/${encodeURIComponent(patientId)}/body-composition-results`
  )
  return response.data.data
}

export async function uploadBodyCompositionMetricFile(patientId: string, phase: CtPhase, file: File): Promise<BodyCompositionResults> {
  const formData = new FormData()
  formData.append('result_file', file)
  const response = await post<BaseResponse<BodyCompositionResults>>(
    `/patients/${encodeURIComponent(patientId)}/body-composition-results/metrics/${phase}`,
    formData
  )
  return response.data.data
}

export async function uploadBodyCompositionTypeFile(patientId: string, file: File): Promise<BodyCompositionResults> {
  const formData = new FormData()
  formData.append('result_file', file)
  const response = await post<BaseResponse<BodyCompositionResults>>(
    `/patients/${encodeURIComponent(patientId)}/body-composition-results/type`,
    formData
  )
  return response.data.data
}

export async function uploadLungPredictionResultFile(
  patientId: string,
  resultType: LungPredictionResultType,
  file: File
): Promise<BodyCompositionResults> {
  const formData = new FormData()
  formData.append('result_file', file)
  const response = await post<BaseResponse<BodyCompositionResults>>(
    `/patients/${encodeURIComponent(patientId)}/lung-prediction-results/${resultType}`,
    formData
  )
  return response.data.data
}

export async function downloadBodyCompositionResultFile(file: PatientResultFile): Promise<Blob> {
  const response = await api.get(file.download_url, { responseType: 'blob' })
  return response.data
}
