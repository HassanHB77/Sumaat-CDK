import { describe, expect, it } from 'vitest'
import { isEmail } from '../lib/validation'

describe('isEmail (same rule as the API)', () => {
  it.each(['a@b.co', 'sara.q+test@gmail.com', ' owner.nakhla@example.com '])('%s is valid', (v) => expect(isEmail(v)).toBe(true))
  it.each(['ali.mubarraz@example.com,', 'a b@c.de', 'a@b', 'a;b@c.de', '<a@b.co>', ''])('%s is rejected', (v) =>
    expect(isEmail(v)).toBe(false),
  )
})
