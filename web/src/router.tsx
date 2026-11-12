import { createBrowserRouter } from 'react-router'
import { GuestOnly, RequireRole, StaffRedirect } from './auth/guards'
import { CounterPage, OwnerHome } from './counter/pages'
import { StaffLayout } from './counter/StaffLayout'
import { CashiersPage } from './owner/CashiersPage'
import { OwnerMenuPage } from './owner/OwnerMenuPage'
import { OwnerSetupPage, RestaurantSettingsPage } from './owner/RestaurantPages'
import { CartPage } from './pages/CartPage'
import { ConfirmPage } from './pages/ConfirmPage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { MenuPage } from './pages/MenuPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { OrderPage } from './pages/OrderPage'
import { OrdersPage } from './pages/OrdersPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { RestaurantsPage } from './pages/RestaurantsPage'
import { RootLayout } from './pages/RootLayout'
import { SignUpPage } from './pages/SignUpPage'

/**
 * Clean URLs (no #). CloudFront serves index.html for any path whose last part has no dot, so deep links
 * survive a refresh. Rules: no dots in route segments; never use /api as a page path.
 *
 * Access (one role per account):
 *   public pages      visitors + customers; owners/cashiers are sent to their own area (StaffRedirect)
 *   /orders*          customers only
 *   login/sign-up     signed-out only (GuestOnly)
 *   /owner/*          owners only (except /owner/signup), staff layout with tabs
 *   /counter          cashiers only, staff layout
 */
export const router = createBrowserRouter([
  {
    // Customer side: public header, cart bar.
    element: <RootLayout />,
    children: [
      {
        element: <StaffRedirect />,
        children: [
          { path: '/', element: <HomePage /> },
          { path: '/restaurants', element: <RestaurantsPage /> },
          { path: '/r/:restaurantId', element: <MenuPage /> },
          { path: '/cart', element: <CartPage /> },
        ],
      },
      {
        element: <RequireRole roles={['customer']} />,
        children: [
          { path: '/orders', element: <OrdersPage /> },
          { path: '/orders/:orderId', element: <OrderPage /> },
        ],
      },
      {
        element: <GuestOnly />,
        children: [
          { path: '/login', element: <LoginPage /> },
          { path: '/signup', element: <SignUpPage role="customer" /> },
          { path: '/owner/signup', element: <SignUpPage role="owner" /> },
          { path: '/confirm', element: <ConfirmPage /> },
          { path: '/forgot-password', element: <PlaceholderPage titleKey="page.forgot" milestone="M7" /> },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
  {
    // Owner area.
    element: <RequireRole roles={['owner']} />,
    children: [
      {
        element: <StaffLayout />,
        children: [
          { path: '/owner', element: <OwnerHome /> },
          { path: '/owner/orders', element: <CounterPage /> },
          { path: '/owner/setup', element: <OwnerSetupPage /> },
          { path: '/owner/menu', element: <OwnerMenuPage /> },
          { path: '/owner/restaurant', element: <RestaurantSettingsPage /> },
          { path: '/owner/cashiers', element: <CashiersPage /> },
        ],
      },
    ],
  },
  {
    // Cashier: the counter only.
    element: <RequireRole roles={['cashier']} />,
    children: [{ element: <StaffLayout />, children: [{ path: '/counter', element: <CounterPage /> }] }],
  },
])
