<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal-box">
      <div class="splash-header">
        <img :src="logoUrl" alt="WFRC Logo" />
        <h2>Statewide ATO and VMT Explorer</h2>
      </div>
      <div class="splash-body">
        <p>Statewide access-to-opportunities and vehicle-miles-traveled analysis for Utah model areas.</p>
        <section class="splash-section">
          <h3>How This Information Is Generated</h3>
          <div class="process-list">
            <div class="process-step">
              <div class="process-number">1</div>
              <div class="process-copy">
                <div class="process-title">Existing and Future Transportation Network</div>
                <div class="process-text">Scenario networks establish the roadway and transportation system used for analysis.</div>
              </div>
            </div>
            <div class="process-step">
              <div class="process-number">2</div>
              <div class="process-copy">
                <div class="process-title">Household and Job Forecast</div>
                <div class="process-text">Land use assumptions provide the households and employment distribution for each scenario year.</div>
              </div>
            </div>
            <div class="process-step">
              <div class="process-number">3</div>
              <div class="process-copy">
                <div class="process-title">TDM Generated Outputs</div>
                <div class="process-text">Model outputs are summarized to TAZs to support ATO and VMT comparisons across model areas.</div>
              </div>
            </div>
          </div>
        </section>
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
