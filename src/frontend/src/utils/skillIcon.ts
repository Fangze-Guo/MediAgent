/**
 * 技能图标工具
 * 根据 skill.type 返回对应的图标（SVG 或 emoji）
 */
import bodySvg from '@/assets/skill-icon/body.svg?raw'
import breastsSvg from '@/assets/skill-icon/breasts.svg?raw'
import lungsSvg from '@/assets/skill-icon/lungs.svg?raw'
import spineSvg from '@/assets/skill-icon/spine.svg?raw'
import tumorSvg from '@/assets/skill-icon/tumour.svg?raw'
import recordsSvg from '@/assets/skill-icon/medical_records.svg?raw'
import esophagusSvg from '@/assets/skill-icon/intestine.svg?raw'

const iconMap: Record<string, string> = {
  'analysis': recordsSvg,
  'body_composition': bodySvg,
  'breast': breastsSvg,
  'lung': lungsSvg,
  'spine': spineSvg,
  'tumor': tumorSvg,
  'esophagus': esophagusSvg,
}

export function getSkillIcon(type: string): string {
  return iconMap[type] || '📦'
}

export function isSvgIcon(icon: string): boolean {
  return icon.startsWith('<svg')
}
