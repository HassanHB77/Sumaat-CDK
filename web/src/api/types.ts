/** Shapes returned by the Sumaat API (see api/models.py in the backend). Money is always integer halalas. */

// Fixed lists, same as api/models.py (tests/unit/test_seed_data_quality.py keeps them identical).
export const DIET_TAGS = [
  'vegetarian', 'vegan', 'gluten_free', 'dairy_free', 'high_protein', 'spicy',
  'low_carb', 'keto', 'low_calorie', 'sugar_free', 'nut_free', 'contains_nuts', 'kids', 'contains_seafood',
] as const
export type DietTag = (typeof DIET_TAGS)[number]

export const CUISINES = [
  'saudi', 'cafe', 'juices', 'sweets', 'burgers', 'pizza', 'bbq', 'healthy',
  'italian', 'indian', 'lebanese', 'turkish', 'asian', 'seafood',
] as const
export type Cuisine = (typeof CUISINES)[number]
export const MAX_CUISINES = 3

export type Restaurant = {
  id: string
  name: string
  nameAr: string
  description: string
  descriptionAr?: string // older rows may lack it
  cuisines?: Cuisine[]
  city: string
  district: string
  lat: number
  lng: number
  hours: string // "HH:MM-HH:MM", Riyadh time; may pass midnight ("13:00-01:00")
  isPaused: boolean
  openNow: boolean // computed by the API: inside hours AND not paused. Never compute it here.
  imageUrl?: string | null // "/img/..." on the site's own address; null/missing = no photo
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
  imageUrl?: string | null // "/img/..." on the site's own address; null/missing = no photo
  popular?: boolean // one of the restaurant's top dishes (last 30 days); only from GET /restaurants/{id}
}

export type RestaurantDetail = Restaurant & {
  menu: MenuItem[]
  typicalReadyMinutes?: number | null // median accept -> ready over the last 30 days (null: too few orders)
}

// --- owner numbers (GET /restaurants/{id}/stats; sales = served orders) ---

export type OwnerStats = {
  today: {
    orders: number
    served: number
    open: number
    rejected: number
    cancelled: number
    salesHalalas: number
    avgOrderHalalas: number
    avgPrepMinutes: number | null
    bestSeller: { itemId: string; name: string; nameAr: string; qty: number } | null
  }
  last7: { date: string; servedOrders: number; salesHalalas: number }[] // oldest first, last = today
}

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

// --- cashiers ---

export type Cashier = {
  sub: string
  name: string
  email: string
  phone: string
  status: 'active' | 'disabled'
  createdAt: string
  updatedAt: string
}
