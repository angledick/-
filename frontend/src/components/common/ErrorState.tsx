import type { ReactNode } from 'react'
import { RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ErrorStateProps {
  title?: string
  description?: string
  /** 提供时渲染「重试」按钮（PRD：接口失败 → 红色提示 + 重试按钮） */
  onRetry?: () => void
  retryLabel?: string
  /** 额外操作节点（放在重试按钮右侧） */
  action?: ReactNode
  compact?: boolean
  className?: string
}

/**
 * 统一错误状态（异步接口失败）。
 * 与顶层 ErrorBoundary（渲染崩溃）分工：本组件用于 fetch 失败等可恢复场景。
 */
export function ErrorState({
  title = '加载失败',
  description = '请检查网络或稍后重试',
  onRetry,
  retryLabel = '重试',
  action,
  compact,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center px-6 text-center',
        compact ? 'py-10' : 'py-16',
        className,
      )}
    >
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-destructive/10">
        <span className="size-2 rounded-full bg-destructive" />
      </div>
      <h3 className="text-[15px] font-semibold text-foreground">{title}</h3>
      <p className="mt-1.5 max-w-sm text-[13px] leading-6 text-muted-foreground">
        {description}
      </p>
      {(onRetry || action) && (
        <div className="mt-5 flex items-center gap-2">
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry} className="gap-2">
              <RefreshCw className="size-4" />
              {retryLabel}
            </Button>
          )}
          {action}
        </div>
      )}
    </div>
  )
}
