export type FileStatus = 'pending' | 'uploading' | 'uploaded' | 'processing' | 'completed' | 'error'

export interface FileUploadStatus {
  file: File
  status: FileStatus
  uploadId?: number
  documentId?: number
  taskId?: number
  tempPath?: string
  error?: string
}

export interface KnowledgeBase {
  id: number
  name: string
  description?: string
  documents: Document[]
  created_at: string
  updated_at: string
  document_count?: number
  chunk_count?: number
}

export interface Document {
  id: number
  file_name: string
  file_path: string
  file_size: number
  content_type: string
  knowledge_base_id: number
  created_at: string
  updated_at: string
  processing_tasks: ProcessingTask[]
}

export interface ProcessingTask {
  id: number
  status: string
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface UploadResult {
  upload_id?: number
  document_id?: number
  file_name: string
  status: 'exists' | 'pending'
  message?: string
  skip_processing: boolean
  temp_path?: string
}

export interface PreviewChunk {
  content: string
  metadata: Record<string, any>
}

export interface PreviewResponse {
  chunks: PreviewChunk[]
  total_chunks: number
}

export interface TaskResponse {
  tasks: Array<{
    upload_id: number
    task_id: number
  }>
}

export interface TaskStatus {
  document_id: number | null
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message?: string
  upload_id: number
  file_name?: string
}
