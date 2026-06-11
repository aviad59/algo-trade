type PageHeaderProps = {
  title: string
  description?: string
  breadcrumb?: string
}

export function PageHeader({ title, description, breadcrumb = 'Pages' }: PageHeaderProps) {
  return (
    <header className="mb-8">
      <p className="text-sm text-muted-foreground">
        {breadcrumb} / <span className="text-foreground/80">{title}</span>
      </p>
      <h1 className="mt-2 text-2xl font-bold tracking-tight md:text-3xl">{title}</h1>
      {description ? <p className="mt-2 max-w-2xl text-muted-foreground">{description}</p> : null}
    </header>
  )
}
