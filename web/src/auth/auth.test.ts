import { describe, expect, it } from 'vitest'
import { isStrongPassword, passwordChecks } from '../lib/password'
import { isValidSaudiMobile, normalizeSaudiMobile, toE164 } from '../lib/phone'
import { cognitoErrorKey } from './cognitoErrors'
import { roleHome, safeNext, userFromPayload } from './session'

describe('phone', () => {
  it.each(['512345678', '0512345678', '05 1234 5678', '051-234-5678', '+966512345678', '00966512345678'])(
    '%s -> +966512345678',
    (input) => {
      expect(isValidSaudiMobile(input)).toBe(true)
      expect(toE164(input)).toBe('+966512345678')
    },
  )

  it.each(['412345678', '51234567', '5123456789', '', 'abc'])('%s is invalid', (input) => {
    expect(isValidSaudiMobile(input)).toBe(false)
  })

  it('normalize keeps what the user typed after +966', () => {
    expect(normalizeSaudiMobile('0512')).toBe('512')
  })
})

describe('password', () => {
  it('pool rules', () => {
    expect(isStrongPassword('Sumaat#1')).toBe(true)
    expect(isStrongPassword('sumaat#1')).toBe(false)
    expect(passwordChecks('Sumaat1')).toEqual({ length: false, upper: true, lower: true, digit: true, symbol: false })
    expect(passwordChecks('SUMAAT#1').lower).toBe(false)
    expect(passwordChecks('Sumaat#x').digit).toBe(false)
  })
})

describe('session', () => {
  it('reads role and restaurant from the ID token payload', () => {
    expect(
      userFromPayload({ sub: 's1', name: 'Sara', email: 'sara@example.com', 'cognito:groups': ['customer'] }),
    ).toEqual({ sub: 's1', name: 'Sara', email: 'sara@example.com', role: 'customer', restaurantId: null })
    const cashier = userFromPayload({ sub: 'c1', 'cognito:groups': ['cashier'], 'custom:restaurantId': 'r1' })
    expect([cashier.role, cashier.restaurantId]).toEqual(['cashier', 'r1'])
    expect(userFromPayload({ sub: 'x' }).role).toBeNull() // just confirmed, group not in token yet
  })

  it('safeNext only allows same-site paths', () => {
    expect(safeNext('/cart')).toBe('/cart')
    expect(safeNext('/r/abc?x=1')).toBe('/r/abc?x=1')
    for (const bad of ['//evil.com', 'https://evil.com', 'javascript:alert(1)', '/\\evil.com', '/login', null]) {
      expect(safeNext(bad)).toBeNull()
    }
  })

  it('roleHome', () => {
    expect(roleHome('customer', '/cart')).toBe('/cart')
    expect(roleHome('customer', null)).toBe('/restaurants')
    expect(roleHome('customer', '/owner/menu')).toBe('/restaurants')
    expect(roleHome('owner', '/cart')).toBe('/owner')
    expect(roleHome('cashier', '/orders')).toBe('/counter')
    expect(roleHome(null)).toBe('/')
  })
})

describe('cognitoErrorKey', () => {
  it.each([
    [{ name: 'NotAuthorizedException', message: 'Incorrect username or password.' }, 'auth.err.wrongCredentials'],
    [{ name: 'NotAuthorizedException', message: 'User is disabled.' }, 'auth.err.disabled'],
    [{ name: 'UsernameExistsException' }, 'auth.err.emailTaken'],
    [{ name: 'CodeMismatchException' }, 'auth.err.codeWrong'],
    [{ name: 'ExpiredCodeException' }, 'auth.err.codeExpired'],
    [{ name: 'LimitExceededException' }, 'auth.err.tooMany'],
    [{ name: 'InvalidParameterException', message: 'Invalid phone number format.' }, 'auth.err.phone'],
    [{ name: 'Whatever' }, 'auth.err.generic'],
    [null, 'auth.err.generic'],
  ])('%o -> %s', (error, key) => {
    expect(cognitoErrorKey(error)).toBe(key)
  })
})
