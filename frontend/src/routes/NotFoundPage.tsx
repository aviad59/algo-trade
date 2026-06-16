import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card'

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-md py-12 text-center">
      <Card>
        <CardHeader>
          <h1 className="text-2xl font-bold">Page not found</h1>
          <CardDescription>The page you requested does not exist.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link to="/">Back to forecast</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
