<template>
  <nav id="navbar">
    <img :src="logoUrl" alt="WFRC" />
    <span>Statewide ATO Explorer</span>
  </nav>

  <div id="app-layout">
    <Sidebar
      :scenario-year="scenarioYear"
      :model-area="modelArea"
      :access-target="accessTarget"
      :travel-mode="travelMode"
      :layer-visible="layerVisible"
      @update:scenarioYear="scenarioYear = $event"
      @update:modelArea="modelArea = $event"
      @update:accessTarget="accessTarget = $event"
      @update:travelMode="travelMode = $event"
      @toggle-layer="onToggleLayer"
    />

    <main id="map-area">
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
      <Tooltip v-if="mapReady" :map="mapInstance" :pinned="pinnedTooltip" :active-column="activeColumn" />
      <Legend />
      <LayerControl :layer-visible="layerVisible" @toggle-layer="onToggleLayer" />
      <div class="empty-state" v-if="!hasData">
        <i class="fa-solid fa-circle-info"></i>
        <span>No ATO data loaded</span>
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
import SplashModal from './components/SplashModal.vue'
import Tooltip from './components/Tooltip.vue'
import { ACCESS_PALETTE, ATO_PMTILES_SOURCE_LAYER, ATO_PMTILES_URL, MODEL_AREAS, SCENARIO_YEARS } from './config/constants.js'
import { findCartoVectorSource, getFirstLabelLayerId, initMap, setExtentBounds } from './composables/useMap.js'

const logoUrl = `${import.meta.env.BASE_URL}logo.png`

const scenarioYear = ref(SCENARIO_YEARS[1])
const modelArea = ref(MODEL_AREAS[0])
const accessTarget = ref('Job')
const travelMode = ref('Auto')
const fillOpacity = ref(0.78)
const is3D = ref(false)
const pinnedTooltip = ref(false)
const showSplash = ref(true)
const isLoading = ref(false)
const loadingText = ref('Loading...')
const mapReady = ref(false)
const hasData = ref(false)
const mapInstance = ref(null)

const layerVisible = reactive({
  'ato-fill': true,
  'taz-outline': true,
  'major-roads': true,
  'pmtiles-ato': Boolean(ATO_PMTILES_URL),
})

const activeColumn = computed(() => `${accessTarget.value}_by${travelMode.value}`)

onMounted(() => {
  mapInstance.value = initMap('map')
  mapInstance.value.on('style.load', setupMapLayers)
})

function emptyFeatureCollection() {
  return { type: 'FeatureCollection', features: [] }
}

function setupMapLayers() {
  const map = mapInstance.value
  if (!map) return

  const firstLabelId = getFirstLabelLayerId(map)
  const cartoSource = findCartoVectorSource(map)

  map.addSource('ato-taz-source', {
    type: 'geojson',
    data: emptyFeatureCollection(),
    generateId: true,
  })

  map.addLayer({
    id: 'ato-taz-fill',
    type: 'fill',
    source: 'ato-taz-source',
    layout: { visibility: layerVisible['ato-fill'] && !is3D.value ? 'visible' : 'none' },
    paint: {
      'fill-color': buildAccessColorExpression(),
      'fill-opacity': fillOpacity.value,
    },
  }, firstLabelId)

  map.addLayer({
    id: 'ato-taz-extrusion',
    type: 'fill-extrusion',
    source: 'ato-taz-source',
    layout: { visibility: layerVisible['ato-fill'] && is3D.value ? 'visible' : 'none' },
    paint: {
      'fill-extrusion-color': buildAccessColorExpression(),
      'fill-extrusion-height': buildExtrusionExpression(),
      'fill-extrusion-opacity': fillOpacity.value,
    },
  }, firstLabelId)

  map.addLayer({
    id: 'ato-taz-line',
    type: 'line',
    source: 'ato-taz-source',
    layout: { visibility: layerVisible['taz-outline'] ? 'visible' : 'none' },
    paint: {
      'line-color': '#233A57',
      'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.25, 12, 0.9],
      'line-opacity': 0.65,
    },
  }, firstLabelId)

  if (ATO_PMTILES_URL) {
    const pmtilesUrl = ATO_PMTILES_URL.startsWith('pmtiles://')
      ? ATO_PMTILES_URL
      : `pmtiles://${ATO_PMTILES_URL}`

    map.addSource('pmtiles-ato-source', {
      type: 'vector',
      url: pmtilesUrl,
    })

    map.addLayer({
      id: 'pmtiles-ato-fill',
      type: 'fill',
      source: 'pmtiles-ato-source',
      'source-layer': ATO_PMTILES_SOURCE_LAYER,
      layout: { visibility: layerVisible['pmtiles-ato'] ? 'visible' : 'none' },
      paint: {
        'fill-color': buildAccessColorExpression(),
        'fill-opacity': fillOpacity.value,
      },
    }, firstLabelId)
  }

  if (cartoSource) {
    addRoadLayers(map, cartoSource, firstLabelId)
  }

  setExtentBounds([[-114.1, 36.9], [-109.0, 42.1]])
  mapReady.value = true
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
  return [
    'case',
    ['has', 'access_value'],
    [
      'interpolate',
      ['linear'],
      ['to-number', ['get', 'access_value']],
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
  return [
    'interpolate',
    ['linear'],
    ['to-number', ['coalesce', ['get', 'access_value'], 0]],
    0, 0,
    1, 4500,
  ]
}

function refreshStyleExpressions() {
  const map = mapInstance.value
  if (!map) return
  for (const layer of ['ato-taz-fill', 'pmtiles-ato-fill']) {
    if (map.getLayer(layer)) {
      map.setPaintProperty(layer, 'fill-color', buildAccessColorExpression())
      map.setPaintProperty(layer, 'fill-opacity', fillOpacity.value)
    }
  }
  if (map.getLayer('ato-taz-extrusion')) {
    map.setPaintProperty('ato-taz-extrusion', 'fill-extrusion-color', buildAccessColorExpression())
    map.setPaintProperty('ato-taz-extrusion', 'fill-extrusion-height', buildExtrusionExpression())
    map.setPaintProperty('ato-taz-extrusion', 'fill-extrusion-opacity', fillOpacity.value)
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

  if (id === 'pmtiles-ato' && map.getLayer('pmtiles-ato-fill')) {
    map.setLayoutProperty('pmtiles-ato-fill', 'visibility', layerVisible[id] ? 'visible' : 'none')
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

function onDownload() {
  console.info('Download will be enabled after ATO data is wired in.')
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

watch(activeColumn, refreshStyleExpressions)
</script>
