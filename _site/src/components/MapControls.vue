<template>
  <div id="map-controls-bar">
    <button class="btn btn-outline-primary btn-sm" :disabled="!hasData" :class="{ disabled: !hasData }" @click="$emit('download')">
      <i class="fa-solid fa-download"></i>
      <span>Download Data</span>
    </button>
    <button class="btn btn-outline-secondary btn-sm" @click="$emit('screenshot')">
      <i class="fa-solid fa-camera"></i>
      <span>Download Map</span>
    </button>

    <div class="active-pill">
      <i class="fa-solid fa-chart-simple"></i>
      <span>{{ activeColumn }}</span>
    </div>

    <div style="flex:1"></div>

    <div class="ctrl-group">
      <label class="ctrl-label" for="opacity">Opacity:</label>
      <input
        id="opacity"
        type="range"
        min="0"
        max="1"
        step="0.05"
        :value="opacity"
        @input="$emit('update:opacity', Number($event.target.value))"
      />
    </div>

    <div v-if="is3D" class="ctrl-group">
      <label class="ctrl-label" for="exaggeration">Z Factor:</label>
      <input
        id="exaggeration"
        type="range"
        min="0.5"
        max="8"
        step="0.25"
        :value="exaggeration"
        @input="$emit('update:exaggeration', Number($event.target.value))"
      />
      <span class="ctrl-value">{{ exaggeration.toFixed(2) }}x</span>
    </div>

    <div class="switch-wrap">
      <label class="toggle-switch">
        <input type="checkbox" :checked="is3D" @change="$emit('update:is3D', $event.target.checked)" />
        <span class="toggle-slider"></span>
      </label>
      <span>3D View</span>
    </div>

    <div class="switch-wrap">
      <label class="toggle-switch">
        <input type="checkbox" :checked="pinnedTooltip" @change="$emit('update:pinnedTooltip', $event.target.checked)" />
        <span class="toggle-slider"></span>
      </label>
      <span>Pin Tooltip</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  activeColumn: { type: String, required: true },
  exaggeration: { type: Number, default: 1 },
  hasData: { type: Boolean, default: false },
  is3D: { type: Boolean, default: false },
  opacity: { type: Number, default: 0.78 },
  pinnedTooltip: { type: Boolean, default: false },
})

defineEmits([
  'download',
  'screenshot',
  'update:exaggeration',
  'update:is3D',
  'update:opacity',
  'update:pinnedTooltip',
])
</script>
