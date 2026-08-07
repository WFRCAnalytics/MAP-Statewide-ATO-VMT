<template>
  <Teleport to="#map-area">
    <div id="pinned-tooltip-container" v-if="pinned">
      <div id="pinned-tooltip-header">
        <i class="fa-solid fa-thumbtack"></i>
        <span>TAZ Details</span>
      </div>
      <div id="pinned-tooltip-content" v-html="pinnedContent || placeholder"></div>
    </div>
  </Teleport>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import { getMetricProperty } from '../composables/useAtoData.js'

const props = defineProps({
  map: { type: Object, required: true },
  pinned: { type: Boolean, default: false },
  datasetMode: { type: String, default: 'ato' },
  modelArea: { type: String, required: true },
  scenarioYear: { type: Number, required: true },
  activeColumn: { type: String, required: true },
  metricLabel: { type: String, required: true },
  metricRowsByTaz: { type: Object, default: null },
})

const emit = defineEmits(['feature-hover'])

const pinnedContent = ref('')
const placeholder = '<div class="tooltip-placeholder"><i class="fa-solid fa-hand-pointer"></i><br>Hover over a TAZ</div>'
const hoverLayers = ['ato-taz-fill', 'ato-taz-extrusion', 'vmt-taz-fill', 'vmt-taz-extrusion']

let popup = null
let hoverHandler = null
let leaveHandler = null
let lastProperties = null

function formatValue(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 'No value'
  return Math.round(number).toLocaleString()
}

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character])
}

function buildHTML(properties) {
  const tazId = properties.CO_TAZID ?? properties.co_tazid ?? properties.tazid ?? 'Unknown'
  const value = properties[getMetricProperty(props.scenarioYear, props.activeColumn)]
    ?? properties[props.activeColumn]
    ?? properties.access_value
  const modelArea = properties.ModelArea ?? props.modelArea
  return `
    <div class="tooltip-card">
      <div class="tooltip-card-header">
        <span>CO_TAZID ${escapeHTML(tazId)}</span>
        <small>${escapeHTML(modelArea)}</small>
      </div>
      <div class="tooltip-card-row">
        <span>${props.scenarioYear} ${escapeHTML(props.metricLabel)}</span>
        <strong>${escapeHTML(formatValue(value))}</strong>
      </div>
    </div>
  `
}

function getTazId(properties) {
  const value = properties.CO_TAZID ?? properties.co_tazid ?? properties.tazid
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function enrichProperties(properties) {
  if (props.datasetMode !== 'vmt') return properties

  const tazId = getTazId(properties)
  if (tazId == null) return properties

  const metricProperties = props.metricRowsByTaz?.get?.(tazId)
  return metricProperties ? { ...properties, ...metricProperties } : properties
}

function refreshPinnedContent() {
  if (props.pinned && lastProperties) {
    lastProperties = enrichProperties(lastProperties)
    pinnedContent.value = buildHTML(lastProperties)
  }
}

onMounted(() => {
  popup = new maplibregl.Popup({
    closeButton: false,
    closeOnClick: false,
    maxWidth: '300px',
    offset: [0, -5],
  })

  hoverHandler = (event) => {
    if (!event.features?.length) return
    props.map.getCanvas().style.cursor = 'pointer'
    lastProperties = enrichProperties(event.features[0].properties ?? {})
    emit('feature-hover', lastProperties)
    const html = buildHTML(lastProperties)
    if (props.pinned) {
      pinnedContent.value = html
    } else {
      popup.setLngLat(event.lngLat).setHTML(html).addTo(props.map)
    }
  }

  leaveHandler = () => {
    props.map.getCanvas().style.cursor = ''
    if (!props.pinned) {
      popup.remove()
    }
  }

  for (const layer of hoverLayers) {
    if (!props.map.getLayer(layer)) continue
    props.map.on('mousemove', layer, hoverHandler)
    props.map.on('mouseleave', layer, leaveHandler)
  }
})

onUnmounted(() => {
  popup?.remove()
  for (const layer of hoverLayers) {
    if (!props.map.getLayer(layer)) continue
    props.map.off('mousemove', layer, hoverHandler)
    props.map.off('mouseleave', layer, leaveHandler)
  }
})

watch(() => props.pinned, (pinned) => {
  if (!pinned) {
    pinnedContent.value = ''
    popup?.remove()
  } else {
    refreshPinnedContent()
  }
})

watch(
  [
    () => props.scenarioYear,
    () => props.activeColumn,
    () => props.metricLabel,
    () => props.metricRowsByTaz,
  ],
  refreshPinnedContent,
)

watch([() => props.modelArea, () => props.datasetMode], () => {
  lastProperties = null
  pinnedContent.value = ''
  emit('feature-hover', null)
  popup?.remove()
})
</script>
