// Download the live /config.json (written by CDK on deploy) into public/config.json for local dev.
// Usage: npm run config:pull      (needs ../outputs.json from `cdk deploy --outputs-file outputs.json`)
import { readFileSync, writeFileSync } from 'node:fs'

const outputs = JSON.parse(readFileSync(new URL('../../outputs.json', import.meta.url), 'utf8'))
const site = outputs.SumaatWeb?.SiteUrl
if (!site) {
  console.error('outputs.json has no SumaatWeb.SiteUrl. Deploy SumaatWeb with --outputs-file outputs.json first.')
  process.exit(1)
}

const res = await fetch(`${site}/config.json`, { cache: 'no-store' })
if (!res.ok) {
  console.error(`Could not download ${site}/config.json (HTTP ${res.status})`)
  process.exit(1)
}
const config = await res.json()
writeFileSync(new URL('../public/config.json', import.meta.url), JSON.stringify(config, null, 2) + '\n')
console.log(`Saved public/config.json from ${site} (git-ignored).`)
