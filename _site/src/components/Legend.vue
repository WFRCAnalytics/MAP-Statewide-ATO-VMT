<template>
  <div v-if="hasData" id="map-legend">
    <div class="legend-title">{{ metricLabel }}</div>
    <div class="legend-items">
      <div v-for="item in legendItems" :key="item.label" class="legend-item">
        <span class="legend-swatch" :style="{ background: item.color }"></span>
        <span class="legend-label">{{ item.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ACCESS_PALETTE } from '../config/constants.js'

const props = defineProps({
  hasData: { type: Boolean, default: false },
  metricLabel: { type: String, default: 'ATO Accessibility' },
  minValue: { type: Number, default: 0 },
  maxValue: { type: Number, default: 0 },
})

function formatNumber(value) {
  if (!Number.isFinite(value)) return '0'
  return Math.round(value).toLocaleString()
}

const legendItems = computed(() => {
  const span = props.maxValue - props.minValue
  return ACCESS_PALETTE.map((color, index) => {
    const value = span > 0
      ? props.minValue + (span * index) / (ACCESS_PALETTE.length - 1)
      : props.minValue
    return { color, label: formatNumber(value) }
  })
})
</script>
