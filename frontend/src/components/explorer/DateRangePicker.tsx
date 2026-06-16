import { forwardRef, useState, type ButtonHTMLAttributes } from 'react'
import { format, isValid, parseISO } from 'date-fns'
import { CalendarIcon } from 'lucide-react'
import type { DateRange } from 'react-day-picker'

import { Button, buttonVariants } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { formatDate } from '@/lib/format'
import { cn } from '@/lib/utils'

export type DateRangeValue = {
  from?: string
  to?: string
}

type DateRangePickerProps = {
  value: DateRangeValue
  onChange: (value: DateRangeValue) => void
}

const PRESETS = [
  {
    id: 'last-quarter',
    label: 'Last quarter',
    range: { from: '2026-01-01', to: '2026-03-31' },
  },
  {
    id: 'ytd',
    label: 'YTD',
    range: { from: '2026-01-01', to: '2026-06-08' },
  },
] as const

function toDate(iso?: string) {
  if (!iso) return undefined
  const date = parseISO(iso)
  return isValid(date) ? date : undefined
}

function toIso(date?: Date) {
  if (!date) return undefined
  return format(date, 'yyyy-MM-dd')
}

const DateFieldButton = forwardRef<
  HTMLButtonElement,
  {
    id: string
    label: string
    value?: string
    placeholder: string
  } & ButtonHTMLAttributes<HTMLButtonElement>
>(function DateFieldButton({ id, label, value, placeholder, className, ...props }, ref) {
  return (
    <button
      ref={ref}
      id={id}
      type="button"
      className={cn(
        buttonVariants({ variant: 'outline' }),
        'h-9 w-full justify-start gap-2 px-3 text-left font-normal',
        !value && 'text-muted-foreground',
        className,
      )}
      {...props}
    >
      <CalendarIcon className="size-4 shrink-0 opacity-70" />
      <span>{value ? formatDate(value) : placeholder}</span>
      <span className="sr-only">{label}</span>
    </button>
  )
})

export function DateRangePicker({ value, onChange }: DateRangePickerProps) {
  const [open, setOpen] = useState(false)
  const selected: DateRange = {
    from: toDate(value.from),
    to: toDate(value.to),
  }

  const handleRangeSelect = (range: DateRange | undefined) => {
    onChange({
      from: toIso(range?.from),
      to: toIso(range?.to),
    })
    if (range?.from && range?.to) {
      setOpen(false)
    }
  }

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">Date range</label>
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((preset) => (
          <Button
            key={preset.id}
            type="button"
            size="sm"
            variant={
              value.from === preset.range.from && value.to === preset.range.to
                ? 'default'
                : 'outline'
            }
            onClick={() => onChange(preset.range)}
          >
            {preset.label}
          </Button>
        ))}
        <Button
          type="button"
          size="sm"
          variant={
            !PRESETS.some(
              (preset) =>
                preset.range.from === value.from && preset.range.to === value.to,
            )
              ? 'default'
              : 'outline'
          }
          onClick={() => onChange({ from: value.from, to: value.to })}
        >
          Custom
        </Button>
      </div>
      <Popover open={open} onOpenChange={setOpen}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground" htmlFor="explorer-from">
              From
            </label>
            <PopoverTrigger asChild>
              <DateFieldButton
                id="explorer-from"
                label="From"
                value={value.from}
                placeholder="Pick start date"
              />
            </PopoverTrigger>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground" htmlFor="explorer-to">
              To
            </label>
            <PopoverTrigger asChild>
              <DateFieldButton
                id="explorer-to"
                label="To"
                value={value.to}
                placeholder="Pick end date"
              />
            </PopoverTrigger>
          </div>
        </div>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="range"
            defaultMonth={selected.from ?? selected.to}
            selected={selected}
            onSelect={handleRangeSelect}
            numberOfMonths={2}
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}
