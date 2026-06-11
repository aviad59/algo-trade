import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ExtractionResultsList } from '@/components/explorer/ExtractionResultsList'
import { EmptyState } from '@/components/shared/EmptyState'
import type { Extraction } from '@/types/contract'

type ExplorerResultsTabsProps = {
  extractions: Extraction[]
  total: number
  materialNames?: Record<string, string>
  loading?: boolean
}

export function ExplorerResultsTabs({
  extractions,
  total,
  materialNames,
  loading,
}: ExplorerResultsTabsProps) {
  return (
    <Tabs defaultValue="extractions">
      <TabsList>
        <TabsTrigger value="extractions">Extractions</TabsTrigger>
        <TabsTrigger value="signal" disabled>
          Signal
        </TabsTrigger>
        <TabsTrigger value="prices" disabled>
          Prices
        </TabsTrigger>
      </TabsList>

      <TabsContent value="extractions" className="mt-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            {loading ? 'Loading results…' : `${total} extraction${total === 1 ? '' : 's'} matched`}
          </p>
          <p className="text-xs text-muted-foreground">Signal and Prices tabs coming soon</p>
        </div>
        {loading ? null : total === 0 ? (
          <EmptyState
            title="No extractions matched"
            description="Try widening the date range, removing the material filter, or selecting different tickers."
          />
        ) : (
          <ExtractionResultsList extractions={extractions} materialNames={materialNames} />
        )}
      </TabsContent>

      <TabsContent value="signal" className="mt-4">
        <p className="text-sm text-muted-foreground">Coming soon</p>
      </TabsContent>

      <TabsContent value="prices" className="mt-4">
        <p className="text-sm text-muted-foreground">Coming soon</p>
      </TabsContent>
    </Tabs>
  )
}
