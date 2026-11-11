import { describe, expect, it } from 'vitest'
import { ar } from './ar'
import { en } from './en'
import { format, initialLang, translate } from './LanguageContext'

describe('i18n', () => {
  it('Arabic has every English key, and none empty', () => {
    expect(Object.keys(ar).sort()).toEqual(Object.keys(en).sort())
    for (const value of Object.values(ar)) expect(value.trim()).not.toBe('')
  })

  it('format replaces {vars}', () => {
    expect(format('Coming in {milestone}', { milestone: 'M1' })).toBe('Coming in M1')
    expect(format('Hi {name}', {})).toBe('Hi {name}')
  })

  it('translate picks the language', () => {
    expect(translate('en', 'nav.cart')).toBe('Cart')
    expect(translate('ar', 'nav.cart')).toBe('السلة')
    expect(translate('ar', 'placeholder.comingIn', { milestone: 'M1' })).toBe('قريبًا في M1')
  })

  it('first visit: saved choice, else browser language', () => {
    expect(initialLang('en', 'ar-SA')).toBe('en')
    expect(initialLang(null, 'ar-SA')).toBe('ar')
    expect(initialLang(null, 'en-US')).toBe('en')
    expect(initialLang('xx', undefined)).toBe('en')
  })
})
