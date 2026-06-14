import { Badge } from '@/components/ui/badge'
import type { ComplianceResult } from '@/types'
import { cn } from '@/lib/utils'

const RISK_META = {
  high: {
    label: '高风险',
    cls: 'bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-400',
  },
  medium: {
    label: '中风险',
    cls: 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400',
  },
  low: {
    label: '低风险',
    cls: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400',
  },
} as const

export function RiskBadge({ level }: { level: ComplianceResult['risk_level'] }) {
  const meta = RISK_META[level]
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium',
        meta.cls,
      )}
    >
      {meta.label}
    </span>
  )
}

function ListBlock({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null
  return (
    <div>
      <div className="mb-1 text-[11px] font-medium text-muted-foreground">{title}</div>
      <div className="space-y-1">
        {items.slice(0, 4).map((item) => (
          <div key={item} className="rounded-sm bg-muted/35 px-2 py-1 text-[11.5px] leading-5">
            {item}
          </div>
        ))}
      </div>
    </div>
  )
}

export function ComplianceCard({ result }: { result: ComplianceResult }) {
  return (
    <div className="space-y-3 rounded-lg border border-border/60 bg-card p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        {result.hs_code && (
          <div className="flex items-baseline gap-1.5">
            <span className="text-[11px] font-medium text-muted-foreground">HS</span>
            <span className="text-[15px] font-semibold tracking-tight">{result.hs_code}</span>
          </div>
        )}
        {result.vat_rate > 0 && (
          <div className="flex items-baseline gap-1.5">
            <span className="text-[11px] font-medium text-muted-foreground">VAT</span>
            <span className="text-[15px] font-semibold tracking-tight">{result.vat_rate}%</span>
          </div>
        )}
        {typeof result.risk_score === 'number' && (
          <div className="flex items-baseline gap-1.5">
            <span className="text-[11px] font-medium text-muted-foreground">风险评分</span>
            <span className="text-[15px] font-semibold tracking-tight">{result.risk_score}/100</span>
          </div>
        )}
        {result.risk_level && <RiskBadge level={result.risk_level} />}
      </div>

      {result.certifications.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {result.certifications.map((cert, i) => (
            <Badge
              key={cert}
              variant={i === 0 ? 'default' : 'secondary'}
              className={cn(
                'text-[11px] font-medium',
                i === 0 && 'bg-primary text-primary-foreground',
              )}
            >
              {cert}
            </Badge>
          ))}
        </div>
      )}

      <div className="grid gap-2 md:grid-cols-2">
        <ListBlock title="风险提示" items={result.risk_flags} />
        <ListBlock title="整改建议" items={result.remediation_steps} />
        <ListBlock title="物流/清关风险" items={result.logistics_flags} />
        <ListBlock title="待办清单" items={result.checklist} />
      </div>
    </div>
  )
}
