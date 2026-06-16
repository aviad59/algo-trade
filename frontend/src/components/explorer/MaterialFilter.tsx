type MaterialOption = {
  id: string
  name: string
}

type MaterialFilterProps = {
  materials: MaterialOption[]
  value?: string
  onChange: (materialId?: string) => void
}

export function MaterialFilter({ materials, value, onChange }: MaterialFilterProps) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium" htmlFor="explorer-material">
        Material (optional)
      </label>
      <select
        id="explorer-material"
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value || undefined)}
        className="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <option value="">All materials</option>
        {materials.map((material) => (
          <option key={material.id} value={material.id}>
            {material.name}
          </option>
        ))}
      </select>
    </div>
  )
}
