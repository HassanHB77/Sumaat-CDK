import type { MenuItem } from '../api/types'
import { useCart } from '../cart/CartContext'
import { needsReplace, qtyOf, type CartRestaurant } from '../cart/cartLogic'
import { useLanguage } from '../i18n/LanguageContext'
import { QtyStepper } from './CartParts'

/** "+ Add", then a − n + stepper once the dish is in the cart. Another restaurant's cart -> ask first. */
export function AddToCart({
  restaurant,
  item,
  disabled,
  onNeedReplace,
}: {
  restaurant: CartRestaurant
  item: MenuItem
  disabled: boolean
  onNeedReplace: (item: MenuItem) => void
}) {
  const { cart, add, setQty } = useCart()
  const { t } = useLanguage()
  const qty = cart.restaurantId === restaurant.id ? qtyOf(cart, item.id) : 0

  if (qty > 0) return <QtyStepper qty={qty} onChange={(n) => setQty(item.id, n)} disabled={disabled} />
  return (
    <button
      type="button"
      className="btn btn-sm btn-primary"
      disabled={disabled}
      title={disabled ? t('cart.closedHint') : undefined}
      onClick={() => (needsReplace(cart, restaurant.id) ? onNeedReplace(item) : add(restaurant, item))}
    >
      + {t('cart.add')}
    </button>
  )
}
