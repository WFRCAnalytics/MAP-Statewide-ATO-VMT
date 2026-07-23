<template>
  <div id="map-legend">
    <div class="legend-title">ATO Accessibility</div>
    <div class="legend-items">
      <div v-for="item in legendItems" :key="item.label" class="legend-item">
        <span class="legend-swatch" :style="{ background: item.color }"></span>
        <span class="legend-label">{{ item.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ACCESS_PALETTE } from '../config/constants.js'

const labels = ['Least', 'Low', 'Moderate', 'High', 'Higher', 'Most']
const legendItems = ACCESS_PALETTE.map((color, index) => ({ color, label: labels[index] }))
</script>
