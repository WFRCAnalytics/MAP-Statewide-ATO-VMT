<template>
  <section class="sidebar-trend-panel">
    <div class="sidebar-panel-heading">
      <i class="fa-solid fa-chart-line"></i>
      <span>{{ geographyLabel }} Trend</span>
      <small>{{ datasetLabel }}</small>
    </div>

    <div v-if="properties" class="sidebar-trend-body">
      <div class="sidebar-taz-summary">
        <div>
          <span>{{ geographyLabel }}</span>
          <strong>{{ geographyName }}</strong>
        </div>
        <div>
          <span>{{ scenarioYear }}</span>
          <strong>{{ formatValue(currentValue) }}</strong>
        </div>
      </div>
      <div class="sidebar-trend-metric">{{ metricLabel }}</div>

      <div v-if="chart.hasSeries" class="tooltip-chart sidebar-tooltip-chart">
        <div class="tooltip-chart-title">
          <span>{{ datasetLabel }} trend</span>
          <strong>{{ chart.minYear }}{{ chart.minYear === chart.maxYear ? '' : `-${chart.maxYear}` }}</strong>
        </div>
        <svg
          class="tooltip-year-chart"
          :viewBox="`0 0 ${chart.width} ${chart.height}`"
          role="img"
          :aria-label="`${metricLabel} by year`"
        >
          <line class="tooltip-chart-grid" :x1="chart.left" :y1="chart.top" :x2="chart.width - chart.right" :y2="chart.top"></line>
          <line class="tooltip-chart-grid" :x1="chart.left" :y1="chart.top + chart.innerHeight" :x2="chart.width - chart.right" :y2="chart.top + chart.innerHeight"></line>
          <text class="tooltip-chart-value-label" x="4" :y="chart.top + 4">{{ formatCompactValue(chart.maxValue) }}</text>
          <text class="tooltip-chart-value-label" x="4" :y="chart.top + chart.innerHeight + 4">{{ formatCompactValue(chart.minValue) }}</text>
          <polyline v-if="chart.linePoints" class="tooltip-chart-line" :points="chart.linePoints"></polyline>
          <circle
            v-for="point in chart.points"
            :key="point.year"
            :class="['tooltip-chart-point', { current: point.current }]"
            :cx="point.x"
            :cy="point.y"
            :r="point.current ? 4.5 : 3.2"
          >
            <title>{{ point.year }}: {{ formatValue(point.value) }}</title>
          </circle>
          <text
            v-for="point in chart.points"
            :key="`${point.year}-label`"
            :class="['tooltip-chart-year', { current: point.current }]"
            :x="point.x"
            :y="chart.height - 5"
          >{{ point.year }}</text>
        </svg>
      </div>
      <div v-else class="tooltip-chart sidebar-tooltip-chart">
        <div class="tooltip-chart-title">{{ datasetLabel }} trend</div>
        <div class="tooltip-chart-empty">No year values available</div>
      </div>
    </div>

    <div v-else class="sidebar-trend-empty">
      <i class="fa-solid fa-location-crosshairs"></i>
      <span>Hover over a {{ geographyLabel.toLowerCase() }}</span>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import {
  getMetricAvailabilityProperty,
  getMetricProperty,
} from '../composables/useAtoData.js'

const props = defineProps({
  properties: { type: Object, default: null },
  datasetLabel: { type: String, default: 'ATO' },
  geographyType: { type: String, default: 'TAZ' },
  modelArea: { type: String, required: true },
  scenarioYear: { type: Number, required: true },
  scenarioYears: { type: Array, default: () => [] },
  activeColumn: { type: String, required: true },
  metricLabel: { type: String, required: true },
})

const geographyLabel = computed(() => (
  props.geographyType === 'CITY'
    ? 'City'
    : 'TAZ'
))

const geographyName = computed(() => (
  props.properties?.GeographyName
    ?? props.properties?.geographyname
    ?? props.properties?.CO_TAZID
    ?? props.properties?.co_tazid
    ?? props.properties?.tazid
    ?? 'Unknown'
))

const currentValue = computed(() => {
  if (!props.properties) return null
  return getYearMetricValue(props.properties, props.scenarioYear)
    ?? props.properties[props.activeColumn]
    ?? props.properties.access_value
})

const chart = computed(() => buildChart(props.properties))

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

function getChartYears() {
  const years = props.scenarioYears.length ? props.scenarioYears : [props.scenarioYear]
  return [...new Set(years.map(Number).filter(Number.isFinite))].sort((a, b) => a - b)
}

function getYearMetricValue(properties, year) {
  const valueProperty = getMetricProperty(year, props.activeColumn)
  const availabilityProperty = getMetricAvailabilityProperty(year, props.activeColumn)
  const availability = properties[availabilityProperty]
  const isAvailable = availability === undefined || availability === null || Number(availability) === 1
  const value = Number(properties[valueProperty])

  if (!isAvailable || !Number.isFinite(value)) return null
  return value
}

function buildYearSeries(properties) {
  if (!properties) return []

  return getChartYears()
    .map((year) => ({
      year,
      value: getYearMetricValue(properties, year),
    }))
    .filter((point) => point.value !== null)
}

function buildChart(properties) {
  const series = buildYearSeries(properties)
  const width = 292
  const height = 108
  const left = 40
  const right = 14
  const top = 12
  const bottom = 24
  const innerWidth = width - left - right
  const innerHeight = height - top - bottom

  if (!series.length) {
    return { hasSeries: false, width, height, left, right, top, bottom, innerHeight }
  }

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
    x: Number(scaleX(point.year).toFixed(1)),
    y: Number(scaleY(point.value).toFixed(1)),
    current: Number(point.year) === Number(props.scenarioYear),
  }))

  return {
    hasSeries: true,
    width,
    height,
    left,
    right,
    top,
    bottom,
    innerHeight,
    minYear,
    maxYear,
    minValue,
    maxValue,
    points,
    linePoints: points.length > 1
      ? points.map((point) => `${point.x},${point.y}`).join(' ')
      : '',
  }
}
</script>
