<template>
  <div class="mpr-viewer">
    <div v-if="loading" class="mpr-loading">Loading viewer...</div>
    <div v-else-if="error" class="mpr-error">{{ error }}</div>
    <div v-else class="mpr-grid">
      <div v-for="pane in panes" :key="pane.axis" class="mpr-pane" @wheel.prevent="handleWheel(pane.axis, $event)">
        <img :src="sliceSrc(pane.axis)" :alt="pane.label" draggable="false" />
        <div class="mpr-pane-label">
          <strong>{{ pane.label }}</strong>
          <span>{{ sliceIndices[pane.axis] + 1 }} / {{ sliceCounts[pane.axis] }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

type Axis = 'axial' | 'coronal' | 'sagittal'

interface ViewerMetadata {
  slice_counts: Record<Axis, number>
  center: Record<Axis, number>
}

const props = defineProps<{
  metadataUrl: string
  ctSliceBaseUrl: string
  maskSliceBaseUrl?: string | null
  cacheKey?: string | null
  visible: boolean
}>()

const panes: Array<{ axis: Axis; label: string }> = [
  { axis: 'axial', label: 'Axial' },
  { axis: 'coronal', label: 'Coronal' },
  { axis: 'sagittal', label: 'Sagittal' },
]

const metadataCache = new Map<string, Promise<ViewerMetadata>>()
const imageCache = new Set<string>()
const loading = ref(false)
const error = ref('')
const sliceCounts = reactive<Record<Axis, number>>({ axial: 1, coronal: 1, sagittal: 1 })
const sliceIndices = reactive<Record<Axis, number>>({ axial: 0, coronal: 0, sagittal: 0 })

async function loadViewer() {
  if (!props.visible || !props.metadataUrl) return
  loading.value = true
  error.value = ''
  try {
    const metadata = await loadMetadata(props.metadataUrl)
    panes.forEach(({ axis }) => {
      sliceCounts[axis] = metadata.slice_counts[axis] || 1
      sliceIndices[axis] = clamp(metadata.center[axis] || 0, 0, sliceCounts[axis] - 1)
    })
    window.setTimeout(() => panes.forEach(({ axis }) => prefetchAround(axis)), 120)
  } catch (err: any) {
    error.value = err?.message || 'Failed to load viewer'
  } finally {
    loading.value = false
  }
}

async function loadMetadata(url: string) {
  const cached = metadataCache.get(url)
  if (cached) return cached
  const promise = fetch(url)
    .then((response) => {
      if (!response.ok) throw new Error(`Failed to load viewer metadata: ${response.status}`)
      return response.json()
    })
    .then((payload) => payload.data as ViewerMetadata)
  metadataCache.set(url, promise)
  return promise
}

function sliceSrc(axis: Axis, index = sliceIndices[axis]) {
  const base = props.maskSliceBaseUrl || props.ctSliceBaseUrl
  const url = `${base}/${axis}/${index}`
  if (!props.cacheKey) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}v=${encodeURIComponent(props.cacheKey)}`
}

function handleWheel(axis: Axis, event: WheelEvent) {
  const delta = event.deltaY > 0 ? 1 : -1
  const nextIndex = clamp(sliceIndices[axis] + delta, 0, sliceCounts[axis] - 1)
  if (nextIndex === sliceIndices[axis]) return
  sliceIndices[axis] = nextIndex
  prefetchAround(axis)
}

function prefetchAround(axis: Axis) {
  const current = sliceIndices[axis]
  for (let offset = -2; offset <= 2; offset += 1) {
    const index = current + offset
    if (index < 0 || index >= sliceCounts[axis]) continue
    prefetchImage(sliceSrc(axis, index))
  }
}

function prefetchImage(url: string) {
  if (imageCache.has(url)) return
  imageCache.add(url)
  const image = new Image()
  image.src = url
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

watch(() => props.visible, (visible) => {
  if (visible) loadViewer()
})

watch(() => [props.metadataUrl, props.ctSliceBaseUrl, props.maskSliceBaseUrl], () => {
  if (props.visible) loadViewer()
})

onMounted(() => {
  if (props.visible) loadViewer()
})
</script>

<style scoped>
.mpr-viewer {
  height: min(76vh, 820px);
  min-height: 520px;
  background: #05070c;
  color: #d1d5db;
}

.mpr-loading,
.mpr-error {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mpr-error {
  color: #fca5a5;
}

.mpr-grid {
  height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px;
}

.mpr-pane {
  min-width: 0;
  min-height: 0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #000;
  border: 1px solid #1f2937;
}

.mpr-pane:first-child {
  grid-row: 1 / 2;
  grid-column: 1 / 2;
}

.mpr-pane:nth-child(2) {
  grid-row: 2 / 3;
  grid-column: 2 / 3;
}

.mpr-pane:nth-child(3) {
  grid-row: 1 / 2;
  grid-column: 2 / 3;
}

.mpr-pane img {
  max-width: 100%;
  max-height: 100%;
  display: block;
  object-fit: contain;
  user-select: none;
}

.mpr-pane-label {
  position: absolute;
  left: 10px;
  bottom: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 7px;
  background: rgba(0, 0, 0, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #f9fafb;
  font-size: 11px;
}

.mpr-pane-label span {
  color: #a7f3d0;
}
</style>
