/**
 * 文件管理API接口 - 简化版，只管理数据集文件
 */
import { get, post } from '@/utils/request'

/**
 * 通用响应接口 - 与后端BaseResponse同步
 */
export interface BaseResponse<T = any> {
    /** 响应码 */
    code: number
    /** 响应数据 */
    data: T
    /** 响应消息 */
    message: string
}

/**
 * 文件信息接口
 */
export interface FileInfo {
    /** 文件ID */
    id: string
    /** 文件名 */
    name: string
    /** 文件大小（字节） */
    size: number
    /** 文件类型 */
    type: string
    /** 文件路径 */
    path: string
    /** 修改时间 */
    modifiedTime: string
    /** 是否为目录 */
    isDirectory: boolean
}

/**
 * 文件列表响应接口
 */
export interface FileListResponse {
    /** 响应码 */
    code: number
    /** 文件列表数据 */
    data: {
        /** 文件列表 */
        files: FileInfo[]
        /** 当前路径 */
        currentPath: string
        /** 父路径 */
        parentPath: string | null
    }
    /** 响应消息 */
    message: string
}

/**
 * 获取数据集文件列表
 * @param path 要浏览的路径，默认为当前目录
 * @returns Promise<FileListResponse> 返回文件列表
 * @throws {Error} 当请求失败时抛出错误
 *
 * @example
 * ```typescript
 * const files = await getDataSetFiles('.')
 * console.log('数据集文件:', files.data.files)
 * ```
 */
export async function getDataSetFiles(path: string = '.'): Promise<FileListResponse> {
    try {
        const response = await get<FileListResponse>(`/files/dataset?target_path=${encodeURIComponent(path)}`)
        return response.data
    } catch (error) {
        console.error('获取数据集文件列表失败:', error)
        throw new Error('获取数据集文件列表失败，请稍后再试')
    }
}

/**
 * 获取任务文件列表
 * @param path 要浏览的路径，默认为当前目录
 * @returns Promise<FileListResponse> 返回文件列表
 * @throws {Error} 当请求失败时抛出错误
 *
 * @example
 * ```typescript
 * const files = await getTaskFiles('.')
 * console.log('任务文件:', files.data.files)
 * ```
 */
export async function getTaskFiles(path: string = '.'): Promise<FileListResponse> {
    try {
        const response = await get<FileListResponse>(`/files/task?target_path=${encodeURIComponent(path)}`)
        return response.data
    } catch (error) {
        console.error('获取数据集文件列表失败:', error)
        throw new Error('获取数据集文件列表失败，请稍后再试')
    }
}

/**
 * 上传文件到数据集
 * @param file 要上传的文件
 * @param targetDir 目标目录，默认为当前目录
 * @param onProgress 上传进度回调函数
 * @returns Promise<BaseResponse<FileInfo>> 返回上传结果
 * @throws {Error} 当上传失败时抛出错误
 *
 * @example
 * ```typescript
 * const file = document.getElementById('fileInput').files[0]
 * const result = await uploadFile(file, '.', (progress) => {
 *   console.log(`上传进度: ${progress}%`)
 * })
 * console.log('文件上传成功:', result.data)
 * ```
 */
export async function uploadFile(
    file: File,
    targetDir: string = '.',
    onProgress?: (progress: number) => void
): Promise<BaseResponse<FileInfo>> {
    try {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('target_dir', targetDir)

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
                try {
                    const response = JSON.parse(xhr.responseText) as BaseResponse<FileInfo>
                    if (xhr.status === 200) {
                        resolve(response)
                    } else {
                        // 非200状态码，也返回响应体（包含详细错误信息）
                        // 但标记为失败，让调用方能获取到错误信息
                        resolve(response)
                    }
                } catch (error) {
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
            
            // 添加认证头
            const token = localStorage.getItem('mediagent_token')
            if (token) {
                xhr.setRequestHeader('Authorization', `Bearer ${token}`)
            }
            
            xhr.timeout = 60000 // 60秒超时
            xhr.send(formData)
        })
    } catch (error) {
        console.error('文件上传失败:', error)
        throw new Error('文件上传失败，请稍后再试')
    }
}

/**
 * 批量上传文件到数据集
 * @param files 要上传的文件列表
 * @param targetDir 目标目录，默认为当前目录
 * @returns Promise<BaseResponse<FileInfo[]>> 返回上传结果
 * @throws {Error} 当上传失败时抛出错误
 */
export async function uploadMultipleFiles(
    files: File[],
    targetDir: string = '.'
): Promise<BaseResponse<FileInfo[]>> {
    try {
        const formData = new FormData()
        files.forEach(file => {
            formData.append('files', file)
        })
        formData.append('target_dir', targetDir)

        const response = await post<BaseResponse<FileInfo[]>>('/files/upload-multiple', formData)
        return response.data
    } catch (error) {
        console.error('批量上传文件失败:', error)
        throw new Error('批量上传文件失败，请稍后再试')
    }
}

/**
 * 删除文件
 * @param fileId 文件ID
 * @returns Promise<BaseResponse<null>> 返回删除结果
 * @throws {Error} 当请求失败时抛出错误
 */
export async function deleteFile(fileId: string): Promise<BaseResponse<null>> {
    try {
        const response = await post<BaseResponse<null>>('/files/delete', {fileId})
        return response.data
    } catch (error) {
        console.error('删除文件失败:', error)
        throw new Error('删除文件失败，请稍后再试')
    }
}

/**
 * 根据路径删除文件
 * @param filePath 文件路径
 * @returns Promise<BaseResponse<null>> 返回删除结果
 * @throws {Error} 当请求失败时抛出错误
 */
export async function deleteFileByPath(filePath: string): Promise<BaseResponse<null>> {
    try {
        const response = await post<BaseResponse<null>>('/files/delete-by-path', {file_path: filePath})
        return response.data
    } catch (error) {
        console.error('删除文件失败:', error)
        throw new Error('删除文件失败，请稍后再试')
    }
}

/**
 * 批量删除文件响应数据
 */
export interface BatchDeleteFilesData {
    /** 删除是否成功 */
    success: boolean
    /** 成功删除的文件数量 */
    deletedCount: number
    /** 失败的文件数量 */
    failedCount: number
    /** 失败的文件列表 */
    failedFiles: Array<{
        fileId: string
        error: string
    }>
}

/**
 * 批量删除文件
 * @param fileIds 文件ID列表
 * @returns Promise<BaseResponse<BatchDeleteFilesData>> 返回批量删除结果
 * @throws {Error} 当请求失败时抛出错误
 */
export async function batchDeleteFiles(fileIds: string[]): Promise<BaseResponse<BatchDeleteFilesData>> {
    try {
        const response = await post<BaseResponse<BatchDeleteFilesData>>('/files/batch-delete', {fileIds})
        return response.data
    } catch (error) {
        console.error('批量删除文件失败:', error)
        throw new Error('批量删除文件失败，请稍后再试')
    }
}

/**
 * 创建文件夹
 * @param folderName 文件夹名称
 * @param currentPath 当前路径
 * @returns Promise<BaseResponse<null>> 创建结果
 */
export async function createFolder(folderName: string, currentPath: string = '.'): Promise<BaseResponse<null>> {
    try {
        const response = await post<BaseResponse<null>>('/files/create-folder', {
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
