<template>
  <nav id="navbar">
    <img :src="logoUrl" alt="WFRC" />
    <span>Statewide ATO and VMT Explorer</span>
    <button class="navbar-info-button" type="button" @click="showSplash = true" aria-label="Open site information">
      <i class="fa-solid fa-circle-info"></i>
    </button>
  </nav>

  <div id="app-layout">
    <Sidebar
      :dataset-mode="datasetMode"
      :scenario-years="scenarioYears"
      :model-areas="modelAreas"
      :scenario-year="scenarioYear"
      :model-area="modelArea"
      :geography-type="geographyType"
      :geography-levels="GEOGRAPHY_LEVELS"
      :disabled-model-areas="disabledModelAreas"
      :access-target="accessTarget"
      :travel-mode="travelMode"
      :vmt-pa="vmtPa"
      :vmt-rate="vmtRate"
      :vmt-rate-options="vmtRateOptions"
      :vmt-purpose-group="vmtPurposeGroup"
      :vmt-purpose="vmtPurpose"
      :vmt-purpose-groups="vmtPurposeGroups"
      :vmt-purposes="vmtPurposes"
      :disabled-access-targets="disabledAccessTargets"
      :disabled-travel-modes="disabledTravelModes"
      :disabled-vmt-purposes="disabledVmtPurposes"
      :record-count="recordCount"
      :active-taz-properties="activeTazProperties"
      :dataset-label="activeDatasetLabel"
      :active-column="activeColumn"
      :metric-label="activeMetricLabel"
      :trend-scenario-years="activeModelScenarioYears"
      @update:datasetMode="onDatasetModeChange"
      @update:scenarioYear="scenarioYear = $event"
      @update:modelArea="modelArea = $event"
      @update:geographyType="geographyType = $event"
      @update:accessTarget="onAccessTargetChange"
      @update:travelMode="onTravelModeChange"
      @update:vmtPa="onVmtPaChange"
      @update:vmtRate="onVmtRateChange"
      @update:vmtPurposeGroup="onVmtPurposeGroupChange"
      @update:vmtPurpose="onVmtPurposeChange"
    />

    <main id="map-area" :class="{ 'overview-visible': layerVisible['overview-map'] }">
      <MapControls
        :active-column="activeMetricLabel"
        :exaggeration="extrusionExaggeration"
        :has-data="hasData"
        :is3-d="is3D"
        :opacity="fillOpacity"
        :pinned-tooltip="pinnedTooltip"
        @download="onDownload"
        @screenshot="onScreenshot"
        @update:exaggeration="onExaggerationChange"
        @update:is3D="on3DChange"
        @update:opacity="onOpacityChange"
        @update:pinnedTooltip="pinnedTooltip = $event"
      />
      <div class="active-metric-description">
        <div class="active-metric-description-label">Current View</div>
        <div class="active-metric-description-text">{{ activeMetricDescription }}</div>
      </div>
      <div id="map"></div>
      <Tooltip
        v-if="mapReady"
        :map="mapInstance"
        :pinned="pinnedTooltip"
        :dataset-mode="datasetMode"
        :geography-type="geographyType"
        :model-area="modelArea"
        :scenario-year="scenarioYear"
        :active-column="activeColumn"
        :metric-label="activeMetricLabel"
        :metric-rows-by-geography="activeMetricRowsByGeography"
        @feature-hover="activeTazProperties = $event"
      />
      <Legend
        :has-data="hasData"
        :metric-label="activeMetricLabel"
        :min-value="minValue"
        :max-value="maxValue"
        :palette="activeLegendPalette"
        :custom-items="activeLegendItems"
        :show-mode-toggle="showLegendModeToggle"
        :legend-mode="legendMode"
        :mode-options="LEGEND_MODE_OPTIONS"
        @update:legendMode="onLegendModeChange"
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
      <div class="map-attribution-inline">
        <a href="https://maplibre.org/" target="_blank" rel="noreferrer">MapLibre</a>
        <span>|</span>
        <span>&copy; <a href="https://carto.com/about-carto/" target="_blank" rel="noreferrer">CARTO</a>, &copy; <a href="http://www.openstreetmap.org/about/" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors</span>
      </div>
    </main>
  </div>

  <SplashModal v-if="showSplash" @close="showSplash = false" />
  <div id="global-tooltip"></div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
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
  GEOGRAPHY_LEVELS,
  MODEL_AREAS,
  SCENARIO_YEARS,
  TRAVEL_MODES,
  VMT_PALETTE,
  VMT_PA_OPTIONS,
  VMT_RATE_OPTIONS,
  VMT_PURPOSE_GROUPS,
  VMT_PURPOSES,
} from './config/constants.js'
import {
  getMetricAvailabilityProperty,
  getMetricProperty,
  getSelectionSummary,
  hasMetricData,
  loadDataManifest,
  loadDataRows,
} from './composables/useAtoData.js'
import {
  findCartoVectorSource,
  getFirstLabelLayerId,
  initMap,
  setExtentBounds,
  setInteractionModeControl,
} from './composables/useMap.js'

const logoUrl = `${import.meta.env.BASE_URL}logo.png`
const DATASET_IDS = DATASETS.map((dataset) => dataset.value)
const GEOGRAPHY_TYPE_IDS = GEOGRAPHY_LEVELS.map((level) => level.value)
const ACCESS_TARGET_IDS = ACCESS_TARGETS.map((target) => target.value)
const TRAVEL_MODE_IDS = TRAVEL_MODES.map((mode) => mode.value)
const VMT_PA_IDS = VMT_PA_OPTIONS.map((option) => option.value)
const VMT_RATE_IDS = VMT_RATE_OPTIONS.map((option) => option.value)
const VMT_PURPOSE_GROUP_IDS = VMT_PURPOSE_GROUPS.map((group) => group.value)
const VMT_DAILY_PERIOD = 'DY'
const INTERACTION_MODES = ['pan', 'rotate']
const MAX_TILT = 85
const LEGEND_MODE_OPTIONS = [
  { label: 'Continuous', value: 'continuous' },
  { label: 'Quintiles', value: 'quantiles' },
]
const DEFAULT_LAYER_VISIBLE = {
  'metric-fill': true,
  'taz-outline': true,
  'major-roads': false,
  'overview-map': true,
}

function parseBooleanParam(value, fallback = false) {
  if (value == null) return fallback
  if (['1', 'true', 'yes'].includes(value.toLowerCase())) return true
  if (['0', 'false', 'no'].includes(value.toLowerCase())) return false
  return fallback
}

function parseNumberParam(value, fallback = null) {
  if (value == null) return fallback
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function parseUrlState() {
  const params = new URLSearchParams(window.location.search)
  const dataset = params.get('dataset')
  const year = parseNumberParam(params.get('year'))
  const opacity = parseNumberParam(params.get('opacity'))
  const zoom = parseNumberParam(params.get('zoom'))
  const lng = parseNumberParam(params.get('lng'))
  const lat = parseNumberParam(params.get('lat'))
  const bearing = parseNumberParam(params.get('bearing'))
  const pitch = parseNumberParam(params.get('pitch'))
  const exaggeration = parseNumberParam(params.get('exaggeration'))
  const interaction = params.get('interaction')
  const geographyType = params.get('geography')
  const vmtRate = params.get('rate')

  return {
    datasetMode: DATASET_IDS.includes(dataset) ? dataset : null,
    scenarioYear: Number.isInteger(year) ? year : null,
    modelArea: params.get('area'),
    geographyType: GEOGRAPHY_TYPE_IDS.includes(geographyType) ? geographyType : null,
    accessTarget: ACCESS_TARGET_IDS.includes(params.get('target')) ? params.get('target') : null,
    travelMode: TRAVEL_MODE_IDS.includes(params.get('mode')) ? params.get('mode') : null,
    vmtPa: VMT_PA_IDS.includes(params.get('pa')) ? params.get('pa') : null,
    vmtRate: VMT_RATE_IDS.includes(vmtRate) ? vmtRate : null,
    vmtPurposeGroup: VMT_PURPOSE_GROUP_IDS.includes(params.get('purposeGroup')) ? params.get('purposeGroup') : null,
    vmtPurpose: params.get('purpose'),
    fillOpacity: opacity != null ? Math.max(0, Math.min(1, opacity)) : null,
    exaggeration: exaggeration != null ? Math.max(0.5, Math.min(8, exaggeration)) : null,
    interactionMode: INTERACTION_MODES.includes(interaction) ? interaction : 'pan',
    is3D: parseBooleanParam(params.get('threeD')),
    pinnedTooltip: parseBooleanParam(params.get('pin')),
    layerVisible: {
      'metric-fill': parseBooleanParam(params.get('fill'), DEFAULT_LAYER_VISIBLE['metric-fill']),
      'taz-outline': parseBooleanParam(params.get('outline'), DEFAULT_LAYER_VISIBLE['taz-outline']),
      'major-roads': parseBooleanParam(params.get('roads'), DEFAULT_LAYER_VISIBLE['major-roads']),
      'overview-map': parseBooleanParam(params.get('overview'), DEFAULT_LAYER_VISIBLE['overview-map']),
    },
    mapView: [lng, lat, zoom].every((value) => value != null)
      ? {
          center: [lng, lat],
          zoom,
          bearing: bearing ?? 0,
          pitch: pitch ?? 0,
        }
      : null,
  }
}

const initialUrlState = parseUrlState()
const hasInitialMapView = Boolean(initialUrlState.mapView)

const datasetMode = ref(initialUrlState.datasetMode ?? 'ato')
const scenarioYear = ref(initialUrlState.scenarioYear ?? SCENARIO_YEARS[1])
const modelArea = ref(initialUrlState.modelArea ?? MODEL_AREAS[0])
const geographyType = ref(initialUrlState.geographyType ?? 'TAZ')
const accessTarget = ref(initialUrlState.accessTarget ?? 'Job')
const travelMode = ref(initialUrlState.travelMode ?? 'Auto')
const vmtPa = ref(initialUrlState.vmtPa ?? 'P')
const vmtRate = ref(initialUrlState.vmtRate ?? defaultVmtRateForPa(initialUrlState.vmtPa ?? 'P'))
const vmtPurposeGroup = ref(initialUrlState.vmtPurposeGroup ?? 'PERSON')
const vmtPurpose = ref(initialUrlState.vmtPurpose ?? 'PERSON_ALL')
const interactionMode = ref(initialUrlState.interactionMode ?? 'pan')
const fillOpacity = ref(initialUrlState.fillOpacity ?? 0.78)
const extrusionExaggeration = ref(initialUrlState.exaggeration ?? 1.5)
const legendMode = ref('continuous')
const is3D = ref(initialUrlState.is3D)
const mapPitch = ref(initialUrlState.mapView?.pitch ?? (initialUrlState.is3D ? 45 : 0))
const pinnedTooltip = ref(initialUrlState.pinnedTooltip)
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
const activeMetricRowsByGeography = ref(new Map())
const manifests = reactive({
  ato: null,
  vmt: null,
})
let disposeMouseModeBindings = null
let vmtRowsRequestId = 0

const layerVisible = reactive({
  ...DEFAULT_LAYER_VISIBLE,
  ...initialUrlState.layerVisible,
})

const activeManifest = computed(() => manifests[datasetMode.value])
const activeDataset = computed(() => (
  DATASETS.find((dataset) => dataset.value === datasetMode.value) ?? DATASETS[0]
))
const activeDatasetLabel = computed(() => activeDataset.value.label)
const scenarioYears = computed(() => activeManifest.value?.scenario_years ?? SCENARIO_YEARS)
const modelAreas = computed(() => MODEL_AREAS)
const supportedModelAreas = computed(() => activeManifest.value?.model_areas ?? MODEL_AREAS)
const vmtRateOptions = computed(() => (
  activeManifest.value?.metric_dimensions?.rate_bases ?? VMT_RATE_OPTIONS
))
const vmtPurposeGroups = computed(() => (
  activeManifest.value?.metric_dimensions?.purpose_groups ?? VMT_PURPOSE_GROUPS
))
const allVmtPurposes = computed(() => activeManifest.value?.metric_dimensions?.purposes ?? VMT_PURPOSES)
const vmtPurposes = computed(() => (
  allVmtPurposes.value.filter((purpose) => purpose.group === vmtPurposeGroup.value)
))
const activeColumn = computed(() => (
  datasetMode.value === 'ato'
    ? `${accessTarget.value}_by${travelMode.value}`
    : vmtMetricColumn(vmtPa.value, VMT_DAILY_PERIOD, vmtPurpose.value, vmtRate.value)
))
const activeMetricLabel = computed(() => {
  if (datasetMode.value === 'vmt') {
    const pa = VMT_PA_OPTIONS.find((item) => item.value === vmtPa.value)
    const rate = vmtRateOptions.value.find((item) => item.value === vmtRate.value)
    const purposeGroup = vmtPurposeGroups.value.find((item) => item.value === vmtPurposeGroup.value)
    const purpose = vmtPurposes.value.find((item) => item.value === vmtPurpose.value)
    const purposeLabel = purpose?.is_group_total
      ? purposeGroup?.label
      : purpose?.label ?? vmtPurpose.value
    const rateLabel = rate?.label ?? vmtRate.value
    return vmtRate.value === 'TOTAL'
      ? `${pa?.label ?? vmtPa.value} ${purposeLabel} VMT`
      : `${pa?.label ?? vmtPa.value} ${purposeLabel} VMT ${rateLabel}`
  }

  const target = ACCESS_TARGETS.find((item) => item.value === accessTarget.value)
  const mode = TRAVEL_MODES.find((item) => item.value === travelMode.value)
  return `${target?.label ?? accessTarget.value} by ${mode?.label ?? travelMode.value}`
})
const activeMetricDescription = computed(() => {
  if (datasetMode.value === 'vmt') {
    return buildVmtDescription()
  }

  return buildAtoDescription()
})
const showLegendModeToggle = computed(() => (
  datasetMode.value === 'vmt' && vmtRate.value !== 'TOTAL'
))
const activePalette = computed(() => (
  datasetMode.value === 'vmt' ? VMT_PALETTE : ACCESS_PALETTE
))
const quantilePalette = computed(() => {
  if (datasetMode.value === 'vmt') {
    return ['#a6bddb', '#67a9cf', '#3690c0', '#1f8aab', '#02818a']
  }

  const palette = activePalette.value.length ? activePalette.value : ACCESS_PALETTE
  if (palette.length <= 5) return palette
  return [0, 0.25, 0.5, 0.75, 1].map((ratio) => (
    palette[Math.round(ratio * (palette.length - 1))]
  ))
})
const activeLegendPalette = computed(() => (
  legendMode.value === 'quantiles' && showLegendModeToggle.value
    ? quantilePalette.value
    : activePalette.value
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
const disabledModelAreas = computed(() => (
  Object.fromEntries(
    MODEL_AREAS.map((area) => [
      area,
      datasetMode.value === 'vmt' && !supportedModelAreas.value.includes(area),
    ]),
  )
))
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
const disabledVmtPurposes = computed(() => (
  Object.fromEntries(
    vmtPurposes.value.map((purpose) => [
      purpose.value,
      !metricHasData(vmtMetricColumn(vmtPa.value, VMT_DAILY_PERIOD, purpose.value, vmtRate.value), 'vmt'),
    ]),
  )
))
const currentMetricValues = computed(() => {
  if (datasetMode.value !== 'vmt') return []
  return [...activeMetricRowsByGeography.value.values()]
    .map((row) => Number(row.metric_value))
    .filter((value) => Number.isFinite(value))
})
const quantileBreaks = computed(() => computeQuantileBreaks(currentMetricValues.value, 5))
const activeLegendItems = computed(() => {
  if (legendMode.value !== 'quantiles' || !showLegendModeToggle.value) return []
  return buildQuantileLegendItems()
})

onMounted(() => {
  mapInstance.value = initMap('map', {
    interactionMode: interactionMode.value,
    onInteractionModeChange: onInteractionModeChange,
  })
  mapInstance.value.on('style.load', async () => {
    await loadManifestOptions()
    setupMapLayers()
    refreshDataLayer({ fit: !hasInitialMapView })

    if (hasInitialMapView) {
      applyMapView(initialUrlState.mapView)
    } else if (is3D.value) {
      mapInstance.value?.setPitch(mapPitch.value || 45)
    }

    syncMapUiStateFromMap()
    refreshStyleExpressions()
    applyInteractionMode()
    bindMapUrlSync()
    syncUrlState()
  })
})

onBeforeUnmount(() => {
  disposeMouseModeBindings?.()
})

function applyMapView(view) {
  const map = mapInstance.value
  if (!map || !view) return
  map.jumpTo({
    center: view.center,
    zoom: view.zoom,
    bearing: view.bearing ?? 0,
    pitch: view.pitch ?? 0,
  })
}

function bindMapUrlSync() {
  const map = mapInstance.value
  if (!map) return
  map.on('moveend', () => {
    syncMapUiStateFromMap()
    refreshStyleExpressions()
    syncUrlState()
  })
}

function syncMapUiStateFromMap() {
  const map = mapInstance.value
  if (!map) return

  mapPitch.value = Math.max(0, Math.min(MAX_TILT, map.getPitch()))
  is3D.value = mapPitch.value > 0.5
}

function syncUrlState() {
  const map = mapInstance.value
  if (!map) return

  const url = new URL(window.location.href)
  const params = url.searchParams
  const center = map.getCenter()

  params.set('dataset', datasetMode.value)
  params.set('year', String(scenarioYear.value))
  params.set('area', modelArea.value)
  params.set('geography', geographyType.value)
  params.set('opacity', fillOpacity.value.toFixed(2))
  params.set('exaggeration', extrusionExaggeration.value.toFixed(2))
  params.set('interaction', interactionMode.value)
  params.set('threeD', String(is3D.value))
  params.set('pin', String(pinnedTooltip.value))
  params.set('fill', String(layerVisible['metric-fill']))
  params.set('outline', String(layerVisible['taz-outline']))
  params.set('roads', String(layerVisible['major-roads']))
  params.set('overview', String(layerVisible['overview-map']))
  params.set('lng', center.lng.toFixed(5))
  params.set('lat', center.lat.toFixed(5))
  params.set('zoom', map.getZoom().toFixed(2))
  params.set('bearing', map.getBearing().toFixed(2))
  params.set('pitch', map.getPitch().toFixed(2))

  if (datasetMode.value === 'ato') {
    params.set('target', accessTarget.value)
    params.set('mode', travelMode.value)
    params.delete('pa')
    params.delete('rate')
    params.delete('period')
    params.delete('purposeGroup')
    params.delete('purpose')
  } else {
    params.set('pa', vmtPa.value)
    params.set('rate', vmtRate.value)
    params.delete('period')
    params.set('purposeGroup', vmtPurposeGroup.value)
    params.set('purpose', vmtPurpose.value)
    params.delete('target')
    params.delete('mode')
  }

  window.history.replaceState({}, '', `${url.pathname}?${params.toString()}${url.hash}`)
}

function getOppositeInteractionMode(mode) {
  return mode === 'rotate' ? 'pan' : 'rotate'
}

function applyInteractionMode() {
  disposeMouseModeBindings?.()
  const map = mapInstance.value
  if (!map) return

  map.dragPan.disable()
  map.dragRotate.disable()

  const container = map.getCanvasContainer()
  let dragState = null

  const clampPitch = (value) => Math.max(0, Math.min(MAX_TILT, value))

  const stopDrag = () => {
    dragState = null
    container.style.cursor = interactionMode.value === 'rotate' ? 'crosshair' : 'grab'
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  }

  const onMouseMove = (event) => {
    if (!dragState) return

    const dx = event.clientX - dragState.lastX
    const dy = event.clientY - dragState.lastY
    dragState.lastX = event.clientX
    dragState.lastY = event.clientY

    if (dragState.mode === 'pan') {
      map.panBy([-dx, -dy], { animate: false })
      return
    }

    const nextBearing = map.getBearing() + (dx * 0.45)
    const nextPitch = clampPitch(map.getPitch() - (dy * 0.35))
    map.jumpTo({ bearing: nextBearing, pitch: nextPitch })
    mapPitch.value = nextPitch
    is3D.value = nextPitch > 0.5
  }

  const onMouseUp = () => {
    stopDrag()
    syncMapUiStateFromMap()
    syncUrlState()
  }

  const onMouseDown = (event) => {
    if (event.button !== 0 && event.button !== 2) return

    const dragMode = event.button === 0
      ? interactionMode.value
      : getOppositeInteractionMode(interactionMode.value)

    event.preventDefault()
    map.stop()
    dragState = {
      button: event.button,
      lastX: event.clientX,
      lastY: event.clientY,
      mode: dragMode,
    }
    container.style.cursor = dragMode === 'rotate' ? 'grabbing' : 'grabbing'
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  const onContextMenu = (event) => {
    event.preventDefault()
  }

  container.style.cursor = interactionMode.value === 'rotate' ? 'crosshair' : 'grab'
  container.addEventListener('mousedown', onMouseDown)
  container.addEventListener('contextmenu', onContextMenu)

  disposeMouseModeBindings = () => {
    stopDrag()
    container.style.cursor = ''
    container.removeEventListener('mousedown', onMouseDown)
    container.removeEventListener('contextmenu', onContextMenu)
  }
}

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
  const buildVersion = manifest.build?.tiles_fingerprint
    ?? manifest.build?.metrics_fingerprint
    ?? manifest.build?.generated_at
    ?? null
  const withVersionParam = (path) => {
    if (!buildVersion) return `${DATA_BASE_URL}/${path}`
    const separator = path.includes('?') ? '&' : '?'
    return `${DATA_BASE_URL}/${path}${separator}v=${encodeURIComponent(buildVersion)}`
  }

  map.addSource(sourceId, {
    type: 'vector',
    url: `pmtiles://${withVersionParam(manifest.files.pmtiles)}`,
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
      url: `pmtiles://${withVersionParam(manifest.files.boundaries_pmtiles)}`,
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
        'line-color': '#98a8b8',
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          6, 0.35,
          9, 0.5,
          12, 0.7,
        ],
        'line-opacity': 0.35,
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
    const availableGeographyTypes = activeManifest.value?.geography_types ?? GEOGRAPHY_TYPE_IDS
    if (!availableGeographyTypes.includes(geographyType.value)) {
      geographyType.value = availableGeographyTypes[0] ?? 'TAZ'
    }
    ensureAvailableMetricSelection()
  } catch (error) {
    console.error('Failed to load data manifests:', error)
  }
}

function metricColumnFor(target, mode) {
  return `${target}_by${mode}`
}

function defaultVmtRateForPa(pa) {
  return 'TOTAL'
}

function vmtMetricColumn(pa, period, purpose, rate = 'TOTAL') {
  const baseColumn = `${pa}_${period}_${purpose}`
  if (rate === 'TOTAL') return baseColumn
  return `${baseColumn}__${rate}`
}

function buildAtoDescription() {
  const targetLabel = accessTarget.value === 'HH' ? 'Households' : 'Jobs'
  const modeLabel = {
    Auto: 'a typical auto commute',
    Tran: 'transit',
    Walk: 'walking',
    Bike: 'biking',
  }[travelMode.value] ?? travelMode.value.toLowerCase()

  if (travelMode.value === 'Auto') {
    return `${targetLabel} within ${modeLabel} (${formatViewContext()}).`
  }

  return `${targetLabel} reachable by ${modeLabel} (${formatViewContext()}).`
}

function buildVmtDescription() {
  const directionLabel = vmtPa.value === 'A' ? 'attracted to' : 'produced by'
  const purposeDescription = getVmtPurposeDescription(vmtPurpose.value, vmtPurposeGroup.value)
  const rateDescription = getVmtRateDescription(vmtRate.value)
  return `Vehicle miles traveled ${directionLabel} ${purposeDescription}${rateDescription} (${formatViewContext()}).`
}

function getVmtRateDescription(rateValue) {
  const rateDescriptions = {
    TOTAL: '',
    PER_HH: ' per household',
    PER_JOB: ' per job',
    PER_HHEQ: ' per household equivalent',
  }
  return rateDescriptions[rateValue] ?? ''
}

function formatViewContext() {
  const geographyLabel = geographyType.value === 'CITY' ? 'City Level' : 'TAZ Level'
  return `${geographyLabel}, ${scenarioYear.value}`
}

function getVmtPurposeDescription(purposeValue, purposeGroupValue) {
  const purposeDescriptions = {
    PERSON_ALL: 'all household trips',
    HBC: 'home-based college trips',
    HBS_Pr: 'home-based primary school trips',
    HBS_Sc: 'home-based secondary school trips',
    HBS: 'home-based school trips',
    HBW: 'home-based work trips',
    NHB: 'non-home-based trips',
    HBO: 'other home-based trips',
    BUS: 'long-distance bus trips',
    OTH: 'other trips',
    REC: 'recreation trips',
    XI: 'external-internal trips',
    IX: 'internal-external trips',
    TRUCK_ALL: 'all truck trips',
    LT: 'light truck trips',
    MD: 'medium truck trips',
    HV: 'heavy truck trips',
    OTHER_ALL: 'all other trips',
  }

  if (purposeDescriptions[purposeValue]) {
    return purposeDescriptions[purposeValue]
  }

  const purposeGroupDescriptions = {
    PERSON: 'household trips',
    TRUCK: 'truck trips',
    OTHER: 'other trips',
  }

  return purposeGroupDescriptions[purposeGroupValue] ?? 'selected trips'
}

function metricHasData(metricColumn, datasetId = datasetMode.value) {
  const manifest = manifests[datasetId]
  if (!manifest) return true

  return hasMetricData(
    manifest,
    scenarioYear.value,
    modelArea.value,
    geographyType.value,
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
    if (disabledModelAreas.value[modelArea.value]) {
      modelArea.value = activeManifest.value.model_areas?.[0] ?? 'Statewide'
    }
    if (!VMT_PA_IDS.includes(vmtPa.value)) {
      vmtPa.value = 'P'
    }
    const availableRateIds = vmtRateOptions.value.map((option) => option.value)
    if (!availableRateIds.includes(vmtRate.value)) {
      vmtRate.value = defaultVmtRateForPa(vmtPa.value)
    }
    if (!vmtPurposeGroups.value.some((group) => group.value === vmtPurposeGroup.value)) {
      vmtPurposeGroup.value = vmtPurposeGroups.value[0]?.value ?? 'PERSON'
    }
    const purposeFromUrl = allVmtPurposes.value.find((purpose) => (
      purpose.value === vmtPurpose.value
    ))
    if (
      purposeFromUrl?.group
      && vmtPurposeGroups.value.some((group) => group.value === purposeFromUrl.group)
      && purposeFromUrl.group !== vmtPurposeGroup.value
    ) {
      vmtPurposeGroup.value = purposeFromUrl.group
    }
    if (!vmtPurposes.value.some((purpose) => purpose.value === vmtPurpose.value)) {
      vmtPurpose.value = vmtPurposes.value[0]?.value ?? `${vmtPurposeGroup.value}_ALL`
    }
    if (disabledVmtPurposes.value[vmtPurpose.value]) {
      const nextPurpose = vmtPurposes.value.find((purpose) => (
        metricHasData(vmtMetricColumn(vmtPa.value, VMT_DAILY_PERIOD, purpose.value, vmtRate.value), 'vmt')
      ))?.value
      if (nextPurpose) {
        vmtPurpose.value = nextPurpose
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
  const valueColumn = activeMetricProperty.value
  const maskExpression = ['==', ['to-number', ['coalesce', ['get', 'StatewideVmtMasked'], 0]], 1]

  if (datasetMode.value === 'vmt') {
    const valueExpression = buildVmtTileValueExpression()
    const quantileExpression = buildQuantileColorExpression(valueExpression)
    if (quantileExpression) {
      if (modelArea.value === 'Statewide') {
        return [
          'case',
          maskExpression,
          '#ffffff',
          ['has', getVmtBaseMetricProperty()],
          quantileExpression,
          '#d9d9d9',
        ]
      }

      return [
        'case',
        ['has', getVmtBaseMetricProperty()],
        quantileExpression,
        '#d9d9d9',
      ]
    }
    if (!(Number.isFinite(minValue.value) && Number.isFinite(maxValue.value)) || maxValue.value <= minValue.value) {
      return [
        'case',
        ['has', getVmtBaseMetricProperty()],
        activePalette.value[activePalette.value.length - 1] ?? '#d9d9d9',
        '#d9d9d9',
      ]
    }

    const valueRamp = buildColorRampExpression(
      valueExpression,
      minValue.value,
      maxValue.value,
    )

    if (modelArea.value === 'Statewide') {
      return [
        'case',
        maskExpression,
        '#ffffff',
        ['has', getVmtBaseMetricProperty()],
        valueRamp,
        '#d9d9d9',
      ]
    }

    return [
      'case',
      ['has', getVmtBaseMetricProperty()],
      valueRamp,
      '#d9d9d9',
    ]
  }

  if (datasetMode.value === 'vmt' && modelArea.value === 'Statewide') {
    return [
      'case',
      maskExpression,
      '#ffffff',
      ['has', `${valueColumn}_norm`],
      buildColorRampExpression(['to-number', ['get', `${valueColumn}_norm`]]),
      '#d9d9d9',
    ]
  }

  return [
    'case',
    ['has', `${valueColumn}_norm`],
    buildColorRampExpression(['to-number', ['get', `${valueColumn}_norm`]]),
    '#d9d9d9',
  ]
}

function buildColorRampExpression(inputExpression, minStop = 0, maxStop = 1) {
  const palette = activePalette.value.length ? activePalette.value : ACCESS_PALETTE
  const spread = maxStop - minStop
  const stops = palette.flatMap((color, index) => {
    const ratio = palette.length > 1 ? index / (palette.length - 1) : 0
    const stop = spread > 0 ? minStop + (ratio * spread) : minStop
    return [Number(stop.toFixed(4)), color]
  })

  return [
    'interpolate',
    ['linear'],
    inputExpression,
    ...stops,
  ]
}

function quantile(sortedValues, ratio) {
  if (!sortedValues.length) return 0
  const position = (sortedValues.length - 1) * ratio
  const lowerIndex = Math.floor(position)
  const upperIndex = Math.ceil(position)
  const lowerValue = sortedValues[lowerIndex]
  const upperValue = sortedValues[upperIndex]
  if (lowerIndex === upperIndex) return lowerValue
  return lowerValue + ((upperValue - lowerValue) * (position - lowerIndex))
}

function computeQuantileBreaks(values, binCount = 5) {
  if (legendMode.value !== 'quantiles' || !showLegendModeToggle.value) return []
  const positiveValues = values
    .filter((value) => Number.isFinite(value) && value > 0)
    .sort((a, b) => a - b)
  if (positiveValues.length < 2) return []

  return Array.from({ length: binCount - 1 }, (_, index) => (
    quantile(positiveValues, (index + 1) / binCount)
  ))
}

function buildQuantileColorExpression(valueExpression) {
  if (legendMode.value !== 'quantiles' || !showLegendModeToggle.value) return null
  if (!quantileBreaks.value.length) return null

  const palette = quantilePalette.value.length ? quantilePalette.value : VMT_PALETTE
  const expression = ['case', ['<=', valueExpression, 0], palette[0]]

  quantileBreaks.value.forEach((threshold, index) => {
    expression.push(['<=', valueExpression, threshold], palette[Math.min(index, palette.length - 1)])
  })

  expression.push(palette[Math.min(quantileBreaks.value.length, palette.length - 1)])
  return expression
}

function formatLegendValue(value) {
  if (!Number.isFinite(value)) return '0'
  if (Math.abs(value) >= 100) return Math.round(value).toLocaleString()
  if (Math.abs(value) >= 10) return value.toFixed(1).replace(/\.0$/, '')
  return value.toFixed(2).replace(/0$/, '').replace(/\.0$/, '')
}

function buildQuantileLegendItems() {
  const palette = quantilePalette.value.length ? quantilePalette.value : VMT_PALETTE
  const positiveValues = currentMetricValues.value
    .filter((value) => Number.isFinite(value) && value > 0)
    .sort((a, b) => a - b)

  if (!positiveValues.length || !quantileBreaks.value.length) return []

  const items = []
  let lowerBound = 0

  quantileBreaks.value.forEach((threshold, index) => {
    items.push({
      color: palette[Math.min(index, palette.length - 1)],
      label: `${formatLegendValue(lowerBound)} to ${formatLegendValue(threshold)}`,
    })
    lowerBound = threshold
  })

  items.push({
    color: palette[Math.min(quantileBreaks.value.length, palette.length - 1)],
    label: `${formatLegendValue(lowerBound)}+`,
  })

  return items
}

function buildExtrusionExpression() {
  if (datasetMode.value === 'vmt') {
    if (!(Number.isFinite(minValue.value) && Number.isFinite(maxValue.value)) || maxValue.value <= minValue.value) {
      return 0
    }

    return [
      'interpolate',
      ['linear'],
      buildVmtTileValueExpression(),
      minValue.value, 0,
      maxValue.value, 4500 * extrusionExaggeration.value,
    ]
  }

  const normalizedColumn = `${activeMetricProperty.value}_norm`
  return [
    'interpolate',
    ['linear'],
    ['to-number', ['coalesce', ['get', normalizedColumn], 0]],
    0, 0,
    1, 4500 * extrusionExaggeration.value,
  ]
}

function getVmtBaseMetricColumn() {
  return `${vmtPa.value}_${VMT_DAILY_PERIOD}_${vmtPurpose.value}`
}

function getVmtBaseMetricProperty() {
  return getMetricProperty(scenarioYear.value, getVmtBaseMetricColumn())
}

function getVmtDenominatorProperty() {
  const denominatorByRate = {
    PER_HH: 'TOTHH',
    PER_JOB: 'TOTEMP',
    PER_HHEQ: 'HH_EQUIV',
  }
  const denominatorColumn = denominatorByRate[vmtRate.value]
  return denominatorColumn ? getMetricProperty(scenarioYear.value, denominatorColumn) : null
}

function buildVmtTileValueExpression() {
  const baseMetricProperty = getVmtBaseMetricProperty()
  const denominatorProperty = getVmtDenominatorProperty()

  if (!denominatorProperty || vmtRate.value === 'TOTAL') {
    return ['to-number', ['coalesce', ['get', baseMetricProperty], 0]]
  }

  return [
    'case',
    ['>', ['to-number', ['coalesce', ['get', denominatorProperty], 0]], 0],
    [
      '/',
      ['to-number', ['coalesce', ['get', baseMetricProperty], 0]],
      ['to-number', ['coalesce', ['get', denominatorProperty], 0]],
    ],
    0,
  ]
}

function buildModelAreaFilter() {
  return [
    'all',
    ['==', ['get', 'ModelArea'], modelArea.value],
    ['==', ['get', 'GeographyType'], geographyType.value],
  ]
}

function buildMetricFilter() {
  if (datasetMode.value === 'vmt') {
    return [
      'all',
      ['==', ['get', 'ModelArea'], modelArea.value],
      ['==', ['get', 'GeographyType'], geographyType.value],
    ]
  }

  return [
    'all',
    ['==', ['get', 'ModelArea'], modelArea.value],
    ['==', ['get', 'GeographyType'], geographyType.value],
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
      geographyType: geographyType.value,
      metricColumn: activeColumn.value,
    })

    selectedRows.value = []
    activeMetricRowsByGeography.value = new Map()
    const requestId = ++vmtRowsRequestId
    recordCount.value = result.recordCount
    minValue.value = result.minValue
    maxValue.value = result.maxValue
    hasData.value = result.hasData
    if (datasetMode.value === 'vmt' && result.hasData) {
      loadActiveVmtRowsByGeography(requestId)
    }
    refreshStyleExpressions()
    setExtentBounds(getSelectionBounds() ?? getManifestBounds())

    if (fit) {
      fitToSelectionBounds()
    }
  } catch (error) {
    console.error('Failed to refresh data layer:', error)
    selectedRows.value = []
    activeMetricRowsByGeography.value = new Map()
    vmtRowsRequestId += 1
    recordCount.value = 0
    minValue.value = 0
    maxValue.value = 0
    hasData.value = false
  }
}

async function loadActiveVmtRowsByGeography(requestId) {
  try {
    const years = activeModelScenarioYears.value.length
      ? activeModelScenarioYears.value
      : [scenarioYear.value]
    const results = await Promise.all(
      years.map((year) => loadDataRows({
        datasetId: 'vmt',
        scenarioYear: year,
        modelArea: modelArea.value,
        geographyType: geographyType.value,
        metricColumn: activeColumn.value,
      })),
    )
    const rowsByGeography = new Map()

    for (const result of results) {
      for (const row of result.rows) {
        const geographyId = String(row.GeographyId ?? row.CO_TAZID ?? '')
        if (!geographyId) continue

        const rowScenarioYear = Number(row.ScenarioYear)
        const valueProperty = getMetricProperty(rowScenarioYear, activeColumn.value)
        const availabilityProperty = getMetricAvailabilityProperty(rowScenarioYear, activeColumn.value)
        const existing = rowsByGeography.get(geographyId) ?? {
          GeographyId: geographyId,
          GeographyName: row.GeographyName ?? geographyId,
          GeographyType: row.GeographyType ?? geographyType.value,
          CO_TAZID: row.CO_TAZID,
          ModelArea: row.ModelArea ?? modelArea.value,
        }

        existing[valueProperty] = row.metric_value
        existing[availabilityProperty] = 1
        if (rowScenarioYear === Number(scenarioYear.value)) {
          existing.metric_value = row.metric_value
          existing.access_value = row.access_value
          existing[activeColumn.value] = row.metric_value
        }
        rowsByGeography.set(geographyId, existing)
      }
    }

    if (requestId === vmtRowsRequestId) {
      activeMetricRowsByGeography.value = rowsByGeography
    }
  } catch (error) {
    console.warn('Failed to load VMT hover values:', error)
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
  const geographyKey = `${modelArea.value}|${geographyType.value}`
  const bounds = activeManifest.value?.model_area_geography_bounds?.[geographyKey]
    ?? activeManifest.value?.model_area_bounds?.[modelArea.value]
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

  syncUrlState()
}

function on3DChange(value) {
  is3D.value = value
  const map = mapInstance.value
  if (!map) return
  refreshStyleExpressions()
  const nextPitch = value ? Math.max(mapPitch.value, 55) : 0
  mapPitch.value = nextPitch
  map.easeTo({ pitch: nextPitch, duration: 500 })
  syncUrlState()
}

function onOpacityChange(value) {
  fillOpacity.value = value
  refreshStyleExpressions()
  syncUrlState()
}

function onExaggerationChange(value) {
  extrusionExaggeration.value = Math.max(0.5, Math.min(8, value))
  refreshStyleExpressions()
  syncUrlState()
}

function onInteractionModeChange(value) {
  if (!INTERACTION_MODES.includes(value)) return
  interactionMode.value = value
  setInteractionModeControl(value)
  applyInteractionMode()
  syncUrlState()
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

function onVmtPaChange(value) {
  if (!VMT_PA_IDS.includes(value)) return
  const shouldResetRate = ['PER_HH', 'PER_JOB'].includes(vmtRate.value)
  vmtPa.value = value
  if (shouldResetRate) {
    vmtRate.value = defaultVmtRateForPa(value)
  }
  ensureAvailableMetricSelection()
}

function onVmtRateChange(value) {
  if (!VMT_RATE_IDS.includes(value)) return
  vmtRate.value = value
  ensureAvailableMetricSelection()
}

function onVmtPurposeGroupChange(value) {
  if (!vmtPurposeGroups.value.some((group) => group.value === value)) return
  vmtPurposeGroup.value = value
  vmtPurpose.value = vmtPurposes.value[0]?.value ?? `${value}_ALL`
  ensureAvailableMetricSelection()
}

function onVmtPurposeChange(value) {
  if (disabledVmtPurposes.value[value]) return
  vmtPurpose.value = value
  ensureAvailableMetricSelection()
}

function onLegendModeChange(value) {
  if (!LEGEND_MODE_OPTIONS.some((option) => option.value === value)) return
  legendMode.value = value
  refreshStyleExpressions()
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
      geographyType: geographyType.value,
      metricColumn: activeColumn.value,
    })
    const rows = result.rows
    selectedRows.value = rows

    const columns = [
      'ScenarioYear',
      'ModelArea',
      'GeographyType',
      'GeographyName',
      'GeographyId',
      ...(datasetMode.value === 'vmt' ? ['TOTHH', 'TOTEMP', 'HH_EQUIV'] : []),
      ...(geographyType.value === 'TAZ'
        ? datasetMode.value === 'ato'
          ? ['SA_TAZID', 'CO_TAZID']
          : ['CO_TAZID']
        : []),
      activeColumn.value,
      'access_value',
    ]
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
    link.download = `${datasetMode.value.toUpperCase()}_${modelArea.value.replace(/[^A-Za-z0-9]+/g, '_')}_${geographyType.value}_${scenarioYear.value}_${activeColumn.value}.csv`
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
  syncUrlState()
})
watch(scenarioYear, () => {
  ensureAvailableMetricSelection()
  refreshDataLayer({ fit: false })
  syncUrlState()
})
watch(activeColumn, () => {
  refreshDataLayer({ fit: false })
  syncUrlState()
})
watch(activeMetricRowsByGeography, () => {
  if (legendMode.value === 'quantiles' && showLegendModeToggle.value) {
    refreshStyleExpressions()
  }
})
watch(modelArea, () => {
  activeTazProperties.value = null
  ensureAvailableMetricSelection()
  refreshDataLayer({ fit: true })
  syncUrlState()
})
watch(geographyType, () => {
  activeTazProperties.value = null
  ensureAvailableMetricSelection()
  refreshDataLayer({ fit: true })
  syncUrlState()
})
watch(showLegendModeToggle, (visible) => {
  if (!visible && legendMode.value !== 'continuous') {
    legendMode.value = 'continuous'
  }
})
watch(pinnedTooltip, () => syncUrlState())
</script>
