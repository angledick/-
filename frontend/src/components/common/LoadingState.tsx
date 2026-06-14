import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

type LoadingVariant = 'cards' | 'list' | 'detail' | 'text'

interface LoadingStateProps {
  /** 骨架形态，默认 cards */
  variant?: LoadingVariant
  /** cards / list / text 模式的重复数量 */
  count?: number
  className?: string
}

/**
 * 统一加载骨架（PRD：列表/卡片 → Skeleton 占位）。
 * 与各页内联手写 Skeleton 的区别：统一模板、视觉一致、按场景选 variant。
 */
export function LoadingState({ variant = 'cards', count = 3, className }: LoadingStateProps) {
  if (variant === 'cards') {
    return (
      <div className={cn('grid gap-3 md:grid-cols-2 xl:grid-cols-3', className)}>
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="rounded-lg border border-border/60 bg-card p-4">
            <div className="mb-5 flex items-center justify-between">
              <Skeleton className="h-3.5 w-20" />
              <Skeleton className="size-4 rounded" />
            </div>
            <Skeleton className="h-9 w-24" />
            <Skeleton className="mt-2 h-4 w-32" />
          </div>
        ))}
      </div>
    )
  }

  if (variant === 'list') {
    return (
      <div className={cn('space-y-2', className)}>
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-3 rounded-md border border-border/60 bg-card p-3"
          >
            <Skeleton className="size-8 shrink-0 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (variant === 'detail') {
    return (
      <div className={cn('space-y-3', className)}>
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    )
  }

  // text
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-4 w-full" />
      ))}
    </div>
  )
}
