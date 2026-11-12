import type { Restaurant } from '../api/types'
import { useLanguage } from '../i18n/LanguageContext'
import { opensAt, parseHours } from '../lib/format'

/** Open / Closed · opens 13:00 / Not taking orders. The state itself always comes from the API. */
export function OpenStatusBadge({ restaurant }: { restaurant: Pick<Restaurant, 'openNow' | 'isPaused' | 'hours'> }) {
  const { t } = useLanguage()
  if (restaurant.openNow) return <span className="badge badge-success font-medium">{t('open.open')}</span>
  if (restaurant.isPaused) return <span className="badge badge-ghost">{t('open.paused')}</span>
  return <span className="badge badge-ghost">{t('open.closedOpens', { time: opensAt(restaurant.hours) })}</span>
}

/** "13:00–01:00 (closes after midnight)" / "Open 24 hours". Times always left-to-right. */
export function HoursText({ hours }: { hours: string }) {
  const { t } = useLanguage()
  const h = parseHours(hours)
  if (h.allDay) return <span>{t('hours.allDay')}</span>
  return (
    <span>
      <span dir="ltr">
        {h.open}–{h.close}
      </span>
      {h.pastMidnight && <span className="ms-1">{t('hours.pastMidnight')}</span>}
    </span>
  )
}
