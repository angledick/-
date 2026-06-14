import { useState, type FormEvent } from 'react'
import { Monitor, Play, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import {
  useBrowserAction,
  useBrowserNavigate,
  useBrowserSnapshot,
  useBrowserStatus,
  useSiteCommand,
} from '@/hooks/queries/useBrowser'

export function BrowserStatusPanel() {
  const [navUrl, setNavUrl] = useState('')
  const [site, setSite] = useState('hackernews')
  const [siteCommand, setSiteCommand] = useState('top')
  const [siteArgs, setSiteArgs] = useState('')
  const [action, setAction] = useState('exec')
  const [actionParams, setActionParams] = useState('{"expression":"document.title"}')
  const [lastResult, setLastResult] = useState<unknown>(null)
  const [clientError, setClientError] = useState<string | null>(null)

  const {
    data: status,
    error: statusError,
    isLoading,
    refetch: refetchStatus,
  } = useBrowserStatus()
  const {
    data: snapshot,
    error: snapshotError,
    isLoading: loadingSnapshot,
    refetch: refetchSnapshot,
  } = useBrowserSnapshot()
  const navigateMutation = useBrowserNavigate()
  const siteMutation = useSiteCommand()
  const actionMutation = useBrowserAction()

  const handleNavigate = async (e: FormEvent) => {
    e.preventDefault()
    const raw = navUrl.trim()
    if (!raw) return
    const url = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`
    setClientError(null)
    try {
      const result = await navigateMutation.mutateAsync({ url })
      setLastResult(result)
      await refetchStatus()
    } catch (err) {
      setClientError(err instanceof Error ? err.message : '导航失败')
    }
  }

  const handleSiteCommand = async (e: FormEvent) => {
    e.preventDefault()
    setClientError(null)
    try {
      const result = await siteMutation.mutateAsync({
        site: site.trim(),
        command: siteCommand.trim(),
        args: siteArgs.split(/\s+/).map((arg) => arg.trim()).filter(Boolean),
      })
      setLastResult(result)
      await refetchStatus()
    } catch (err) {
      setClientError(err instanceof Error ? err.message : '站点命令失败')
    }
  }

  const handleBrowserAction = async (e: FormEvent) => {
    e.preventDefault()
    setClientError(null)
    try {
      const parsedParams = actionParams.trim() ? JSON.parse(actionParams) : {}
      const result = await actionMutation.mutateAsync({
        action: action.trim(),
        params: parsedParams,
      })
      setLastResult(result)
      await refetchStatus()
    } catch (err) {
      setClientError(err instanceof Error ? err.message : '浏览器动作失败')
    }
  }

  return (
    <details className="group my-2 rounded-md border border-border/55 bg-card/55">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-[12.5px] transition-colors hover:bg-muted/30 [&::-webkit-details-marker]:hidden">
        <span className="flex min-w-0 items-center gap-2">
          <Monitor className="size-3.5 text-blue-500" />
          <span className="truncate font-medium">浏览器自动化</span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {status && (
            <Badge variant={status.active ? 'default' : 'outline'} className="h-5 px-1.5 text-[10.5px]">
              {status.active ? '运行中' : '空闲'}
            </Badge>
          )}
          <Monitor className="size-3.5 text-muted-foreground transition-transform group-open:rotate-90" />
        </span>
      </summary>
      <div className="space-y-3 border-t border-border/45 px-3 py-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">状态信息</span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => refetchStatus()}
            disabled={isLoading}
            className="h-7 gap-1.5 px-2"
          >
            <RefreshCw className={cn('size-3', isLoading && 'animate-spin')} />
            刷新
          </Button>
        </div>

        {isLoading && <div className="text-sm text-muted-foreground">加载中...</div>}
        {statusError && (
          <div className="rounded-md border border-destructive/25 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {statusError instanceof Error ? statusError.message : '状态获取失败'}
          </div>
        )}

        {status && (
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">守护进程</span>
              <span>{(status.daemon_running ?? status.active) ? '已连接' : '未运行'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">当前 URL</span>
              <span className="max-w-xs truncate font-mono text-xs">
                {status.current_url || '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">页面标题</span>
              <span className="max-w-xs truncate">{status.page_title || '—'}</span>
            </div>
            {status.last_action && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">最近操作</span>
                <span className="truncate">{status.last_action}</span>
              </div>
            )}
            {status.sites && status.sites.length > 0 && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">可用站点</span>
                <span className="max-w-xs truncate">{status.sites.slice(0, 6).join(', ')}</span>
              </div>
            )}
          </div>
        )}

        <div className="grid gap-3 border-t pt-3 lg:grid-cols-3">
          <form onSubmit={handleNavigate} className="space-y-2 rounded-md border bg-background/70 p-3">
            <div className="text-xs font-medium text-muted-foreground">导航</div>
            <Input
              value={navUrl}
              onChange={(e) => setNavUrl(e.target.value)}
              placeholder="https://example.com"
              className="h-8 text-xs"
            />
            <Button
              type="submit"
              size="sm"
              className="h-8 gap-1.5"
              disabled={navigateMutation.isPending || !navUrl.trim()}
            >
              <Play className="size-3.5" />
              执行
            </Button>
          </form>

          <form onSubmit={handleSiteCommand} className="space-y-2 rounded-md border bg-background/70 p-3">
            <div className="text-xs font-medium text-muted-foreground">站点命令</div>
            <div className="grid grid-cols-2 gap-2">
              <Input value={site} onChange={(e) => setSite(e.target.value)} className="h-8 text-xs" />
              <Input value={siteCommand} onChange={(e) => setSiteCommand(e.target.value)} className="h-8 text-xs" />
            </div>
            <Input
              value={siteArgs}
              onChange={(e) => setSiteArgs(e.target.value)}
              placeholder="args"
              className="h-8 text-xs"
            />
            <Button
              type="submit"
              size="sm"
              className="h-8 gap-1.5"
              disabled={siteMutation.isPending || !site.trim() || !siteCommand.trim()}
            >
              <Play className="size-3.5" />
              执行
            </Button>
          </form>

          <form onSubmit={handleBrowserAction} className="space-y-2 rounded-md border bg-background/70 p-3">
            <div className="text-xs font-medium text-muted-foreground">浏览器动作</div>
            <Input value={action} onChange={(e) => setAction(e.target.value)} className="h-8 text-xs" />
            <Textarea
              value={actionParams}
              onChange={(e) => setActionParams(e.target.value)}
              className="min-h-20 text-xs"
            />
            <Button
              type="submit"
              size="sm"
              className="h-8 gap-1.5"
              disabled={actionMutation.isPending || !action.trim()}
            >
              <Play className="size-3.5" />
              执行
            </Button>
          </form>
        </div>

        {(clientError || lastResult !== null) && (
          <div className="rounded-md border bg-background/70 p-3">
            {clientError && <div className="mb-2 text-xs text-destructive">{clientError}</div>}
            {lastResult !== null && (
              <pre className="max-h-56 overflow-auto text-[11px] leading-5 text-muted-foreground">
                {JSON.stringify(lastResult, null, 2)}
              </pre>
            )}
          </div>
        )}

        <div className="flex items-center justify-between border-t pt-2">
          <span className="text-xs font-medium text-muted-foreground">快照</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => refetchSnapshot()}
            disabled={loadingSnapshot}
            className="h-7 gap-1.5 px-2"
          >
            <RefreshCw className={cn('size-3', loadingSnapshot && 'animate-spin')} />
            获取快照
          </Button>
        </div>

        {snapshot && (
          <div className="space-y-2">
            {snapshot.error && (
              <div className="rounded-md border border-destructive/25 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                {snapshot.error}
              </div>
            )}
            {snapshot.screenshot && (
              <img
                src={`data:image/png;base64,${snapshot.screenshot}`}
                alt="Browser snapshot"
                className="w-full rounded border"
              />
            )}
            {snapshot.html_preview && (
              <pre className="max-h-48 overflow-auto rounded-md border bg-muted/30 px-3 py-2 text-xs leading-5 text-muted-foreground">
                {snapshot.html_preview}
              </pre>
            )}
            <div className="text-xs text-muted-foreground">
              {snapshot.url || '暂无页面'} • {new Date(snapshot.timestamp).toLocaleString('zh-CN')}
            </div>
          </div>
        )}
        {snapshotError && (
          <div className="rounded-md border border-destructive/25 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {snapshotError instanceof Error ? snapshotError.message : '快照获取失败'}
          </div>
        )}
      </div>
    </details>
  )
}
