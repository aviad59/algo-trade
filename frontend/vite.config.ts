import { createReadStream, existsSync, statSync } from 'node:fs'
import type { ServerResponse } from 'node:http'
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import type { IncomingMessage } from 'node:http'
import { defineConfig } from 'vitest/config'
import { loadEnv, type Plugin } from 'vite'

const repoRoot = path.resolve(__dirname, '..')
const mockRoot = path.resolve(repoRoot, 'backend/mock/v1')

function serveMockBundle(
  req: IncomingMessage,
  res: ServerResponse,
  next: (error?: Error) => void,
) {
  if (!req.url?.startsWith('/mock/v1/')) {
    next()
    return
  }

  const relativePath = decodeURIComponent(req.url.slice('/mock/v1/'.length).split('?')[0] || '')
  const filePath = path.resolve(mockRoot, relativePath)

  if (!filePath.startsWith(mockRoot) || !existsSync(filePath) || !statSync(filePath).isFile()) {
    next()
    return
  }

  res.setHeader('Content-Type', 'application/json')
  createReadStream(filePath).pipe(res)
}

function mockApiPlugin(): Plugin {
  return {
    name: 'mock-api',
    configureServer(server) {
      server.middlewares.use(serveMockBundle)
    },
    configurePreviewServer(server) {
      server.middlewares.use(serveMockBundle)
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, repoRoot, '')
  const apiPort = env.ALGO_TRADE_API_PORT || '8000'

  return {
    envDir: repoRoot,
    plugins: [mockApiPlugin(), react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      proxy: {
        '/api/v1': {
          target: `http://localhost:${apiPort}`,
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'node',
      include: ['tests/**/*.test.ts'],
    },
  }
})
