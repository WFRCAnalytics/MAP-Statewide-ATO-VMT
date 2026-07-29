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
import {
  getAtoMetricAvailabilityProperty,
  getAtoMetricProperty,
} from '../composables/useAtoData.js'

const props = defineProps({
  map: { type: Object, required: true },
  pinned: { type: Boolean, default: false },
  modelArea: { type: String, required: true },
  scenarioYear: { type: Number, required: true },
  scenarioYears: { type: Array, default: () => [] },
  activeColumn: { type: String, required: true },
})

const pinnedContent = ref('')
const placeholder = '<div class="tooltip-placeholder"><i class="fa-solid fa-hand-pointer"></i><br>Hover over a TAZ</div>'
const hoverLayers = ['ato-taz-fill', 'ato-taz-extrusion']

let popup = null
let hoverHandler = null
let leaveHandler = null
let lastProperties = null

function formatValue(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 'No value'
  return Math.round(number).toLocaleString()
}

function formatCompactValue(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return ''
  const absolute = Math.abs(number)
  if (absolute >= 1_000_000) {
    return `${(number / 1_000_000).toFixed(absolute >= 10_000_000 ? 0 : 1)}M`
  }
  if (absolute >= 1_000) {
    return `${(number / 1_000).toFixed(absolute >= 100_000 ? 0 : 1)}k`
  }
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

function getChartYears() {
  const years = props.scenarioYears.length ? props.scenarioYears : [props.scenarioYear]
  return [...new Set(years.map(Number).filter(Number.isFinite))].sort((a, b) => a - b)
}

function getYearMetricValue(properties, year) {
  const valueProperty = getAtoMetricProperty(year, props.activeColumn)
  const availabilityProperty = getAtoMetricAvailabilityProperty(year, props.activeColumn)
  const availability = properties[availabilityProperty]
  const isAvailable = availability === undefined || availability === null || Number(availability) === 1
  const value = Number(properties[valueProperty])

  if (!isAvailable || !Number.isFinite(value)) return null
  return value
}

function buildYearSeries(properties) {
  return getChartYears()
    .map((year) => ({
      year,
      value: getYearMetricValue(properties, year),
    }))
    .filter((point) => point.value !== null)
}

function buildLineChart(properties) {
  const series = buildYearSeries(properties)

  if (!series.length) {
    return `
      <div class="tooltip-chart">
        <div class="tooltip-chart-title">ATO trend</div>
        <div class="tooltip-chart-empty">No year values available</div>
      </div>
    `
  }

  const width = 248
  const height = 96
  const left = 38
  const right = 14
  const top = 12
  const bottom = 22
  const innerWidth = width - left - right
  const innerHeight = height - top - bottom
  const years = series.map((point) => point.year)
  const values = series.map((point) => point.value)
  const minYear = Math.min(...years)
  const maxYear = Math.max(...years)
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  const yearSpread = maxYear - minYear
  const valueSpread = maxValue - minValue

  const scaleX = (year) => (
    yearSpread > 0
      ? left + ((year - minYear) / yearSpread) * innerWidth
      : left + innerWidth / 2
  )
  const scaleY = (value) => (
    valueSpread > 0
      ? top + ((maxValue - value) / valueSpread) * innerHeight
      : top + innerHeight / 2
  )

  const points = series.map((point) => ({
    ...point,
    x: scaleX(point.year),
    y: scaleY(point.value),
    current: Number(point.year) === Number(props.scenarioYear),
  }))
  const linePoints = points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' ')
  const line = points.length > 1
    ? `<polyline class="tooltip-chart-line" points="${linePoints}"></polyline>`
    : ''
  const circles = points.map((point) => `
    <circle
      class="tooltip-chart-point${point.current ? ' current' : ''}"
      cx="${point.x.toFixed(1)}"
      cy="${point.y.toFixed(1)}"
      r="${point.current ? 4.5 : 3.2}"
    >
      <title>${point.year}: ${escapeHTML(formatValue(point.value))}</title>
    </circle>
  `).join('')
  const labels = points.map((point) => `
    <text
      class="tooltip-chart-year${point.current ? ' current' : ''}"
      x="${point.x.toFixed(1)}"
      y="${height - 5}"
    >${point.year}</text>
  `).join('')

  return `
    <div class="tooltip-chart">
      <div class="tooltip-chart-title">
        <span>ATO trend</span>
        <strong>${minYear}${minYear === maxYear ? '' : `-${maxYear}`}</strong>
      </div>
      <svg class="tooltip-year-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHTML(props.activeColumn)} by year">
        <line class="tooltip-chart-grid" x1="${left}" y1="${top}" x2="${width - right}" y2="${top}"></line>
        <line class="tooltip-chart-grid" x1="${left}" y1="${top + innerHeight}" x2="${width - right}" y2="${top + innerHeight}"></line>
        <text class="tooltip-chart-value-label" x="4" y="${top + 4}">${escapeHTML(formatCompactValue(maxValue))}</text>
        <text class="tooltip-chart-value-label" x="4" y="${top + innerHeight + 4}">${escapeHTML(formatCompactValue(minValue))}</text>
        ${line}
        ${circles}
        ${labels}
      </svg>
    </div>
  `
}

function buildHTML(properties) {
  const tazId = properties.CO_TAZID ?? properties.co_tazid ?? properties.tazid ?? 'Unknown'
  const value = properties[getAtoMetricProperty(props.scenarioYear, props.activeColumn)]
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
        <span>${props.scenarioYear} ${escapeHTML(props.activeColumn)}</span>
        <strong>${escapeHTML(formatValue(value))}</strong>
      </div>
      ${buildLineChart(properties)}
    </div>
  `
}

function refreshPinnedContent() {
  if (props.pinned && lastProperties) {
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
    lastProperties = event.features[0].properties ?? {}
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
  [() => props.scenarioYear, () => props.activeColumn, () => props.scenarioYears],
  refreshPinnedContent,
)

watch(() => props.modelArea, () => {
  lastProperties = null
  pinnedContent.value = ''
  popup?.remove()
})
</script>
