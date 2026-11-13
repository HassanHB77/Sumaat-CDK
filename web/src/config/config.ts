/**
 * Runtime config, loaded from /config.json before the app renders.
 * CDK writes it on every deploy (infra/web_stack.py); locally `npm run config:pull` copies the live one.
 * Nothing in it is secret: these are values every browser needs.
 */
export type AppConfig = {
  region: string
  userPoolId: string
  userPoolClientId: string
  locationApiKey: string
  apiBase: string // "/api"
  chatPath?: string // "/agent/chat" (AI chat, Step 9); absent = no chat button
  chatDailyLimit?: number // messages per customer per business day
}

let current: AppConfig | null = null

export async function loadConfig(fetchImpl: typeof fetch = fetch): Promise<AppConfig> {
  const res = await fetchImpl('/config.json', { cache: 'no-store' })
  if (!res.ok) throw new Error(`config.json: HTTP ${res.status}`)
  const data = (await res.json()) as Partial<AppConfig>
  for (const key of ['region', 'userPoolId', 'userPoolClientId', 'apiBase'] as const) {
    if (!data[key]) throw new Error(`config.json is missing "${key}"`)
  }
  current = { locationApiKey: '', ...data } as AppConfig
  return current
}

export function getConfig(): AppConfig {
  if (!current) throw new Error('Config not loaded yet')
  return current
}
