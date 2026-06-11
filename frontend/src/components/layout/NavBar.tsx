import { NavLink } from 'react-router-dom'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-3 py-2 text-sm font-medium transition-colors ${
    isActive
      ? 'bg-slate-800 text-white'
      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  }`

export function NavBar() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <NavLink to="/" className="text-lg font-semibold text-slate-900">
          algo-trade
        </NavLink>
        <nav className="flex flex-wrap gap-1">
          <NavLink to="/" end className={linkClass}>
            Forecast
          </NavLink>
          <NavLink to="/explorer" className={linkClass}>
            Explorer
          </NavLink>
          <NavLink to="/about" className={linkClass}>
            About
          </NavLink>
        </nav>
      </div>
    </header>
  )
}
