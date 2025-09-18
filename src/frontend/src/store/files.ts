/**
 * 文件管理状态管理
 * 使用Pinia管理文件列表、上传状态、选择状态等
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getFileList, deleteFile, batchDeleteFiles, downloadFile, createFolderAPI, type FileListResponse } from '@/apis/files'

export const useFileStore = defineStore('files', () => {
  // 状态
  const fileList = ref<FileListResponse['files']>([])
  const loading = ref(false)
  const selectedFileIds = ref<string[]>([])
  const searchText = ref('')
  const error = ref<string | null>(null)
  const currentPath = ref('.')
  const parentPath = ref<string | null>(null)

  // 计算属性
  const selectedFiles = computed(() => 
    fileList.value.filter(file => selectedFileIds.value.includes(file.id))
  )

  const selectedCount = computed(() => selectedFileIds.value.length)

  const filteredFiles = computed(() => {
    let filtered = fileList.value
    
    // 搜索过滤
    if (searchText.value) {
      filtered = filtered.filter(file => 
        file.name.toLowerCase().includes(searchText.value.toLowerCase())
      )
    }
    
    return filtered
  })

  const fileStats = computed(() => {
    const totalFiles = fileList.value.length
    const totalSize = fileList.value.reduce((sum, file) => sum + file.size, 0)
    const directories = fileList.value.filter(file => file.isDirectory).length
    const imageFiles = fileList.value.filter(file => file.type.startsWith('image/')).length
    const csvFiles = fileList.value.filter(file => file.type.includes('csv')).length
    const dicomFiles = fileList.value.filter(file => file.type.includes('dicom')).length
    const otherFiles = totalFiles - directories - imageFiles - csvFiles - dicomFiles

    return {
      totalFiles,
      totalSize,
      directories,
      imageFiles,
      csvFiles,
      dicomFiles,
      otherFiles
    }
  })

  // 操作
  const setLoading = (value: boolean) => {
    loading.value = value
  }

  const setError = (message: string | null) => {
    error.value = message
  }

  const setSearchText = (text: string) => {
    searchText.value = text
  }

  const setSelectedFileIds = (ids: string[]) => {
    selectedFileIds.value = ids
  }

  const toggleFileSelection = (fileId: string) => {
    const index = selectedFileIds.value.indexOf(fileId)
    if (index > -1) {
      selectedFileIds.value.splice(index, 1)
    } else {
      selectedFileIds.value.push(fileId)
    }
  }

  const selectAllFiles = () => {
    selectedFileIds.value = filteredFiles.value.map(file => file.id)
  }

  const clearSelection = () => {
    selectedFileIds.value = []
  }

  // 获取文件列表
  const fetchFileList = async (path: string = '.') => {
    try {
      setLoading(true)
      setError(null)
      const response = await getFileList(path)
      fileList.value = response.files
      // 更新路径信息
      if (response.currentPath !== undefined) {
        currentPath.value = response.currentPath
      }
      if (response.parentPath !== undefined) {
        parentPath.value = response.parentPath
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '获取文件列表失败'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  // 删除单个文件
  const removeFile = async (fileId: string) => {
    try {
      setLoading(true)
      setError(null)
      const result = await deleteFile(fileId)
      
      if (result.success) {
        // 从列表中移除文件
        fileList.value = fileList.value.filter(file => file.id !== fileId)
        // 从选中列表中移除
        const index = selectedFileIds.value.indexOf(fileId)
        if (index > -1) {
          selectedFileIds.value.splice(index, 1)
        }
        return true
      } else {
        setError(result.error || '删除文件失败')
        return false
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '删除文件失败'
      setError(errorMessage)
      return false
    } finally {
      setLoading(false)
    }
  }

  // 批量删除文件
  const removeFiles = async (fileIds: string[]) => {
    try {
      setLoading(true)
      setError(null)
      const result = await batchDeleteFiles(fileIds)
      
      if (result.success) {
        // 从列表中移除文件
        fileList.value = fileList.value.filter(file => !fileIds.includes(file.id))
        // 清空选中列表
        clearSelection()
        return { success: true, deletedCount: result.deletedCount }
      } else {
        setError(result.error || '批量删除失败')
        return { success: false, deletedCount: 0 }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '批量删除失败'
      setError(errorMessage)
      return { success: false, deletedCount: 0 }
    } finally {
      setLoading(false)
    }
  }

  // 下载文件
  const downloadFileById = async (fileId: string) => {
    try {
      setError(null)
      const result = await downloadFile(fileId)
      
      if (result.success && result.downloadUrl) {
        return { success: true, downloadUrl: result.downloadUrl }
      } else {
        setError(result.error || '下载文件失败')
        return { success: false, downloadUrl: null }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '下载文件失败'
      setError(errorMessage)
      return { success: false, downloadUrl: null }
    }
  }

  // 添加文件到列表（上传成功后调用）
  const addFile = (file: FileListResponse['files'][0]) => {
    // 检查文件是否已存在
    const existingIndex = fileList.value.findIndex(f => f.id === file.id)
    if (existingIndex > -1) {
      // 更新现有文件
      fileList.value[existingIndex] = file
    } else {
      // 添加新文件
      fileList.value.unshift(file) // 添加到列表顶部
    }
  }

  // 更新文件信息
  const updateFile = (fileId: string, updates: Partial<FileListResponse['files'][0]>) => {
    const index = fileList.value.findIndex(file => file.id === fileId)
    if (index > -1) {
      fileList.value[index] = { ...fileList.value[index], ...updates }
    }
  }

  // 根据ID查找文件
  const getFileById = (fileId: string) => {
    return fileList.value.find(file => file.id === fileId)
  }

  // 创建文件夹
  const createFolder = async (folderName: string, currentPath: string = '.') => {
    try {
      setLoading(true)
      setError(null)
      const result = await createFolderAPI(folderName, currentPath)
      if (result.success) {
        // 刷新文件列表
        await fetchFileList(currentPath)
        return { success: true }
      } else {
        setError(result.message || '创建文件夹失败')
        return { success: false, message: result.message || '创建文件夹失败' }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '创建文件夹失败'
      setError(errorMessage)
      return { success: false, message: errorMessage }
    } finally {
      setLoading(false)
    }
  }

  // 重置状态
  const reset = () => {
    fileList.value = []
    selectedFileIds.value = []
    searchText.value = ''
    error.value = null
    loading.value = false
  }

  return {
    // 状态
    fileList,
    loading,
    selectedFileIds,
    searchText,
    error,
    
    // 计算属性
    selectedFiles,
    selectedCount,
    filteredFiles,
    fileStats,
    
    // 操作
    setLoading,
    setError,
    setSearchText,
    setSelectedFileIds,
    toggleFileSelection,
    selectAllFiles,
    clearSelection,
    fetchFileList,
    removeFile,
    removeFiles,
    downloadFileById,
    addFile,
    updateFile,
    getFileById,
    createFolder,
    reset,
    currentPath,
    parentPath
  }
})
