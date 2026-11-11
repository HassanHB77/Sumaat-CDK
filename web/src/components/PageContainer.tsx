import type { ReactNode } from 'react'

export function PageContainer({ title, children }: { title?: string; children?: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-6">
      {title && <h1 className="mb-4 text-2xl font-bold">{title}</h1>}
      {children}
    </main>
  )
}
