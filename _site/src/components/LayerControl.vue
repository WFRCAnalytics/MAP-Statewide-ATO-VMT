<template>
  <div id="layer-control-panel">
    <button class="lc-header" @click="open = !open">
      <i class="fa-solid fa-layer-group"></i>
      <span>Layers</span>
      <i :class="open ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down'" style="margin-left:auto;font-size:0.7rem;"></i>
    </button>
    <div v-show="open" class="lc-body">
      <div class="lc-section-label">Map Layers</div>
      <div v-for="layer in MAP_LAYER_DEFS" :key="layer.id" class="lc-row">
        <span>{{ layer.label }}</span>
        <button class="layer-toggle-btn" :class="{ active: layerVisible[layer.id] }" @click="$emit('toggle-layer', layer.id)">
          <i :class="layerVisible[layer.id] ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash'"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { MAP_LAYER_DEFS } from '../config/layers.js'

defineProps({
  layerVisible: { type: Object, required: true },
})

defineEmits(['toggle-layer'])

const open = ref(false)
</script>
