export const MAP_CENTER = [-111.891, 40.7608]
export const MAP_ZOOM = 7
export const BRAND_BLUE = '#233A57'
export const ACCESS_PALETTE = ['#EDF8B1', '#C7E9B4', '#7FCDBB', '#41B6C4', '#1D91C0', '#225EA8']
export const DATA_BASE_URL = new URL('data/', window.location.href).href.replace(/\/$/, '')

export const SCENARIO_YEARS = [2019, 2023, 2028]
export const MODEL_AREAS = [
  'Statewide',
  'Wasatch Front',
  'Cache',
  'Dixie',
  'Summit Wasatch',
  'Iron',
]

export const ACCESS_TARGETS = [
  { label: 'Jobs', value: 'Job', icon: 'fa-briefcase' },
  { label: 'Households', value: 'HH', icon: 'fa-house' },
]

export const TRAVEL_MODES = [
  { label: 'Auto', value: 'Auto', icon: 'fa-car' },
  { label: 'Transit', value: 'Tran', icon: 'fa-train-subway' },
  { label: 'Walk', value: 'Walk', icon: 'fa-person-walking' },
  { label: 'Bike', value: 'Bike', icon: 'fa-bicycle' },
]
