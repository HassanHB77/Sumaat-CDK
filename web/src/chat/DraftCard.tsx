import { Link } from 'react-router'
import { useCart } from '../cart/CartContext'
import type { CartDraft } from '../cart/cartLogic'
import { useLanguage } from '../i18n/LanguageContext'
import { formatMoney, pickName } from '../lib/format'

/** The assistant's cart draft: review it, then "Add to cart" (replaces the cart; a note says so). */
export function DraftCard({ draft, added, onAdded }: { draft: CartDraft; added: boolean; onAdded: () => void }) {
  const { cart, count, replaceWith } = useCart()
  const { t, lang } = useLanguage()
  const replaces = count > 0 && !added

  return (
    <div className="card card-border bg-base-100 mt-2 w-full text-base-content">
      <div className="card-body gap-2 p-3">
        <div className="text-xs font-semibold uppercase opacity-60">{t('chat.draft')}</div>
        <div className="font-semibold">{pickName(draft.restaurant, lang)}</div>
        <ul className="text-sm">
          {draft.lines.map((l) => (
            <li key={l.itemId} className="flex justify-between gap-2">
              <span>
                <span dir="ltr">{l.qty} ×</span> {pickName(l, lang)}
              </span>
              <span dir="ltr" className="whitespace-nowrap">{formatMoney(l.priceHalalas * l.qty, lang)}</span>
            </li>
          ))}
        </ul>
        <div className="flex justify-between border-t border-base-300 pt-1 text-sm font-semibold">
          <span>{t('chat.total')}</span>
          <span dir="ltr">{formatMoney(draft.totalHalalas, lang)}</span>
        </div>
        {added ? (
          <div className="flex items-center justify-between gap-2">
            <span className="text-success text-sm">{t('chat.added')}</span>
            <Link to="/cart" className="btn btn-sm btn-outline">
              {t('chat.viewCart')}
            </Link>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {replaces && (
              <p className="text-warning-content bg-warning/20 rounded px-2 py-1 text-xs">
                {t('chat.replaces', { count, restaurant: pickName({ name: cart.restaurantName, nameAr: cart.restaurantNameAr }, lang) })}
              </p>
            )}
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={() => {
                replaceWith(draft)
                onAdded()
              }}
            >
              {t('chat.addToCart')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
