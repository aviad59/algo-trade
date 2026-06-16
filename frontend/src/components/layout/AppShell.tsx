import { Outlet } from 'react-router-dom'
import { ErrorBoundary } from '@/components/shared/ErrorBoundary'
import { DisclaimerBanner } from './DisclaimerBanner'
import { SideNav } from './SideNav'

export function AppShell() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground md:flex-row">
      <SideNav />
      <div className="flex min-w-0 flex-1 flex-col">
        <DisclaimerBanner />
        <main className="flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
