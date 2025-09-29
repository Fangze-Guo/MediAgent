/**
 * 沙盒相关API接口
 * 提供与后端沙盒处理服务的交互功能
 */
import { get, post } from '@/utils/request'

/**
 * DICOM转换请求参数
 */
export interface DicomConvertRequest {
  /** DICOM文件目录路径 */
  dicom_directory: string
  /** 输出文件路径 */
  output_file: string
  /** 是否压缩 */
  compression?: boolean
}

/**
 * 重采样请求参数
 */
export interface ResampleRequest {
  /** 输入目录 */
  input_directory: string
  /** 输出目录 */
  output_directory: string
  /** 目标体素间距 */
  target_spacing: string
  /** 插值方法 */
  interpolation: 'Linear' | 'Nearest' | 'Cubic'
  /** 批量处理模式 */
  batch_mode?: boolean
}

/**
 * 归一化请求参数
 */
export interface NormalizeRequest {
  /** 输入目录 */
  input_directory: string
  /** 输出目录 */
  output_directory: string
  /** 归一化方法 */
  method: 'z-score' | 'min-max' | 'percentile'
  /** 百分比裁剪值 */
  percentiles?: string
  /** 生成统计报告 */
  generate_stats?: boolean
}

/**
 * 处理响应结构
 */
export interface ProcessResponse {
  success: boolean
  message?: string
  stdout?: string
  stderr?: string
  timestamp?: string
  [key: string]: any
}

/**
 * DICOM转NII转换
 * @param params 转换参数
 * @returns Promise<ProcessResponse> 返回处理结果
 */
export async function convertDicomToNii(params: DicomConvertRequest): Promise<ProcessResponse> {
  try {
    const response = await post<ProcessResponse>('/convert', null, {
      params: params
    })
    return response.data
  } catch (error: any) {
    console.error('DICOM转换失败:', error)
    throw new Error('DICOM转换失败，请检查输入文件路径')
  }
}

/**
 * 图像重采样
 * @param params 重采样参数
 * @returns Promise<ProcessResponse> 返回处理结果
 */
export async function resampleImages(params: ResampleRequest): Promise<ProcessResponse> {
  try {
    const response = await post<ProcessResponse>('/resample/', params)
    return response.data
  } catch (error: any) {
    console.error('图像重采样失败:', error)
    throw new Error('图像重采样失败，请检查输入文件')
  }
}

/**
 * 图像归一化
 * @param params 归一化参数
 * @returns Promise<ProcessResponse> 返回处理结果
 */
export async function normalizeImages(params: NormalizeRequest): Promise<ProcessResponse> {
  try {
    const response = await post<ProcessResponse>('/normalize/', params)
    return response.data
  } catch (error: any) {
    console.error('图像归一化失败:', error)
    throw new Error('图像归一化失败，请检查输入文件')
  }
}

/**
 * 获取转换状态
 * @returns Promise<ProcessResponse> 返回服务状态
 */
export async function getConvertStatus(): Promise<ProcessResponse> {
  try {
    const response = await get<ProcessResponse>('/convert/status')
    return response.data
  } catch (error: any) {
    console.error('获取转换状态失败:', error)
    throw new Error('获取转换状态失败')
  }
}
