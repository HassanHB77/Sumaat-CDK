import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router/dom'
import { ToastProvider } from './components/Toast'
import { LanguageProvider } from './i18n/LanguageContext'
import { router } from './router'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      retry: (count, error: any) => {
        // Don't retry answers that won't change (4xx), except 429 (throttled). Network/5xx: up to 2 times.
        const status = error?.status
        if (status === 429) return count < 3
        if (status >= 400 && status < 500) return false
        return count < 2
      },
    },
  },
})

/** Auth (M2) and Cart (M3) providers join here. */
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </LanguageProvider>
    </QueryClientProvider>
  )
}
