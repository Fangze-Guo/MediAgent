<template>
  <div class="mpr-viewer">
    <div v-if="loading" class="mpr-loading">Loading viewer...</div>
    <div v-else-if="error" class="mpr-error">{{ error }}</div>
    <div v-else class="mpr-grid">
      <div v-for="pane in panes" :key="pane.axis" class="mpr-pane" @wheel.prevent="handleWheel(pane.axis, $event)">
        <canvas
          v-show="localVolumeReady"
          :ref="(el) => setCanvasRef(pane.axis, el as HTMLCanvasElement | null)"
        />
        <img v-show="!localVolumeReady" :src="displayedSliceSrc(pane.axis)" :alt="pane.label" draggable="false" />
        <div class="mpr-pane-label">
          <strong>{{ pane.label }}</strong>
          <span>{{ sliceIndices[pane.axis] + 1 }} / {{ sliceCounts[pane.axis] }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, reactive, ref, watch } from 'vue'

type Axis = 'axial' | 'coronal' | 'sagittal'

interface ViewerMetadata {
  slice_counts: Record<Axis, number>
  center: Record<Axis, number>
  shape?: { x: number; y: number; z: number }
  spacing?: { x: number; y: number; z: number }
}

interface VolumeShape {
  x: number
  y: number
  z: number
}

interface VolumeSpacing {
  x: number
  y: number
  z: number
}

const props = defineProps<{
  metadataUrl: string
  ctSliceBaseUrl: string
  maskSliceBaseUrl?: string | null
  ctVolumeUrl?: string | null
  maskVolumeUrl?: string | null
  cacheKey?: string | null
  visible: boolean
}>()

const panes: Array<{ axis: Axis; label: string }> = [
  { axis: 'axial', label: 'Axial' },
  { axis: 'coronal', label: 'Coronal' },
  { axis: 'sagittal', label: 'Sagittal' },
]
const PREFETCH_RADIUS = 36
const PREFETCH_CONCURRENCY = 8

const metadataCache = new Map<string, Promise<ViewerMetadata>>()
const loadedImageUrls = new Set<string>()
const imagePromises = new Map<string, Promise<void>>()
const loading = ref(false)
const error = ref('')
const localVolumeReady = ref(false)
const sliceCounts = reactive<Record<Axis, number>>({ axial: 1, coronal: 1, sagittal: 1 })
const sliceIndices = reactive<Record<Axis, number>>({ axial: 0, coronal: 0, sagittal: 0 })
const desiredIndices = reactive<Record<Axis, number>>({ axial: 0, coronal: 0, sagittal: 0 })
const wheelDeltas = reactive<Record<Axis, number>>({ axial: 0, coronal: 0, sagittal: 0 })
const pendingLoads = reactive<Record<Axis, number | null>>({ axial: null, coronal: null, sagittal: null })
const prefetchQueue: string[] = []
const canvasRefs = new Map<Axis, HTMLCanvasElement>()
const localVolume = {
  ct: null as Uint8Array | null,
  mask: null as Uint8Array | null,
  shape: null as VolumeShape | null,
  spacing: null as VolumeSpacing | null,
}
let activePrefetches = 0
let wheelFrame = 0
let localLoadId = 0

async function loadViewer() {
  if (!props.visible || !props.metadataUrl) return
  loading.value = true
  error.value = ''
  try {
    const metadata = await loadMetadata(props.metadataUrl)
    panes.forEach(({ axis }) => {
      sliceCounts[axis] = metadata.slice_counts[axis] || 1
      sliceIndices[axis] = clamp(metadata.center[axis] || 0, 0, sliceCounts[axis] - 1)
      desiredIndices[axis] = sliceIndices[axis]
      pendingLoads[axis] = null
    })
    panes.forEach(({ axis }) => loadTargetSlice(axis, sliceIndices[axis], 1))
    window.setTimeout(() => panes.forEach(({ axis }) => prefetchAround(axis, 1)), 120)
    loadLocalVolumes(metadata)
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

function displayedSliceSrc(axis: Axis) {
  return sliceSrc(axis, sliceIndices[axis])
}

function handleWheel(axis: Axis, event: WheelEvent) {
  const magnitude = Math.min(8, Math.max(1, Math.round(Math.abs(event.deltaY) / 80)))
  wheelDeltas[axis] += event.deltaY > 0 ? magnitude : -magnitude
  if (wheelFrame) return
  wheelFrame = window.requestAnimationFrame(flushWheelDeltas)
}

function flushWheelDeltas() {
  wheelFrame = 0
  panes.forEach(({ axis }) => {
    const delta = wheelDeltas[axis]
    if (!delta) return
    wheelDeltas[axis] = 0
    const direction = delta > 0 ? 1 : -1
    const nextIndex = clamp(desiredIndices[axis] + delta, 0, sliceCounts[axis] - 1)
    if (nextIndex === desiredIndices[axis]) return
    desiredIndices[axis] = nextIndex
    loadTargetSlice(axis, nextIndex, direction)
  })
}

function loadTargetSlice(axis: Axis, index: number, direction: number) {
  if (localVolumeReady.value) {
    sliceIndices[axis] = index
    renderLocalSlice(axis)
    return
  }
  const url = sliceSrc(axis, index)
  pendingLoads[axis] = index
  prefetchAround(axis, direction)
  if (loadedImageUrls.has(url)) {
    applyLoadedSlice(axis, index)
    return
  }
  loadImage(url)
    .then(() => {
      if (pendingLoads[axis] === index && desiredIndices[axis] === index) {
        applyLoadedSlice(axis, index)
      }
    })
    .catch(() => {
      if (pendingLoads[axis] === index) {
        pendingLoads[axis] = null
      }
    })
}

function applyLoadedSlice(axis: Axis, index: number) {
  sliceIndices[axis] = index
  pendingLoads[axis] = null
  prefetchAround(axis, 0)
}

function prefetchAround(axis: Axis, direction = 0) {
  const current = desiredIndices[axis]
  const offsets = prioritizedOffsets(direction)
  offsets.forEach((offset, position) => {
    const index = current + offset
    if (index < 0 || index >= sliceCounts[axis]) return
    enqueuePrefetch(sliceSrc(axis, index), position < 10)
  })
}

function prioritizedOffsets(direction: number) {
  const offsets = [0]
  const forward = direction >= 0 ? 1 : -1
  const backward = -forward
  for (let offset = 1; offset <= PREFETCH_RADIUS; offset += 1) {
    offsets.push(forward * offset)
    offsets.push(backward * offset)
  }
  return offsets
}

function enqueuePrefetch(url: string, priority = false) {
  if (loadedImageUrls.has(url) || imagePromises.has(url) || prefetchQueue.includes(url)) return
  if (priority) {
    prefetchQueue.unshift(url)
  } else {
    prefetchQueue.push(url)
  }
  drainPrefetchQueue()
}

function drainPrefetchQueue() {
  while (activePrefetches < PREFETCH_CONCURRENCY && prefetchQueue.length > 0) {
    const url = prefetchQueue.shift()
    if (!url || loadedImageUrls.has(url) || imagePromises.has(url)) continue
    activePrefetches += 1
    loadImage(url)
      .catch(() => undefined)
      .finally(() => {
        activePrefetches -= 1
        drainPrefetchQueue()
      })
  }
}

function loadImage(url: string) {
  if (loadedImageUrls.has(url)) return Promise.resolve()
  const cached = imagePromises.get(url)
  if (cached) return cached
  const promise = new Promise<void>((resolve, reject) => {
    const image = new Image()
    image.onload = () => {
      loadedImageUrls.add(url)
      imagePromises.delete(url)
      resolve()
    }
    image.onerror = () => {
      imagePromises.delete(url)
      reject(new Error(`Failed to load slice: ${url}`))
    }
    image.src = url
  })
  imagePromises.set(url, promise)
  return promise
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function setCanvasRef(axis: Axis, element: HTMLCanvasElement | null) {
  if (element) {
    canvasRefs.set(axis, element)
    if (localVolumeReady.value) renderLocalSlice(axis)
  } else {
    canvasRefs.delete(axis)
  }
}

async function loadLocalVolumes(metadata: ViewerMetadata) {
  const loadId = localLoadId + 1
  localLoadId = loadId
  localVolumeReady.value = false
  localVolume.ct = null
  localVolume.mask = null
  localVolume.shape = metadata.shape || null
  localVolume.spacing = metadata.spacing || null
  if (!props.ctVolumeUrl || !localVolume.shape) return
  try {
    const ctBuffer = await fetchBinary(props.ctVolumeUrl)
    if (loadId !== localLoadId) return
    localVolume.ct = new Uint8Array(ctBuffer)
    const expectedSize = localVolume.shape.x * localVolume.shape.y * localVolume.shape.z
    if (localVolume.ct.byteLength !== expectedSize) {
      localVolume.ct = null
      return
    }
    if (props.maskVolumeUrl) {
      try {
        const maskBuffer = await fetchBinary(props.maskVolumeUrl)
        if (loadId !== localLoadId) return
        const mask = new Uint8Array(maskBuffer)
        if (mask.byteLength === expectedSize) {
          localVolume.mask = mask
        }
      } catch {
        localVolume.mask = null
      }
    }
    if (loadId !== localLoadId) return
    panes.forEach(({ axis }) => {
      sliceIndices[axis] = desiredIndices[axis]
    })
    localVolumeReady.value = true
    await nextTick()
    renderAllLocalSlices()
  } catch {
    localVolumeReady.value = false
  }
}

async function fetchBinary(url: string) {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Failed to load volume: ${response.status}`)
  return response.arrayBuffer()
}

function renderAllLocalSlices() {
  panes.forEach(({ axis }) => renderLocalSlice(axis))
}

function renderLocalSlice(axis: Axis) {
  const canvas = canvasRefs.get(axis)
  const ct = localVolume.ct
  const shape = localVolume.shape
  if (!canvas || !ct || !shape) return
  const spacing = localVolume.spacing || { x: 1, y: 1, z: 1 }
  const source = planeGeometry(axis, shape, spacing)
  const targetWidth = Math.max(1, Math.round(source.rows * source.physicalRatio))
  canvas.width = targetWidth
  canvas.height = source.rows
  const context = canvas.getContext('2d')
  if (!context) return
  const image = context.createImageData(targetWidth, source.rows)
  const data = image.data
  const index = clamp(sliceIndices[axis], 0, sliceCounts[axis] - 1)
  const palette = labelPalette()
  for (let row = 0; row < source.rows; row += 1) {
    const sourceColScale = source.cols / targetWidth
    for (let col = 0; col < targetWidth; col += 1) {
      const sourceCol = Math.min(source.cols - 1, Math.floor(col * sourceColScale))
      const volumeOffset = volumeIndex(axis, index, row, sourceCol, shape)
      const gray = ct[volumeOffset] || 0
      const out = (row * targetWidth + col) * 4
      const label = localVolume.mask?.[volumeOffset] || 0
      if (label > 0) {
        const color = palette[(label - 1) % palette.length]
        data[out] = Math.round(gray * 0.5 + color[0] * 0.5)
        data[out + 1] = Math.round(gray * 0.5 + color[1] * 0.5)
        data[out + 2] = Math.round(gray * 0.5 + color[2] * 0.5)
      } else {
        data[out] = gray
        data[out + 1] = gray
        data[out + 2] = gray
      }
      data[out + 3] = 255
    }
  }
  context.putImageData(image, 0, 0)
}

function planeGeometry(axis: Axis, shape: VolumeShape, spacing: VolumeSpacing) {
  if (axis === 'axial') {
    return {
      rows: shape.y,
      cols: shape.x,
      physicalRatio: (shape.x * spacing.x) / Math.max(1, shape.y * spacing.y),
    }
  }
  if (axis === 'coronal') {
    return {
      rows: shape.z,
      cols: shape.x,
      physicalRatio: (shape.x * spacing.x) / Math.max(1, shape.z * spacing.z),
    }
  }
  return {
    rows: shape.z,
    cols: shape.y,
    physicalRatio: (shape.y * spacing.y) / Math.max(1, shape.z * spacing.z),
  }
}

function volumeIndex(axis: Axis, slice: number, row: number, col: number, shape: VolumeShape) {
  if (axis === 'axial') {
    return slice * shape.y * shape.x + row * shape.x + col
  }
  if (axis === 'coronal') {
    const z = shape.z - 1 - row
    return z * shape.y * shape.x + slice * shape.x + col
  }
  const z = shape.z - 1 - row
  return z * shape.y * shape.x + col * shape.x + slice
}

function labelPalette() {
  return [
    [255, 0, 0],
    [0, 255, 0],
    [0, 0, 255],
    [255, 255, 0],
    [0, 255, 255],
    [255, 0, 255],
    [255, 239, 213],
    [0, 0, 205],
    [205, 133, 63],
    [210, 180, 140],
    [102, 205, 170],
    [0, 0, 128],
    [0, 139, 139],
    [46, 139, 87],
    [255, 228, 225],
    [106, 90, 205],
    [221, 160, 221],
    [233, 150, 122],
    [165, 42, 42],
    [255, 250, 250],
  ]
}

watch(() => props.visible, (visible) => {
  if (visible) loadViewer()
})

watch(() => [props.metadataUrl, props.ctSliceBaseUrl, props.maskSliceBaseUrl, props.ctVolumeUrl, props.maskVolumeUrl], () => {
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

.mpr-pane img,
.mpr-pane canvas {
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
