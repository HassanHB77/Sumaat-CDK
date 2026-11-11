import { Outlet } from 'react-router'
import { PublicHeader } from '../components/PublicHeader'

/** M0: one layout for everything. Staff pages get their own header (StaffHeader) in M4/M5. */
export function RootLayout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <PublicHeader />
      <Outlet />
    </div>
  )
}
