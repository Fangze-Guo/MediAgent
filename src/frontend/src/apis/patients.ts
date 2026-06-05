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

export interface PatientCtStatus {
  phase: CtPhase
  status: 'empty' | 'ready'
  file_name?: string | null
  file_size?: number | null
  uploaded_at?: string | null
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
