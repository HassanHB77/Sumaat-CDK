import { createBrowserRouter } from 'react-router'
import { GuestOnly, RequireRole, StaffRedirect } from './auth/guards'
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
 *   /owner/*          owners only (except /owner/signup)
 *   /counter          cashiers only
 *   login/sign-up     signed-out only (GuestOnly)
 */
export const router = createBrowserRouter([
  {
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
      {
        element: <RequireRole roles={['owner']} />,
        children: [
          { path: '/owner', element: <PlaceholderPage titleKey="page.owner" milestone="M5" /> },
          { path: '/owner/setup', element: <PlaceholderPage titleKey="page.ownerSetup" milestone="M5" /> },
          { path: '/owner/orders', element: <PlaceholderPage titleKey="page.ownerOrders" milestone="M4" /> },
          { path: '/owner/menu', element: <PlaceholderPage titleKey="page.ownerMenu" milestone="M5" /> },
          { path: '/owner/restaurant', element: <PlaceholderPage titleKey="page.ownerRestaurant" milestone="M5" /> },
          { path: '/owner/cashiers', element: <PlaceholderPage titleKey="page.ownerCashiers" milestone="M6" /> },
        ],
      },
      {
        element: <RequireRole roles={['cashier']} />,
        children: [{ path: '/counter', element: <PlaceholderPage titleKey="page.counter" milestone="M4" /> }],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
