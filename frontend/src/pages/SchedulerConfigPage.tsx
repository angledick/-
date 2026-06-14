import { useEffect, useId, useState, type ComponentType, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Boxes,
  Clock3,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Settings2,
  Timer,
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
import { useConfirm } from '@/hooks/useConfirm'
import {
  useCreateSchedulerJob,
  useSchedulerBinding,
  useSchedulerDashboard,
  useSchedulerJobAction,
} from '@/hooks/queries/useScheduler'
import type { SchedulerJobItem, SchedulerTaskWorker, SchedulerWorkerItem } from '@/lib/api/os'
import { formatDateTime, lifecycleLabels } from '@/lib/lifecycle'
import { cn } from '@/lib/utils'

type Tab = 'global' | 'product' | 'template'

function jobStatus(job: SchedulerJobItem) {
  if (isPausedJob(job)) return { label: '已暂停', className: 'border-amber-200 bg-amber-50 text-amber-700' }
  return { label: '运行中', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' }
}

function isPausedJob(job: SchedulerJobItem) {
  return job.pending || !job.next_run_time
}

function triggerText(job: SchedulerJobItem) {
  if (job.trigger.type === 'interval') return job.trigger.interval_human || `${job.trigger.interval_seconds ?? 0}s`
  if (job.trigger.type === 'cron') return job.trigger.cron_human || job.trigger.expression || 'cron'
  return 'unknown'
}

function displayJobName(id: string) {
  const map: Record<string, string> = {
    proactive_regulation_scan: '风险情报检索',
    proactive_heartbeat: '心跳自检',
    proactive_shopify_sync: 'Shopify 商品同步',
  }
  for (const [prefix, label] of Object.entries(map)) {
    if (id.startsWith(prefix)) return label
  }
  return id
}

export default function SchedulerConfigPage() {
  const confirm = useConfirm()
  const [searchParams, setSearchParams] = useSearchParams()
  const dashboard = useSchedulerDashboard()
  const jobAction = useSchedulerJobAction()
  const createJob = useCreateSchedulerJob()
  const binding = useSchedulerBinding()
  const [createOpen, setCreateOpen] = useState(false)
  const tab = normalizeTab(searchParams.get('tab'))

  const grouped = dashboard.data?.grouped
  const config = dashboard.data?.config
  const globalJobs = grouped?.global ?? []
  const productJobs = grouped?.products ?? {}
  const productMeta = grouped?.product_meta ?? {}
  const productIds = Object.keys(productJobs)
  const allJobs = [...globalJobs, ...Object.values(productJobs).flat()]
  const loading = dashboard.isLoading || dashboard.isFetching
  const activeJobs = allJobs.filter((job) => !isPausedJob(job)).length
  const pausedJobs = allJobs.filter(isPausedJob).length
  const tasks = config?.tasks ?? []
  const workers = config?.available_workers ?? []

  const setTab = (next: Tab) => {
    const params = new URLSearchParams(searchParams)
    if (next === 'global') params.delete('tab')
    else params.set('tab', next)
    setSearchParams(params, { replace: true })
  }

  const runAction = async (job: SchedulerJobItem, action: 'pause' | 'resume' | 'trigger' | 'delete') => {
    if (action === 'delete') {
      const ok = await confirm({
        title: '删除定时任务',
        description: `确认删除「${displayJobName(job.id)}」？`,
        variant: 'destructive',
        confirmLabel: '删除',
      })
      if (!ok) return
    }
    await jobAction.mutateAsync({ jobId: job.id, action })
    toast.success(action === 'trigger' ? '任务已触发' : action === 'delete' ? '任务已删除' : '任务状态已更新')
  }

  const updateBinding = async (taskName: string, workerCode: string) => {
    await binding.mutateAsync({ taskName, workerCode })
    toast.success('Worker 绑定已更新')
  }

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-[1400px] px-6 py-7 sm:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-2 text-[12px] font-medium text-muted-foreground">
                <span className="h-px w-6 bg-border" />
                定时任务配置
              </div>
              <h1 className="text-[28px] font-semibold tracking-tight">调度中心</h1>
              <p className="mt-1 max-w-2xl text-[14px] leading-6 text-muted-foreground">
                管理全局任务、产品级巡检任务和任务到 Worker 的绑定关系
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" className="h-9 text-[13px]" onClick={() => dashboard.refetch()} disabled={loading}>
                <RefreshCw className={cn('mr-2 size-4', loading && 'animate-spin')} />
                刷新
              </Button>
              <Button className="h-9 text-[13px]" onClick={() => setCreateOpen(true)} disabled={!grouped?.enabled}>
                <Plus className="mr-2 size-4" />
                新建任务
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] space-y-7 px-6 py-8 sm:px-8">
        <section className="grid gap-3 md:grid-cols-4">
          <Summary label="全局任务" value={globalJobs.length} detail="系统级计划任务" Icon={Timer} />
          <Summary label="产品覆盖" value={productIds.length} detail="存在产品级任务的产品" Icon={Boxes} />
          <Summary label="运行中" value={activeJobs} detail="下次运行时间有效" Icon={Play} />
          <Summary label="已暂停" value={pausedJobs} detail="暂停或无下次运行时间" Icon={Clock3} />
        </section>

        {!grouped?.enabled && !loading && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-[13px] text-amber-800">
            调度器当前未运行。请先启动后端 scheduler 后再管理任务。
          </div>
        )}

        <div className="inline-flex rounded-lg border border-border/60 bg-card p-1">
          <TabButton active={tab === 'global'} onClick={() => setTab('global')}>全局任务</TabButton>
          <TabButton active={tab === 'product'} onClick={() => setTab('product')}>产品任务</TabButton>
          <TabButton active={tab === 'template'} onClick={() => setTab('template')}>模板绑定</TabButton>
        </div>

        {loading ? (
          <div className="flex items-center justify-center rounded-lg border border-border/60 bg-card py-20 text-sm text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            加载定时任务...
          </div>
        ) : tab === 'global' ? (
          <JobList
            jobs={globalJobs}
            empty="暂无全局任务"
            busy={jobAction.isPending}
            onAction={runAction}
          />
        ) : tab === 'product' ? (
          <div className="space-y-4">
            {productIds.length === 0 ? (
              <EmptyState text="暂无产品级任务。创建产品后，后端会自动注册产品巡检任务。" />
            ) : (
              productIds.map((productId) => (
                <section key={productId} className="rounded-lg border border-border/60 bg-card p-4">
                  <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-[15px] font-semibold">{productMeta[productId]?.name || productId}</h2>
                      <p className="mt-1 text-[12px] text-muted-foreground">
                        {(productMeta[productId]?.target_markets ?? []).join(' · ') || '未设置市场'}
                        {productMeta[productId]?.lifecycle_stage
                          ? ` · ${lifecycleLabels[productMeta[productId].lifecycle_stage]}`
                          : ''}
                      </p>
                    </div>
                    <Badge variant="outline" className="text-[10px]">
                      {productJobs[productId]?.length ?? 0} 个任务
                    </Badge>
                  </div>
                  <JobList
                    jobs={productJobs[productId] ?? []}
                    empty="暂无任务"
                    busy={jobAction.isPending}
                    onAction={runAction}
                    compact
                  />
                </section>
              ))
            )}
          </div>
        ) : (
          <TemplateBindings
            tasks={tasks}
            workers={workers}
            busy={binding.isPending}
            onBind={updateBinding}
          />
        )}
      </div>

      <CreateJobDialog
        open={createOpen}
        tasks={tasks}
        saving={createJob.isPending}
        onClose={() => setCreateOpen(false)}
        onSubmit={async (body) => {
          await createJob.mutateAsync(body)
          toast.success('任务已创建')
          setCreateOpen(false)
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
  Icon: ComponentType<{ className?: string }>
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

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'h-8 rounded-md px-3 text-[13px] font-medium transition-colors',
        active ? 'bg-foreground text-background' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}

function JobList({
  jobs,
  empty,
  busy,
  onAction,
  compact,
}: {
  jobs: SchedulerJobItem[]
  empty: string
  busy: boolean
  onAction: (job: SchedulerJobItem, action: 'pause' | 'resume' | 'trigger' | 'delete') => void
  compact?: boolean
}) {
  if (!jobs.length) return <EmptyState text={empty} />

  return (
    <div className={cn('grid gap-3', !compact && 'xl:grid-cols-2')}>
      {jobs.map((job) => {
        const status = jobStatus(job)
        return (
          <div key={job.id} className="rounded-lg border border-border/60 bg-card p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="truncate text-[14px] font-semibold">{displayJobName(job.id)}</h3>
                <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">{job.id}</p>
              </div>
              <span className={cn('shrink-0 rounded-md border px-2 py-0.5 text-[10px] font-semibold', status.className)}>
                {status.label}
              </span>
            </div>
            <div className="mt-4 grid gap-2 text-[12px] sm:grid-cols-3">
              <Info label="触发器" value={triggerText(job)} />
              <Info label="下次运行" value={formatDateTime(job.next_run_time)} />
              <Info label="范围" value={job.scope === 'product' ? '产品级' : '全局'} />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="outline" size="sm" className="h-8 text-[12px]" disabled={busy} onClick={() => onAction(job, 'trigger')}>
                <Play className="mr-1.5 size-3.5" />
                立即执行
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-[12px]"
                disabled={busy}
                onClick={() => onAction(job, isPausedJob(job) ? 'resume' : 'pause')}
              >
                {isPausedJob(job) ? '恢复' : '暂停'}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`删除定时任务 ${displayJobName(job.id)}`}
                title={`删除定时任务 ${displayJobName(job.id)}`}
                className="ml-auto h-8 px-2 text-destructive"
                disabled={busy}
                onClick={() => onAction(job, 'delete')}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md border border-border/60 bg-background px-3 py-2">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className="mt-1 truncate text-[12px] font-medium">{value}</div>
    </div>
  )
}

function TemplateBindings({
  tasks,
  workers,
  busy,
  onBind,
}: {
  tasks: SchedulerTaskWorker[]
  workers: SchedulerWorkerItem[]
  busy: boolean
  onBind: (taskName: string, workerCode: string) => void
}) {
  if (!tasks.length) return <EmptyState text="暂无任务模板。请检查后端 data/scheduler 配置。" />

  return (
    <div className="rounded-lg border border-border/60 bg-card">
      <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1.8fr)_220px] gap-3 border-b border-border/60 px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        <div>任务模板</div>
        <div>说明</div>
        <div>绑定 Worker</div>
      </div>
      {tasks.map((task) => (
        <div key={task.task_name} className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1.8fr)_220px] gap-3 border-b border-border/60 px-4 py-3 last:border-b-0">
          <div className="min-w-0">
            <div className="truncate text-[13px] font-semibold">{task.display_name || task.task_name}</div>
            <div className="mt-1 truncate font-mono text-[11px] text-muted-foreground">{task.task_name}</div>
          </div>
          <div className="min-w-0 text-[12px] leading-5 text-muted-foreground">
            {task.description || '暂无说明'}
            <div className="mt-1 font-mono text-[10.5px]">
              {task.default_trigger} · {JSON.stringify(task.default_args ?? {})}
            </div>
          </div>
          <select
            aria-label={`${task.display_name || task.task_name} 绑定 Worker`}
            value={task.bound_worker || ''}
            disabled={busy}
            onChange={(e) => onBind(task.task_name, e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-[12px] outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">未绑定</option>
            {workers.map((worker) => (
              <option key={worker.worker_code} value={worker.worker_code}>
                {worker.worker_name || worker.worker_code}
              </option>
            ))}
          </select>
        </div>
      ))}
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-muted/30 p-10 text-center text-[13px] text-muted-foreground">
      <Settings2 className="mx-auto mb-3 size-8" />
      {text}
    </div>
  )
}

function CreateJobDialog({
  open,
  tasks,
  saving,
  onClose,
  onSubmit,
}: {
  open: boolean
  tasks: SchedulerTaskWorker[]
  saving: boolean
  onClose: () => void
  onSubmit: (body: {
    task: string
    trigger_type: 'interval' | 'cron'
    trigger_args: Record<string, unknown>
    job_id?: string
    replace_existing?: boolean
  }) => Promise<void>
}) {
  const [task, setTask] = useState(tasks[0]?.task_name ?? '')
  const [triggerType, setTriggerType] = useState<'interval' | 'cron'>('interval')
  const [minutes, setMinutes] = useState('30')
  const [hour, setHour] = useState('9')
  const [minute, setMinute] = useState('0')
  const [jobId, setJobId] = useState('')
  const taskId = useId()

  useEffect(() => {
    const firstTask = tasks[0]
    if (!firstTask) return
    if (!task || !tasks.some((item) => item.task_name === task)) {
      setTask(firstTask.task_name)
    }
  }, [task, tasks])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!task.trim()) return toast.error('请选择任务模板')
    const triggerArgs =
      triggerType === 'interval'
        ? { minutes: Math.max(1, Number(minutes) || 30) }
        : { hour: String(hour || '9'), minute: String(minute || '0') }
    await onSubmit({
      task,
      trigger_type: triggerType,
      trigger_args: triggerArgs,
      job_id: jobId.trim() || undefined,
      replace_existing: true,
    })
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建定时任务</DialogTitle>
          <DialogDescription>选择后端注册的任务模板，并配置触发方式。</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <div>
            <label htmlFor={taskId} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">任务模板</label>
            <select
              id={taskId}
              name="task"
              value={task}
              onChange={(e) => setTask(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-1 focus:ring-ring"
            >
              {tasks.map((item) => (
                <option key={item.task_name} value={item.task_name}>
                  {item.display_name || item.task_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">触发方式</label>
            <div className="inline-flex rounded-lg border border-border/60 bg-card p-1">
              <TabButton active={triggerType === 'interval'} onClick={() => setTriggerType('interval')}>间隔</TabButton>
              <TabButton active={triggerType === 'cron'} onClick={() => setTriggerType('cron')}>Cron</TabButton>
            </div>
          </div>
          {triggerType === 'interval' ? (
            <LabeledInput name="interval_minutes" label="间隔分钟" value={minutes} onChange={setMinutes} type="number" inputMode="numeric" min="1" />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              <LabeledInput name="cron_hour" label="小时" value={hour} onChange={setHour} type="number" inputMode="numeric" min="0" max="23" />
              <LabeledInput name="cron_minute" label="分钟" value={minute} onChange={setMinute} type="number" inputMode="numeric" min="0" max="59" />
            </div>
          )}
          <LabeledInput name="job_id" label="Job ID 可选" value={jobId} onChange={setJobId} autoComplete="off" />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>取消</Button>
            <Button type="submit" disabled={saving || !task}>
              {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
              创建
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function LabeledInput({
  name,
  label,
  value,
  onChange,
  type = 'text',
  inputMode,
  autoComplete = 'off',
  min,
  max,
}: {
  name: string
  label: string
  value: string
  onChange: (value: string) => void
  type?: React.HTMLInputTypeAttribute
  inputMode?: React.HTMLAttributes<HTMLInputElement>['inputMode']
  autoComplete?: string
  min?: string
  max?: string
}) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</label>
      <input
        id={id}
        name={name}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        inputMode={inputMode}
        autoComplete={autoComplete}
        min={min}
        max={max}
        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-1 focus:ring-ring"
      />
    </div>
  )
}

function normalizeTab(value: string | null): Tab {
  return value === 'product' || value === 'template' ? value : 'global'
}
