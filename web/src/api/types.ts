/** Shapes returned by the Sumaat API (see api/models.py in the backend). Money is always integer halalas. */

export type DietTag = 'vegetarian' | 'vegan' | 'gluten_free' | 'dairy_free' | 'high_protein' | 'spicy'

export const DIET_TAGS: DietTag[] = ['vegetarian', 'vegan', 'gluten_free', 'dairy_free', 'high_protein', 'spicy']

export type Restaurant = {
  id: string
  name: string
  nameAr: string
  description: string
  city: string
  district: string
  lat: number
  lng: number
  hours: string // "HH:MM-HH:MM", Riyadh time; may pass midnight ("13:00-01:00")
  isPaused: boolean
  openNow: boolean // computed by the API: inside hours AND not paused. Never compute it here.
  createdAt: string
  updatedAt: string
}

export type NearbyRestaurant = Restaurant & { distanceKm: number }

export type MenuItem = {
  id: string
  restaurantId: string
  name: string
  nameAr: string
  category: string
  priceHalalas: number
  calories: number
  dietTags: DietTag[]
  isAvailable: boolean
}

export type RestaurantDetail = Restaurant & { menu: MenuItem[] }

export type Categories = { categories: string[] } // in menu order
