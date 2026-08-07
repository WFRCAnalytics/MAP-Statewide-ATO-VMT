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
        <option
          v-for="area in modelAreas"
          :key="area"
          :value="area"
          :disabled="disabledModelAreas[area]"
        >
          {{ area }}
        </option>
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
      <div v-if="datasetMode === 'ato'" class="mode-grid travel-mode-row">
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

      <span v-if="datasetMode === 'vmt'" class="step-header">Step 3: Choose VMT Direction</span>
      <div v-if="datasetMode === 'vmt'" class="segmented-control">
        <button
          v-for="pa in VMT_PA_OPTIONS"
          :key="pa.value"
          class="segmented-button"
          :class="{ active: vmtPa === pa.value }"
          :title="pa.label"
          @click="$emit('update:vmtPa', pa.value)"
        >
          <i :class="`fa-solid ${pa.icon}`"></i>
          <span>{{ pa.label }}</span>
        </button>
      </div>

      <span v-if="datasetMode === 'vmt'" class="step-header">Step 4: Choose Purpose</span>
      <select
        v-if="datasetMode === 'vmt'"
        class="lu-select"
        :value="vmtPurposeGroup"
        @change="$emit('update:vmtPurposeGroup', $event.target.value)"
      >
        <option
          v-for="group in vmtPurposeGroups"
          :key="group.value"
          :value="group.value"
        >
          {{ group.label }}
        </option>
      </select>
      <select
        v-if="datasetMode === 'vmt'"
        class="lu-select"
        :value="vmtPurpose"
        @change="$emit('update:vmtPurpose', $event.target.value)"
      >
        <option
          v-for="purpose in vmtPurposes"
          :key="purpose.value"
          :value="purpose.value"
          :disabled="disabledVmtPurposes[purpose.value]"
        >
          {{ purpose.label }}
        </option>
      </select>

      <TrendChart
        :properties="activeTazProperties"
        :dataset-label="datasetLabel"
        :model-area="modelArea"
        :scenario-year="scenarioYear"
        :scenario-years="trendScenarioYears"
        :active-column="activeColumn"
        :metric-label="metricLabel"
      />

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
import TrendChart from './TrendChart.vue'
import {
  ACCESS_TARGETS,
  DATASETS,
  MODEL_AREAS,
  SCENARIO_YEARS,
  TRAVEL_MODES,
  VMT_PA_OPTIONS,
  VMT_PURPOSE_GROUPS,
  VMT_PURPOSES,
} from '../config/constants.js'

defineProps({
  datasetMode: { type: String, default: 'ato' },
  scenarioYears: { type: Array, default: () => SCENARIO_YEARS },
  modelAreas: { type: Array, default: () => MODEL_AREAS },
  scenarioYear: { type: Number, required: true },
  modelArea: { type: String, required: true },
  disabledModelAreas: { type: Object, default: () => ({}) },
  accessTarget: { type: String, required: true },
  travelMode: { type: String, required: true },
  vmtPa: { type: String, default: 'P' },
  vmtPurposeGroup: { type: String, default: 'PERSON' },
  vmtPurpose: { type: String, default: 'PERSON_ALL' },
  vmtPurposeGroups: { type: Array, default: () => VMT_PURPOSE_GROUPS },
  vmtPurposes: { type: Array, default: () => VMT_PURPOSES },
  disabledAccessTargets: { type: Object, default: () => ({}) },
  disabledTravelModes: { type: Object, default: () => ({}) },
  disabledVmtPurposes: { type: Object, default: () => ({}) },
  recordCount: { type: Number, default: 0 },
  activeTazProperties: { type: Object, default: null },
  datasetLabel: { type: String, default: 'ATO' },
  activeColumn: { type: String, required: true },
  metricLabel: { type: String, required: true },
  trendScenarioYears: { type: Array, default: () => [] },
})

defineEmits([
  'update:datasetMode',
  'update:scenarioYear',
  'update:modelArea',
  'update:accessTarget',
  'update:travelMode',
  'update:vmtPa',
  'update:vmtPurposeGroup',
  'update:vmtPurpose',
])
</script>
