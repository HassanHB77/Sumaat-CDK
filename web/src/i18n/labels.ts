import { en, type MessageKey } from './en'

function isKey(key: string): key is MessageKey {
  return key in en
}

type T = (key: MessageKey, vars?: Record<string, string | number>) => string

/** Translated category name; categories added later (via CLI) without a translation show as they are. */
export function categoryLabel(category: string, t: T): string {
  const key = `cat.${category}`
  return isKey(key) ? t(key) : category
}

export function dietLabel(tag: string, t: T): string {
  const key = `diet.${tag}`
  return isKey(key) ? t(key) : tag
}

export function cuisineLabel(cuisine: string, t: T): string {
  const key = `cuisine.${cuisine}`
  return isKey(key) ? t(key) : cuisine
}
