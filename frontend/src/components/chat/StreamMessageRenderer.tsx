import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Loader2,
  PlayCircle,
  Wrench,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { PlanStep, StreamAction, StreamEvent } from '@/types'
import {
  AgentStatusPanel,
  ArbitrationPanel,
  BrowserResultCard,
} from './RuntimePanels'

function EventShell({
  children,
  className,
  defaultOpen = false,
  header,
  summary,
}: {
  children: ReactNode
  className?: string
  defaultOpen?: boolean
  header: ReactNode
  summary?: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div
      className={cn(
        'my-2 overflow-hidden rounded-md border border-border/55 bg-card/55 shadow-none',
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 border-b border-border/45 px-3 py-2 text-left transition-colors hover:bg-muted/30"
      >
        <div className="flex min-w-0 flex-1 items-center gap-2">{header}</div>
        <div className="flex shrink-0 items-center gap-2">
          {summary}
          {open ? (
            <ChevronDown className="size-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-3.5 text-muted-foreground" />
          )}
        </div>
      </button>
      {open && <div>{children}</div>}
    </div>
  )
}

function JsonPreview({ value }: { value: unknown }) {
  return (
    <pre className="max-h-36 overflow-auto rounded-sm bg-muted/40 px-3 py-2 text-[11.5px] leading-5 text-muted-foreground">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

function riskLabel(level?: StreamAction['risk_level'] | 'critical') {
  if (level === 'high') return '高风险'
  if (level === 'medium') return '中风险'
  if (level === 'low') return '低风险'
  if (level === 'critical') return '严重风险'
  return null
}

function SkillEventBlock({ event }: { event: Extract<StreamEvent, { type: 'skill_start' | 'skill_end' }> }) {
  const done = event.type === 'skill_end'
  const failed = done && event.status === 'error'
  const isModel = /mimo|llm|model/i.test(event.skill)
  const pendingLabel = isModel ? '模型生成' : '工具调用'
  const doneLabel = isModel ? '模型结果' : '工具结果'
  const payloadLabel = done ? (isModel ? '生成摘要' : '返回结果') : (isModel ? '模型参数' : '调用参数')

  return (
    <EventShell
      className={cn(!done && 'border-primary/25 bg-primary/[0.025]')}
      defaultOpen={false}
      header={
        <>
          {done ? (
            failed ? (
              <AlertTriangle className="size-3.5 shrink-0 text-destructive" />
            ) : (
              <CheckCircle2 className="size-3.5 shrink-0 text-success" />
            )
          ) : (
            <Loader2 className="size-3.5 shrink-0 animate-spin text-primary" />
          )}
          <span className="truncate text-[12.5px] font-medium">{event.skill}</span>
          <span className="truncate text-[11px] text-muted-foreground">
            {done ? doneLabel : pendingLabel}
          </span>
        </>
      }
      summary={
        <Badge
          variant="secondary"
          className={cn(
            'h-5 shrink-0 px-1.5 text-[10.5px] font-medium',
            failed && 'bg-destructive/10 text-destructive',
          )}
        >
          {done ? (failed ? '失败' : `${event.duration_ms ?? 0}ms`) : (isModel ? '生成中' : '运行中')}
        </Badge>
      }
    >
      <div className="space-y-2 px-3 py-2.5">
        <div className="text-[11.5px] font-medium text-muted-foreground/90">
          {payloadLabel}
        </div>
        <JsonPreview value={done ? event.result : event.args} />
      </div>
    </EventShell>
  )
}

function ThinkingBlock({ event }: { event: Extract<StreamEvent, { type: 'thinking' }> }) {
  return (
    <EventShell
      className="border-dashed bg-muted/[0.16]"
      defaultOpen={false}
      header={
        <>
          <Clock3 className="size-3.5 text-muted-foreground" />
          <span className="text-[12.5px] font-medium">诊断依据</span>
          {event.depth !== undefined && (
            <span className="text-[11px] text-muted-foreground">depth {event.depth}</span>
          )}
        </>
      }
    >
      <div className="px-3 py-2 text-[12.5px] leading-6 text-muted-foreground">
        {event.content}
      </div>
    </EventShell>
  )
}

function getStepIcon(status: PlanStep['status']) {
  if (status === 'done') return <CheckCircle2 className="size-3.5 text-success" />
  if (status === 'running') return <Loader2 className="size-3.5 animate-spin text-primary" />
  if (status === 'failed') return <AlertTriangle className="size-3.5 text-destructive" />
  return <Clock3 className="size-3.5 text-muted-foreground/70" />
}

function PlanBlock({ event }: { event: Extract<StreamEvent, { type: 'plan' }> }) {
  const completed = event.steps.filter((step) => step.status === 'done').length

  return (
    <EventShell
      defaultOpen={false}
      header={
        <>
          <PlayCircle className="size-3.5 text-primary" />
          <span className="text-[12.5px] font-medium">执行计划</span>
        </>
      }
      summary={
        <span className="text-[11px] tabular-nums text-muted-foreground">
          {completed}/{event.steps.length}
        </span>
      }
    >
      <div className="space-y-1 px-3 py-2.5">
        {event.steps.map((step, index) => (
          <div
            key={step.id}
            className={cn(
              'flex items-start gap-2 rounded-sm px-2 py-1.5',
              index === event.current && step.status !== 'done' && 'bg-primary/[0.055]',
            )}
          >
            <span className="mt-0.5 shrink-0">{getStepIcon(step.status)}</span>
            <div className="min-w-0 flex-1">
              <div className="text-[12.5px] leading-5">{step.action}</div>
              {(step.skill || step.duration_ms || step.expected_result) && (
                <div className="mt-0.5 text-[11px] leading-4 text-muted-foreground/85">
                  {[step.skill, step.duration_ms ? `${step.duration_ms}ms` : null, step.expected_result]
                    .filter(Boolean)
                    .join(' | ')}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </EventShell>
  )
}

function ActionSuggestionCard({ action }: { action: StreamAction }) {
  const label = riskLabel(action.risk_level)

  return (
    <div className="rounded-md border border-border/55 bg-background/80 px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[12.5px] font-medium">{action.label}</div>
          {action.description && (
            <div className="mt-1 text-[11.5px] leading-5 text-muted-foreground">
              {action.description}
            </div>
          )}
        </div>
        {label && (
          <Badge variant="outline" className="h-5 shrink-0 px-1.5 text-[10.5px]">
            {label}
          </Badge>
        )}
      </div>
      <div className="mt-2 flex items-center justify-between gap-3">
        <div className="truncate text-[11px] text-muted-foreground/85">
          {action.skill ? `Skill: ${action.skill}` : action.expected_result}
        </div>
        <div className="flex shrink-0 gap-1.5">
          <Button size="sm" variant="outline" className="h-7 px-2 text-[11.5px]">
            修改
          </Button>
          <Button size="sm" className="h-7 px-2 text-[11.5px]">
            执行
          </Button>
        </div>
      </div>
    </div>
  )
}

function ActionCardGroup({ event }: { event: Extract<StreamEvent, { type: 'action_card' }> }) {
  return (
    <EventShell
      defaultOpen={false}
      header={
        <>
          <Wrench className="size-3.5 text-primary" />
          <span className="text-[12.5px] font-medium">建议操作</span>
        </>
      }
      summary={<span className="text-[11px] text-muted-foreground">{event.actions.length} 项</span>}
    >
      <div className="space-y-2 px-3 py-2.5">
        {event.actions.map((action) => (
          <ActionSuggestionCard key={action.id} action={action} />
        ))}
      </div>
    </EventShell>
  )
}

function ErrorBlock({ event }: { event: Extract<StreamEvent, { type: 'error' }> }) {
  return (
    <EventShell
      className="border-destructive/30 bg-destructive/5"
      defaultOpen
      header={
        <>
          <AlertTriangle className="size-3.5 text-destructive" />
          <span className="font-medium text-destructive">{event.code}</span>
        </>
      }
    >
      <div className="px-3 py-2 text-[12.5px] text-destructive">{event.message}</div>
    </EventShell>
  )
}

export function StreamMessageRenderer({
  content,
  events,
  streaming,
}: {
  content: string
  events: StreamEvent[]
  streaming?: boolean
}) {
  const latestPlanIndex = events.reduce(
    (latest, event, index) => (event.type === 'plan' ? index : latest),
    -1,
  )
  const completedSkills = new Set(
    events
      .filter((event): event is Extract<StreamEvent, { type: 'skill_end' }> => event.type === 'skill_end')
      .map((event) => event.skill),
  )

  return (
    <div className="space-y-2">
      {events.map((event, index) => {
        if (event.type === 'token' || event.type === 'done') return null
        if (event.type === 'skill_start' && completedSkills.has(event.skill)) return null
        if (event.type === 'skill_start' || event.type === 'skill_end') {
          return <SkillEventBlock key={`${event.type}-${index}`} event={event} />
        }
        if (event.type === 'thinking') {
          return <ThinkingBlock key={`${event.type}-${index}`} event={event} />
        }
        if (event.type === 'plan') {
          if (index !== latestPlanIndex) return null
          return <PlanBlock key={`${event.type}-${index}`} event={event} />
        }
        if (event.type === 'action_card') {
          return <ActionCardGroup key={`${event.type}-${index}`} event={event} />
        }
        if (event.type === 'agent_status') {
          return (
            <AgentStatusPanel
              key={`${event.type}-${index}`}
              agents={event.agents}
            />
          )
        }
        if (event.type === 'conflict') {
          return (
            <ArbitrationPanel
              key={`${event.type}-${index}`}
              conflicts={event.conflicts}
            />
          )
        }
        if (event.type === 'browser_result') {
          return (
            <BrowserResultCard
              key={`${event.type}-${index}`}
              result={event.result}
            />
          )
        }
        if (event.type === 'error') {
          return <ErrorBlock key={`${event.type}-${index}`} event={event} />
        }
        return null
      })}

      {(content || streaming) && (
        <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-3 prose-p:leading-relaxed prose-pre:bg-muted prose-pre:p-4 prose-ul:my-3 prose-ol:my-3 prose-li:my-1 prose-headings:mb-2 prose-headings:mt-4">
          {content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          ) : (
            <span className="inline-flex items-center gap-2 text-[13px] text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" />
              等待事件流
            </span>
          )}
        </div>
      )}
    </div>
  )
}
