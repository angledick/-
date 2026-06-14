import { useState } from 'react'
import { Bell, CheckCheck } from 'lucide-react'

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/common/EmptyState'
import { cn } from '@/lib/utils'
import {
  useMarkAllRead,
  useMarkRead,
  useNotifications,
  useUnreadCount,
  type NotificationItem,
} from '@/hooks/queries/useNotifications'

function timeLabel(t?: string | number): string {
  if (t == null) return ''
  const ms = typeof t === 'number' ? (t > 1e12 ? t : t * 1000) : Date.parse(t)
  if (!Number.isFinite(ms)) return ''
  const diff = Date.now() - ms
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return `${Math.floor(diff / 86_400_000)} 天前`
}

/**
 * 全局通知铃铛（PRD：顶部右上角铃铛 + 红点 + 抽屉最近 20 条）。
 * 真数据：GET /notifications/unread-count（红点，30s 轮询）+ GET /notifications（抽屉）。
 */
export function NotificationBell({ className }: { className?: string }) {
  const [open, setOpen] = useState(false)
  const unread = useUnreadCount()
  const { data: list, isLoading } = useNotifications(open)
  const markRead = useMarkRead()
  const markAll = useMarkAllRead()
  const count = unread.data ?? 0

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          type="button"
          aria-label={`通知${count > 0 ? `，${count} 条未读` : ''}`}
          className={cn(
            'relative flex size-9 items-center justify-center rounded-md text-foreground/75 transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            className,
          )}
        >
          <Bell className="size-5" />
          {count > 0 && (
            <span className="absolute right-1 top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground">
              {count > 99 ? '99+' : count}
            </span>
          )}
        </button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[min(92vw,380px)] p-0">
        <SheetHeader className="border-b border-border/60 px-4 py-3">
          <SheetTitle className="flex items-center justify-between text-[15px]">
            <span>通知</span>
            {count > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1.5 text-[12px]"
                disabled={markAll.isPending}
                onClick={() => markAll.mutate()}
              >
                <CheckCheck className="size-3.5" />
                全部已读
              </Button>
            )}
          </SheetTitle>
          <SheetDescription className="sr-only">最近通知，点击单条标记已读</SheetDescription>
        </SheetHeader>
        <div className="overflow-y-auto">
          {isLoading ? (
            <div className="space-y-2 p-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : !list || list.length === 0 ? (
            <EmptyState icon={Bell} title="暂无通知" description="新预警与政策更新会出现在这里" compact />
          ) : (
            <ul className="divide-y divide-border/60">
              {list.map((n: NotificationItem) => {
                const read = n.is_read ?? n.read ?? false
                return (
                  <li key={String(n.id)}>
                    <button
                      type="button"
                      onClick={() => !read && markRead.mutate(String(n.id))}
                      className="flex w-full gap-2.5 px-4 py-3 text-left transition-colors hover:bg-muted/40"
                    >
                      <span
                        className={cn(
                          'mt-1.5 size-1.5 shrink-0 rounded-full',
                          read ? 'bg-transparent' : 'bg-primary',
                        )}
                      />
                      <span className="min-w-0 flex-1">
                        <span
                          className={cn(
                            'block truncate text-[13px]',
                            read ? 'text-muted-foreground' : 'font-medium text-foreground',
                          )}
                        >
                          {n.title}
                        </span>
                        {(n.message || n.body) && (
                          <span className="mt-0.5 line-clamp-2 block text-[12px] leading-5 text-muted-foreground">
                            {n.message || n.body}
                          </span>
                        )}
                        <span className="mt-1 block text-[11px] text-muted-foreground/70">
                          {timeLabel(n.created_at)}
                        </span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
