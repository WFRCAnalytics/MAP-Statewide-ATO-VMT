<template>
  <aside id="sidebar">
    <div id="sidebar-top">
      <span class="step-header" style="margin-top:0">Explore</span>
      <div class="segmented-control">
        <button
          v-for="dataset in DATASETS"
          :key="dataset.value"
          class="segmented-button"
          :class="{ active: datasetMode === dataset.value }"
          :title="dataset.title"
          @click="$emit('update:datasetMode', dataset.value)"
        >
          <i :class="`fa-solid ${dataset.icon}`"></i>
          <span>{{ dataset.label }}</span>
        </button>
      </div>

      <span class="step-header">Step 1: Select Scenario</span>
      <select class="lu-select" :value="scenarioYear" @change="$emit('update:scenarioYear', Number($event.target.value))">
        <option v-for="year in scenarioYears" :key="year" :value="year">{{ year }}</option>
      </select>
    </div>

    <div id="sidebar-body">
      <span class="step-header">Step 2: Select Model Area</span>
      <select class="lu-select" :value="modelArea" @change="$emit('update:modelArea', $event.target.value)">
        <option v-for="area in modelAreas" :key="area" :value="area">{{ area }}</option>
      </select>

      <span v-if="datasetMode === 'ato'" class="step-header">Step 3: Choose Accessibility</span>
      <div v-if="datasetMode === 'ato'" class="segmented-control">
        <button
          v-for="target in ACCESS_TARGETS"
          :key="target.value"
          class="segmented-button"
          :class="{
            active: accessTarget === target.value && !disabledAccessTargets[target.value],
            disabled: disabledAccessTargets[target.value],
          }"
          :disabled="disabledAccessTargets[target.value]"
          :title="disabledAccessTargets[target.value] ? 'No data for this selection' : target.label"
          @click="$emit('update:accessTarget', target.value)"
        >
          <i :class="`fa-solid ${target.icon}`"></i>
          <span>{{ target.label }}</span>
        </button>
      </div>

      <span v-if="datasetMode === 'ato'" class="step-header">Step 4: Choose Travel Mode</span>
      <div v-if="datasetMode === 'ato'" class="mode-grid">
        <button
          v-for="mode in TRAVEL_MODES"
          :key="mode.value"
          class="mode-button"
          :class="{
            active: travelMode === mode.value && !disabledTravelModes[mode.value],
            disabled: disabledTravelModes[mode.value],
          }"
          :disabled="disabledTravelModes[mode.value]"
          :title="disabledTravelModes[mode.value] ? 'No data for this selection' : mode.label"
          @click="$emit('update:travelMode', mode.value)"
        >
          <i :class="`fa-solid ${mode.icon}`"></i>
          <span>{{ mode.label }}</span>
        </button>
      </div>

      <span v-if="datasetMode === 'vmt'" class="step-header">Step 3: Choose VMT Period</span>
      <div v-if="datasetMode === 'vmt'" class="mode-grid">
        <button
          v-for="period in VMT_PERIODS"
          :key="period.value"
          class="mode-button"
          :class="{
            active: vmtPeriod === period.value && !disabledVmtPeriods[period.value],
            disabled: disabledVmtPeriods[period.value],
          }"
          :disabled="disabledVmtPeriods[period.value]"
          :title="disabledVmtPeriods[period.value] ? 'No data for this selection' : period.label"
          @click="$emit('update:vmtPeriod', period.value)"
        >
          <i :class="`fa-solid ${period.icon}`"></i>
          <span>{{ period.label }}</span>
        </button>
      </div>

      <div class="accordion">
        <div class="accordion-item">
          <button class="accordion-button" @click="layerPanelOpen = !layerPanelOpen">
            <span>Map Layers</span>
            <i :class="layerPanelOpen ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down'"></i>
          </button>
          <div v-show="layerPanelOpen" class="accordion-body">
            <div v-for="layer in MAP_LAYER_DEFS" :key="layer.id" class="toggle-row">
              <div class="toggle-row-label">
                <span>{{ layer.label }}</span>
                <i class="fa-regular fa-circle-question help-icon" v-tooltip="layer.help"></i>
              </div>
              <button
                class="layer-toggle-btn"
                :class="{ active: layerVisible[layer.id] }"
                :title="`Toggle ${layer.label}`"
                @click="$emit('toggle-layer', layer.id)"
              >
                <i :class="layerVisible[layer.id] ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash'"></i>
              </button>
            </div>
          </div>
        </div>
      </div>

      <hr class="sidebar-hr" />

      <div class="data-status">
        <div class="data-status-icon"><i class="fa-solid fa-database"></i></div>
        <div>
          <div class="data-status-title">{{ modelArea }} {{ datasetMode.toUpperCase() }} loaded</div>
          <p>{{ recordCount.toLocaleString() }} TAZ records available for the current selection.</p>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref } from 'vue'
import {
  ACCESS_TARGETS,
  DATASETS,
  MODEL_AREAS,
  SCENARIO_YEARS,
  TRAVEL_MODES,
  VMT_PERIODS,
} from '../config/constants.js'
import { MAP_LAYER_DEFS } from '../config/layers.js'

defineProps({
  datasetMode: { type: String, default: 'ato' },
  scenarioYears: { type: Array, default: () => SCENARIO_YEARS },
  modelAreas: { type: Array, default: () => MODEL_AREAS },
  scenarioYear: { type: Number, required: true },
  modelArea: { type: String, required: true },
  accessTarget: { type: String, required: true },
  travelMode: { type: String, required: true },
  vmtPeriod: { type: String, default: 'DY_VMT' },
  disabledAccessTargets: { type: Object, default: () => ({}) },
  disabledTravelModes: { type: Object, default: () => ({}) },
  disabledVmtPeriods: { type: Object, default: () => ({}) },
  layerVisible: { type: Object, required: true },
  recordCount: { type: Number, default: 0 },
})

defineEmits([
  'update:datasetMode',
  'update:scenarioYear',
  'update:modelArea',
  'update:accessTarget',
  'update:travelMode',
  'update:vmtPeriod',
  'toggle-layer',
])

const layerPanelOpen = ref(true)
</script>
