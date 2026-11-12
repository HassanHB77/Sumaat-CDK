import { Outlet } from 'react-router'
import { CartBar } from '../components/CartParts'
import { PublicHeader } from '../components/PublicHeader'
import { VerifyEmailNote } from '../components/VerifyEmailNote'

/** Visitors + customers (staff get their own header in M4/M5). Bottom padding leaves room for the cart bar. */
export function RootLayout() {
  return (
    <div className="flex min-h-dvh flex-col pb-24">
      <PublicHeader />
      <VerifyEmailNote />
      <Outlet />
      <CartBar />
    </div>
  )
}
