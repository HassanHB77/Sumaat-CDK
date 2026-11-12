import { Navigate } from 'react-router'
import { useLanguage } from '../i18n/LanguageContext'
import { OrderBoard } from './OrderBoard'
import { useStaff } from './StaffLayout'

/** /counter (cashier) and /owner/orders (owner): the same board for the signed-in user's restaurant. */
export function CounterPage() {
  const { restaurantId, soundOn } = useStaff()
  const { t } = useLanguage()
  if (!restaurantId) return <p className="alert alert-warning">{t('counter.noRestaurant')}</p>
  return <OrderBoard restaurantId={restaurantId} soundOn={soundOn} />
}

/** /owner: orders if the owner has a restaurant, otherwise set one up first (M5). */
export function OwnerHome() {
  const { restaurantId } = useStaff()
  return <Navigate to={restaurantId ? '/owner/orders' : '/owner/setup'} replace />
}
