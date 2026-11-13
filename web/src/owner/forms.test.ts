import { describe, expect, it } from 'vitest'
import { changedFields, composeHours, halalasToSar, parseSar, splitHours, validateItem, validateRestaurant } from './forms'

describe('hours', () => {
  it('split and compose', () => {
    expect(splitHours('13:00-01:00')).toEqual({ open: '13:00', close: '01:00', allDay: false })
    expect(splitHours('00:00-00:00').allDay).toBe(true)
    expect(composeHours('12:00', '23:30', false)).toBe('12:00-23:30')
    expect(composeHours('13:00', '01:00', false)).toBe('13:00-01:00') // past midnight
    expect(composeHours('x', 'y', true)).toBe('00:00-00:00')
    expect(composeHours('25:00', '23:00', false)).toBeNull()
    expect(composeHours('10:00', '10:00', false)).toBeNull() // use "Open 24 hours" instead
  })
})

describe('price', () => {
  it.each([
    ['48', 4800],
    ['48.5', 4850],
    ['48.50', 4850],
    ['0.99', 99],
    ['10000', 1_000_000],
  ])('%s -> %i halalas', (text, halalas) => {
    expect(parseSar(text)).toBe(halalas)
  })

  it.each(['', '1,5', '-1', '12.345', '0', 'abc', '10000.01'])('%s is rejected', (text) => {
    expect(parseSar(text)).toBeNull()
  })

  it('halalas -> SAR text', () => {
    expect(halalasToSar(4850)).toBe('48.50')
    expect(halalasToSar(99)).toBe('0.99')
  })
})

describe('changedFields', () => {
  it('only what changed', () => {
    const a = { name: 'A', priceHalalas: 100, dietTags: ['vegan'], isAvailable: true }
    expect(changedFields(a, { ...a })).toEqual({})
    expect(changedFields(a, { ...a, priceHalalas: 150, dietTags: ['vegan'] })).toEqual({ priceHalalas: 150 })
    expect(changedFields(a, { ...a, dietTags: ['vegan', 'spicy'] })).toEqual({ dietTags: ['vegan', 'spicy'] })
  })
})

describe('validation', () => {
  const good = {
    name: 'Test Bakery',
    nameAr: 'مخبز تجريبي',
    description: '',
    descriptionAr: '',
    cuisines: ['saudi' as const],
    city: 'Al-Hofuf',
    district: 'Al-Kut',
    lat: 25.38,
    lng: 49.588,
    hours: '07:00-22:00',
  }

  it('restaurant', () => {
    expect(validateRestaurant(good)).toEqual({})
    const e = validateRestaurant({ ...good, name: ' ', description: 'x'.repeat(501), lat: 24.7, hours: '' })
    expect(Object.keys(e).sort()).toEqual(['description', 'hours', 'lat', 'name'])
  })

  it('restaurant cuisines (1 to 3) and Arabic description', () => {
    expect(validateRestaurant({ ...good, cuisines: [] }).cuisines).toBe('owner.err.cuisines')
    expect(validateRestaurant({ ...good, cuisines: ['pizza', 'italian', 'burgers', 'bbq'] }).cuisines).toBe('owner.err.cuisines')
    expect(validateRestaurant({ ...good, cuisines: ['pizza', 'italian', 'burgers'] })).toEqual({})
    expect(validateRestaurant({ ...good, descriptionAr: 'x'.repeat(501) }).descriptionAr).toBe('owner.err.tooLong')
  })

  it('menu item', () => {
    const item = { name: 'Tea', nameAr: 'شاي', category: 'Drinks', price: '5', calories: '', dietTags: [], isAvailable: true }
    expect(validateItem(item)).toEqual({})
    expect(Object.keys(validateItem({ ...item, price: '5.555', calories: '-3', category: '' })).sort()).toEqual([
      'calories',
      'category',
      'price',
    ])
  })
})
