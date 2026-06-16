import * as React from 'react'
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { DayPicker } from 'react-day-picker'

import { cn } from '@/lib/utils'
import { buttonVariants } from '@/components/ui/button'

function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  ...props
}: React.ComponentProps<typeof DayPicker>) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn(
        'group/calendar bg-background p-3 [--cell-size:2rem] [[data-slot=popover-content]_&]:bg-transparent',
        className,
      )}
      classNames={{
        root: 'w-fit',
        months: 'relative flex flex-col gap-4 md:flex-row',
        month: 'flex w-full flex-col gap-4',
        nav: 'absolute inset-x-0 top-0 flex w-full items-center justify-between',
        button_previous: cn(
          buttonVariants({ variant: 'outline' }),
          'size-(--cell-size) p-0 select-none aria-disabled:opacity-50',
        ),
        button_next: cn(
          buttonVariants({ variant: 'outline' }),
          'size-(--cell-size) p-0 select-none aria-disabled:opacity-50',
        ),
        month_caption: 'flex h-(--cell-size) w-full items-center justify-center px-(--cell-size)',
        caption_label: 'text-sm font-medium select-none',
        month_grid: 'w-full border-collapse',
        weekdays: 'flex',
        weekday:
          'flex-1 rounded-md text-[0.8rem] font-normal text-muted-foreground select-none',
        week: 'mt-2 flex w-full',
        day: cn(
          'group/day relative aspect-square w-full p-0 text-center select-none',
          props.mode === 'range'
            ? '[&:first-child[data-selected=true]_button]:rounded-l-md [&:last-child[data-selected=true]_button]:rounded-r-md'
            : '[data-selected=true]:rounded-md',
        ),
        day_button: cn(
          buttonVariants({ variant: 'ghost' }),
          'size-(--cell-size) p-0 font-normal aria-selected:opacity-100',
        ),
        range_start:
          'rounded-l-md bg-accent [&>button]:bg-primary [&>button]:text-primary-foreground',
        range_middle: 'rounded-none bg-accent',
        range_end:
          'rounded-r-md bg-accent [&>button]:bg-primary [&>button]:text-primary-foreground',
        selected:
          'bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground',
        today: 'rounded-md bg-accent text-accent-foreground',
        outside: 'text-muted-foreground aria-selected:text-muted-foreground',
        disabled: 'text-muted-foreground opacity-50',
        hidden: 'invisible',
        ...classNames,
      }}
      components={{
        Chevron: ({ className: iconClassName, orientation, ...iconProps }) => {
          const Icon = orientation === 'left' ? ChevronLeftIcon : ChevronRightIcon
          return <Icon className={cn('size-4', iconClassName)} {...iconProps} />
        },
      }}
      {...props}
    />
  )
}

export { Calendar }
