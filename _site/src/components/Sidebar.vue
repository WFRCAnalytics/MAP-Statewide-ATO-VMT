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

      <span class="step-header">Step 3: Select Geography</span>
      <div class="segmented-control geography-control">
        <button
          v-for="level in geographyLevels"
          :key="level.value"
          class="segmented-button"
          :class="{ active: geographyType === level.value }"
          :title="level.label"
          @click="$emit('update:geographyType', level.value)"
        >
          <i :class="`fa-solid ${level.icon}`"></i>
          <span>{{ level.label }}</span>
        </button>
      </div>
      <div v-if="datasetMode === 'ato' && geographyType === 'CITY'" class="geography-note">
        City Region ATO values are simple averages of the included TAZ values.
      </div>

      <span v-if="datasetMode === 'ato'" class="step-header">Step 4: Choose Accessibility</span>
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

      <span v-if="datasetMode === 'ato'" class="step-header">Step 5: Choose Travel Mode</span>
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

      <span v-if="datasetMode === 'vmt'" class="step-header">Step 4: Choose VMT Direction</span>
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

      <span v-if="datasetMode === 'vmt'" class="step-header">Step 5: Display VMT As</span>
      <div v-if="datasetMode === 'vmt'" class="segmented-control vmt-rate-row">
        <button
          v-for="rate in vmtRateOptions"
          :key="rate.value"
          class="segmented-button"
          :class="{ active: vmtRate === rate.value }"
          :title="rate.label"
          @click="$emit('update:vmtRate', rate.value)"
        >
          <i :class="`fa-solid ${rate.icon}`"></i>
          <span>{{ rate.label }}</span>
        </button>
      </div>
      <div v-if="datasetMode === 'vmt'" class="geography-note">
        HH Equiv = households + 0.55 jobs.
      </div>

      <span v-if="datasetMode === 'vmt'" class="step-header">Step 6: Choose Purpose</span>
      <div v-if="datasetMode === 'vmt'" class="vmt-purpose-row">
        <select
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
      </div>

      <TrendChart
        :properties="activeTazProperties"
        :dataset-label="datasetLabel"
        :geography-type="geographyType"
        :model-area="modelArea"
        :scenario-year="scenarioYear"
        :scenario-years="trendScenarioYears"
        :active-column="activeColumn"
        :metric-label="metricLabel"
      />

      <hr class="sidebar-hr" />
    </div>
  </aside>
</template>

<script setup>
import TrendChart from './TrendChart.vue'
import {
  ACCESS_TARGETS,
  DATASETS,
  GEOGRAPHY_LEVELS,
  MODEL_AREAS,
  SCENARIO_YEARS,
  TRAVEL_MODES,
  VMT_PA_OPTIONS,
  VMT_RATE_OPTIONS,
  VMT_PURPOSE_GROUPS,
  VMT_PURPOSES,
} from '../config/constants.js'

defineProps({
  datasetMode: { type: String, default: 'ato' },
  scenarioYears: { type: Array, default: () => SCENARIO_YEARS },
  modelAreas: { type: Array, default: () => MODEL_AREAS },
  scenarioYear: { type: Number, required: true },
  modelArea: { type: String, required: true },
  geographyType: { type: String, default: 'TAZ' },
  geographyLevels: { type: Array, default: () => GEOGRAPHY_LEVELS },
  disabledModelAreas: { type: Object, default: () => ({}) },
  accessTarget: { type: String, required: true },
  travelMode: { type: String, required: true },
  vmtPa: { type: String, default: 'P' },
  vmtRate: { type: String, default: 'TOTAL' },
  vmtPurposeGroup: { type: String, default: 'PERSON' },
  vmtPurpose: { type: String, default: 'PERSON_ALL' },
  vmtRateOptions: { type: Array, default: () => VMT_RATE_OPTIONS },
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
  'update:geographyType',
  'update:accessTarget',
  'update:travelMode',
  'update:vmtPa',
  'update:vmtRate',
  'update:vmtPurposeGroup',
  'update:vmtPurpose',
])
</script>
