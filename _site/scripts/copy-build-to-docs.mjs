import { cp, mkdir, readdir, rm, stat } from 'node:fs/promises'
import { dirname, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const siteDir = resolve(scriptDir, '..')
const repoRoot = resolve(siteDir, '..')
const distDir = resolve(siteDir, 'dist')
const docsDir = resolve(repoRoot, 'docs')

async function pathExists(path) {
  try {
    await stat(path)
    return true
  } catch (error) {
    if (error.code === 'ENOENT') return false
    throw error
  }
}

if (!(await pathExists(distDir))) {
  throw new Error('Missing _site/dist. Run `npm run build:site` before copying to docs.')
}

if (!docsDir.endsWith(`${sep}docs`)) {
  throw new Error(`Refusing to overwrite unexpected docs path: ${docsDir}`)
}

await mkdir(docsDir, { recursive: true })
for (const entry of await readdir(docsDir)) {
  const entryPath = resolve(docsDir, entry)

  try {
    await rm(entryPath, {
      recursive: true,
      force: true,
      maxRetries: 5,
      retryDelay: 200,
    })
  } catch (error) {
    if (entry === '.serve-logs' && ['EBUSY', 'EPERM'].includes(error.code)) {
      console.warn(`Skipping locked local log folder: ${entryPath}`)
      continue
    }

    throw error
  }
}
await cp(distDir, docsDir, { recursive: true, force: true })

console.log(`Copied ${distDir} to ${docsDir}`)
