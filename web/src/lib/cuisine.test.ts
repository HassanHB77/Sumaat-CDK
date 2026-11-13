import { describe, expect, it } from 'vitest'
import { availableCuisines, filterByCuisine } from './cuisine'
import { pickDescription } from './format'

const pizza = { id: 'p', cuisines: ['pizza' as const, 'italian' as const] }
const sushi = { id: 's', cuisines: ['asian' as const, 'seafood' as const] }
const old: { id: string; cuisines?: ('pizza' | 'asian')[] } = { id: 'o' } // a row from before cuisines existed

describe('cuisine filter', () => {
  it('offers only cuisines that are present, in the fixed order', () => {
    expect(availableCuisines([sushi, pizza, old])).toEqual(['pizza', 'italian', 'asian', 'seafood'])
    expect(availableCuisines([])).toEqual([])
  })

  it('keeps restaurants with ANY selected cuisine', () => {
    expect(filterByCuisine([pizza, sushi, old], [])).toEqual([pizza, sushi, old])
    expect(filterByCuisine([pizza, sushi, old], ['italian'])).toEqual([pizza])
    expect(filterByCuisine([pizza, sushi, old], ['italian', 'seafood'])).toEqual([pizza, sushi])
    expect(filterByCuisine([pizza, sushi, old], ['bbq'])).toEqual([])
  })
})

describe('pickDescription', () => {
  it('uses the site language, falling back to the other one', () => {
    const both = { description: 'Smash burgers.', descriptionAr: 'برجر سماش.' }
    expect(pickDescription(both, 'en')).toBe('Smash burgers.')
    expect(pickDescription(both, 'ar')).toBe('برجر سماش.')
    expect(pickDescription({ description: 'Only English' }, 'ar')).toBe('Only English')
    expect(pickDescription({ description: '', descriptionAr: ' ' }, 'en')).toBe('')
  })
})
