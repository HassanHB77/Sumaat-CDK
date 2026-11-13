/// <reference types="vitest/config" />
import { readFileSync } from 'node:fs'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/**
 * Local dev: "/api" (and "/agent", the AI chat) are proxied to the DEPLOYED site (CloudFront -> API Gateway /
 * AgentCore), so the app always calls relative paths, exactly like in production. The URL comes from ../outputs.json
 * (written by `cdk deploy --outputs-file outputs.json`); override with SUMAAT_API_ORIGIN.
 */
function apiOrigin(): string {
  if (process.env.SUMAAT_API_ORIGIN) return process.env.SUMAAT_API_ORIGIN
  try {
    const outputs = JSON.parse(readFileSync(new URL('../outputs.json', import.meta.url), 'utf8'))
    return outputs.SumaatWeb.SiteUrl
  } catch {
    return 'https://dawmf7ub9dh1o.cloudfront.net'
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
  server: {
    port: 5173, // the map key and API CORS allow exactly this origin
    strictPort: true,
    proxy: {
      '/api': { target: apiOrigin(), changeOrigin: true, secure: true },
      '/agent': { target: apiOrigin(), changeOrigin: true, secure: true },
    },
  },
  test: {
    environment: 'jsdom',
  },
})
