<template>
  <div v-if="hasData" id="map-legend">
    <div class="legend-title">{{ metricLabel }}</div>
    <div v-if="showModeToggle" class="legend-mode-toggle">
      <button
        v-for="option in modeOptions"
        :key="option.value"
        type="button"
        class="legend-mode-button"
        :class="{ active: legendMode === option.value }"
        @click="$emit('update:legendMode', option.value)"
      >
        {{ option.label }}
      </button>
    </div>
    <div class="legend-items">
      <div v-for="(item, index) in legendItems" :key="`${index}-${item.label}`" class="legend-item">
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
  metricLabel: { type: String, default: 'Selected Metric' },
  minValue: { type: Number, default: 0 },
  maxValue: { type: Number, default: 0 },
  palette: { type: Array, default: () => ACCESS_PALETTE },
  customItems: { type: Array, default: () => [] },
  showModeToggle: { type: Boolean, default: false },
  legendMode: { type: String, default: 'continuous' },
  modeOptions: { type: Array, default: () => [] },
})

defineEmits(['update:legendMode'])

function formatNumber(value) {
  if (!Number.isFinite(value)) return '0'
  return Math.round(value).toLocaleString()
}

function getRoundingStep(span) {
  const absoluteSpan = Math.abs(span)
  if (absoluteSpan >= 25_000) return 5_000
  if (absoluteSpan >= 5_000) return 1_000
  if (absoluteSpan >= 1_000) return 500
  if (absoluteSpan >= 100) return 50
  if (absoluteSpan >= 10) return 5
  return 1
}

function roundToStep(value, step) {
  if (!Number.isFinite(value)) return 0
  return Math.round(value / step) * step
}

const legendItems = computed(() => {
  if (props.customItems.length) return props.customItems

  const span = props.maxValue - props.minValue
  const step = getRoundingStep(span)
  const palette = props.palette.length ? props.palette : ACCESS_PALETTE

  return palette.map((color, index) => {
    const value = span > 0
      ? props.minValue + (span * index) / (palette.length - 1)
      : props.minValue
    return { color, label: formatNumber(roundToStep(value, step)) }
  })
})
</script>
