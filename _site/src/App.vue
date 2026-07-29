<template>
  <nav id="navbar">
    <img :src="logoUrl" alt="WFRC" />
    <span>Statewide ATO Explorer</span>
  </nav>

  <div id="app-layout">
    <Sidebar
      :scenario-years="scenarioYears"
      :model-areas="modelAreas"
      :scenario-year="scenarioYear"
      :model-area="modelArea"
      :access-target="accessTarget"
      :travel-mode="travelMode"
      :disabled-access-targets="disabledAccessTargets"
      :disabled-travel-modes="disabledTravelModes"
      :layer-visible="layerVisible"
      :record-count="recordCount"
      @update:scenarioYear="scenarioYear = $event"
      @update:modelArea="modelArea = $event"
      @update:accessTarget="onAccessTargetChange"
      @update:travelMode="onTravelModeChange"
      @toggle-layer="onToggleLayer"
    />

    <main id="map-area" :class="{ 'overview-visible': layerVisible['overview-map'] }">
      <MapControls
        :active-column="activeColumn"
        :has-data="hasData"
        :is3-d="is3D"
        :opacity="fillOpacity"
        :pinned-tooltip="pinnedTooltip"
        @download="onDownload"
        @screenshot="onScreenshot"
        @update:is3D="on3DChange"
        @update:opacity="onOpacityChange"
        @update:pinnedTooltip="pinnedTooltip = $event"
      />
      <div id="map"></div>
      <Tooltip
        v-if="mapReady"
        :map="mapInstance"
        :pinned="pinnedTooltip"
        :model-area="modelArea"
        :scenario-year="scenarioYear"
        :scenario-years="activeModelScenarioYears"
        :active-column="activeColumn"
      />
      <Legend
        :has-data="hasData"
        :metric-label="activeColumn"
        :min-value="minValue"
        :max-value="maxValue"
      />
      <LayerControl :layer-visible="layerVisible" @toggle-layer="onToggleLayer" />
      <OverviewMap
        v-if="mapReady"
        :main-map="mapInstance"
        :visible="layerVisible['overview-map']"
        :model-bounds="overviewModelBounds"
        :state-bounds="overviewStateBounds"
      />
      <div class="empty-state" v-if="!hasData && !isLoading">
        <i class="fa-solid fa-circle-info"></i>
        <span>No ATO data for current selection</span>
      </div>
      <div id="loading-overlay" v-if="isLoading">
        <div class="loading-spinner"></div>
        <div class="loading-text">{{ loadingText }}</div>
      </div>
    </main>
  </div>

  <SplashModal v-if="showSplash" @close="showSplash = false" />
  <div id="global-tooltip"></div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import Sidebar from './components/Sidebar.vue'
import MapControls from './components/MapControls.vue'
import LayerControl from './components/LayerControl.vue'
import Legend from './components/Legend.vue'
import OverviewMap from './components/OverviewMap.vue'
import SplashModal from './components/SplashModal.vue'
import Tooltip from './components/Tooltip.vue'
import {
  ACCESS_PALETTE,
  ACCESS_TARGETS,
  DATA_BASE_URL,
  MODEL_AREAS,
  SCENARIO_YEARS,
  TRAVEL_MODES,
} from './config/constants.js'
import {
  getAtoMetricAvailabilityProperty,
  getAtoMetricProperty,
  getAtoSelectionSummary,
  hasAtoMetricData,
  loadAtoManifest,
  loadAtoRows,
} from './composables/useAtoData.js'
import { findCartoVectorSource, getFirstLabelLayerId, initMap, setExtentBounds } from './composables/useMap.js'

const logoUrl = `${import.meta.env.BASE_URL}logo.png`

const scenarioYear = ref(SCENARIO_YEARS[1])
const modelArea = ref(MODEL_AREAS[0])
const scenarioYears = ref(SCENARIO_YEARS)
const modelAreas = ref(MODEL_AREAS)
const accessTarget = ref('Job')
const travelMode = ref('Auto')
const fillOpacity = ref(0.78)
const is3D = ref(false)
const pinnedTooltip = ref(true)
const showSplash = ref(true)
const isLoading = ref(false)
const loadingText = ref('Loading...')
const mapReady = ref(false)
const hasData = ref(false)
const mapInstance = ref(null)
const recordCount = ref(0)
const minValue = ref(0)
const maxValue = ref(0)
const selectedRows = ref([])
const atoManifest = ref(null)

const layerVisible = reactive({
  'ato-fill': true,
  'taz-outline': true,
  'major-roads': false,
  'overview-map': true,
})

const activeColumn = computed(() => `${accessTarget.value}_by${travelMode.value}`)
const activeMetricProperty = computed(() => getAtoMetricProperty(scenarioYear.value, activeColumn.value))
const activeMetricAvailabilityProperty = computed(() => (
  getAtoMetricAvailabilityProperty(scenarioYear.value, activeColumn.value)
))
const overviewModelBounds = computed(() => getSelectionBounds())
const overviewStateBounds = computed(() => getManifestBounds())
const activeModelScenarioYears = computed(() => {
  const years = atoManifest.value?.scenario_years_by_model_area?.[modelArea.value] ?? scenarioYears.value
  return [...new Set((years ?? []).map(Number).filter(Number.isFinite))].sort((a, b) => a - b)
})
const disabledAccessTargets = computed(() => (
  Object.fromEntries(
    ACCESS_TARGETS.map((target) => [
      target.value,
      !TRAVEL_MODES.some((mode) => metricHasData(metricColumnFor(target.value, mode.value))),
    ]),
  )
))
const disabledTravelModes = computed(() => (
  Object.fromEntries(
    TRAVEL_MODES.map((mode) => [
      mode.value,
      !metricHasData(metricColumnFor(accessTarget.value, mode.value)),
    ]),
  )
))

onMounted(() => {
  mapInstance.value = initMap('map')
  mapInstance.value.on('style.load', async () => {
    await loadManifestOptions()
    setupMapLayers()
    refreshAtoLayer({ fit: true })
  })
})

function setupMapLayers() {
  const map = mapInstance.value
  if (!map) return

  hideBasemapRoadLayers(map)

  const firstLabelId = getFirstLabelLayerId(map)
  const cartoSource = findCartoVectorSource(map)
  const pmtilesFile = atoManifest.value?.files?.pmtiles
  const boundaryPmtilesFile = atoManifest.value?.files?.boundaries_pmtiles
  const sourceLayer = atoManifest.value?.pmtiles?.source_layer ?? 'ato_taz'
  const boundarySourceLayer = atoManifest.value?.boundary_pmtiles?.source_layer ?? 'ato_taz_boundary'

  if (pmtilesFile) {
    map.addSource('ato-taz-source', {
      type: 'vector',
      url: `pmtiles://${DATA_BASE_URL}/${pmtilesFile}`,
    })

    map.addLayer({
      id: 'ato-taz-fill',
      type: 'fill',
      source: 'ato-taz-source',
      'source-layer': sourceLayer,
      filter: buildAtoFilter(),
      layout: { visibility: layerVisible['ato-fill'] && !is3D.value ? 'visible' : 'none' },
      paint: {
        'fill-color': buildAccessColorExpression(),
        'fill-antialias': false,
        'fill-opacity': fillOpacity.value,
      },
    }, firstLabelId)

    map.addLayer({
      id: 'ato-taz-extrusion',
      type: 'fill-extrusion',
      source: 'ato-taz-source',
      'source-layer': sourceLayer,
      filter: buildAtoFilter(),
      layout: { visibility: layerVisible['ato-fill'] && is3D.value ? 'visible' : 'none' },
      paint: {
        'fill-extrusion-color': buildAccessColorExpression(),
        'fill-extrusion-height': buildExtrusionExpression(),
        'fill-extrusion-opacity': fillOpacity.value,
      },
    }, firstLabelId)

  }
  if (cartoSource) {
    addRoadLayers(map, cartoSource, firstLabelId)
  }

  if (boundaryPmtilesFile) {
    map.addSource('ato-boundary-source', {
      type: 'vector',
      url: `pmtiles://${DATA_BASE_URL}/${boundaryPmtilesFile}`,
    })

    map.addLayer({
      id: 'ato-taz-line',
      type: 'line',
      source: 'ato-boundary-source',
      'source-layer': boundarySourceLayer,
      filter: buildAtoFilter(),
      minzoom: 6,
      layout: { visibility: layerVisible['taz-outline'] ? 'visible' : 'none' },
      paint: {
        'line-color': '#557799',
        'line-width': 0.8,
        'line-opacity': 0.45,
      },
    }, firstLabelId)
  }

  setExtentBounds(getSelectionBounds() ?? [[-114.1, 36.9], [-109.0, 42.1]])
  mapReady.value = true
}

async function loadManifestOptions() {
  try {
    const manifest = await loadAtoManifest()
    atoManifest.value = manifest
    if (manifest.scenario_years?.length) {
      scenarioYears.value = manifest.scenario_years
      if (!scenarioYears.value.includes(scenarioYear.value)) {
        scenarioYear.value = scenarioYears.value[0]
      }
    }
    if (manifest.model_areas?.length) {
      modelAreas.value = manifest.model_areas
      if (!modelAreas.value.includes(modelArea.value)) {
        modelArea.value = modelAreas.value[0]
      }
    }
    ensureAvailableMetricSelection()
  } catch (error) {
    console.error('Failed to load ATO manifest:', error)
  }
}

function metricColumnFor(target, mode) {
  return `${target}_by${mode}`
}

function metricHasData(metricColumn) {
  const manifest = atoManifest.value
  if (!manifest) return true

  return hasAtoMetricData(
    manifest,
    scenarioYear.value,
    modelArea.value,
    metricColumn,
  )
}

function getFirstAvailableTarget() {
  return ACCESS_TARGETS.find((target) => (
    TRAVEL_MODES.some((mode) => metricHasData(metricColumnFor(target.value, mode.value)))
  ))?.value
}

function getFirstAvailableMode(target) {
  return TRAVEL_MODES.find((mode) => (
    metricHasData(metricColumnFor(target, mode.value))
  ))?.value
}

function ensureAvailableMetricSelection() {
  if (!atoManifest.value) return

  let nextTarget = accessTarget.value
  if (disabledAccessTargets.value[nextTarget]) {
    nextTarget = getFirstAvailableTarget() ?? nextTarget
  }

  let nextMode = travelMode.value
  if (!metricHasData(metricColumnFor(nextTarget, nextMode))) {
    nextMode = getFirstAvailableMode(nextTarget) ?? nextMode
  }

  if (nextTarget !== accessTarget.value) {
    accessTarget.value = nextTarget
  }
  if (nextMode !== travelMode.value) {
    travelMode.value = nextMode
  }
}

function hideBasemapRoadLayers(map) {
  const style = map.getStyle()
  style.layers.forEach((layer) => {
    if (
      layer['source-layer'] === 'transportation' ||
      layer['source-layer'] === 'transportation_name'
    ) {
      try {
        map.setLayoutProperty(layer.id, 'visibility', 'none')
      } catch {}
    }
  })
}

function addRoadLayers(map, cartoSource, firstLabelId) {
  try {
    map.addLayer({
      id: 'roads-major',
      type: 'line',
      source: cartoSource,
      'source-layer': 'transportation',
      filter: ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary', 'secondary']]],
      layout: { visibility: layerVisible['major-roads'] ? 'visible' : 'none' },
      paint: {
        'line-color': ['match', ['get', 'class'], 'motorway', '#e892a2', 'trunk', '#f9b29c', '#bbbbbb'],
        'line-width': ['interpolate', ['linear'], ['zoom'], 7, 0.5, 12, 1.5, 16, 4],
        'line-opacity': 0.9,
      },
    }, firstLabelId)
  } catch (error) {
    console.warn('Could not add basemap road layer:', error)
  }
}

function buildAccessColorExpression() {
  const normalizedColumn = `${activeMetricProperty.value}_norm`
  return [
    'case',
    ['has', normalizedColumn],
    [
      'interpolate',
      ['linear'],
      ['to-number', ['get', normalizedColumn]],
      0, ACCESS_PALETTE[0],
      0.2, ACCESS_PALETTE[1],
      0.4, ACCESS_PALETTE[2],
      0.6, ACCESS_PALETTE[3],
      0.8, ACCESS_PALETTE[4],
      1, ACCESS_PALETTE[5],
    ],
    '#d9d9d9',
  ]
}

function buildExtrusionExpression() {
  const normalizedColumn = `${activeMetricProperty.value}_norm`
  return [
    'interpolate',
    ['linear'],
    ['to-number', ['coalesce', ['get', normalizedColumn], 0]],
    0, 0,
    1, 4500,
  ]
}

function buildAtoFilter() {
  return [
    'all',
    ['==', ['get', 'ModelArea'], modelArea.value],
    ['==', ['to-number', ['coalesce', ['get', activeMetricAvailabilityProperty.value], 0]], 1],
  ]
}

function refreshAtoLayer({ fit = false } = {}) {
  const map = mapInstance.value
  const manifest = atoManifest.value
  if (!mapReady.value || !map || !manifest) return

  try {
    const result = getAtoSelectionSummary({
      manifest,
      scenarioYear: scenarioYear.value,
      modelArea: modelArea.value,
      metricColumn: activeColumn.value,
    })

    selectedRows.value = []
    recordCount.value = result.recordCount
    minValue.value = result.minValue
    maxValue.value = result.maxValue
    hasData.value = result.hasData
    refreshStyleExpressions()
    setExtentBounds(getSelectionBounds() ?? getManifestBounds())

    if (fit) {
      fitToSelectionBounds()
    }
  } catch (error) {
    console.error('Failed to refresh ATO layer:', error)
    selectedRows.value = []
    recordCount.value = 0
    minValue.value = 0
    maxValue.value = 0
    hasData.value = false
  }
}

function getManifestBounds() {
  const bounds = atoManifest.value?.bounds
  if (!Array.isArray(bounds) || bounds.length !== 4) return null
  const [minLng, minLat, maxLng, maxLat] = bounds.map(Number)
  if (![minLng, minLat, maxLng, maxLat].every(Number.isFinite)) return null
  return [[minLng, minLat], [maxLng, maxLat]]
}

function getSelectionBounds() {
  const bounds = atoManifest.value?.model_area_bounds?.[modelArea.value]
  if (!Array.isArray(bounds) || bounds.length !== 4) return getManifestBounds()
  const [minLng, minLat, maxLng, maxLat] = bounds.map(Number)
  if (![minLng, minLat, maxLng, maxLat].every(Number.isFinite)) return getManifestBounds()
  return [[minLng, minLat], [maxLng, maxLat]]
}

function fitToSelectionBounds() {
  const map = mapInstance.value
  const mapBounds = getSelectionBounds()
  if (!map || !mapBounds) return
  setExtentBounds(mapBounds)
  map.fitBounds(mapBounds, {
    padding: 35,
    maxZoom: modelArea.value === 'Statewide' ? 10 : 11,
    duration: 700,
  })
}

function refreshStyleExpressions() {
  const map = mapInstance.value
  if (!map) return
  const filter = buildAtoFilter()
  if (map.getLayer('ato-taz-fill')) {
    map.setFilter('ato-taz-fill', filter)
    map.setPaintProperty('ato-taz-fill', 'fill-color', buildAccessColorExpression())
    map.setPaintProperty('ato-taz-fill', 'fill-opacity', fillOpacity.value)
  }
  if (map.getLayer('ato-taz-extrusion')) {
    map.setFilter('ato-taz-extrusion', filter)
    map.setPaintProperty('ato-taz-extrusion', 'fill-extrusion-color', buildAccessColorExpression())
    map.setPaintProperty('ato-taz-extrusion', 'fill-extrusion-height', buildExtrusionExpression())
    map.setPaintProperty('ato-taz-extrusion', 'fill-extrusion-opacity', fillOpacity.value)
  }
  if (map.getLayer('ato-taz-line')) {
    map.setFilter('ato-taz-line', filter)
  }
}

function onToggleLayer(id) {
  layerVisible[id] = !layerVisible[id]
  const map = mapInstance.value
  if (!map) return

  if (id === 'ato-fill') {
    const visible2d = layerVisible[id] && !is3D.value ? 'visible' : 'none'
    const visible3d = layerVisible[id] && is3D.value ? 'visible' : 'none'
    if (map.getLayer('ato-taz-fill')) map.setLayoutProperty('ato-taz-fill', 'visibility', visible2d)
    if (map.getLayer('ato-taz-extrusion')) map.setLayoutProperty('ato-taz-extrusion', 'visibility', visible3d)
  }

  if (id === 'taz-outline' && map.getLayer('ato-taz-line')) {
    map.setLayoutProperty('ato-taz-line', 'visibility', layerVisible[id] ? 'visible' : 'none')
  }

  if (id === 'major-roads' && map.getLayer('roads-major')) {
    map.setLayoutProperty('roads-major', 'visibility', layerVisible[id] ? 'visible' : 'none')
  }

}

function on3DChange(value) {
  is3D.value = value
  const map = mapInstance.value
  if (!map) return
  if (map.getLayer('ato-taz-fill')) {
    map.setLayoutProperty('ato-taz-fill', 'visibility', layerVisible['ato-fill'] && !value ? 'visible' : 'none')
  }
  if (map.getLayer('ato-taz-extrusion')) {
    map.setLayoutProperty('ato-taz-extrusion', 'visibility', layerVisible['ato-fill'] && value ? 'visible' : 'none')
  }
  map.easeTo({ pitch: value ? 45 : 0, duration: 500 })
}

function onOpacityChange(value) {
  fillOpacity.value = value
  refreshStyleExpressions()
}

function onAccessTargetChange(value) {
  if (disabledAccessTargets.value[value]) return
  accessTarget.value = value
  ensureAvailableMetricSelection()
}

function onTravelModeChange(value) {
  if (disabledTravelModes.value[value]) return
  travelMode.value = value
}

async function onDownload() {
  if (!hasData.value) return
  isLoading.value = true
  loadingText.value = `Preparing ${activeColumn.value} download...`

  try {
    const result = await loadAtoRows({
      scenarioYear: scenarioYear.value,
      modelArea: modelArea.value,
      metricColumn: activeColumn.value,
    })
    const rows = result.rows
    selectedRows.value = rows

    const columns = ['ScenarioYear', 'ModelArea', 'SA_TAZID', 'CO_TAZID', activeColumn.value, 'access_value']
    const header = columns.join(',')
    const body = rows
      .map((row) => [
        row.ScenarioYear,
        row.ModelArea,
        row.SA_TAZID,
        row.CO_TAZID,
        row.metric_value,
        row.access_value,
      ].join(','))
      .join('\n')
    const blob = new Blob([`${header}\n${body}`], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `ATO_${modelArea.value.replace(/[^A-Za-z0-9]+/g, '_')}_${scenarioYear.value}_${activeColumn.value}.csv`
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Failed to prepare ATO download:', error)
  } finally {
    isLoading.value = false
  }
}

function onScreenshot() {
  const map = mapInstance.value
  if (!map) return
  map.once('render', () => {
    const link = document.createElement('a')
    link.href = map.getCanvas().toDataURL('image/png')
    link.download = 'StatewideATOExplorer_Map.png'
    link.click()
  })
  map.triggerRepaint()
}

watch(scenarioYear, () => {
  ensureAvailableMetricSelection()
  refreshAtoLayer({ fit: false })
})
watch(activeColumn, () => refreshAtoLayer({ fit: false }))
watch(modelArea, () => {
  ensureAvailableMetricSelection()
  refreshAtoLayer({ fit: true })
})
</script>
