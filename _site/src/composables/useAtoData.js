import { DATA_BASE_URL } from '../config/constants.js'

let connection = null
let manifestCache = null

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

export function getAtoMetricProperty(scenarioYear, metricColumn) {
  return `y${Number(scenarioYear)}_${metricColumn}`
}

export function getAtoMetricAvailabilityProperty(scenarioYear, metricColumn) {
  return `${getAtoMetricProperty(scenarioYear, metricColumn)}_has`
}

export function getAtoMetricRange(manifest, scenarioYear, modelArea, metricColumn) {
  const groupedRange = manifest.metric_ranges?.[`${Number(scenarioYear)}|${modelArea}`]?.[metricColumn]
  return {
    minValue: Number(groupedRange?.min ?? 0),
    maxValue: Number(groupedRange?.max ?? 0),
    hasRange: Boolean(groupedRange),
  }
}

export function hasAtoMetricData(manifest, scenarioYear, modelArea, metricColumn) {
  const { maxValue, hasRange } = getAtoMetricRange(
    manifest,
    scenarioYear,
    modelArea,
    metricColumn,
  )
  const recordCount = Number(
    manifest.record_counts?.[`${Number(scenarioYear)}|${modelArea}`] ?? 0,
  )

  return hasRange
    && recordCount > 0
    && Number.isFinite(maxValue)
    && maxValue > 0
    && Boolean(manifest.files?.pmtiles)
}

export function getAtoSelectionSummary({ manifest, scenarioYear, modelArea, metricColumn }) {
  const { minValue, maxValue, hasRange } = getAtoMetricRange(
    manifest,
    scenarioYear,
    modelArea,
    metricColumn,
  )
  const recordCount = Number(
    manifest.record_counts?.[`${Number(scenarioYear)}|${modelArea}`]
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

export async function loadAtoManifest() {
  if (manifestCache) return manifestCache
  const response = await fetch(`${DATA_BASE_URL}/ato/manifest.json`)
  if (!response.ok) {
    throw new Error(`Failed to load ATO manifest: ${response.status}`)
  }
  manifestCache = await response.json()
  return manifestCache
}

export async function loadAtoRows({ scenarioYear, modelArea, metricColumn }) {
  const manifest = await loadAtoManifest()
  if (!manifest.metrics.includes(metricColumn)) {
    throw new Error(`Metric ${metricColumn} is not listed in the ATO manifest`)
  }

  const conn = await getConnection()
  const metricsUrl = `${DATA_BASE_URL}/${manifest.files.metrics}`
  const metricIdentifier = quoteIdentifier(metricColumn)
  const modelAreaSql = quoteString(modelArea)

  const table = await conn.query(`
    SELECT
      "ScenarioYear",
      "ModelArea",
      "SA_TAZID",
      "CO_TAZID",
      CAST(${metricIdentifier} AS DOUBLE) AS metric_value
    FROM read_parquet('${metricsUrl}')
    WHERE "ScenarioYear" = ${Number(scenarioYear)}
      AND "ModelArea" = '${modelAreaSql}'
    ORDER BY "CO_TAZID"
  `)

  const rows = tableToRows(table)
  const { minValue, maxValue } = getAtoMetricRange(manifest, scenarioYear, modelArea, metricColumn)
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
