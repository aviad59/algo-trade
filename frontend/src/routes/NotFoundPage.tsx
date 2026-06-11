import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="text-center">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <p className="mt-2 text-slate-600">The page you requested does not exist.</p>
      <Link to="/" className="mt-4 inline-block text-blue-600 underline">
        Back to forecast
      </Link>
    </div>
  )
}
