import maplibregl from 'maplibre-gl'
import MaplibreGeocoder from '@maplibre/maplibre-gl-geocoder'
import { Protocol } from 'pmtiles'
import { MAP_CENTER, MAP_ZOOM } from '../config/constants.js'

let mapInstance = null
let currentBounds = null
let pmtilesProtocol = null

export function registerPMTilesProtocol() {
  if (pmtilesProtocol) return pmtilesProtocol
  pmtilesProtocol = new Protocol()
  maplibregl.addProtocol('pmtiles', pmtilesProtocol.tile)
  return pmtilesProtocol
}

export function setExtentBounds(bounds) {
  currentBounds = bounds
}

const nominatimApi = {
  forwardGeocode: async (config) => {
    try {
      const viewbox = '-114.05,42.1,-109.04,36.9'
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(config.query)}&format=geojson&limit=5&countrycodes=us&viewbox=${viewbox}&bounded=1`
      const response = await fetch(url, { headers: { 'Accept-Language': 'en' } })
      const geojson = await response.json()
      return {
        features: geojson.features.map((feature) => {
          const bbox = feature.bbox
          const center = bbox
            ? [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
            : feature.geometry.coordinates
          return {
            type: 'Feature',
            geometry: { type: 'Point', coordinates: center },
            place_name: feature.properties.display_name,
            text: feature.properties.display_name,
            place_type: ['place'],
            center,
            bbox,
          }
        }),
      }
    } catch {
      return { features: [] }
    }
  },
}

class ZoomToExtentControl {
  onAdd(map) {
    this.map = map
    this.container = document.createElement('div')
    this.container.className = 'maplibregl-ctrl maplibregl-ctrl-group'
    const button = document.createElement('button')
    button.title = 'Zoom to ATO extent'
    button.setAttribute('aria-label', 'Zoom to ATO extent')
    button.innerHTML = '<i class="fa-solid fa-expand"></i>'
    button.onclick = () => {
      if (currentBounds) map.fitBounds(currentBounds, { padding: 40, maxZoom: 13, duration: 800 })
    }
    this.container.appendChild(button)
    return this.container
  }

  onRemove() {
    this.container.parentNode?.removeChild(this.container)
    this.map = null
  }
}

class TiltResetControl {
  onAdd(map) {
    this.map = map
    this.container = document.createElement('div')
    this.container.className = 'maplibregl-ctrl maplibregl-ctrl-group'
    const button = document.createElement('button')
    button.title = 'Reset tilt and north'
    button.setAttribute('aria-label', 'Reset tilt and north')
    button.innerHTML = '<i class="fa-solid fa-location-arrow"></i>'
    button.onclick = () => map.easeTo({ bearing: 0, pitch: 0, duration: 400 })
    this.container.appendChild(button)
    return this.container
  }

  onRemove() {
    this.container.parentNode?.removeChild(this.container)
    this.map = null
  }
}

export function initMap(containerId) {
  registerPMTilesProtocol()

  mapInstance = new maplibregl.Map({
    container: containerId,
    style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
    center: MAP_CENTER,
    zoom: MAP_ZOOM,
    preserveDrawingBuffer: true,
  })

  mapInstance.addControl(
    new MaplibreGeocoder(nominatimApi, {
      maplibregl,
      placeholder: 'Search Utah address...',
      proximity: { longitude: MAP_CENTER[0], latitude: MAP_CENTER[1] },
      flyTo: { duration: 1200 },
    }),
    'top-left',
  )
  mapInstance.addControl(new maplibregl.GeolocateControl({ trackUserLocation: false }), 'top-left')
  mapInstance.addControl(new maplibregl.NavigationControl(), 'top-left')
  mapInstance.addControl(new TiltResetControl(), 'top-left')
  mapInstance.addControl(new ZoomToExtentControl(), 'top-left')
  mapInstance.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }), 'bottom-left')

  return mapInstance
}

export function getMap() {
  return mapInstance
}

export function getFirstLabelLayerId(map) {
  return map.getStyle().layers.find(
    (layer) => layer.type === 'symbol' && layer.layout?.['text-field'],
  )?.id
}

export function findCartoVectorSource(map) {
  const sources = map.getStyle().sources
  return Object.keys(sources).find((key) => {
    const source = sources[key]
    return source.type === 'vector' && (key === 'carto' || key === 'openmaptiles' || key.includes('carto'))
  })
}
