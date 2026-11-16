import { Link } from 'react-router'
import type { NearbyRestaurant } from '../api/types'
import { useLanguage } from '../i18n/LanguageContext'
import { formatKm, pickDescription, pickName } from '../lib/format'
import { CuisineBadges } from './CuisineParts'
import { HoursText, OpenStatusBadge } from './OpenStatusBadge'
import { Photo } from './Photo'
import { RestaurantIcon } from './RestaurantIcon'

export function RestaurantCard({ restaurant: r }: { restaurant: NearbyRestaurant }) {
  const { lang } = useLanguage()
  const closed = !r.openNow
  const description = pickDescription(r, lang)
  return (
    <Link
      to={`/r/${r.id}`}
      className={`card card-side bg-base-100 shadow-sm transition hover:shadow-md ${closed ? 'opacity-70' : ''}`}
    >
      <figure className="ps-4">
        <Photo src={r.imageUrl} className="size-20" dimmed={closed} fallback={<RestaurantIcon dimmed={closed} />} />
      </figure>
      <div className="card-body gap-1 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="card-title text-lg">{pickName(r, lang)}</h2>
          <OpenStatusBadge restaurant={r} />
        </div>
        <p className="text-sm text-muted">
          {r.district} · {r.city} · <span dir="ltr">{formatKm(r.distanceKm, lang)}</span>
        </p>
        <CuisineBadges cuisines={r.cuisines} />
        {description && <p className="line-clamp-1 text-sm">{description}</p>}
        <p className="text-sm text-muted">
          <HoursText hours={r.hours} />
        </p>
      </div>
    </Link>
  )
}
