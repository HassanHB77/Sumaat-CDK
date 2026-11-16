import { describe, expect, it } from 'vitest'
import { checkPhotoFile, fitSize, MAX_INPUT_BYTES, PhotoError } from './images'

describe('fitSize', () => {
  it('shrinks the longest side to 1200 and keeps the shape', () => {
    expect(fitSize(4032, 3024)).toEqual({ width: 1200, height: 900 })
    expect(fitSize(3024, 4032)).toEqual({ width: 900, height: 1200 })
  })
  it('never enlarges small photos', () => {
    expect(fitSize(800, 600)).toEqual({ width: 800, height: 600 })
  })
})

describe('checkPhotoFile', () => {
  const file = (type: string, size: number) => {
    const f = new File(['x'], 'p', { type })
    Object.defineProperty(f, 'size', { value: size })
    return f
  }
  it('accepts images', () => {
    expect(() => checkPhotoFile(file('image/heic', 5_000_000))).not.toThrow()
  })
  it('refuses non-images and huge files', () => {
    expect(() => checkPhotoFile(file('application/pdf', 100))).toThrow(PhotoError)
    expect(() => checkPhotoFile(file('image/jpeg', MAX_INPUT_BYTES + 1))).toThrow(PhotoError)
  })
})
