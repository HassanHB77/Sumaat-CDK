import { Outlet } from 'react-router'
import { CartBar } from '../components/CartParts'
import { PublicHeader } from '../components/PublicHeader'

/** Visitors + customers (staff get their own header in M4/M5). Bottom padding leaves room for the cart bar. */
export function RootLayout() {
  return (
    <div className="flex min-h-dvh flex-col pb-24">
      <PublicHeader />
      <Outlet />
      <CartBar />
    </div>
  )
}
