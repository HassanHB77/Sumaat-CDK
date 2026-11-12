import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { MenuItem } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import {
  addItem,
  EMPTY_CART,
  itemCount,
  parseCart,
  reconcile,
  setNote,
  setQty,
  totalHalalas,
  type Cart,
  type CartRestaurant,
} from './cartLogic'

const STORAGE_KEY = 'sumaat.cart'

type CartValue = {
  cart: Cart
  count: number
  total: number
  add: (restaurant: CartRestaurant, item: MenuItem) => void
  setQty: (itemId: string, qty: number) => void
  setNote: (note: string) => void
  clear: () => void
  /** Match the cart to a freshly loaded menu; true if something changed (show a message). */
  reconcileWith: (restaurantId: string, menu: MenuItem[]) => boolean
}

const CartContext = createContext<CartValue | null>(null)

function load(): Cart {
  try {
    return parseCart(localStorage.getItem(STORAGE_KEY))
  } catch {
    return { ...EMPTY_CART }
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [cart, setCart] = useState<Cart>(load)
  const cartRef = useRef(cart) // latest cart for reconcileWith (kept stable for effects that call it)

  // Save on every change.
  useEffect(() => {
    cartRef.current = cart
    try {
      if (cart.lines.length) localStorage.setItem(STORAGE_KEY, JSON.stringify(cart))
      else localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* private mode: the cart just won't survive a reload */
    }
  }, [cart])

  // Same cart in every tab.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setCart(parseCart(e.newValue))
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  // Clear on log out (shared devices): the next person starts with an empty cart.
  const { status } = useAuth()
  const wasSignedIn = useRef(false)
  useEffect(() => {
    if (status === 'signedIn') wasSignedIn.current = true
    if (status === 'signedOut' && wasSignedIn.current) {
      wasSignedIn.current = false
      setCart({ ...EMPTY_CART })
    }
  }, [status])

  const reconcileWith = useCallback((restaurantId: string, menu: MenuItem[]) => {
    const result = reconcile(cartRef.current, restaurantId, menu)
    if (result.changed) setCart(result.cart)
    return result.changed
  }, [])

  const value = useMemo<CartValue>(
    () => ({
      cart,
      count: itemCount(cart),
      total: totalHalalas(cart),
      add: (restaurant, item) => setCart((c) => addItem(c, restaurant, item)),
      setQty: (itemId, qty) => setCart((c) => setQty(c, itemId, qty)),
      setNote: (note) => setCart((c) => setNote(c, note)),
      clear: () => setCart({ ...EMPTY_CART }),
      reconcileWith,
    }),
    [cart, reconcileWith],
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart(): CartValue {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used inside <CartProvider>')
  return ctx
}
