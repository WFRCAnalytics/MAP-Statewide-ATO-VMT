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

const props = defineProps({
  map: { type: Object, required: true },
  pinned: { type: Boolean, default: false },
  activeColumn: { type: String, required: true },
})

const pinnedContent = ref('')
const placeholder = '<div class="tooltip-placeholder"><i class="fa-solid fa-hand-pointer"></i><br>Hover over a TAZ</div>'
const hoverLayers = ['ato-taz-fill', 'ato-taz-extrusion', 'pmtiles-ato-fill']

let popup = null
let hoverHandler = null
let leaveHandler = null

function formatValue(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 'No value'
  return Math.round(number).toLocaleString()
}

function buildHTML(properties) {
  const tazId = properties.CO_TAZID ?? properties.co_tazid ?? properties.tazid ?? 'Unknown'
  const value = properties.access_value ?? properties[props.activeColumn]
  return `
    <div class="tooltip-card">
      <div class="tooltip-card-header">CO_TAZID ${tazId}</div>
      <div class="tooltip-card-row">
        <span>${props.activeColumn}</span>
        <strong>${formatValue(value)}</strong>
      </div>
    </div>
  `
}

onMounted(() => {
  popup = new maplibregl.Popup({
    closeButton: false,
    closeOnClick: false,
    maxWidth: '280px',
    offset: [0, -5],
  })

  hoverHandler = (event) => {
    if (!event.features?.length) return
    props.map.getCanvas().style.cursor = 'pointer'
    const html = buildHTML(event.features[0].properties ?? {})
    if (props.pinned) {
      pinnedContent.value = html
    } else {
      popup.setLngLat(event.lngLat).setHTML(html).addTo(props.map)
    }
  }

  leaveHandler = () => {
    props.map.getCanvas().style.cursor = ''
    if (props.pinned) {
      pinnedContent.value = ''
    } else {
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
  }
})
</script>
