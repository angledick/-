import type { ComponentType, ReactNode } from 'react'
import { Inbox } from 'lucide-react'

import { cn } from '@/lib/utils'

interface EmptyStateProps {
  /** 顶部图标，默认收件箱 */
  icon?: ComponentType<{ className?: string }>
  title: string
  description?: string
  /** 可选主操作（Button 等） */
  action?: ReactNode
  /** 紧凑模式：列表内嵌用，减少纵向留白 */
  compact?: boolean
  className?: string
}

/**
 * 统一空状态。
 * 用法：<EmptyState icon={MessageSquare} title="还没有查询记录" description="…" action={<Button>开始查询</Button>} />
 */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  compact,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center px-6 text-center',
        compact ? 'py-10' : 'py-16',
        className,
      )}
    >
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-muted">
        <Icon className="size-6 text-muted-foreground" />
      </div>
      <h3 className="text-[15px] font-semibold text-foreground">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-sm text-[13px] leading-6 text-muted-foreground">
          {description}
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
