import { useMemo, useState, type FormEvent } from 'react'
import { Clock3, GitBranch, History, Plus, Search } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  useActionChain,
  useActionChains,
  useActionChainTrail,
  useCreateEvent,
  useEventChain,
  useEventChains,
  useEventChainTimeline,
  useFilterEvents,
} from '@/hooks/queries/useChains'

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-48 overflow-auto rounded-md bg-muted/35 px-3 py-2 text-[11px] leading-5 text-muted-foreground">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

function TrailView({ chainId }: { chainId: string }) {
  const { data: trail, isLoading } = useActionChainTrail(chainId)
  const { data: detail, isLoading: loadingDetail } = useActionChain(chainId)

  if (isLoading || loadingDetail) return <div className="text-sm text-muted-foreground">加载中...</div>

  return (
    <div className="space-y-3">
      {detail && (
        <div className="grid gap-2 text-xs sm:grid-cols-3">
          <div className="rounded-md border bg-background/70 px-3 py-2">
            <div className="text-muted-foreground">状态</div>
            <div className="mt-1 font-medium">{detail.status}</div>
          </div>
          <div className="rounded-md border bg-background/70 px-3 py-2">
            <div className="text-muted-foreground">节点数</div>
            <div className="mt-1 font-medium">{detail.total_actions}</div>
          </div>
          <div className="rounded-md border bg-background/70 px-3 py-2">
            <div className="text-muted-foreground">Chain ID</div>
            <div className="mt-1 truncate font-mono">{detail.chain_id}</div>
          </div>
        </div>
      )}

      {trail?.map((step, i) => (
        <div key={i} className="flex gap-2 rounded-md border px-3 py-2 text-sm">
          <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
            {i + 1}
          </span>
          <span className="leading-relaxed">{step}</span>
        </div>
      ))}

      {detail?.actions.map((action) => (
        <details key={action.action_id} className="rounded-md border bg-background/70">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-xs [&::-webkit-details-marker]:hidden">
            <span className="min-w-0 truncate">
              <span className="font-medium">{action.agent}</span>
              <span className="mx-1 text-muted-foreground">/</span>
              {action.description_nl}
            </span>
            <Badge variant="outline" className="shrink-0 text-[10px]">
              {action.status}
            </Badge>
          </summary>
          <div className="space-y-2 border-t px-3 py-2">
            <JsonBlock value={{ input: action.input, output: action.output }} />
          </div>
        </details>
      ))}
    </div>
  )
}

function TimelineView({ chainId }: { chainId: string }) {
  const [source, setSource] = useState('')
  const [eventType, setEventType] = useState('')
  const [severity, setSeverity] = useState('')
  const [tags, setTags] = useState('')
  const [newSource, setNewSource] = useState('manual')
  const [newType, setNewType] = useState('note')
  const [newSeverity, setNewSeverity] = useState('medium')
  const [newTags, setNewTags] = useState('')
  const [description, setDescription] = useState('')

  const filterParams = useMemo(() => ({
    source: source.trim() || undefined,
    event_type: eventType.trim() || undefined,
    severity: severity.trim() || undefined,
    tags: tags.trim() || undefined,
    max_count: 100,
  }), [eventType, severity, source, tags])

  const { data: detail, isLoading: loadingDetail } = useEventChain(chainId)
  const { data: timeline, isLoading } = useEventChainTimeline(chainId)
  const { data: filteredEvents, isLoading: filtering } = useFilterEvents(chainId, filterParams)
  const createEvent = useCreateEvent()

  if (isLoading || loadingDetail) return <div className="text-sm text-muted-foreground">加载中...</div>

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault()
    const text = description.trim()
    if (!text) return
    await createEvent.mutateAsync({
      chain_id: chainId,
      source: newSource.trim() || 'manual',
      type: newType.trim() || 'note',
      description_nl: text,
      severity: newSeverity.trim() || 'medium',
      tags: newTags.split(',').map((tag) => tag.trim()).filter(Boolean),
      payload: {},
    })
    setDescription('')
  }

  return (
    <div className="space-y-4">
      {detail && (
        <div className="grid gap-2 text-xs sm:grid-cols-3">
          <div className="rounded-md border bg-background/70 px-3 py-2">
            <div className="text-muted-foreground">事件数</div>
            <div className="mt-1 font-medium">{detail.total_events}</div>
          </div>
          <div className="rounded-md border bg-background/70 px-3 py-2 sm:col-span-2">
            <div className="text-muted-foreground">Chain ID</div>
            <div className="mt-1 truncate font-mono">{detail.chain_id}</div>
          </div>
        </div>
      )}

      {timeline?.map((item, i) => (
        <div key={i} className="flex gap-2 rounded-md border px-3 py-2 text-sm">
          <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
            {i + 1}
          </span>
          <span className="leading-relaxed">{item}</span>
        </div>
      ))}

      <div className="rounded-md border bg-background/70 p-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Search className="size-3.5" />
          事件筛选
        </div>
        <div className="grid gap-2 sm:grid-cols-4">
          <Input value={source} onChange={(e) => setSource(e.target.value)} placeholder="source" className="h-8 text-xs" />
          <Input value={eventType} onChange={(e) => setEventType(e.target.value)} placeholder="type" className="h-8 text-xs" />
          <Input value={severity} onChange={(e) => setSeverity(e.target.value)} placeholder="severity" className="h-8 text-xs" />
          <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="tags" className="h-8 text-xs" />
        </div>
        <div className="mt-3 space-y-2">
          {filtering && <div className="text-xs text-muted-foreground">筛选中...</div>}
          {filteredEvents?.map((event) => (
            <div key={event.event_id} className="rounded-md border bg-card px-3 py-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate font-medium">{event.description_nl}</span>
                <Badge variant="outline" className="shrink-0 text-[10px]">
                  {event.severity}
                </Badge>
              </div>
              <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                <span>{event.source}</span>
                <span>{event.type}</span>
                <span>{new Date(event.timestamp).toLocaleString('zh-CN')}</span>
              </div>
              {event.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {event.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-[10px]">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <form onSubmit={handleCreate} className="rounded-md border bg-background/70 p-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Plus className="size-3.5" />
          追加事件
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          <Input value={newSource} onChange={(e) => setNewSource(e.target.value)} className="h-8 text-xs" />
          <Input value={newType} onChange={(e) => setNewType(e.target.value)} className="h-8 text-xs" />
          <Input value={newSeverity} onChange={(e) => setNewSeverity(e.target.value)} className="h-8 text-xs" />
        </div>
        <Textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="事件描述"
          className="mt-2 min-h-20 text-xs"
        />
        <Input
          value={newTags}
          onChange={(e) => setNewTags(e.target.value)}
          placeholder="标签，逗号分隔"
          className="mt-2 h-8 text-xs"
        />
        {createEvent.error && (
          <div className="mt-2 text-xs text-destructive">
            {createEvent.error instanceof Error ? createEvent.error.message : '创建失败'}
          </div>
        )}
        <Button type="submit" size="sm" className="mt-2 h-8 gap-1.5" disabled={createEvent.isPending || !description.trim()}>
          <Plus className="size-3.5" />
          追加
        </Button>
      </form>
    </div>
  )
}

export function ChainHistoryDrawer() {
  const [selectedActionChain, setSelectedActionChain] = useState<string | null>(null)
  const [selectedEventChain, setSelectedEventChain] = useState<string | null>(null)

  const { data: actionChains, isLoading: loadingActions } = useActionChains()
  const { data: eventChains, isLoading: loadingEvents } = useEventChains()

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <History className="size-4" />
          链路历史
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>链路历史</SheetTitle>
        </SheetHeader>
        <Tabs defaultValue="actions" className="mt-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="actions">操作链</TabsTrigger>
            <TabsTrigger value="events">事件链</TabsTrigger>
          </TabsList>

          <TabsContent value="actions" className="space-y-4">
            {loadingActions && <div className="text-sm text-muted-foreground">加载中...</div>}
            {!loadingActions && actionChains?.length === 0 && (
              <div className="text-sm text-muted-foreground">暂无操作链记录</div>
            )}
            {actionChains?.map((chain) => (
              <div key={chain.chain_id} className="space-y-2">
                <button
                  onClick={() => setSelectedActionChain(
                    selectedActionChain === chain.chain_id ? null : chain.chain_id
                  )}
                  className="flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-muted/50"
                >
                  <GitBranch className="mt-0.5 size-4 shrink-0 text-primary" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-mono text-xs text-muted-foreground">
                        {chain.chain_id.slice(0, 16)}...
                      </span>
                      <Badge variant="outline" className="shrink-0">
                        {chain.total_actions} 步
                      </Badge>
                    </div>
                    <div className="mt-1 line-clamp-2 text-sm">
                      {chain.trail_preview.join(' → ')}
                    </div>
                  </div>
                </button>
                {selectedActionChain === chain.chain_id && (
                  <div className="ml-7 mt-2">
                    <TrailView chainId={chain.chain_id} />
                  </div>
                )}
              </div>
            ))}
          </TabsContent>

          <TabsContent value="events" className="space-y-4">
            {loadingEvents && <div className="text-sm text-muted-foreground">加载中...</div>}
            {!loadingEvents && eventChains?.length === 0 && (
              <div className="text-sm text-muted-foreground">暂无事件链记录</div>
            )}
            {eventChains?.map((chain) => (
              <div key={chain.chain_id} className="space-y-2">
                <button
                  onClick={() => setSelectedEventChain(
                    selectedEventChain === chain.chain_id ? null : chain.chain_id
                  )}
                  className="flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-muted/50"
                >
                  <Clock3 className="mt-0.5 size-4 shrink-0 text-orange-500" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-mono text-xs text-muted-foreground">
                        {chain.chain_id.slice(0, 16)}...
                      </span>
                      <Badge variant="outline" className="shrink-0">
                        {chain.total_events} 事件
                      </Badge>
                    </div>
                    <div className="mt-1 line-clamp-2 text-sm">
                      {chain.timeline_preview.join(' → ')}
                    </div>
                  </div>
                </button>
                {selectedEventChain === chain.chain_id && (
                  <div className="ml-7 mt-2">
                    <TimelineView chainId={chain.chain_id} />
                  </div>
                )}
              </div>
            ))}
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  )
}
