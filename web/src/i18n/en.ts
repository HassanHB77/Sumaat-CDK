/** English strings. Arabic (ar.ts) must have exactly the same keys (TypeScript checks it). */
export const en = {
  'app.name': 'Sumaat',
  'app.tagline': 'Order ahead. Pick up hot.',
  'lang.switch': 'عربي',
  'lang.switchLabel': 'Switch to Arabic',

  'nav.restaurants': 'Restaurants',
  'nav.cart': 'Cart',
  'nav.orders': 'My orders',
  'nav.login': 'Log in',
  'nav.signup': 'Sign up',

  'home.find': 'Find food near you',
  'home.owner': 'Own a restaurant? Join Sumaat',
  'home.step1': 'Choose',
  'home.step2': 'Order',
  'home.step3': 'Pick up & pay at the counter',

  'page.restaurants': 'Restaurants near you',
  'page.menu': 'Menu',
  'page.cart': 'Your cart',
  'page.login': 'Log in',
  'page.signup': 'Create your account',
  'page.ownerSignup': 'Register your restaurant',
  'page.confirm': 'Confirm your email',
  'page.forgot': 'Reset your password',
  'page.orders': 'My orders',
  'page.order': 'Order',
  'page.owner': 'My restaurant',
  'page.ownerSetup': 'Set up your restaurant',
  'page.ownerOrders': 'Orders',
  'page.ownerMenu': 'Menu',
  'page.ownerRestaurant': 'Restaurant details',
  'page.ownerCashiers': 'Cashiers',
  'page.counter': 'Counter',

  'placeholder.comingIn': 'Coming in {milestone}',
  'notFound.title': 'Page not found',
  'notFound.home': 'Back to home',

  'status.api': 'API',
  'status.config': 'config',
  'status.build': 'build',

  'error.config': "We couldn't load the app settings. Please refresh the page.",
  'error.network': 'No connection — retry',
} as const

export type MessageKey = keyof typeof en
