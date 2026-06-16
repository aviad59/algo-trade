import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const src = join(root, '..', 'backend', 'mock', 'v1')
const dest = join(root, 'public', 'mock', 'v1')

function copyDir(from, to) {
  mkdirSync(to, { recursive: true })

  for (const entry of readdirSync(from, { withFileTypes: true })) {
    const sourcePath = join(from, entry.name)
    const destPath = join(to, entry.name)

    if (entry.isDirectory()) {
      copyDir(sourcePath, destPath)
      continue
    }

    try {
      writeFileSync(destPath, readFileSync(sourcePath))
    } catch (error) {
      const code = error instanceof Error && 'code' in error ? String(error.code) : ''
      if (code === 'EPERM' || code === 'EBUSY') {
        continue
      }
      throw error
    }
  }
}

copyDir(src, dest)
console.log('Synced backend/mock/v1 -> frontend/public/mock/v1')
