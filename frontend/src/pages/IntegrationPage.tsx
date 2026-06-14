import { useEffect, useId, useMemo, useState } from 'react'
import {
  Cable,
  CheckCircle2,
  Loader2,
  PlugZap,
  RefreshCw,
  Settings2,
  Trash2,
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
import { Input } from '@/components/ui/input'
import { useConfirm } from '@/hooks/useConfirm'
import {
  useCreateIntegration,
  useDeleteIntegration,
  useIntegrationsDashboard,
  useSyncIntegration,
  useTestIntegration,
  useUpdateIntegrationConfig,
} from '@/hooks/queries/useIntegrations'
import type { IntegrationConnection, IntegrationProviderTemplate } from '@/lib/api/os'
import { cn } from '@/lib/utils'

const fallbackProviders: IntegrationProviderTemplate[] = [
  {
    provider: 'shopify',
    name: 'Shopify',
    auth_type: 'oauth2',
    config_fields: ['shop', 'api_key', 'api_secret', 'redirect_uri'],
    description: '店铺产品、订单和库存同步，用于上架后合规巡检。',
  },
  {
    provider: 'erpnext',
    name: 'ERPNext',
    auth_type: 'token',
    config_fields: ['base_url', 'api_key', 'api_secret'],
    description: '采购、库存和财务数据同步，用于供应链合规校验。',
  },
  {
    provider: '17track',
    name: '17TRACK',
    auth_type: 'token',
    config_fields: ['api_key'],
    description: '物流轨迹同步，用于履约阶段异常监控。',
  },
  {
    provider: 'chatwoot',
    name: 'Chatwoot',
    auth_type: 'token',
    config_fields: ['base_url', 'api_access_token', 'account_id'],
    description: '客服工单与会话接入，用于售后风险沉淀。',
  },
  {
    provider: 'feishu',
    name: '飞书',
    auth_type: 'oauth2',
    config_fields: ['app_id', 'app_secret', 'redirect_uri'],
    description: '团队通知和审批协作。',
  },
  {
    provider: 'dingtalk',
    name: '钉钉',
    auth_type: 'oauth2',
    config_fields: ['app_key', 'app_secret', 'agent_id'],
    description: '企业消息和机器人通知。',
  },
]

const statusTone: Record<string, string> = {
  connected: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300',
  configured: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300',
  connecting: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300',
  disconnected: 'border-border bg-muted/40 text-muted-foreground',
  error: 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300',
  not_configured: 'border-border bg-muted/40 text-muted-foreground',
}

const statusLabel: Record<string, string> = {
  connected: '已连接',
  configured: '待连接',
  connecting: '连接中',
  disconnected: '未连接',
  not_configured: '未配置',
  error: '异常',
}

export default function IntegrationPage() {
  const confirm = useConfirm()
  const dashboard = useIntegrationsDashboard()
  const createIntegration = useCreateIntegration()
  const updateConfig = useUpdateIntegrationConfig()
  const testIntegration = useTestIntegration()
  const syncIntegration = useSyncIntegration()
  const deleteIntegration = useDeleteIntegration()
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<IntegrationConnection | null>(null)

  const providers = dashboard.data?.providers?.length ? dashboard.data.providers : fallbackProviders
  const connections = dashboard.data?.connections ?? []
  const providerStatus: Record<string, { name: string; icon?: string; status: string; connected: number; total_connections: number }> =
    dashboard.data?.status ?? {}
  const loading = dashboard.isLoading || dashboard.isFetching

  const connectedCount = Object.values(providerStatus).filter(s => s?.status === 'connected').length
  const providerCards = useMemo(
    () =>
      providers.map((provider) => ({
        provider,
        status: providerStatus[provider.provider],
        connections: connections.filter((conn) => conn.provider === provider.provider),
      })),
    [connections, providerStatus, providers],
  )

  const handleTest = async (conn: IntegrationConnection) => {
    const result = await testIntegration.mutateAsync(conn.id)
    if (result.ok === false || result.status === 'failed' || result.status === 'error') {
      toast.error(result.error || result.message || '连接测试失败')
    } else {
      toast.success(result.message || '连接测试通过')
    }
  }

  const handleSync = async (conn: IntegrationConnection) => {
    const result = await syncIntegration.mutateAsync(conn.id)
    if (result.ok === false || result.status === 'failed' || result.status === 'error') {
      toast.error(result.message || '同步失败')
    } else {
      toast.success(result.message || '同步任务已触发')
    }
  }

  const handleDelete = async (conn: IntegrationConnection) => {
    const ok = await confirm({
      title: '断开第三方连接',
      description: `确认断开「${conn.label || conn.provider}」？`,
      variant: 'destructive',
      confirmLabel: '断开',
    })
    if (!ok) return
    await deleteIntegration.mutateAsync(conn.id)
    toast.success('连接已断开')
  }

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-[1400px] px-6 py-7 sm:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-2 text-[12px] font-medium text-muted-foreground">
                <span className="h-px w-6 bg-border" />
                第三方平台连接
              </div>
              <h1 className="text-[28px] font-semibold tracking-tight">集成管理</h1>
              <p className="mt-1 max-w-2xl text-[14px] leading-6 text-muted-foreground">
                展示最新后端的 Provider 模板、连接状态和同步入口
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" className="h-9 text-[13px]" onClick={() => dashboard.refetch()} disabled={loading}>
                <RefreshCw className={cn('mr-2 size-4', loading && 'animate-spin')} />
                刷新
              </Button>
              <Button className="h-9 text-[13px]" onClick={() => setCreating(true)}>
                <PlugZap className="mr-2 size-4" />
                新建连接
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] space-y-7 px-6 py-8 sm:px-8">
        <section className="grid gap-3 md:grid-cols-3">
          <Summary label="Provider 模板" value={providers.length} detail="后端可用平台类型" Icon={Cable} />
          <Summary label="连接总数" value={connections.length} detail="已创建第三方连接" Icon={PlugZap} />
          <Summary label="已连接" value={connectedCount} detail="状态为 connected" Icon={CheckCircle2} />
        </section>

        {loading ? (
          <div className="flex items-center justify-center rounded-lg border border-border/60 bg-card py-20 text-sm text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            加载集成状态...
          </div>
        ) : (
          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {providerCards.map(({ provider, status, connections: providerConnections }) => (
              <div key={provider.provider} className="flex min-h-[260px] flex-col rounded-lg border border-border/60 bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <PlugZap className="size-4 text-muted-foreground" />
                      <h2 className="truncate text-[15px] font-semibold">{provider.name || provider.provider}</h2>
                    </div>
                    <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-muted-foreground">
                      {provider.description || '暂无说明'}
                    </p>
                  </div>
                  <span className={cn('shrink-0 rounded-md border px-2 py-0.5 text-[10px] font-semibold', statusTone[status?.status || 'not_configured'])}>
                    {statusLabel[status?.status || 'not_configured'] || status?.status || '未配置'}
                  </span>
                </div>

                <div className="mt-4 flex flex-wrap gap-1.5">
                  <Badge variant="outline" className="text-[10px]">{provider.auth_type || 'custom'}</Badge>
                  {(provider.config_fields ?? []).slice(0, 4).map((field) => (
                    <Badge key={field} variant="outline" className="text-[10px] text-muted-foreground">{field}</Badge>
                  ))}
                </div>

                <div className="mt-4 space-y-2">
                  {providerConnections.length === 0 ? (
                    <div className="rounded-md border border-dashed border-border bg-muted/25 px-3 py-4 text-center text-[12px] text-muted-foreground">
                      暂无连接
                    </div>
                  ) : (
                    providerConnections.map((conn) => (
                      <ConnectionRow
                        key={conn.id}
                        connection={conn}
                        busy={testIntegration.isPending || syncIntegration.isPending || deleteIntegration.isPending}
                        onEdit={() => setEditing(conn)}
                        onTest={() => handleTest(conn)}
                        onSync={() => handleSync(conn)}
                        onDelete={() => handleDelete(conn)}
                      />
                    ))
                  )}
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  className="mt-auto h-8 text-[12px]"
                  onClick={() => setCreating(true)}
                >
                  <PlugZap className="mr-1.5 size-3.5" />
                  添加 {provider.name || provider.provider}
                </Button>
              </div>
            ))}
          </section>
        )}
      </div>

      <IntegrationDialog
        open={creating}
        providers={providers}
        saving={createIntegration.isPending}
        onClose={() => setCreating(false)}
        onSubmit={async (body) => {
          await createIntegration.mutateAsync(body)
          toast.success('连接已创建')
          setCreating(false)
        }}
      />
      <ConfigDialog
        connection={editing}
        saving={updateConfig.isPending}
        onClose={() => setEditing(null)}
        onSubmit={async (id, config) => {
          await updateConfig.mutateAsync({ id, config })
          toast.success('配置已更新')
          setEditing(null)
        }}
      />
    </div>
  )
}

function Summary({
  label,
  value,
  detail,
  Icon,
}: {
  label: string
  value: number
  detail: string
  Icon: React.ComponentType<{ className?: string }>
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-card p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="text-[12px] font-medium text-muted-foreground">{label}</div>
        <Icon className="size-4 text-muted-foreground" />
      </div>
      <div className="text-[30px] font-semibold leading-none tracking-tight tabular-nums">{value}</div>
      <div className="mt-2 text-[12px] text-muted-foreground">{detail}</div>
    </div>
  )
}

function ConnectionRow({
  connection,
  busy,
  onEdit,
  onTest,
  onSync,
  onDelete,
}: {
  connection: IntegrationConnection
  busy: boolean
  onEdit: () => void
  onTest: () => void
  onSync: () => void
  onDelete: () => void
}) {
  return (
    <div className="rounded-md border border-border/60 bg-background p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-[13px] font-semibold">{connection.label || connection.id}</div>
          <div className="mt-0.5 truncate text-[11px] text-muted-foreground">{connection.id}</div>
        </div>
        <span className={cn('rounded-md border px-1.5 py-0.5 text-[10px] font-semibold', statusTone[connection.status] || statusTone.disconnected)}>
          {statusLabel[connection.status] || connection.status}
        </span>
      </div>
      {connection.last_error && (
        <div className="mt-2 line-clamp-2 text-[11px] text-destructive">{connection.last_error}</div>
      )}
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Button variant="outline" size="sm" className="h-7 px-2 text-[11px]" disabled={busy} onClick={onTest}>测试</Button>
        <Button variant="outline" size="sm" className="h-7 px-2 text-[11px]" disabled={busy} onClick={onSync}>同步</Button>
        <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px]" disabled={busy} onClick={onEdit}>
          <Settings2 className="mr-1 size-3" />
          配置
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label={`删除连接 ${connection.label || connection.id}`}
          title={`删除连接 ${connection.label || connection.id}`}
          className="ml-auto h-7 px-2 text-destructive"
          disabled={busy}
          onClick={onDelete}
        >
          <Trash2 className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}

function IntegrationDialog({
  open,
  providers,
  saving,
  onClose,
  onSubmit,
}: {
  open: boolean
  providers: IntegrationProviderTemplate[]
  saving: boolean
  onClose: () => void
  onSubmit: (body: { provider: string; label?: string; config?: Record<string, unknown> }) => Promise<void>
}) {
  const [provider, setProvider] = useState(providers[0]?.provider ?? 'shopify')
  const [label, setLabel] = useState('')
  const [configText, setConfigText] = useState('{}')
  const [jsonError, setJsonError] = useState('')
  const providerId = useId()
  const selectedProvider = providers.find((item) => item.provider === provider)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const config = parseJsonObject(configText)
    if (!config) {
      setJsonError('配置必须是合法 JSON 对象，例如 {"api_key":"…"}')
      return
    }
    setJsonError('')
    await onSubmit({ provider, label: label.trim(), config })
    setLabel('')
    setConfigText('{}')
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建第三方连接</DialogTitle>
          <DialogDescription>按最新后端 Provider 模板创建连接，敏感配置只写入后端。</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <div>
            <label htmlFor={providerId} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Provider</label>
            <select
              id={providerId}
              name="provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-1 focus:ring-ring"
            >
              {providers.map((item) => (
                <option key={item.provider} value={item.provider}>
                  {item.name || item.provider}
                </option>
              ))}
            </select>
          </div>
          <Field name="label" label="连接名称" value={label} onChange={setLabel} placeholder="如：德国站 Shopify…" />
          <JsonField
            name="config"
            value={configText}
            onChange={(value) => {
              setConfigText(value)
              if (jsonError) setJsonError('')
            }}
            fields={selectedProvider?.config_fields}
            error={jsonError}
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>取消</Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
              创建
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ConfigDialog({
  connection,
  saving,
  onClose,
  onSubmit,
}: {
  connection: IntegrationConnection | null
  saving: boolean
  onClose: () => void
  onSubmit: (id: string, config: Record<string, unknown>) => Promise<void>
}) {
  const [configText, setConfigText] = useState('{}')
  const [jsonError, setJsonError] = useState('')

  useEffect(() => {
    if (!connection) return
    setConfigText(JSON.stringify(connection.config ?? {}, null, 2))
    setJsonError('')
  }, [connection])

  if (!connection) return null

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const config = parseJsonObject(configText)
    if (!config) {
      setJsonError('配置必须是合法 JSON 对象，例如 {"api_key":"…"}')
      return
    }
    setJsonError('')
    await onSubmit(connection.id, config)
    setConfigText('{}')
  }

  return (
    <Dialog open={!!connection} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>更新连接配置</DialogTitle>
          <DialogDescription>{connection.label || connection.provider}</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <JsonField
            name="config"
            value={configText}
            onChange={(value) => {
              setConfigText(value)
              if (jsonError) setJsonError('')
            }}
            error={jsonError}
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>取消</Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function Field({
  name,
  label,
  value,
  onChange,
  placeholder,
}: {
  name: string
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
}) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</label>
      <Input id={id} name={name} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} autoComplete="off" />
    </div>
  )
}

function JsonField({
  name,
  value,
  onChange,
  fields,
  error,
}: {
  name: string
  value: string
  onChange: (value: string) => void
  fields?: string[]
  error?: string
}) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">配置 JSON</label>
      {fields?.length ? (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {fields.map((field) => (
            <Badge key={field} variant="outline" className="font-mono text-[10px] text-muted-foreground">
              {field}
            </Badge>
          ))}
        </div>
      ) : null}
      <textarea
        id={id}
        name={name}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        autoComplete="off"
        spellCheck={false}
        className="min-h-[128px] w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-[12px] outline-none focus:ring-1 focus:ring-ring"
        placeholder='{"api_key":"…"}'
      />
      {error ? <p id={`${id}-error`} className="mt-1.5 text-[12px] text-destructive">{error}</p> : null}
    </div>
  )
}

function parseJsonObject(value: string) {
  try {
    const parsed = JSON.parse(value || '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : null
  } catch {
    return null
  }
}
