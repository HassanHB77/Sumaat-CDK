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

// --- orders ---

export type OrderStatus = 'PLACED' | 'ACCEPTED' | 'READY_FOR_PICKUP' | 'SERVED' | 'REJECTED' | 'CANCELLED'

export type OrderLine = {
  itemId: string
  name: string
  nameAr: string
  unitPriceHalalas: number
  qty: number
  lineTotalHalalas: number
}

export type StatusChange = {
  status: OrderStatus
  at: string // UTC ISO
  by: string
  role: 'customer' | 'owner' | 'cashier'
  reason?: string | null
}

export type Order = {
  id: string
  orderNumber: number // restarts at #1 every business day: always show it with the date
  businessDate: string // "YYYY-MM-DD" (04:00-04:00 Riyadh)
  restaurantId: string
  restaurantName: string
  restaurantNameAr?: string | null
  customerName?: string | null
  customerPhone?: string | null
  items: OrderLine[]
  totalHalalas: number // VAT included
  note?: string | null
  status: OrderStatus
  statusHistory: StatusChange[]
  createdAt: string
  updatedAt: string
}

export type PlaceOrderBody = {
  restaurantId: string
  items: { itemId: string; qty: number }[] // never prices: the API uses its own
  note?: string
}
