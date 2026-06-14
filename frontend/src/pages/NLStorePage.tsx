/**
 * NL Store — 自然语言存储管理
 * namespace 分组 + 全文搜索 + CRUD
 */
import { useEffect, useState } from 'react'
import { useConfirm } from '@/hooks/useConfirm'
import {
  FileText,
  Loader2,
  Plus,
  Search,
  Tag,
  Trash2,
  BookOpen,
} from 'lucide-react'
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  useCreateNLRecord,
  useDeleteNLRecord,
  useNLRecord,
  useNLRecords,
  useNLSearch,
  useUpdateNLRecord,
} from '@/hooks/queries/useNLStore'
import { cn } from '@/lib/utils'
import type { NLRecordCreateRequest, NLSearchResult } from '@/types'

const DEFAULT_NS = 'default'
const EMPTY_RECORD: NLRecordCreateRequest = { key: '', title: '', content_nl: '', tags: [] }

export default function NLStorePage() {
  const [tab, setTab] = useState('browse')
  const confirm = useConfirm()
  const [namespace, setNamespace] = useState(DEFAULT_NS)
  const [nsInput, setNsInput] = useState(DEFAULT_NS)
  const [editing, setEditing] = useState<NLRecordCreateRequest | null>(null)
  const [adding, setAdding] = useState(false)
  const [searchQ, setSearchQ] = useState('')
  const [viewing, setViewing] = useState<string | null>(null)

  const { data: records, isLoading } = useNLRecords(namespace)
  const search = useNLSearch()
  const createRec = useCreateNLRecord(namespace)
  const updateRec = useUpdateNLRecord(namespace)
  const deleteRec = useDeleteNLRecord(namespace)
  const { data: editingRecord, isLoading: loadingEditingRecord } = useNLRecord(
    namespace,
    editing?.key ?? '',
  )

  const [searchResults, setSearchResults] = useState<NLSearchResult[] | null>(null)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQ.trim()) return
    try {
      const r = await search.mutateAsync({ q: searchQ.trim() })
      setSearchResults(r)
      if (r.length === 0) toast.info('未命中')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '搜索失败')
    }
  }

  const handleSave = async (req: NLRecordCreateRequest) => {
    const p = editing
      ? updateRec.mutateAsync({ ...req, key: editing.key })
      : createRec.mutateAsync(req)
    return p
      .then(() => { setAdding(false); setEditing(null); toast.success(editing ? '已更新' : '已创建') })
      .catch((e) => toast.error(e.message))
  }

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-[1100px] px-6 py-7 sm:px-8 flex items-end justify-between">
          <div>
            <h1 className="text-[28px] font-semibold tracking-tight">记忆库</h1>
            <p className="mt-1 text-[14px] text-muted-foreground">
              自然语言存储 · namespace 分组 · 全文搜索
            </p>
          </div>
          <Button onClick={() => setAdding(true)} size="sm">
            <Plus className="mr-2 size-4" /> 添加记录
          </Button>
        </div>
      </div>

      <div className="mx-auto max-w-[1100px] px-6 py-8 sm:px-8 space-y-6">
        {/* Namespace selector */}
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">Namespace</label>
            <input
              value={nsInput}
              onChange={(e) => setNsInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && setNamespace(nsInput.trim() || DEFAULT_NS)}
              placeholder={DEFAULT_NS}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <Button variant="outline" size="sm" onClick={() => setNamespace(nsInput.trim() || DEFAULT_NS)}>
            切换
          </Button>
          <span className="text-xs text-muted-foreground pb-1.5">当前: <span className="font-mono">{namespace}</span></span>
        </div>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="mb-5">
            <TabsTrigger value="browse" className="gap-1.5">
              <BookOpen className="size-3.5" /> 浏览
            </TabsTrigger>
            <TabsTrigger value="search" className="gap-1.5">
              <Search className="size-3.5" /> 搜索
            </TabsTrigger>
          </TabsList>

          <TabsContent value="browse">
            {isLoading ? <Loader /> : (
              <div className="space-y-3">
                {(!records || records.length === 0) ? (
                  <div className="rounded-lg border border-dashed border-border bg-muted/30 p-12 text-center">
                    <FileText className="mx-auto size-8 text-muted-foreground mb-3" />
                    <p className="text-sm text-muted-foreground">
                      namespace "{namespace}" 下暂无记录。点击右上角添加。
                    </p>
                  </div>
                ) : (
                  records.map((item) => (
                    <div
                      key={item.key}
                      className={cn(
                        'rounded-lg border border-border bg-card p-4 cursor-pointer transition-colors hover:border-foreground/20',
                        viewing === item.key && 'ring-1 ring-primary/30',
                      )}
                      onClick={() => setViewing(viewing === item.key ? null : item.key)}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <FileText className="size-4 shrink-0 text-muted-foreground" />
                            <span className="font-semibold text-[14px]">{item.title || item.key}</span>
                            <span className="text-[11px] font-mono text-muted-foreground">{item.key}</span>
                          </div>
                          {item.tags?.length > 0 && (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {item.tags.map((t) => (
                                <Badge key={t} variant="outline" className="text-[10px]">
                                  <Tag className="size-2.5 mr-0.5" /> {t}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => { e.stopPropagation(); setEditing({ key: item.key, title: item.title, content_nl: '', tags: item.tags }) }}
                            className="h-7 text-xs"
                          >
                            编辑
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={async (e) => {
                              e.stopPropagation()
                              if (!(await confirm({ title: '删除记录', description: '确认删除？', variant: 'destructive' }))) return
                              deleteRec.mutateAsync(item.key).then(() => toast.success('已删除')).catch((e) => toast.error(e.message))
                            }}
                            className="h-7 text-xs text-destructive"
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </div>
                      </div>
                      <div className="mt-1 text-[11px] text-muted-foreground">
                        {item.updated_at}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </TabsContent>

          <TabsContent value="search">
            <form onSubmit={handleSearch} className="flex items-end gap-3 mb-5">
              <div className="flex-1">
                <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">全文搜索</label>
                <input
                  value={searchQ}
                  onChange={(e) => setSearchQ(e.target.value)}
                  placeholder="输入关键词搜 title + content + tags"
                  className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              <Button type="submit" disabled={search.isPending}>
                {search.isPending ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
                {search.isPending ? '搜索中' : '搜索'}
              </Button>
            </form>
            {searchResults && (
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground">命中 {searchResults.length} 条</p>
                {searchResults.map((r, i) => (
                  <div key={i} className="rounded-lg border border-border bg-card p-4 space-y-2">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="font-mono text-muted-foreground">{r.namespace}/{r.key}</span>
                      <span className="font-medium">{r.title}</span>
                      <span className="ml-auto tabular-nums text-muted-foreground">score {(r.score * 100).toFixed(0)}%</span>
                    </div>
                    <p className="text-[13px] leading-5 text-foreground/85">{r.content_preview}</p>
                    {r.tags?.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {r.tags.map((t) => (
                          <span key={t} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{t}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>

        {/* Add/Edit Dialog */}
        <NLRecordDialog
          open={adding || !!editing}
          onClose={() => { setAdding(false); setEditing(null) }}
          initial={editingRecord
            ? {
                key: editingRecord.key,
                title: editingRecord.title,
                content_nl: editingRecord.content_nl,
                metadata: editingRecord.metadata,
                tags: editingRecord.tags,
              }
            : (editing || EMPTY_RECORD)}
          namespace={namespace}
          onSave={handleSave}
          saving={createRec.isPending || updateRec.isPending || loadingEditingRecord}
        />
      </div>
    </div>
  )
}

function NLRecordDialog({
  open,
  onClose,
  initial,
  namespace,
  onSave,
  saving,
}: {
  open: boolean
  onClose: () => void
  initial: NLRecordCreateRequest
  namespace: string
  onSave: (req: NLRecordCreateRequest) => Promise<unknown>
  saving: boolean
}) {
  const [form, setForm] = useState(initial)

  useEffect(() => {
    if (open) setForm(initial)
  }, [
    open,
    initial.key,
    initial.title,
    initial.content_nl,
    initial.metadata,
    initial.tags,
  ])

  const handle = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.key.trim()) return toast.error('key 不能为空')
    await onSave({ ...form, tags: form.tags?.filter(t => t.trim()) })
  }

  const tagStr = form.tags?.join(', ') ?? ''

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initial.key ? '编辑记录' : '添加记录'}</DialogTitle>
          <DialogDescription>namespace: {namespace}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handle} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">Key</label>
            <input
              value={form.key}
              onChange={(e) => setForm({ ...form, key: e.target.value })}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              disabled={!!initial.key}
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">标题</label>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">内容</label>
            <textarea
              value={form.content_nl}
              onChange={(e) => setForm({ ...form, content_nl: e.target.value })}
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="自然语言描述..."
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">标签（逗号分隔）</label>
            <input
              value={tagStr}
              onChange={(e) => setForm({ ...form, tags: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="合规, 德国, CE认证"
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>取消</Button>
            <Button type="submit" disabled={saving || !form.key.trim()}>
              {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function Loader() {
  return (
    <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
      <Loader2 className="mr-2 size-4 animate-spin" /> 加载中…
    </div>
  )
}
