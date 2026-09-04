import { cn } from '@/lib/utils'

interface CardProps {
  className?: string
  children: React.ReactNode
}

export function Card({ className, children }: CardProps) {
  return (
    <div className={cn('rounded-xl border border-surface-border bg-surface-card p-6 transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-500/40 hover:shadow-lg hover:shadow-brand-900/10', className)}>
      {children}
    </div>
  )
}

export function CardHeader({ className, children }: CardProps) {
  return <div className={cn('mb-4', className)}>{children}</div>
}

export function CardTitle({ className, children }: CardProps) {
  return <h3 className={cn('text-lg font-semibold text-slate-100', className)}>{children}</h3>
}
