export const MAP_CENTER = [-111.891, 40.7608]
export const MAP_ZOOM = 7
export const BRAND_BLUE = '#233A57'
export const ACCESS_PALETTE = ['#EDF8B1', '#C7E9B4', '#7FCDBB', '#41B6C4', '#1D91C0', '#225EA8']
export const VMT_PALETTE = ['#f7fcfd', '#d0d1e6', '#a6bddb', '#67a9cf', '#ef8a62', '#b2182b']
export const DATA_BASE_URL = new URL('data/', window.location.href).href.replace(/\/$/, '')

export const DATASETS = [
  { label: 'ATO', value: 'ato', title: 'Access to Opportunity', icon: 'fa-bullseye' },
  { label: 'VMT', value: 'vmt', title: 'Vehicle Miles Traveled', icon: 'fa-road' },
]

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

export const VMT_PERIODS = [
  { label: 'AM', value: 'AM_VMT', icon: 'fa-sun' },
  { label: 'Midday', value: 'MD_VMT', icon: 'fa-cloud-sun' },
  { label: 'PM', value: 'PM_VMT', icon: 'fa-city' },
  { label: 'Evening', value: 'EV_VMT', icon: 'fa-moon' },
  { label: 'Daily', value: 'DY_VMT', icon: 'fa-calendar-day' },
]
