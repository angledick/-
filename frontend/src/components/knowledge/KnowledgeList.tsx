/**
 * KnowledgeList — 已导入文档列表
 * 表格 + 状态徽章 + 市场标签 + 删除按钮（确认走 AlertDialog）
 */
import { useState } from 'react'
import { FileText, Link2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  useDeleteDoc,
  useKnowledgeDocs,
} from '@/hooks/queries/useKnowledge'
import { MARKET_LABEL, STATUS_LABEL } from '@/lib/api/knowledge'
import { cn } from '@/lib/utils'
import type { KnowledgeDoc, KnowledgeMarket } from '@/types'

const STATUS_TONE: Record<KnowledgeDoc['status'], string> = {
  indexing: 'bg-warning/15 text-warning-foreground border-warning/30',
  done: 'bg-success/15 text-success border-success/30',
  error: 'bg-destructive/15 text-destructive border-destructive/30',
}

/** doc.name 来作为 aria-label / Dialog 标题，React 文本节点自动转义，无 XSS。 */
function escapeAria(s: string): string {
  return s.replace(/["\\]/g, '\\$&')
}

function formatTime(ts: number): string {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  return d.toLocaleString('zh-CN', { hour12: false })
}

export function KnowledgeList() {
  const { data: docs, isLoading, isError, error } = useKnowledgeDocs()
  const deleteDoc = useDeleteDoc()
  const [pending, setPending] = useState<KnowledgeDoc | null>(null)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
        加载中…
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
        加载失败：{error instanceof Error ? error.message : '未知错误'}
      </div>
    )
  }

  if (!docs || docs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/30 p-10 text-center">
        <p className="text-sm text-muted-foreground">
          还没有导入任何文档。切到「PDF 上传」或「URL 导入」开始。
        </p>
      </div>
    )
  }

  const confirmDelete = async () => {
    if (!pending) return
    try {
      await deleteDoc.mutateAsync(pending.id)
      toast.success('已删除')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '删除失败')
    } finally {
      setPending(null)
    }
  }

  return (
    <>
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <caption className="sr-only">已导入的合规知识库文档列表</caption>
          <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th scope="col" className="text-left px-4 py-2.5 font-medium">名称</th>
              <th scope="col" className="text-left px-4 py-2.5 font-medium">类型</th>
              <th scope="col" className="text-left px-4 py-2.5 font-medium">市场</th>
              <th scope="col" className="text-left px-4 py-2.5 font-medium">状态</th>
              <th scope="col" className="text-right px-4 py-2.5 font-medium">块数</th>
              <th scope="col" className="text-left px-4 py-2.5 font-medium">导入时间</th>
              <th scope="col" className="w-12"><span className="sr-only">操作</span></th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr
                key={d.id}
                className="border-t border-border hover:bg-muted/30 transition-colors"
              >
                <td className="px-4 py-3 max-w-[280px]">
                  <div className="flex items-center gap-2">
                    {d.doc_type === 'pdf' ? (
                      <FileText className="size-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <Link2 className="size-4 shrink-0 text-muted-foreground" />
                    )}
                    <span className="truncate font-medium text-foreground">{d.name}</span>
                  </div>
                  {d.error_msg && (
                    <p
                      className="mt-1 text-xs text-destructive truncate"
                      title={d.error_msg}
                    >
                      {d.error_msg.length > 80
                        ? d.error_msg.slice(0, 80) + '…'
                        : d.error_msg}
                    </p>
                  )}
                </td>
                <td className="px-4 py-3 text-xs uppercase tracking-wider text-muted-foreground">
                  {d.doc_type}
                </td>
                <td className="px-4 py-3 text-xs">
                  {MARKET_LABEL[d.market as KnowledgeMarket] ?? d.market}
                </td>
                <td className="px-4 py-3">
                  <Badge
                    variant="outline"
                    className={cn('text-[10px] uppercase tracking-wider', STATUS_TONE[d.status])}
                  >
                    {STATUS_LABEL[d.status]}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                  {d.chunk_count || '—'}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground tabular-nums">
                  {formatTime(d.created_at)}
                </td>
                <td className="px-2 py-3">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setPending(d)}
                    disabled={deleteDoc.isPending}
                    className="size-7 text-muted-foreground hover:text-destructive"
                    aria-label={`删除 ${escapeAria(d.name)}`}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={!!pending} onOpenChange={(o) => !o && setPending(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              确认删除「<span className="font-medium text-foreground">{pending?.name}</span>」？
              此操作会同时清除 ChromaDB 中的向量，无法恢复。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPending(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleteDoc.isPending}
            >
              {deleteDoc.isPending ? '删除中…' : '确认删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
