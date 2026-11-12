import { createBrowserRouter } from 'react-router'
import { HomePage } from './pages/HomePage'
import { MenuPage } from './pages/MenuPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { RestaurantsPage } from './pages/RestaurantsPage'
import { RootLayout } from './pages/RootLayout'

/**
 * Clean URLs (no #). CloudFront serves index.html for any path whose last part has no dot, so deep links
 * survive a refresh. Rules: no dots in route segments; never use /api as a page path.
 * Pages are placeholders until their milestone (M1-M6); role guards arrive in M2.
 */
export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: '/', element: <HomePage /> },

      // public + customer
      { path: '/restaurants', element: <RestaurantsPage /> },
      { path: '/r/:restaurantId', element: <MenuPage /> },
      { path: '/cart', element: <PlaceholderPage titleKey="page.cart" milestone="M3" /> },
      { path: '/orders', element: <PlaceholderPage titleKey="page.orders" milestone="M3" /> },
      { path: '/orders/:orderId', element: <PlaceholderPage titleKey="page.order" milestone="M3" /> },

      // auth
      { path: '/login', element: <PlaceholderPage titleKey="page.login" milestone="M2" /> },
      { path: '/signup', element: <PlaceholderPage titleKey="page.signup" milestone="M2" /> },
      { path: '/owner/signup', element: <PlaceholderPage titleKey="page.ownerSignup" milestone="M2" /> },
      { path: '/confirm', element: <PlaceholderPage titleKey="page.confirm" milestone="M2" /> },
      { path: '/forgot-password', element: <PlaceholderPage titleKey="page.forgot" milestone="M7" /> },

      // owner
      { path: '/owner', element: <PlaceholderPage titleKey="page.owner" milestone="M5" /> },
      { path: '/owner/setup', element: <PlaceholderPage titleKey="page.ownerSetup" milestone="M5" /> },
      { path: '/owner/orders', element: <PlaceholderPage titleKey="page.ownerOrders" milestone="M4" /> },
      { path: '/owner/menu', element: <PlaceholderPage titleKey="page.ownerMenu" milestone="M5" /> },
      { path: '/owner/restaurant', element: <PlaceholderPage titleKey="page.ownerRestaurant" milestone="M5" /> },
      { path: '/owner/cashiers', element: <PlaceholderPage titleKey="page.ownerCashiers" milestone="M6" /> },

      // cashier
      { path: '/counter', element: <PlaceholderPage titleKey="page.counter" milestone="M4" /> },

      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
