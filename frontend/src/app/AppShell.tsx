import { Outlet, ScrollRestoration } from 'react-router-dom'
import { TopNav } from '@/components/layout/TopNav'

export function AppShell() {
  return (
    <>
      <a className="sr-only" href="#main">
        Skip to content
      </a>
      <TopNav />
      <main id="main">
        <Outlet />
      </main>
      <ScrollRestoration />
    </>
  )
}
