import { del, get, post, put } from '@/utils/request'

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
