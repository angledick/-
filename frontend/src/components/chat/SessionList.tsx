import { useId, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Plus, Trash2, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SessionSummary } from '@/types'

/** 默认显示最近 N 条会话，其余收起 */
const DEFAULT_VISIBLE = 12

interface Props {
  sessions: SessionSummary[]
  currentId: string | undefined
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onNew: () => void
  defaultOpen?: boolean
}

function dateGroup(ts: number): string {
  const now = Date.now() / 1000
  const diff = now - ts
  if (diff < 86400) return '今天'
  if (diff < 86400 * 2) return '昨天'
  if (diff < 86400 * 7) return '最近 7 天'
  return '更早'
}

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * Sidebar 内的"会话"折叠区 — ChatGPT 风格
 * - 默认展示最近 DEFAULT_VISIBLE 条，其余折叠
 * - 按时间分组（今天 / 昨天 / 最近 7 天 / 更早）
 * - 选中态用微背景，删除按钮 hover 出现
 */
export function SessionList({
  sessions,
  currentId,
  onSelect,
  onDelete,
  onNew,
  defaultOpen = true,
}: Props) {
  const [open, setOpen] = useState(defaultOpen)
  const [expanded, setExpanded] = useState(false)
  const sectionId = useId()
  const contentId = `${sectionId}-content`

  // sessions 已按 updated_at 倒序；收起时仍保留当前会话，避免选中态消失。
  const recent = expanded ? sessions : sessions.slice(0, DEFAULT_VISIBLE)
  const activeSession =
    !expanded && currentId ? sessions.find((session) => session.id === currentId) : undefined
  const visible =
    activeSession && !recent.some((session) => session.id === activeSession.id)
      ? [...recent, activeSession]
      : recent
  const visibleIds = new Set(visible.map((session) => session.id))
  const hiddenCount = Math.max(0, sessions.length - visibleIds.size)

  const groups: Record<string, SessionSummary[]> = {}
  for (const s of visible) {
    const g = dateGroup(s.updated_at)
    ;(groups[g] ??= []).push(s)
  }
  const groupOrder = ['今天', '昨天', '最近 7 天', '更早'] as const

  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls={contentId}
        className="group/header flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
      >
        <ChevronDown
          className={cn(
            'size-3 shrink-0 transition-transform',
            open ? 'rotate-0' : '-rotate-90',
          )}
        />
        <span className="flex-1">会话</span>
        {sessions.length > 0 && (
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-muted-foreground">
            {sessions.length}
          </span>
        )}
      </button>

      {open && (
        <div id={contentId} className="animate-fade-in space-y-2 pt-0.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onNew}
            className="h-7 w-full justify-center gap-1.5 rounded-md border-dashed text-[11.5px] font-medium"
          >
            <Plus className="size-3" />
            新建对话
          </Button>

          {sessions.length === 0 ? (
            <div className="px-2 py-3 text-center text-[11px] text-muted-foreground">
              暂无历史对话
            </div>
          ) : (
            <div className="space-y-2.5 pr-0.5">
              {groupOrder
                .filter((g) => groups[g]?.length)
                .map((group) => (
                  <div key={group}>
                    <div className="mb-0.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
                      {group}
                    </div>
                    <div className="space-y-0.5">
                      {groups[group]?.map((s) => (
                        <SessionItem
                          key={s.id}
                          session={s}
                          active={s.id === currentId}
                          onSelect={onSelect}
                          onDelete={onDelete}
                        />
                      ))}
                    </div>
                  </div>
                ))}

              {/* 收起/展开 */}
              {sessions.length > DEFAULT_VISIBLE && (expanded || hiddenCount > 0) && (
                <button
                  type="button"
                  onClick={() => setExpanded(!expanded)}
                  aria-expanded={expanded}
                  aria-controls={contentId}
                  aria-label={expanded ? '收起更早的对话' : `查看更早的对话，还有 ${hiddenCount} 条`}
                  className="flex w-full items-center justify-center gap-1 rounded-md py-1 text-[11px] text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
                >
                  <ChevronsUpDown className="size-3" />
                  {expanded ? '收起' : `查看更早的对话 (${hiddenCount})`}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SessionItem({
  session: s,
  active,
  onSelect,
  onDelete,
}: {
  session: SessionSummary
  active: boolean
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}) {
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (deleting) return
    setDeleting(true)
    try {
      await onDelete(s.id)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="group/item relative">
      <button
        onClick={() => onSelect(s.id)}
        className={cn(
          'flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-[12.5px] transition-colors',
          active
            ? 'bg-foreground/[0.06] font-medium text-foreground'
            : 'text-foreground/80 hover:bg-muted/60 hover:text-foreground',
        )}
      >
        <span className="min-w-0 flex-1 truncate leading-snug">{s.title}</span>
        <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
          {fmtTime(s.updated_at)}
        </span>
      </button>
      <button
        onClick={handleDelete}
        title="删除会话"
        className={cn(
          'absolute right-1 top-1/2 flex size-5 -translate-y-1/2 items-center justify-center rounded text-muted-foreground transition-opacity',
          'opacity-0 group-hover/item:opacity-100 hover:bg-destructive/10 hover:text-destructive',
          deleting && 'cursor-wait opacity-100',
        )}
      >
        <Trash2 className="size-3" />
      </button>
    </div>
  )
}
