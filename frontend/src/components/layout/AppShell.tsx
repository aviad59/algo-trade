import { Outlet } from 'react-router-dom'
import { DisclaimerBanner } from './DisclaimerBanner'
import { NavBar } from './NavBar'

export function AppShell() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <DisclaimerBanner />
      <NavBar />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
