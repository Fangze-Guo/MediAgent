<template>
  <div ref="el" class="xss-container" />
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
// @ts-ignore
import Spreadsheet from 'x-data-spreadsheet'
import 'x-data-spreadsheet/dist/xspreadsheet.css'

const props = defineProps<{
  sheets: Record<string, string[][]>
  height?: number
}>()

const el = ref<HTMLElement | null>(null)
let xss: any = null

const buildData = (sheets: Record<string, string[][]>) =>
  Object.entries(sheets).map(([name, rows]) => ({
    name,
    rows: {
      len: rows.length,  // 明确告知行数，不用 x-data-spreadsheet 的默认值
      ...Object.fromEntries(
        rows.map((row, ri) => [
          ri,
          { cells: Object.fromEntries(row.map((cell, ci) => [ci, { text: cell ?? '' }])) },
        ])
      ),
    },
  }))

const init = () => {
  if (!el.value) return
  el.value.innerHTML = ''
  const h = props.height ?? 500
  const allRows = Object.values(props.sheets)
  const maxRows = Math.max(...allRows.map(r => r.length), 1)
  const maxCols = Math.max(...allRows.flatMap(r => r.map(row => row.length)), 1)
  xss = new Spreadsheet(el.value, {
    showToolbar: false,
    showContextmenu: false,
    row: { len: maxRows, height: 26 },
    col: { len: maxCols, width: 120, indexWidth: 60 },
    view: {
      height: () => h,
      width: () => el.value?.clientWidth ?? 820,
    },
  })
  xss.loadData(buildData(props.sheets))
}

onMounted(() => nextTick(init))

watch(
  () => props.sheets,
  () => {
    if (xss) xss.loadData(buildData(props.sheets))
    else nextTick(init)
  },
  { deep: true }
)

onBeforeUnmount(() => { xss = null })
</script>

<style scoped>
.xss-container {
  width: 100%;
}

</style>
