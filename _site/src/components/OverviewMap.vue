<template>
  <div v-show="visible" id="overview-map-panel" aria-label="Overview map">
    <div id="overview-map"></div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import { MAP_CENTER } from '../config/constants.js'

const props = defineProps({
  mainMap: { type: Object, default: null },
  visible: { type: Boolean, default: true },
  modelBounds: { type: Array, default: null },
  stateBounds: { type: Array, default: null },
})

let overviewMap = null
let resizeObserver = null
let isInitialized = false

const UTAH_OUTLINE_FEATURE = {
  type: 'Feature',
  properties: {},
  geometry: {
    type: 'Polygon',
    coordinates: [[
      [-114.0529, 36.9979],
      [-109.0452, 36.9991],
      [-109.0501, 41.0007],
      [-111.0467, 41.0007],
      [-111.0471, 42.0016],
      [-114.0417, 42.0007],
      [-114.0529, 36.9979],
    ]],
  },
}

function boundsToPolygon(bounds) {
  if (!Array.isArray(bounds) || bounds.length !== 2) return null
  const [[west, south], [east, north]] = bounds.map((point) => point.map(Number))
  if (![west, south, east, north].every(Number.isFinite)) return null

  return {
    type: 'Feature',
    properties: {},
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
      ]],
    },
  }
}

function emptyFeatureCollection() {
  return { type: 'FeatureCollection', features: [] }
}

function featureCollection(feature) {
  return { type: 'FeatureCollection', features: feature ? [feature] : [] }
}

function flattenBounds(bounds) {
  if (!Array.isArray(bounds) || bounds.length !== 2) return null
  const values = bounds.flat().map(Number)
  return values.every(Number.isFinite) ? values : null
}

function boundsMatch(firstBounds, secondBounds) {
  const first = flattenBounds(firstBounds)
  const second = flattenBounds(secondBounds)
  if (!first || !second || first.length !== second.length) return false
  return first.every((value, index) => Math.abs(value - second[index]) < 0.0001)
}

function getMainMapBoundsFeature() {
  if (!props.mainMap) return null
  const bounds = props.mainMap.getBounds()
  return boundsToPolygon([
    [bounds.getWest(), bounds.getSouth()],
    [bounds.getEast(), bounds.getNorth()],
  ])
}

function setSourceData(sourceId, data) {
  const source = overviewMap?.getSource(sourceId)
  if (source) source.setData(data)
}

function updateViewportBox() {
  if (!overviewMap || !props.mainMap) return
  setSourceData('overview-viewport-source', featureCollection(getMainMapBoundsFeature()))
}

function updateModelBox() {
  if (!overviewMap) return
  const isStatewide = boundsMatch(props.modelBounds, props.stateBounds)
  setSourceData(
    'overview-model-source',
    featureCollection(isStatewide ? null : boundsToPolygon(props.modelBounds)),
  )
}

function fitOverviewToState() {
  if (!overviewMap) return
  const fallbackBounds = [[-114.1, 36.9], [-109.0, 42.1]]
  const bounds = props.stateBounds ?? fallbackBounds
  overviewMap.fitBounds(bounds, { padding: 12, duration: 0 })
}

function addOverviewLayers() {
  overviewMap.addSource('overview-utah-source', {
    type: 'geojson',
    data: featureCollection(UTAH_OUTLINE_FEATURE),
  })
  overviewMap.addSource('overview-model-source', {
    type: 'geojson',
    data: emptyFeatureCollection(),
  })
  overviewMap.addSource('overview-viewport-source', {
    type: 'geojson',
    data: emptyFeatureCollection(),
  })

  overviewMap.addLayer({
    id: 'overview-utah-fill',
    type: 'fill',
    source: 'overview-utah-source',
    paint: {
      'fill-color': '#ffffff',
      'fill-opacity': 0.5,
    },
  })
  overviewMap.addLayer({
    id: 'overview-utah-line',
    type: 'line',
    source: 'overview-utah-source',
    paint: {
      'line-color': '#233A57',
      'line-width': 2.2,
      'line-opacity': 0.95,
    },
  })
  overviewMap.addLayer({
    id: 'overview-model-fill',
    type: 'fill',
    source: 'overview-model-source',
    paint: {
      'fill-color': '#377eb8',
      'fill-opacity': 0.12,
    },
  })
  overviewMap.addLayer({
    id: 'overview-model-line',
    type: 'line',
    source: 'overview-model-source',
    paint: {
      'line-color': '#233A57',
      'line-width': 1.6,
      'line-opacity': 0.9,
    },
  })
  overviewMap.addLayer({
    id: 'overview-viewport-fill',
    type: 'fill',
    source: 'overview-viewport-source',
    paint: {
      'fill-color': '#e8572d',
      'fill-opacity': 0.16,
    },
  })
  overviewMap.addLayer({
    id: 'overview-viewport-line',
    type: 'line',
    source: 'overview-viewport-source',
    paint: {
      'line-color': '#e8572d',
      'line-width': 2,
      'line-opacity': 0.95,
    },
  })
}

function bindMainMapEvents() {
  props.mainMap?.on('move', updateViewportBox)
  props.mainMap?.on('zoom', updateViewportBox)
}

function unbindMainMapEvents(map = props.mainMap) {
  map?.off('move', updateViewportBox)
  map?.off('zoom', updateViewportBox)
}

function initializeOverviewMap() {
  if (!props.mainMap || isInitialized) return
  isInitialized = true

  overviewMap = new maplibregl.Map({
    container: 'overview-map',
    style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
    center: MAP_CENTER,
    zoom: 4.4,
    attributionControl: false,
    interactive: false,
    preserveDrawingBuffer: true,
  })

  overviewMap.on('load', () => {
    addOverviewLayers()
    fitOverviewToState()
    updateModelBox()
    updateViewportBox()
  })

  bindMainMapEvents()

  const container = document.getElementById('overview-map-panel')
  if (container && 'ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(() => overviewMap?.resize())
    resizeObserver.observe(container)
  }
}

watch(
  () => props.mainMap,
  async () => {
    await nextTick()
    initializeOverviewMap()
  },
  { immediate: true },
)

watch(
  () => props.visible,
  async (visible) => {
    if (!visible) return
    await nextTick()
    initializeOverviewMap()
    overviewMap?.resize()
    updateViewportBox()
  },
)

watch(
  () => props.modelBounds,
  () => updateModelBox(),
  { deep: true },
)

watch(
  () => props.stateBounds,
  () => {
    fitOverviewToState()
    updateModelBox()
    updateViewportBox()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  unbindMainMapEvents()
  resizeObserver?.disconnect()
  overviewMap?.remove()
  overviewMap = null
  isInitialized = false
})
</script>
