<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal-box">
      <div class="splash-header">
        <img :src="logoUrl" alt="WFRC Logo" />
        <h2>Statewide ATO and VMT Explorer</h2>
      </div>
      <div class="splash-body">
        <p>Statewide access-to-opportunities and vehicle-miles-traveled analysis for Utah model areas.</p>
        <div class="feature-grid">
          <div class="feature-item">
            <div class="feature-icon"><i class="fa-solid fa-map-location-dot"></i></div>
            <div class="feature-title">TAZ Geography</div>
            <div class="feature-text">CO_TAZID map units</div>
          </div>
          <div class="feature-item">
            <div class="feature-icon"><i class="fa-solid fa-layer-group"></i></div>
            <div class="feature-title">Scenario Views</div>
            <div class="feature-text">Year and area filters</div>
          </div>
          <div class="feature-item">
            <div class="feature-icon"><i class="fa-solid fa-box-archive"></i></div>
            <div class="feature-title">ATO and VMT</div>
            <div class="feature-text">Access metrics and link VMT summarized to TAZs</div>
          </div>
        </div>
        <div class="instruction-box">
          <i class="fa-solid fa-circle-info"></i>
          <strong> Data status:</strong> ATO and VMT layers are loaded from processed PMTiles.
        </div>
      </div>
      <div class="splash-footer">
        <button class="btn-get-started" @click="$emit('close')">GET STARTED</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineEmits(['close'])
const logoUrl = `${import.meta.env.BASE_URL}logo.png`
</script>
