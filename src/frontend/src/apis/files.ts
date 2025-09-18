/**
 * 文件上传相关API接口
 * 提供文件上传、管理和工具调用功能
 */
import { get, post } from '@/utils/request'

/**
 * 文件上传响应接口
 */
export interface FileUploadResponse {
    /** 上传是否成功 */
    success: boolean
    /** 文件信息 */
    file: {
        /** 文件ID */
        id: string
        /** 原始文件名 */
        originalName: string
        /** 文件大小（字节） */
        size: number
        /** 文件类型 */
        type: string
        /** 文件路径 */
        path: string
        /** 上传时间 */
        uploadTime: string
    }
    /** 错误信息（如果上传失败） */
    error?: string
}

/**
 * 文件列表响应接口
 */
export interface FileListResponse {
    /** 文件列表 */
    files: Array<{
        id: string
        name: string
        size: number
        type: string
        path: string
        modifiedTime: string
        isDirectory: boolean
    }>
    /** 当前路径 */
    currentPath?: string
    /** 父路径 */
    parentPath?: string | null
}

/**
 * 上传文件到服务器
 * @param file 要上传的文件
 * @param onProgress 上传进度回调函数
 * @returns Promise<FileUploadResponse> 返回上传结果
 * @throws {Error} 当上传失败时抛出错误
 *
 * @example
 * ```typescript
 * const file = document.getElementById('fileInput').files[0]
 * const result = await uploadFile(file, (progress) => {
 *   console.log(`上传进度: ${progress}%`)
 * })
 * console.log('文件上传成功:', result.file)
 * ```
 */
export async function uploadFile(
    file: File,
    onProgress?: (progress: number) => void
): Promise<FileUploadResponse> {
    try {
        const formData = new FormData()
        formData.append('file', file)

        // 使用XMLHttpRequest来支持上传进度
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest()

            // 监听上传进度
            xhr.upload.addEventListener('progress', (event) => {
                if (event.lengthComputable && onProgress) {
                    const progress = Math.round((event.loaded / event.total) * 100)
                    onProgress(progress)
                }
            })

            // 监听请求完成
            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText) as FileUploadResponse
                        resolve(response)
                    } catch (error) {
                        reject(new Error('解析响应失败'))
                    }
                } else {
                    reject(new Error(`上传失败: ${xhr.status}`))
                }
            })

            // 监听请求错误
            xhr.addEventListener('error', () => {
                reject(new Error('网络错误'))
            })

            // 监听请求超时
            xhr.addEventListener('timeout', () => {
                reject(new Error('上传超时'))
            })

            // 获取API基础URL
            const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'

            // 发送请求
            xhr.open('POST', `${baseURL}/files/upload`)
            xhr.timeout = 60000 // 60秒超时
            xhr.send(formData)
        })
    } catch (error) {
        console.error('文件上传失败:', error)
        throw new Error('文件上传失败，请稍后再试')
    }
}

/**
 * 获取已上传的文件列表
 * @returns Promise<FileListResponse> 返回文件列表
 * @throws {Error} 当请求失败时抛出错误
 *
 * @example
 * ```typescript
 * const files = await getFileList()
 * console.log('已上传文件:', files.files)
 * ```
 */
export async function getFileList(path: string = '.'): Promise<FileListResponse> {
    try {
        const response = await get<FileListResponse>(`/files?path=${encodeURIComponent(path)}`)
        return response.data
    } catch (error) {
        console.error('获取文件列表失败:', error)
        throw new Error('获取文件列表失败，请稍后再试')
    }
}

/**
 * 格式化文件大小
 * @param bytes 文件大小（字节）
 * @returns 格式化后的文件大小字符串
 */
export function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B'

    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * 检查文件类型是否支持
 * @param file 文件对象
 * @returns 是否支持该文件类型
 */
export function isSupportedFileType(file: File): boolean {
    const supportedTypes = [
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/gif',
        'image/webp',
        'text/csv',
        'application/csv',
        'application/dicom'
    ]

    return supportedTypes.includes(file.type) ||
        file.name.toLowerCase().endsWith('.csv') ||
        file.name.toLowerCase().endsWith('.dcm') ||
        !!file.name.toLowerCase().match(/\.(jpg|jpeg|png|gif|webp|dcm)$/i)
}

/**
 * 删除文件响应接口
 */
export interface DeleteFileResponse {
    /** 删除是否成功 */
    success: boolean
    /** 错误信息（如果删除失败） */
    error?: string
}

/**
 * 批量删除文件响应接口
 */
export interface BatchDeleteFilesResponse {
    /** 删除是否成功 */
    success: boolean
    /** 成功删除的文件数量 */
    deletedCount: number
    /** 错误信息（如果删除失败） */
    error?: string
}

/**
 * 下载文件响应接口
 */
export interface DownloadFileResponse {
    /** 下载是否成功 */
    success: boolean
    /** 文件下载URL */
    downloadUrl?: string
    /** 错误信息（如果下载失败） */
    error?: string
}

/**
 * 删除单个文件
 * @param fileId 文件ID
 * @returns Promise<DeleteFileResponse> 返回删除结果
 * @throws {Error} 当请求失败时抛出错误
 *
 * @example
 * ```typescript
 * const result = await deleteFile('file-id-123')
 * if (result.success) {
 *   console.log('文件删除成功')
 * }
 * ```
 */
export async function deleteFile(fileId: string): Promise<DeleteFileResponse> {
    try {
        const response = await post<DeleteFileResponse>('/files/delete', {fileId})
        return response.data
    } catch (error) {
        console.error('删除文件失败:', error)
        throw new Error('删除文件失败，请稍后再试')
    }
}

/**
 * 批量删除文件
 * @param fileIds 文件ID列表
 * @returns Promise<BatchDeleteFilesResponse> 返回批量删除结果
 * @throws {Error} 当请求失败时抛出错误
 *
 * @example
 * ```typescript
 * const result = await batchDeleteFiles(['file-id-1', 'file-id-2'])
 * console.log(`成功删除 ${result.deletedCount} 个文件`)
 * ```
 */
export async function batchDeleteFiles(fileIds: string[]): Promise<BatchDeleteFilesResponse> {
    try {
        const response = await post<BatchDeleteFilesResponse>('/files/batch-delete', {fileIds})
        return response.data
    } catch (error) {
        console.error('批量删除文件失败:', error)
        throw new Error('批量删除文件失败，请稍后再试')
    }
}

/**
 * 下载文件
 * @param fileId 文件ID
 * @returns Promise<DownloadFileResponse> 返回下载结果
 * @throws {Error} 当请求失败时抛出错误
 *
 * @example
 * ```typescript
 * const result = await downloadFile('file-id-123')
 * if (result.success && result.downloadUrl) {
 *   window.open(result.downloadUrl, '_blank')
 * }
 * ```
 */
export async function downloadFile(fileId: string): Promise<DownloadFileResponse> {
    try {
        const response = await post<DownloadFileResponse>('/files/download', {fileId})
        return response.data
    } catch (error) {
        console.error('下载文件失败:', error)
        throw new Error('下载文件失败，请稍后再试')
    }
}

/**
 * 本地文件信息接口
 */
export interface LocalFileInfo {
    id: string
    name: string
    size: number
    type: string
    path: string
    modifiedTime: string
    isDirectory: boolean
}

/**
 * 本地文件列表响应接口
 */
export interface LocalFileListResponse {
    files: LocalFileInfo[]
    currentPath: string
    parentPath: string | null
}

/**
 * 获取本地文件列表
 * @param path 要浏览的路径，默认为当前目录
 * @returns Promise<LocalFileListResponse> 返回本地文件列表
 * @throws {Error} 当请求失败时抛出错误
 *
 * @example
 * ```typescript
 * const files = await getLocalFiles('.')
 * console.log('当前目录文件:', files.files)
 * ```
 */
export async function getLocalFiles(path: string = '.'): Promise<LocalFileListResponse> {
    try {
        const response = await get<LocalFileListResponse>(`/files/local?path=${encodeURIComponent(path)}`)
        return response.data
    } catch (error) {
        console.error('获取本地文件列表失败:', error)
        throw new Error('获取本地文件列表失败，请稍后再试')
    }
}

/**
 * 获取本地文件下载URL
 * @param filePath 文件路径
 * @returns 本地文件下载URL
 */
export function getLocalFileDownloadUrl(filePath: string): string {
    const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'
    return `${baseURL}/files/local/serve?path=${encodeURIComponent(filePath)}`
}

/**
 * 输出文件信息接口
 */
export interface OutputFileInfo {
    id: string
    name: string
    size: number
    type: string
    path: string
    modifiedTime: string
    isDirectory: boolean
}

/**
 * 输出文件列表响应接口
 */
export interface OutputFileListResponse {
    files: OutputFileInfo[]
    currentPath: string
    parentPath: string | null
}

/**
 * 获取输出文件列表
 * @param path 要浏览的路径，默认为当前目录
 * @returns Promise<OutputFileListResponse> 返回输出文件列表
 * @throws {Error} 当请求失败时抛出错误
 *
 * @example
 * ```typescript
 * const files = await getOutputFiles('.')
 * console.log('当前输出目录文件:', files.files)
 * ```
 */
export async function getOutputFiles(path: string = '.'): Promise<OutputFileListResponse> {
    try {
        const response = await get<OutputFileListResponse>(`/files/output?path=${encodeURIComponent(path)}`)
        return response.data
    } catch (error) {
        console.error('获取输出文件列表失败:', error)
        throw new Error('获取输出文件列表失败，请稍后再试')
    }
}

/**
 * 创建文件夹
 * @param folderName 文件夹名称
 * @param currentPath 当前路径
 * @returns 创建结果
 */
export async function createFolderAPI(folderName: string, currentPath: string = '.'): Promise<{
    success: boolean;
    message?: string
}> {
    try {
        const response = await post<{ success: boolean; message?: string }>('/files/create-folder', {
            folderName,
            currentPath
        })
        return response.data
    } catch (error) {
        console.error('创建文件夹失败:', error)
        throw new Error('创建文件夹失败，请稍后再试')
    }
}

/**
 * 删除本地文件
 * @param filePath 文件路径
 * @returns 删除结果
 */
export async function deleteLocalFile(filePath: string): Promise<{ success: boolean; message?: string }> {
    try {
        const response = await post<{ success: boolean; message?: string }>('/files/local/delete', {
            filePath
        })
        return response.data
    } catch (error) {
        console.error('删除本地文件失败:', error)
        throw new Error('删除本地文件失败，请稍后再试')
    }
}

/**
 * 删除输出文件
 * @param filePath 文件路径
 * @returns 删除结果
 */
export async function deleteOutputFile(filePath: string): Promise<{ success: boolean; message?: string }> {
    try {
        const response = await post<{ success: boolean; message?: string }>('/files/output/delete', {
            filePath
        })
        return response.data
    } catch (error) {
        console.error('删除输出文件失败:', error)
        throw new Error('删除输出文件失败，请稍后再试')
    }
}