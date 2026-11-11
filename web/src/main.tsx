import '@fontsource/ibm-plex-sans-arabic/400.css'
import '@fontsource/ibm-plex-sans-arabic/500.css'
import '@fontsource/ibm-plex-sans-arabic/700.css'
import './index.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { configureApi } from './api/client'
import { configureAmplify } from './auth/amplify'
import { loadConfig } from './config/config'
import { App } from './App'
import { initialLang, translate } from './i18n/LanguageContext'

const root = createRoot(document.getElementById('root')!)

/** Startup: /config.json -> Amplify + API client -> render. Nothing renders before the config is known. */
async function start() {
  try {
    const config = await loadConfig()
    configureAmplify(config)
    configureApi({ base: config.apiBase })
  } catch (e) {
    console.error(e)
    let saved: string | null = null
    try {
      saved = localStorage.getItem('sumaat.lang')
    } catch {
      /* ignore */
    }
    const lang = initialLang(saved, navigator.language)
    document.documentElement.lang = lang
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'
    root.render(
      <main className="mx-auto max-w-md p-8 text-center">
        <p className="alert alert-error">{translate(lang, 'error.config')}</p>
      </main>,
    )
    return
  }
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

start()
