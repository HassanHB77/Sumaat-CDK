import { describe, expect, it } from 'vitest'
import { generatePassword, isStrongPassword } from '../lib/password'
import { validateCashier } from './CashierDialogs'

describe('generatePassword', () => {
  it('always meets the pool rules, 12 chars, no look-alikes', () => {
    const seen = new Set<string>()
    for (let i = 0; i < 200; i++) {
      const pw = generatePassword()
      expect(pw).toHaveLength(12)
      expect(isStrongPassword(pw)).toBe(true)
      expect(pw).not.toMatch(/[0O1lI]/)
      seen.add(pw)
    }
    expect(seen.size).toBe(200) // random, not repeating
  })
})

describe('validateCashier', () => {
  const good = { name: 'Ali', email: 'ali@example.com', phone: '0512345678', password: 'Sumaat#1' }
  it('good input passes', () => expect(validateCashier(good)).toEqual({}))
  it('reports each bad field', () => {
    expect(Object.keys(validateCashier({ name: ' ', email: 'ali@', phone: '123', password: 'weak' })).sort()).toEqual([
      'email',
      'name',
      'password',
      'phone',
    ])
  })
})
