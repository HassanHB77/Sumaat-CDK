/**
 * Photos: shrink in the browser, then upload straight to S3 with the API's presigned form.
 *
 * Phones take 3-12 MB photos; we send a ~1200 px JPEG (usually 150-400 KB), which is fast on mobile data and
 * small for customers to download. The API only accepts JPEG up to 3 MB.
 */
import { attachImage, getImageUploadForm } from '../api/endpoints'
import type { MenuItem, Restaurant } from '../api/types'

export const MAX_SIDE = 1200 // px, longest side after shrinking
export const MAX_INPUT_BYTES = 15 * 1024 * 1024 // refuse bigger originals before even reading them
const QUALITY = 0.85

export class PhotoError extends Error {
  code: 'notImage' | 'tooBig' | 'failed'
  constructor(code: 'notImage' | 'tooBig' | 'failed', message: string = code) {
    super(message)
    this.code = code
  }
}

/** New width/height that fit inside max x max, keeping the shape; never enlarges. */
export function fitSize(width: number, height: number, max = MAX_SIDE): { width: number; height: number } {
  const scale = Math.min(1, max / Math.max(width, height))
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) }
}

/** Check the file the owner picked (before reading it). */
export function checkPhotoFile(file: File): void {
  if (!file.type.startsWith('image/')) throw new PhotoError('notImage')
  if (file.size > MAX_INPUT_BYTES) throw new PhotoError('tooBig')
}

/** Any browser-readable image -> JPEG Blob, longest side <= MAX_SIDE (EXIF rotation applied). */
export async function resizeToJpeg(file: File): Promise<Blob> {
  checkPhotoFile(file)
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  } catch {
    throw new PhotoError('notImage')
  }
  const { width, height } = fitSize(bitmap.width, bitmap.height)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new PhotoError('failed', 'no canvas')
  ctx.fillStyle = '#fff' // transparent PNGs get a white background instead of black
  ctx.fillRect(0, 0, width, height)
  ctx.drawImage(bitmap, 0, 0, width, height)
  bitmap.close()
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY))
  if (!blob) throw new PhotoError('failed', 'could not encode JPEG')
  return blob
}

/** Shrink + upload + attach. Returns the updated restaurant (no itemId) or dish. */
export async function uploadPhoto<T extends Restaurant | MenuItem>(restaurantId: string, file: File, itemId?: string): Promise<T> {
  const jpeg = await resizeToJpeg(file)
  const form = await getImageUploadForm(restaurantId, itemId)
  if (jpeg.size > form.maxBytes) throw new PhotoError('tooBig')

  const body = new FormData()
  for (const [k, v] of Object.entries(form.fields)) body.append(k, v)
  body.append('file', jpeg, 'photo.jpg') // the file must be the LAST field of an S3 POST
  let res: Response
  try {
    res = await fetch(form.url, { method: 'POST', body })
  } catch {
    throw new PhotoError('failed', 'network')
  }
  if (!res.ok) throw new PhotoError('failed', `S3 ${res.status}`)

  return attachImage<T>(restaurantId, form.key, itemId)
}
