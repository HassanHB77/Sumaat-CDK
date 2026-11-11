import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ar } from './ar'
import { en, type MessageKey } from './en'

export type Lang = 'en' | 'ar'

const STORAGE_KEY = 'sumaat.lang'
const dictionaries: Record<Lang, Record<MessageKey, string>> = { en, ar }

/** Replace {name} placeholders. Unknown placeholders are left as they are. */
export function format(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (match, name) => (name in vars ? String(vars[name]) : match))
}

export function translate(lang: Lang, key: MessageKey, vars?: Record<string, string | number>): string {
  return format(dictionaries[lang][key] ?? en[key] ?? key, vars)
}

/** First visit: saved choice, else Arabic if the browser prefers Arabic, else English. */
export function initialLang(saved: string | null, browserLang: string | undefined): Lang {
  if (saved === 'ar' || saved === 'en') return saved
  return browserLang?.toLowerCase().startsWith('ar') ? 'ar' : 'en'
}

type LanguageValue = {
  lang: Lang
  dir: 'ltr' | 'rtl'
  setLang: (lang: Lang) => void
  toggle: () => void
  t: (key: MessageKey, vars?: Record<string, string | number>) => string
}

const LanguageContext = createContext<LanguageValue | null>(null)

function readSaved(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => initialLang(readSaved(), navigator.language))
  const dir = lang === 'ar' ? 'rtl' : 'ltr'

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = dir
  }, [lang, dir])

  const setLang = useCallback((next: Lang) => {
    setLangState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* private mode: just don't remember */
    }
  }, [])

  const value = useMemo<LanguageValue>(
    () => ({
      lang,
      dir,
      setLang,
      toggle: () => setLang(lang === 'ar' ? 'en' : 'ar'),
      t: (key, vars) => translate(lang, key, vars),
    }),
    [lang, dir, setLang],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageValue {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used inside <LanguageProvider>')
  return ctx
}
