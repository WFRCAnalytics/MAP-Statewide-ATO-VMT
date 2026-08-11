import { DATA_BASE_URL } from '../config/constants.js'

let connection = null
const manifestCache = {}

async function getConnection() {
  if (connection) return connection

  const duckdb = await import('@duckdb/duckdb-wasm')
  const bundle = {
    mainModule: new URL('@duckdb/duckdb-wasm/dist/duckdb-eh.wasm', import.meta.url).href,
    mainWorker: new URL('@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js', import.meta.url).href,
  }

  const worker = new Worker(bundle.mainWorker)
  const db = new duckdb.AsyncDuckDB(
    new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING),
    worker,
  )

  try {
    await db.instantiate(bundle.mainModule)
  } catch (error) {
    if (!(error instanceof TypeError) || !error.message.includes('MIME type')) throw error
    const response = await fetch(bundle.mainModule)
    const buffer = await response.arrayBuffer()
    const blobUrl = URL.createObjectURL(new Blob([buffer], { type: 'application/wasm' }))
    try {
      await db.instantiate(blobUrl)
    } finally {
      URL.revokeObjectURL(blobUrl)
    }
  }

  connection = await db.connect()
  return connection
}

function tableToRows(table) {
  const rowCount = table.numRows
  const fields = table.schema.fields
  const columns = fields.map((field) => table.getChild(field.name))
  const rows = new Array(rowCount)

  for (let rowIndex = 0; rowIndex < rowCount; rowIndex += 1) {
    const row = {}
    for (let colIndex = 0; colIndex < fields.length; colIndex += 1) {
      const value = columns[colIndex]?.get(rowIndex) ?? null
      row[fields[colIndex].name] =
        value === null ? null
          : typeof value === 'bigint' ? Number(value)
            : typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? value
              : null
    }
    rows[rowIndex] = row
  }

  return rows
}

function quoteIdentifier(identifier) {
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(identifier)) {
    throw new Error(`Unsafe metric column: ${identifier}`)
  }
  return `"${identifier}"`
}

function quoteString(value) {
  return String(value).replace(/'/g, "''")
}

export function getMetricProperty(scenarioYear, metricColumn) {
  return `y${Number(scenarioYear)}_${metricColumn}`
}

export function getMetricAvailabilityProperty(scenarioYear, metricColumn) {
  return `${getMetricProperty(scenarioYear, metricColumn)}_has`
}

export function getAtoMetricProperty(scenarioYear, metricColumn) {
  return getMetricProperty(scenarioYear, metricColumn)
}

export function getAtoMetricAvailabilityProperty(scenarioYear, metricColumn) {
  return getMetricAvailabilityProperty(scenarioYear, metricColumn)
}

export function getMetricRange(manifest, scenarioYear, modelArea, geographyType, metricColumn) {
  const groupedRange = manifest.metric_ranges?.[`${Number(scenarioYear)}|${modelArea}|${geographyType}`]?.[metricColumn]
  return {
    minValue: Number(groupedRange?.min ?? 0),
    maxValue: Number(groupedRange?.max ?? 0),
    hasRange: Boolean(groupedRange),
  }
}

export function getAtoMetricRange(manifest, scenarioYear, modelArea, geographyType, metricColumn) {
  return getMetricRange(manifest, scenarioYear, modelArea, geographyType, metricColumn)
}

export function hasMetricData(manifest, scenarioYear, modelArea, geographyType, metricColumn) {
  const { maxValue, hasRange } = getMetricRange(
    manifest,
    scenarioYear,
    modelArea,
    geographyType,
    metricColumn,
  )
  const recordCount = Number(
    manifest.record_counts?.[`${Number(scenarioYear)}|${modelArea}|${geographyType}`] ?? 0,
  )

  return hasRange
    && recordCount > 0
    && Number.isFinite(maxValue)
    && maxValue > 0
    && Boolean(manifest.files?.pmtiles)
}

export function hasAtoMetricData(manifest, scenarioYear, modelArea, geographyType, metricColumn) {
  return hasMetricData(manifest, scenarioYear, modelArea, geographyType, metricColumn)
}

export function getSelectionSummary({ manifest, scenarioYear, modelArea, geographyType, metricColumn }) {
  const { minValue, maxValue, hasRange } = getMetricRange(
    manifest,
    scenarioYear,
    modelArea,
    geographyType,
    metricColumn,
  )
  const recordCount = Number(
    manifest.record_counts?.[`${Number(scenarioYear)}|${modelArea}|${geographyType}`]
      ?? manifest.pmtiles?.feature_count
      ?? 0,
  )

  return {
    recordCount,
    minValue,
    maxValue,
    hasData: hasRange
      && recordCount > 0
      && Number.isFinite(maxValue)
      && maxValue > 0
      && Boolean(manifest.files?.pmtiles),
  }
}

export function getAtoSelectionSummary(options) {
  return getSelectionSummary(options)
}

export async function loadDataManifest(datasetId = 'ato') {
  if (manifestCache[datasetId]) return manifestCache[datasetId]

  const response = await fetch(`${DATA_BASE_URL}/${datasetId}/manifest.json`)
  if (!response.ok) {
    throw new Error(`Failed to load ${datasetId.toUpperCase()} manifest: ${response.status}`)
  }
  manifestCache[datasetId] = await response.json()
  return manifestCache[datasetId]
}

export async function loadAtoManifest() {
  return loadDataManifest('ato')
}

export async function loadDataRows({ datasetId = 'ato', scenarioYear, modelArea, geographyType, metricColumn }) {
  const manifest = await loadDataManifest(datasetId)
  if (!manifest.metrics.includes(metricColumn)) {
    throw new Error(`Metric ${metricColumn} is not listed in the ${datasetId.toUpperCase()} manifest`)
  }

  const conn = await getConnection()
  const metricsUrl = `${DATA_BASE_URL}/${manifest.files.metrics}`
  const metricIdentifier = quoteIdentifier(metricColumn)
  const modelAreaSql = quoteString(modelArea)
  const geographyTypeSql = quoteString(geographyType)
  const idColumns = datasetId === 'ato' ? '"SA_TAZID",' : ''
  const extraColumns = datasetId === 'vmt' ? '"TOTHH", "TOTEMP", "HH_EQUIV",' : ''

  const table = await conn.query(`
    SELECT
      "ScenarioYear",
      "ModelArea",
      "GeographyType",
      "GeographyId",
      "GeographyName",
      ${idColumns}
      ${extraColumns}
      "CO_TAZID",
      CAST(${metricIdentifier} AS DOUBLE) AS metric_value
    FROM read_parquet('${metricsUrl}')
    WHERE "ScenarioYear" = ${Number(scenarioYear)}
      AND "ModelArea" = '${modelAreaSql}'
      AND "GeographyType" = '${geographyTypeSql}'
    ORDER BY "GeographyName", "GeographyId"
  `)

  const rows = tableToRows(table)
  const { minValue, maxValue } = getMetricRange(manifest, scenarioYear, modelArea, geographyType, metricColumn)
  const spread = maxValue - minValue

  for (const row of rows) {
    const metricValue = Number(row.metric_value)
    row.access_value = spread > 0 ? (metricValue - minValue) / spread : 0
  }

  return {
    rows,
    minValue,
    maxValue,
  }
}

export async function loadAtoRows(options) {
  return loadDataRows({ ...options, datasetId: 'ato' })
}
