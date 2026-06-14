import { useId, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Boxes,
  CheckCircle2,
  Clock3,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  ShieldCheck,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useConfirm } from '@/hooks/useConfirm'
import {
  useCreateProduct,
  useDeleteProduct,
  useProductComplianceCheck,
  useProductsDashboard,
  useUpdateProductLifecycle,
} from '@/hooks/queries/useProducts'
import type { ProductEvent, ProductItem, ProductLifecycle, RiskAlertItem } from '@/lib/api/os'
import {
  alertId,
  alertText,
  buildStageTimes,
  complianceLabels,
  formatDateTime,
  lifecycleLabels,
  lifecycleSteps,
  severityLabels,
  sortAlerts,
} from '@/lib/lifecycle'
import { cn } from '@/lib/utils'

const stageHints: Record<ProductLifecycle, string> = {
  concept: '需求与品类确认',
  design: '标签、说明书和材料设计',
  sourcing: '供应商、证书和票据收集',
  ready: '上架前合规确认',
  active: '在售市场巡检',
  fulfilling: '订单、物流和清关履约',
  aftersale: '客诉、召回和售后留痕',
  end: '下架、归档和退市',
}

const statusTone: Record<string, string> = {
  pending: 'border-border bg-muted/40 text-muted-foreground',
  checking: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300',
  passed: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300',
  failed: 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300',
}

const severityTone: Record<string, string> = {
  low: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300',
  medium: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300',
  high: 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300',
  critical: 'border-red-300 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300',
}

const lifecycleTransitions: Record<ProductLifecycle, ProductLifecycle[]> = {
  concept: ['design', 'sourcing'],
  design: ['sourcing', 'ready'],
  sourcing: ['ready', 'design'],
  ready: ['active', 'sourcing'],
  active: ['fulfilling', 'end'],
  fulfilling: ['aftersale', 'active', 'end'],
  aftersale: ['end', 'active'],
  end: ['concept'],
}

function activeAlertsForProduct(product: ProductItem, alerts: RiskAlertItem[]) {
  return sortAlerts(
    alerts.filter((alert) => {
      const affected = alert.affected_products ?? []
      return affected.includes(product.id) || affected.includes(product.name)
    }),
  )
}

export default function ProductCompliancePage() {
  const navigate = useNavigate()
  const confirm = useConfirm()
  const dashboard = useProductsDashboard()
  const createProduct = useCreateProduct()
  const updateLifecycle = useUpdateProductLifecycle()
  const deleteProduct = useDeleteProduct()
  const complianceCheck = useProductComplianceCheck()
  const [addOpen, setAddOpen] = useState(false)

  const products = dashboard.data?.products ?? []
  const eventsByProduct = dashboard.data?.eventsByProduct ?? {}
  const alerts = dashboard.data?.alerts ?? []
  const activeAlerts = alerts.filter((alert) => !alert.dismissed)
  const loading = dashboard.isLoading || dashboard.isFetching

  const stageCounts = useMemo(
    () =>
      lifecycleSteps.map((stage) => ({
        stage,
        label: lifecycleLabels[stage],
        count: products.filter((product) => product.lifecycle_stage === stage).length,
      })),
    [products],
  )

  const grouped = lifecycleSteps
    .map((stage) => ({
      stage,
      products: products.filter((product) => product.lifecycle_stage === stage),
    }))
    .filter((group) => group.products.length > 0)

  const handleCreate = async (body: {
    name: string
    product_type: string
    target_markets: string[]
    hs_code: string
    vendor: string
    tags: string[]
  }) => {
    await createProduct.mutateAsync(body)
    toast.success('产品已创建')
    setAddOpen(false)
  }

  const handleLifecycle = async (product: ProductItem, stage: ProductLifecycle) => {
    await updateLifecycle.mutateAsync({
      productId: product.id,
      stage,
      reason: `前端手动调整为 ${lifecycleLabels[stage]}`,
    })
    toast.success('生命周期已更新')
  }

  const handleCheck = async (product: ProductItem) => {
    const market = product.target_markets[0] || '欧盟'
    await complianceCheck.mutateAsync({ productId: product.id, market })
    toast.success('合规检查已触发')
  }

  const handleDelete = async (product: ProductItem) => {
    const ok = await confirm({
      title: '归档产品',
      description: `确认归档「${product.name}」？产品数据会从当前台账移除。`,
      variant: 'destructive',
      confirmLabel: '归档',
    })
    if (!ok) return
    await deleteProduct.mutateAsync(product.id)
    toast.success('产品已归档')
  }

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-[1400px] px-6 py-7 sm:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-2 text-[12px] font-medium text-muted-foreground">
                <span className="h-px w-6 bg-border" />
                生命周期合规台账
              </div>
              <h1 className="text-[28px] font-semibold tracking-tight">产品合规</h1>
              <p className="mt-1 max-w-2xl text-[14px] leading-6 text-muted-foreground">
                基于最新产品 API 展示生命周期节点、最近事件和关联告警
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                className="h-9 text-[13px]"
                onClick={() => dashboard.refetch()}
                disabled={loading}
              >
                <RefreshCw className={cn('mr-2 size-4', loading && 'animate-spin')} />
                刷新
              </Button>
              <Button className="h-9 text-[13px]" onClick={() => setAddOpen(true)}>
                <Plus className="mr-2 size-4" />
                新建产品
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] space-y-7 px-6 py-8 sm:px-8">
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Summary label="产品数" value={products.length} detail="当前纳管产品" Icon={Boxes} />
          <Summary
            label="活跃告警"
            value={activeAlerts.length}
            detail="未忽略风险预警"
            Icon={AlertTriangle}
            danger={activeAlerts.length > 0}
          />
          <Summary
            label="平均健康度"
            value={products.length ? Math.round(products.reduce((sum, item) => sum + (item.health_score ?? 0), 0) / products.length) : 0}
            detail="来自合规状态与风险等级"
            Icon={ShieldCheck}
          />
          <Summary
            label="已通过"
            value={products.filter((product) => product.compliance_status === 'passed').length}
            detail="合规状态为 passed"
            Icon={CheckCircle2}
          />
        </section>

        <section className="rounded-lg border border-border/60 bg-card p-4">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-[15px] font-semibold">生命周期节点分布</h2>
              <p className="mt-1 text-[12px] text-muted-foreground">
                卡片内的节点时间由产品创建、生命周期变更事件和更新时间共同推导
              </p>
            </div>
            {activeAlerts.length > 0 ? (
              <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">
                <AlertTriangle className="mr-1 size-3" />
                {activeAlerts.length} 条告警待处理
              </Badge>
            ) : (
              <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">
                <CheckCircle2 className="mr-1 size-3" />
                暂无活跃告警
              </Badge>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
            {stageCounts.map((item) => (
              <div key={item.stage} className="rounded-md border border-border/60 bg-background px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[12px] font-semibold">{item.label}</span>
                  <span className={cn('text-[12px] font-semibold tabular-nums', item.count ? 'text-primary' : 'text-muted-foreground')}>
                    {item.count}
                  </span>
                </div>
                <div className="mt-1 truncate text-[10.5px] text-muted-foreground">{stageHints[item.stage]}</div>
              </div>
            ))}
          </div>
        </section>

        {loading ? (
          <div className="flex items-center justify-center rounded-lg border border-border/60 bg-card py-20 text-sm text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            加载产品台账...
          </div>
        ) : products.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/30 p-12 text-center">
            <Boxes className="mx-auto mb-3 size-9 text-muted-foreground" />
            <div className="text-[15px] font-semibold">暂无产品</div>
            <div className="mt-1 text-[13px] text-muted-foreground">创建产品后，系统会自动注册产品级定时任务</div>
            <Button className="mt-4 h-9 text-[13px]" onClick={() => setAddOpen(true)}>
              <Plus className="mr-2 size-4" />
              新建产品
            </Button>
          </div>
        ) : (
          grouped.map((group) => (
            <section key={group.stage}>
              <div className="mb-3 flex items-center gap-2">
                <h2 className="text-[15px] font-semibold">{lifecycleLabels[group.stage]}</h2>
                <Badge variant="outline" className="text-[10px]">{group.products.length} 个</Badge>
                <span className="text-[12px] text-muted-foreground">{stageHints[group.stage]}</span>
              </div>
              <div className="grid auto-rows-fr gap-3 md:grid-cols-2 xl:grid-cols-3">
                {group.products.map((product) => (
                  <ProductLedgerCard
                    key={product.id}
                    product={product}
                    events={eventsByProduct[product.id] ?? []}
                    alerts={activeAlertsForProduct(product, alerts)}
                    busy={updateLifecycle.isPending || complianceCheck.isPending || deleteProduct.isPending}
                    onOpenChat={() => navigate(`/app/products/${product.id}/chat`)}
                    onLifecycle={(stage) => handleLifecycle(product, stage)}
                    onCheck={() => handleCheck(product)}
                    onDelete={() => handleDelete(product)}
                  />
                ))}
              </div>
            </section>
          ))
        )}
      </div>

      <ProductDialog
        open={addOpen}
        saving={createProduct.isPending}
        onClose={() => setAddOpen(false)}
        onSubmit={handleCreate}
      />
    </div>
  )
}

function Summary({
  label,
  value,
  detail,
  Icon,
  danger,
}: {
  label: string
  value: number
  detail: string
  Icon: React.ComponentType<{ className?: string }>
  danger?: boolean
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-card p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="text-[12px] font-medium text-muted-foreground">{label}</div>
        <Icon className="size-4 text-muted-foreground" />
      </div>
      <div className={cn('text-[30px] font-semibold leading-none tracking-tight tabular-nums', danger && 'text-destructive')}>
        {value}
      </div>
      <div className="mt-2 text-[12px] text-muted-foreground">{detail}</div>
    </div>
  )
}

function ProductLedgerCard({
  product,
  events,
  alerts,
  busy,
  onOpenChat,
  onLifecycle,
  onCheck,
  onDelete,
}: {
  product: ProductItem
  events: ProductEvent[]
  alerts: RiskAlertItem[]
  busy: boolean
  onOpenChat: () => void
  onLifecycle: (stage: ProductLifecycle) => void
  onCheck: () => void
  onDelete: () => void
}) {
  const stageTimes = buildStageTimes(product, events)
  const currentIndex = Math.max(0, lifecycleSteps.indexOf(product.lifecycle_stage))
  const topAlert = alerts[0]
  const health = product.health_score ?? 0
  const recentMilestones = lifecycleSteps
    .map((stage) => ({ stage, time: stageTimes[stage] }))
    .filter((item): item is { stage: ProductLifecycle; time: string } => Boolean(item.time))
    .slice(-2)
  const allowedNextStages = lifecycleTransitions[product.lifecycle_stage] ?? []

  return (
    <div className="flex h-full flex-col rounded-lg border border-border/60 bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Boxes className="size-4 shrink-0 text-muted-foreground" />
            <h3 className="truncate text-[14px] font-semibold">{product.name}</h3>
          </div>
          <p className="mt-1 truncate text-[12px] text-muted-foreground">
            {product.target_markets?.join(' · ') || '未设置市场'}
            {product.vendor ? ` · ${product.vendor}` : ''}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <span className={cn('rounded-md border px-2 py-0.5 text-[10px] font-semibold', statusTone[product.compliance_status] || statusTone.pending)}>
            {complianceLabels[product.compliance_status] || product.compliance_status}
          </span>
          {alerts.length > 0 && (
            <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
              {alerts.length} 告警
            </span>
          )}
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>健康度</span>
          <span className="font-semibold tabular-nums">{health}%</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={cn('h-full rounded-full transition-all', health >= 80 ? 'bg-emerald-500' : health >= 50 ? 'bg-amber-500' : 'bg-rose-500')}
            style={{ width: `${Math.max(0, Math.min(100, health))}%` }}
          />
        </div>
      </div>

      <div className="mt-4 rounded-md border border-border/60 bg-background p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-[12px] font-semibold">
            <Clock3 className="size-3.5 text-muted-foreground" />
            生命周期节点
          </span>
          <span className="truncate text-[11px] text-muted-foreground">
            {lifecycleLabels[product.lifecycle_stage]} · {formatDateTime(stageTimes[product.lifecycle_stage])}
          </span>
        </div>
        <div className="mt-3 flex items-center">
          {lifecycleSteps.map((stage, index) => {
            const done = index < currentIndex
            const current = index === currentIndex
            const hasTime = Boolean(stageTimes[stage])
            return (
              <div key={stage} className="flex flex-1 items-center last:flex-none" title={`${lifecycleLabels[stage]} · ${formatDateTime(stageTimes[stage])}`}>
                <span
                  className={cn(
                    'size-2.5 shrink-0 rounded-full',
                    current ? 'bg-primary ring-2 ring-primary/15' : done ? 'bg-emerald-500' : hasTime ? 'bg-amber-500' : 'bg-border',
                  )}
                />
                {index < lifecycleSteps.length - 1 && (
                  <span className={cn('mx-1 h-px flex-1', index < currentIndex ? 'bg-emerald-500/40' : 'bg-border')} />
                )}
              </div>
            )
          })}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {recentMilestones.length > 0 ? recentMilestones.map((item) => (
            <div key={item.stage} className="min-w-0">
              <div className="truncate text-[10px] text-muted-foreground">{lifecycleLabels[item.stage]}</div>
              <div className="truncate text-[11px] font-medium">{formatDateTime(item.time)}</div>
            </div>
          )) : (
            <div className="col-span-2 text-[11px] text-muted-foreground">暂无节点事件记录</div>
          )}
        </div>
      </div>

      {topAlert && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[12px] font-semibold">{topAlert.title}</div>
              <div className="mt-0.5 line-clamp-2 text-[11px] opacity-80">{alertText(topAlert)}</div>
            </div>
            <span className={cn('shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold', severityTone[topAlert.severity] || severityTone.low)}>
              {severityLabels[topAlert.severity] || topAlert.severity}
            </span>
          </div>
        </div>
      )}

      {(product.certifications ?? []).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {(product.certifications ?? []).slice(0, 4).map((cert) => (
            <span key={cert.name} className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              <BadgeCheck className="size-3" />
              {cert.name}
            </span>
          ))}
        </div>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-2 pt-4">
        <Select
          value={product.lifecycle_stage}
          onValueChange={(value) => {
            const next = value as ProductLifecycle
            if (next !== product.lifecycle_stage) onLifecycle(next)
          }}
          disabled={busy}
        >
          <SelectTrigger
            aria-label={`${product.name} 生命周期阶段`}
            className="h-8 w-[88px] border-border/70 bg-background px-2 text-[12px] shadow-none"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="start" className="min-w-[112px]">
            {lifecycleSteps.map((stage) => (
              <SelectItem
                key={stage}
                value={stage}
                disabled={stage !== product.lifecycle_stage && !allowedNextStages.includes(stage)}
                className="text-[12px]"
              >
                {lifecycleLabels[stage]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" className="h-8 text-[12px]" disabled={busy} onClick={onCheck}>
          <ShieldCheck className="mr-1.5 size-3.5" />
          检查
        </Button>
        <Button variant="outline" size="sm" className="h-8 text-[12px]" onClick={onOpenChat}>
          <MessageSquare className="mr-1.5 size-3.5" />
          对话
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label={`归档产品 ${product.name}`}
          title={`归档产品 ${product.name}`}
          className="ml-auto h-8 px-2 text-destructive"
          disabled={busy}
          onClick={onDelete}
        >
          <Trash2 className="size-3.5" />
        </Button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[10.5px] text-muted-foreground">
        <span>
          可流转至 {allowedNextStages.map((stage) => lifecycleLabels[stage]).join(' / ') || '无'}
        </span>
        {product.hs_code && <span>HS {product.hs_code}</span>}
        <span className="ml-auto flex items-center gap-1">
          进入对话
          <ArrowRight className="size-3" />
        </span>
      </div>
      {alerts.map((alert) => (
        <span key={alertId(alert)} className="sr-only">{alert.title}</span>
      ))}
    </div>
  )
}

function ProductDialog({
  open,
  saving,
  onClose,
  onSubmit,
}: {
  open: boolean
  saving: boolean
  onClose: () => void
  onSubmit: (body: {
    name: string
    product_type: string
    target_markets: string[]
    hs_code: string
    vendor: string
    tags: string[]
  }) => Promise<void>
}) {
  const [form, setForm] = useState({
    name: '',
    product_type: '',
    target_markets: 'eu,de,us',
    hs_code: '',
    vendor: '',
    tags: '',
  })

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) return toast.error('产品名称不能为空')
    await onSubmit({
      name: form.name.trim(),
      product_type: form.product_type.trim(),
      target_markets: splitList(form.target_markets),
      hs_code: form.hs_code.trim(),
      vendor: form.vendor.trim(),
      tags: splitList(form.tags),
    })
    setForm({ name: '', product_type: '', target_markets: 'eu,de,us', hs_code: '', vendor: '', tags: '' })
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建产品</DialogTitle>
          <DialogDescription>创建后后端会同步注册产品级巡检任务。</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <Field name="name" label="产品名称" value={form.name} onChange={(name) => setForm({ ...form, name })} placeholder="如 LED 灯带…" autoComplete="off" />
          <div className="grid gap-3 sm:grid-cols-2">
            <Field name="product_type" label="产品类型" value={form.product_type} onChange={(product_type) => setForm({ ...form, product_type })} placeholder="lighting / toy…" autoComplete="off" />
            <Field name="hs_code" label="HS 编码" value={form.hs_code} onChange={(hs_code) => setForm({ ...form, hs_code })} placeholder="8541.4100…" autoComplete="off" inputMode="decimal" />
          </div>
          <Field name="target_markets" label="目标市场" value={form.target_markets} onChange={(target_markets) => setForm({ ...form, target_markets })} placeholder="eu,de,us…" autoComplete="off" />
          <div className="grid gap-3 sm:grid-cols-2">
            <Field name="vendor" label="供应商" value={form.vendor} onChange={(vendor) => setForm({ ...form, vendor })} placeholder="可选…" autoComplete="organization" />
            <Field name="tags" label="标签" value={form.tags} onChange={(tags) => setForm({ ...form, tags })} placeholder="逗号分隔…" autoComplete="off" />
          </div>
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

function Field({
  name,
  label,
  value,
  onChange,
  placeholder,
  autoComplete = 'off',
  inputMode,
}: {
  name: string
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  autoComplete?: string
  inputMode?: React.HTMLAttributes<HTMLInputElement>['inputMode']
}) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </label>
      <Input
        id={id}
        name={name}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        inputMode={inputMode}
      />
    </div>
  )
}

function splitList(value: string) {
  return value
    .split(/[,\n，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}
