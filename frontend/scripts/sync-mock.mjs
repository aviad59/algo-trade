import { cpSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const src = join(root, '..', 'backend', 'mock', 'v1')
const dest = join(root, 'public', 'mock', 'v1')

rmSync(dest, { recursive: true, force: true })
cpSync(src, dest, { recursive: true })
console.log('Synced backend/mock/v1 -> frontend/public/mock/v1')
