<template>
  <nav id="navbar">
    <img :src="logoUrl" alt="WFRC" />
    <span>Statewide ATO and VMT Explorer</span>
  </nav>

  <div id="app-layout">
    <Sidebar
      :dataset-mode="datasetMode"
      :scenario-years="scenarioYears"
      :model-areas="modelAreas"
      :scenario-year="scenarioYear"
      :model-area="modelArea"
      :access-target="accessTarget"
      :travel-mode="travelMode"
      :vmt-period="vmtPeriod"
      :disabled-access-targets="disabledAccessTargets"
      :disabled-travel-modes="disabledTravelModes"
      :disabled-vmt-periods="disabledVmtPeriods"
      :record-count="recordCount"
      :active-taz-properties="activeTazProperties"
      :dataset-label="activeDatasetLabel"
      :active-column="activeColumn"
      :metric-label="activeMetricLabel"
      :trend-scenario-years="activeModelScenarioYears"
      @update:datasetMode="onDatasetModeChange"
      @update:scenarioYear="scenarioYear = $event"
      @update:modelArea="modelArea = $event"
      @update:accessTarget="onAccessTargetChange"
      @update:travelMode="onTravelModeChange"
      @update:vmtPeriod="onVmtPeriodChange"
    />

    <main id="map-area" :class="{ 'overview-visible': layerVisible['overview-map'] }">
      <MapControls
        :active-column="activeMetricLabel"
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
        :dataset-mode="datasetMode"
        :model-area="modelArea"
        :scenario-year="scenarioYear"
        :active-column="activeColumn"
        :metric-label="activeMetricLabel"
        @feature-hover="activeTazProperties = $event"
      />
      <Legend
        :has-data="hasData"
        :metric-label="activeMetricLabel"
        :min-value="minValue"
        :max-value="maxValue"
        :palette="activePalette"
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
        <span>No {{ activeDatasetLabel }} data for current selection</span>
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
  DATASETS,
  DATA_BASE_URL,
  MODEL_AREAS,
  SCENARIO_YEARS,
  TRAVEL_MODES,
  VMT_PALETTE,
  VMT_PERIODS,
} from './config/constants.js'
import {
  getMetricAvailabilityProperty,
  getMetricProperty,
  getSelectionSummary,
  hasMetricData,
  loadDataManifest,
  loadDataRows,
} from './composables/useAtoData.js'
import { findCartoVectorSource, getFirstLabelLayerId, initMap, setExtentBounds } from './composables/useMap.js'

const logoUrl = `${import.meta.env.BASE_URL}logo.png`
const DATASET_IDS = DATASETS.map((dataset) => dataset.value)

const datasetMode = ref('ato')
const scenarioYear = ref(SCENARIO_YEARS[1])
const modelArea = ref(MODEL_AREAS[0])
const accessTarget = ref('Job')
const travelMode = ref('Auto')
const vmtPeriod = ref('DY_VMT')
const fillOpacity = ref(0.78)
const is3D = ref(false)
const pinnedTooltip = ref(false)
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
const activeTazProperties = ref(null)
const manifests = reactive({
  ato: null,
  vmt: null,
})

const layerVisible = reactive({
  'metric-fill': true,
  'taz-outline': true,
  'major-roads': false,
  'overview-map': true,
})

const activeManifest = computed(() => manifests[datasetMode.value])
const activeDataset = computed(() => (
  DATASETS.find((dataset) => dataset.value === datasetMode.value) ?? DATASETS[0]
))
const activeDatasetLabel = computed(() => activeDataset.value.label)
const scenarioYears = computed(() => activeManifest.value?.scenario_years ?? SCENARIO_YEARS)
const modelAreas = computed(() => activeManifest.value?.model_areas ?? MODEL_AREAS)
const activeColumn = computed(() => (
  datasetMode.value === 'ato'
    ? `${accessTarget.value}_by${travelMode.value}`
    : vmtPeriod.value
))
const activeMetricLabel = computed(() => {
  if (datasetMode.value === 'vmt') {
    const period = VMT_PERIODS.find((item) => item.value === vmtPeriod.value)
    return period ? `${period.label} VMT` : vmtPeriod.value
  }

  const target = ACCESS_TARGETS.find((item) => item.value === accessTarget.value)
  const mode = TRAVEL_MODES.find((item) => item.value === travelMode.value)
  return `${target?.label ?? accessTarget.value} by ${mode?.label ?? travelMode.value}`
})
const activePalette = computed(() => (
  datasetMode.value === 'vmt' ? VMT_PALETTE : ACCESS_PALETTE
))
const activeMetricProperty = computed(() => getMetricProperty(scenarioYear.value, activeColumn.value))
const activeMetricAvailabilityProperty = computed(() => (
  getMetricAvailabilityProperty(scenarioYear.value, activeColumn.value)
))
const overviewModelBounds = computed(() => getSelectionBounds())
const overviewStateBounds = computed(() => getManifestBounds())
const activeModelScenarioYears = computed(() => {
  const years = activeManifest.value?.scenario_years_by_model_area?.[modelArea.value] ?? scenarioYears.value
  return [...new Set((years ?? []).map(Number).filter(Number.isFinite))].sort((a, b) => a - b)
})
const disabledAccessTargets = computed(() => (
  Object.fromEntries(
    ACCESS_TARGETS.map((target) => [
      target.value,
      !TRAVEL_MODES.some((mode) => metricHasData(metricColumnFor(target.value, mode.value), 'ato')),
    ]),
  )
))
const disabledTravelModes = computed(() => (
  Object.fromEntries(
    TRAVEL_MODES.map((mode) => [
      mode.value,
      !metricHasData(metricColumnFor(accessTarget.value, mode.value), 'ato'),
    ]),
  )
))
const disabledVmtPeriods = computed(() => (
  Object.fromEntries(
    VMT_PERIODS.map((period) => [
      period.value,
      !metricHasData(period.value, 'vmt'),
    ]),
  )
))

onMounted(() => {
  mapInstance.value = initMap('map')
  mapInstance.value.on('style.load', async () => {
    await loadManifestOptions()
    setupMapLayers()
    refreshDataLayer({ fit: true })
  })
})

function setupMapLayers() {
  const map = mapInstance.value
  if (!map) return

  hideBasemapRoadLayers(map)

  const firstLabelId = getFirstLabelLayerId(map)
  const cartoSource = findCartoVectorSource(map)
  for (const datasetId of DATASET_IDS) {
    addDatasetLayers(map, datasetId, manifests[datasetId], firstLabelId)
  }

  if (cartoSource) {
    addRoadLayers(map, cartoSource, firstLabelId)
  }

  setExtentBounds(getSelectionBounds() ?? [[-114.1, 36.9], [-109.0, 42.1]])
  mapReady.value = true
}

function addDatasetLayers(map, datasetId, manifest, firstLabelId) {
  if (!manifest?.files?.pmtiles) return

  const sourceLayer = manifest.pmtiles?.source_layer ?? `${datasetId}_taz`
  const boundarySourceLayer = manifest.boundary_pmtiles?.source_layer ?? `${datasetId}_taz_boundary`
  const sourceId = `${datasetId}-taz-source`
  const boundarySourceId = `${datasetId}-boundary-source`
  const fillLayerId = `${datasetId}-taz-fill`
  const extrusionLayerId = `${datasetId}-taz-extrusion`
  const lineLayerId = `${datasetId}-taz-line`
  const isActive = datasetId === datasetMode.value

  map.addSource(sourceId, {
    type: 'vector',
    url: `pmtiles://${DATA_BASE_URL}/${manifest.files.pmtiles}`,
  })

  map.addLayer({
    id: fillLayerId,
    type: 'fill',
    source: sourceId,
    'source-layer': sourceLayer,
    filter: isActive ? buildMetricFilter() : buildModelAreaFilter(),
    layout: { visibility: getFillVisibility(datasetId, false) },
    paint: {
      'fill-color': buildMetricColorExpression(),
      'fill-antialias': false,
      'fill-opacity': fillOpacity.value,
    },
  }, firstLabelId)

  map.addLayer({
    id: extrusionLayerId,
    type: 'fill-extrusion',
    source: sourceId,
    'source-layer': sourceLayer,
    filter: isActive ? buildMetricFilter() : buildModelAreaFilter(),
    layout: { visibility: getFillVisibility(datasetId, true) },
    paint: {
      'fill-extrusion-color': buildMetricColorExpression(),
      'fill-extrusion-height': buildExtrusionExpression(),
      'fill-extrusion-opacity': fillOpacity.value,
    },
  }, firstLabelId)

  if (manifest.files.boundaries_pmtiles) {
    map.addSource(boundarySourceId, {
      type: 'vector',
      url: `pmtiles://${DATA_BASE_URL}/${manifest.files.boundaries_pmtiles}`,
    })

    map.addLayer({
      id: lineLayerId,
      type: 'line',
      source: boundarySourceId,
      'source-layer': boundarySourceLayer,
      filter: isActive ? buildMetricFilter() : buildModelAreaFilter(),
      minzoom: 6,
      layout: { visibility: getLineVisibility(datasetId) },
      paint: {
        'line-color': '#557799',
        'line-width': 0.8,
        'line-opacity': 0.45,
      },
    }, firstLabelId)
  }
}

async function loadManifestOptions() {
  try {
    const [atoManifest, vmtManifest] = await Promise.all([
      loadDataManifest('ato'),
      loadDataManifest('vmt'),
    ])
    manifests.ato = atoManifest
    manifests.vmt = vmtManifest

    if (!scenarioYears.value.includes(scenarioYear.value)) {
      scenarioYear.value = scenarioYears.value[0]
    }
    if (!modelAreas.value.includes(modelArea.value)) {
      modelArea.value = modelAreas.value[0]
    }
    ensureAvailableMetricSelection()
  } catch (error) {
    console.error('Failed to load data manifests:', error)
  }
}

function metricColumnFor(target, mode) {
  return `${target}_by${mode}`
}

function metricHasData(metricColumn, datasetId = datasetMode.value) {
  const manifest = manifests[datasetId]
  if (!manifest) return true

  return hasMetricData(
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
  if (!activeManifest.value) return

  if (datasetMode.value === 'vmt') {
    if (disabledVmtPeriods.value[vmtPeriod.value]) {
      const nextPeriod = VMT_PERIODS.find((period) => metricHasData(period.value, 'vmt'))?.value
      if (nextPeriod) {
        vmtPeriod.value = nextPeriod
      }
    }
    return
  }

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

function buildMetricColorExpression() {
  const normalizedColumn = `${activeMetricProperty.value}_norm`
  return [
    'case',
    ['has', normalizedColumn],
    [
      'interpolate',
      ['linear'],
      ['to-number', ['get', normalizedColumn]],
      0, activePalette.value[0],
      0.2, activePalette.value[1],
      0.4, activePalette.value[2],
      0.6, activePalette.value[3],
      0.8, activePalette.value[4],
      1, activePalette.value[5],
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

function buildModelAreaFilter() {
  return ['==', ['get', 'ModelArea'], modelArea.value]
}

function buildMetricFilter() {
  return [
    'all',
    ['==', ['get', 'ModelArea'], modelArea.value],
    ['==', ['to-number', ['coalesce', ['get', activeMetricAvailabilityProperty.value], 0]], 1],
  ]
}

function getFillVisibility(datasetId, extrusion) {
  const visible = datasetId === datasetMode.value
    && layerVisible['metric-fill']
    && (extrusion ? is3D.value : !is3D.value)
  return visible ? 'visible' : 'none'
}

function getLineVisibility(datasetId) {
  const visible = datasetId === datasetMode.value && layerVisible['taz-outline']
  return visible ? 'visible' : 'none'
}

function refreshDataLayer({ fit = false } = {}) {
  const map = mapInstance.value
  const manifest = activeManifest.value
  if (!mapReady.value || !map || !manifest) return

  try {
    const result = getSelectionSummary({
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
    console.error('Failed to refresh data layer:', error)
    selectedRows.value = []
    recordCount.value = 0
    minValue.value = 0
    maxValue.value = 0
    hasData.value = false
  }
}

function getManifestBounds() {
  const bounds = activeManifest.value?.bounds
  if (!Array.isArray(bounds) || bounds.length !== 4) return null
  const [minLng, minLat, maxLng, maxLat] = bounds.map(Number)
  if (![minLng, minLat, maxLng, maxLat].every(Number.isFinite)) return null
  return [[minLng, minLat], [maxLng, maxLat]]
}

function getSelectionBounds() {
  const bounds = activeManifest.value?.model_area_bounds?.[modelArea.value]
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

  for (const datasetId of DATASET_IDS) {
    const isActive = datasetId === datasetMode.value
    const filter = isActive ? buildMetricFilter() : buildModelAreaFilter()
    const fillLayerId = `${datasetId}-taz-fill`
    const extrusionLayerId = `${datasetId}-taz-extrusion`
    const lineLayerId = `${datasetId}-taz-line`

    if (map.getLayer(fillLayerId)) {
      map.setFilter(fillLayerId, filter)
      map.setLayoutProperty(fillLayerId, 'visibility', getFillVisibility(datasetId, false))
      if (isActive) {
        map.setPaintProperty(fillLayerId, 'fill-color', buildMetricColorExpression())
        map.setPaintProperty(fillLayerId, 'fill-opacity', fillOpacity.value)
      }
    }
    if (map.getLayer(extrusionLayerId)) {
      map.setFilter(extrusionLayerId, filter)
      map.setLayoutProperty(extrusionLayerId, 'visibility', getFillVisibility(datasetId, true))
      if (isActive) {
        map.setPaintProperty(extrusionLayerId, 'fill-extrusion-color', buildMetricColorExpression())
        map.setPaintProperty(extrusionLayerId, 'fill-extrusion-height', buildExtrusionExpression())
        map.setPaintProperty(extrusionLayerId, 'fill-extrusion-opacity', fillOpacity.value)
      }
    }
    if (map.getLayer(lineLayerId)) {
      map.setFilter(lineLayerId, filter)
      map.setLayoutProperty(lineLayerId, 'visibility', getLineVisibility(datasetId))
    }
  }
}

function onToggleLayer(id) {
  layerVisible[id] = !layerVisible[id]
  const map = mapInstance.value
  if (!map) return

  if (id === 'metric-fill') {
    refreshStyleExpressions()
  }

  if (id === 'taz-outline') {
    refreshStyleExpressions()
  }

  if (id === 'major-roads' && map.getLayer('roads-major')) {
    map.setLayoutProperty('roads-major', 'visibility', layerVisible[id] ? 'visible' : 'none')
  }

}

function on3DChange(value) {
  is3D.value = value
  const map = mapInstance.value
  if (!map) return
  refreshStyleExpressions()
  map.easeTo({ pitch: value ? 45 : 0, duration: 500 })
}

function onOpacityChange(value) {
  fillOpacity.value = value
  refreshStyleExpressions()
}

function onDatasetModeChange(value) {
  if (!DATASET_IDS.includes(value)) return
  datasetMode.value = value
  ensureAvailableMetricSelection()
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

function onVmtPeriodChange(value) {
  if (disabledVmtPeriods.value[value]) return
  vmtPeriod.value = value
}

async function onDownload() {
  if (!hasData.value) return
  isLoading.value = true
  loadingText.value = `Preparing ${activeMetricLabel.value} download...`

  try {
    const result = await loadDataRows({
      datasetId: datasetMode.value,
      scenarioYear: scenarioYear.value,
      modelArea: modelArea.value,
      metricColumn: activeColumn.value,
    })
    const rows = result.rows
    selectedRows.value = rows

    const columns = datasetMode.value === 'ato'
      ? ['ScenarioYear', 'ModelArea', 'SA_TAZID', 'CO_TAZID', activeColumn.value, 'access_value']
      : ['ScenarioYear', 'ModelArea', 'CO_TAZID', activeColumn.value, 'access_value']
    const header = columns.join(',')
    const body = rows
      .map((row) => columns.map((column) => (
        column === activeColumn.value ? row.metric_value : row[column]
      )).join(','))
      .join('\n')
    const blob = new Blob([`${header}\n${body}`], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${datasetMode.value.toUpperCase()}_${modelArea.value.replace(/[^A-Za-z0-9]+/g, '_')}_${scenarioYear.value}_${activeColumn.value}.csv`
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Failed to prepare data download:', error)
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
    link.download = 'Statewide_ATO_VMT_Explorer_Map.png'
    link.click()
  })
  map.triggerRepaint()
}

watch(datasetMode, () => {
  activeTazProperties.value = null
  ensureAvailableMetricSelection()
  refreshDataLayer({ fit: false })
})
watch(scenarioYear, () => {
  ensureAvailableMetricSelection()
  refreshDataLayer({ fit: false })
})
watch(activeColumn, () => refreshDataLayer({ fit: false }))
watch(modelArea, () => {
  activeTazProperties.value = null
  ensureAvailableMetricSelection()
  refreshDataLayer({ fit: true })
})
</script>
