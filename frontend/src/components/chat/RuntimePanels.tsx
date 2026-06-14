import { type ReactNode } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  GitBranch,
  Globe2,
  Loader2,
  Network,
  ShieldAlert,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useActionChainTrail } from '@/hooks/queries/useChains'
import type {
  ActionNode,
  AgentStatus,
  BrowserResult,
  ConflictResult,
} from '@/types'

function JsonPreview({ value, maxHeight = 'max-h-48' }: { value: unknown; maxHeight?: string }) {
  return (
    <pre
      className={cn(
        'overflow-auto rounded-md bg-muted/40 px-3 py-2 text-[11.5px] leading-5 text-muted-foreground',
        maxHeight,
      )}
    >
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

function PanelShell({
  children,
  className,
  defaultOpen = false,
  icon,
  meta,
  title,
}: {
  children: ReactNode
  className?: string
  defaultOpen?: boolean
  icon: ReactNode
  meta?: ReactNode
  title: string
}) {
  return (
    <details
      className={cn(
        'group my-2 rounded-md border border-border/55 bg-card/55',
        className,
      )}
      open={defaultOpen}
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-[12.5px] transition-colors hover:bg-muted/30 [&::-webkit-details-marker]:hidden">
        <span className="flex min-w-0 items-center gap-2">
          {icon}
          <span className="truncate font-medium">{title}</span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {meta}
          <GitBranch className="size-3.5 text-muted-foreground transition-transform group-open:rotate-90" />
        </span>
      </summary>
      <div className="border-t border-border/45 px-3 py-2.5">{children}</div>
    </details>
  )
}

function normalizeAgentName(agent: string) {
  const labels: Record<string, string> = {
    CodexAgent: 'Codex Agent',
    RuleEngine: '规则引擎',
    RAG: '法规检索',
    NLU: '意图解析',
    ConflictArbiter: '冲突仲裁',
    OpenCLI: '浏览器控制',
    codex_agent: 'Codex Agent',
    rule_engine: '规则引擎',
    rag_search: '法规检索',
    nlu_parser: '意图解析',
    conflict_arbiter: '冲突仲裁',
  }
  return labels[agent] ?? agent.replace(/_/g, ' ')
}

function statusMeta(status: AgentStatus['status'] | ActionNode['status']) {
  if (status === 'running') {
    return {
      label: '运行中',
      icon: <Loader2 className="size-3.5 animate-spin text-primary" />,
      className: 'border-primary/25 bg-primary/5 text-primary',
    }
  }
  if (status === 'success' || status === 'complete') {
    return {
      label: '完成',
      icon: <CheckCircle2 className="size-3.5 text-success" />,
      className: 'border-success/25 bg-success/10 text-success',
    }
  }
  if (status === 'failed' || status === 'error') {
    return {
      label: '失败',
      icon: <XCircle className="size-3.5 text-destructive" />,
      className: 'border-destructive/25 bg-destructive/10 text-destructive',
    }
  }
  return {
    label: '等待',
    icon: <Clock3 className="size-3.5 text-muted-foreground" />,
    className: 'border-border/60 bg-muted/30 text-muted-foreground',
  }
}

function summarizeResult(agent: string, result?: Record<string, unknown>) {
  if (!result) return ''
  if (agent === 'NLU') {
    return [result.product, result.target_country].filter(Boolean).join(' -> ')
  }
  if (agent === 'RuleEngine') {
    return [`HS=${result.hs_code ?? 'N/A'}`, result.vat_rate ? `VAT=${result.vat_rate}%` : null]
      .filter(Boolean)
      .join(' | ')
  }
  if (agent === 'RAG') {
    const citations = result.citations
    return Array.isArray(citations) ? `匹配 ${citations.length} 条` : ''
  }
  return ''
}

export function AgentStatusPanel({
  agents,
  defaultOpen = false,
}: {
  agents: AgentStatus[]
  defaultOpen?: boolean
}) {
  if (!agents.length) return null

  return (
    <PanelShell
      defaultOpen={defaultOpen}
      icon={<Network className="size-3.5 text-primary" />}
      meta={<span className="text-[11px] text-muted-foreground">{agents.length} 个 Agent</span>}
      title="多智能体执行状态"
    >
      <div className="flex flex-wrap gap-2">
        {agents.map((agent) => {
          const meta = statusMeta(agent.status)
          const summary = summarizeResult(agent.agent, agent.result)
          return (
            <div
              key={agent.agent}
              className={cn(
                'inline-flex max-w-full items-center gap-2 rounded-md border px-2.5 py-1.5 text-[12px]',
                meta.className,
              )}
            >
              {meta.icon}
              <span className="font-medium">{normalizeAgentName(agent.agent)}</span>
              <span className="text-[11px] opacity-80">{meta.label}</span>
              {summary && <span className="max-w-[180px] truncate text-[11px] opacity-75">{summary}</span>}
            </div>
          )
        })}
      </div>
    </PanelShell>
  )
}

export function ActionChainPanel({ chainId }: { chainId?: string }) {
  const { data: trail, isLoading, error } = useActionChainTrail(chainId ?? null)

  if (!chainId) return null

  return (
    <PanelShell
      icon={<GitBranch className="size-3.5 text-primary" />}
      meta={
        <span className="text-[11px] tabular-nums text-muted-foreground">
          {isLoading ? '加载中' : trail ? `${trail.length} 步` : chainId.slice(0, 12)}
        </span>
      }
      title="Action Chain 决策链路"
    >
      {isLoading && (
        <div className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" />
          加载决策链路
        </div>
      )}
      {error && (
        <div className="text-[12.5px] text-destructive">决策链路暂时不可用</div>
      )}
      {!isLoading && trail && trail.length > 0 && (
        <div className="space-y-2">
          {trail.map((step, index) => (
            <div
              key={index}
              className="flex gap-2 rounded-md border border-border/55 bg-background/75 px-3 py-2"
            >
              <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-medium">
                {index + 1}
              </span>
              <span className="text-[12.5px] leading-relaxed">{step}</span>
            </div>
          ))}
        </div>
      )}
    </PanelShell>
  )
}

export function BrowserResultCard({ result }: { result?: BrowserResult }) {
  if (!result) return null
  const ok = result.ok
  const dataCount = Array.isArray(result.data) ? result.data.length : 0

  return (
    <PanelShell
      className={cn(ok ? 'border-primary/25 bg-primary/[0.025]' : 'border-destructive/25 bg-destructive/5')}
      defaultOpen
      icon={ok ? <Globe2 className="size-3.5 text-primary" /> : <AlertTriangle className="size-3.5 text-destructive" />}
      meta={
        <Badge variant="outline" className="h-5 px-1.5 text-[10.5px]">
          {ok ? '成功' : '失败'}
        </Badge>
      }
      title="浏览器执行结果"
    >
      <div className="space-y-3">
        <div className="grid gap-2 text-[12.5px] sm:grid-cols-2">
          <div className="rounded-md border border-border/55 bg-background/70 px-3 py-2">
            <div className="text-[11px] text-muted-foreground">动作</div>
            <div className="mt-0.5 font-medium">{result.action_type || 'browser_action'}</div>
          </div>
          <div className="rounded-md border border-border/55 bg-background/70 px-3 py-2">
            <div className="text-[11px] text-muted-foreground">结果</div>
            <div className="mt-0.5 font-medium">{dataCount ? `${dataCount} 条数据` : result.title || (ok ? '已完成' : '未完成')}</div>
          </div>
        </div>
        {result.url && (
          <a
            href={result.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex max-w-full items-center gap-1.5 truncate text-[12px] text-primary hover:underline"
          >
            <ExternalLink className="size-3.5 shrink-0" />
            <span className="truncate">{result.url}</span>
          </a>
        )}
        {result.error && (
          <div className="rounded-md border border-destructive/25 bg-destructive/10 px-3 py-2 text-[12.5px] text-destructive">
            {result.error}
          </div>
        )}
        {dataCount > 0 && <JsonPreview value={result.data} />}
        {result.raw && (
          <details>
            <summary className="cursor-pointer text-[11.5px] font-medium text-muted-foreground">
              原始响应
            </summary>
            <div className="mt-2">
              <JsonPreview value={result.raw} />
            </div>
          </details>
        )}
      </div>
    </PanelShell>
  )
}

const conflictLabels: Record<string, string> = {
  hs_code: 'HS 编码冲突',
  vat_rate: '税率冲突',
  certification: '认证清单冲突',
  risk_level: '风险等级冲突',
}

export function ArbitrationPanel({ conflicts }: { conflicts?: ConflictResult[] }) {
  if (!conflicts?.length) return null

  return (
    <PanelShell
      className="border-amber-500/25 bg-amber-500/[0.04]"
      defaultOpen={false}
      icon={<ShieldAlert className="size-3.5 text-amber-600" />}
      meta={<span className="text-[11px] text-muted-foreground">{conflicts.length} 项</span>}
      title="冲突仲裁"
    >
      <div className="space-y-2">
        {conflicts.map((conflict, index) => (
          <div key={`${conflict.type}-${index}`} className="rounded-md border border-amber-500/20 bg-background/80 px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-[12.5px] font-medium">
                {conflictLabels[conflict.type] ?? conflict.type}
              </div>
              <Badge variant="outline" className="h-5 px-1.5 text-[10.5px] text-success">
                {conflict.resolution}
              </Badge>
            </div>
            <div className="mt-2 grid gap-1 text-[11.5px] text-muted-foreground">
              {Object.entries(conflict.sources).map(([source, value]) => (
                <div key={source} className="flex justify-between gap-3">
                  <span>{source}</span>
                  <span className="font-medium text-foreground">{value}</span>
                </div>
              ))}
            </div>
            <div className="mt-2 text-[11.5px] leading-5 text-muted-foreground">
              {conflict.reason}
            </div>
          </div>
        ))}
      </div>
    </PanelShell>
  )
}
