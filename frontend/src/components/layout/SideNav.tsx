import { Compass, Info, LayoutDashboard } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { APP_NAME } from '@/lib/brand'
import { cn } from '@/lib/utils'

type NavItem = {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
}

const navItems: NavItem[] = [
  { to: '/', label: 'Forecast', icon: LayoutDashboard, end: true },
  { to: '/explorer', label: 'Explorer', icon: Compass },
  { to: '/about', label: 'About', icon: Info },
]

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
    isActive
      ? 'bg-primary/15 text-primary'
      : 'text-muted-foreground hover:bg-secondary/80 hover:text-foreground',
  )

export function SideNav() {
  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-border/60 bg-sidebar md:w-64 md:border-r md:border-b-0 md:min-h-screen">
      <div className="flex items-center gap-2 px-4 py-5 md:px-5">
        <div className="flex size-9 items-center justify-center rounded-xl bg-primary/20 text-primary">
          <LayoutDashboard className="size-5" />
        </div>
        <NavLink to="/" className="text-lg font-semibold tracking-tight text-foreground">
          {APP_NAME}
        </NavLink>
      </div>

      <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:px-4 md:pb-6">
        {navItems.map(({ to, label, icon: Icon, end = false }) => (
          <NavLink key={to} to={to} end={end} className={linkClass}>
            <Icon className="size-4 shrink-0" />
            <span className="whitespace-nowrap">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto hidden px-5 pb-6 text-xs text-muted-foreground md:block">
        Narrative signals from SEC filings
      </div>
    </aside>
  )
}
