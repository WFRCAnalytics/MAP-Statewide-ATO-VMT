export const MAP_CENTER = [-111.891, 40.7608]
export const MAP_ZOOM = 7
export const BRAND_BLUE = '#233A57'
export const ACCESS_PALETTE = [
  'rgb(241, 244, 255)',
  'rgb(49, 57, 138)',
  'rgb(27, 169, 230)',
  'rgb(0, 167, 78)',
  'rgb(108, 183, 74)',
  'rgb(224, 157, 46)',
  'rgb(235, 103, 45)',
  'rgb(229, 39, 45)',
  'rgb(175, 41, 68)',
]
export const VMT_PALETTE = [
  '#e3e8f0',
  '#c7d5e4',
  '#a6bddb',
  '#67a9cf',
  '#3690c0',
  '#1f8aab',
  '#02818a',
  '#016c59',
  '#014636',
]
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
export const GEOGRAPHY_LEVELS = [
  { label: 'TAZ', value: 'TAZ', icon: 'fa-draw-polygon' },
  { label: 'City', value: 'CITY', icon: 'fa-city' },
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

export const VMT_PA_OPTIONS = [
  { label: 'Produced', value: 'P', icon: 'fa-arrow-up-from-bracket' },
  { label: 'Attracted', value: 'A', icon: 'fa-arrow-down-to-bracket' },
]

export const VMT_RATE_OPTIONS = [
  { label: 'Total', value: 'TOTAL', icon: 'fa-road' },
  { label: 'Per HH', value: 'PER_HH', icon: 'fa-house' },
  { label: 'Per Job', value: 'PER_JOB', icon: 'fa-briefcase' },
  { label: 'HH Equiv', value: 'PER_HHEQ', icon: 'fa-scale-balanced' },
]

export const VMT_PURPOSE_GROUPS = [
  { label: 'Household', value: 'PERSON', all_value: 'PERSON_ALL' },
  { label: 'Truck', value: 'TRUCK', all_value: 'TRUCK_ALL' },
  { label: 'Other', value: 'OTHER', all_value: 'OTHER_ALL' },
]

export const VMT_PURPOSES = [
  { label: 'All', value: 'PERSON_ALL', group: 'PERSON', is_group_total: true },
  { label: 'HBC', value: 'HBC', group: 'PERSON', is_group_total: false },
  { label: 'HBS Pr', value: 'HBS_Pr', group: 'PERSON', is_group_total: false },
  { label: 'HBS Sc', value: 'HBS_Sc', group: 'PERSON', is_group_total: false },
  { label: 'HBS', value: 'HBS', group: 'PERSON', is_group_total: false },
  { label: 'HBW', value: 'HBW', group: 'PERSON', is_group_total: false },
  { label: 'NHB', value: 'NHB', group: 'PERSON', is_group_total: false },
  { label: 'HBO', value: 'HBO', group: 'PERSON', is_group_total: false },
  { label: 'All', value: 'TRUCK_ALL', group: 'TRUCK', is_group_total: true },
  { label: 'LT', value: 'LT', group: 'TRUCK', is_group_total: false },
  { label: 'MD', value: 'MD', group: 'TRUCK', is_group_total: false },
  { label: 'HV', value: 'HV', group: 'TRUCK', is_group_total: false },
  { label: 'All', value: 'OTHER_ALL', group: 'OTHER', is_group_total: true },
]
