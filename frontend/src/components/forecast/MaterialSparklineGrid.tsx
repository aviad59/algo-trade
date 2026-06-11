import { MaterialSparkline } from '@/components/forecast/MaterialSparkline'
import type { TopMaterial } from '@/types/contract'

type MaterialSparklineGridProps = {
  materials: TopMaterial[]
}

export function MaterialSparklineGrid({ materials }: MaterialSparklineGridProps) {
  if (materials.length === 0) {
    return null
  }

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold">Signal curves</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {materials.map((material) => (
          <MaterialSparkline
            key={material.material_id}
            materialId={material.material_id}
            name={material.name}
          />
        ))}
      </div>
    </section>
  )
}
