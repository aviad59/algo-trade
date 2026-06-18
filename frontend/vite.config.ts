import { createReadStream, existsSync, statSync } from 'node:fs'
import type { ServerResponse } from 'node:http'
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import type { IncomingMessage } from 'node:http'
import { defineConfig, type Plugin } from 'vitest/config'

const mockRoot = path.resolve(__dirname, '../backend/mock/v1')

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

export default defineConfig({
  plugins: [mockApiPlugin(), react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
})
