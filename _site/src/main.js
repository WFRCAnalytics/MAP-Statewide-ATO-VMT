import { createApp } from 'vue'
import '@maplibre/maplibre-gl-geocoder/dist/maplibre-gl-geocoder.css'
import './style.css'
import App from './App.vue'

const app = createApp(App)

let tooltipElement = null
function getTooltipElement() {
  if (!tooltipElement) tooltipElement = document.getElementById('global-tooltip')
  return tooltipElement
}

app.directive('tooltip', {
  mounted(el, { value }) {
    el.addEventListener('mouseenter', () => {
      if (!value) return
      const tip = getTooltipElement()
      if (!tip) return
      const rect = el.getBoundingClientRect()
      tip.textContent = value
      tip.style.left = `${rect.left + rect.width / 2}px`
      tip.style.top = `${rect.top - 6}px`
      tip.classList.add('visible')
    })
    el.addEventListener('mouseleave', () => {
      getTooltipElement()?.classList.remove('visible')
    })
  },
})

app.mount('#app')
