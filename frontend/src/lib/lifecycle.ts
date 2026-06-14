import type { ProductEvent, ProductItem, ProductLifecycle, RiskAlertItem } from '@/lib/api/os'

export const lifecycleSteps: ProductLifecycle[] = [
  'concept',
  'design',
  'sourcing',
  'ready',
  'active',
  'fulfilling',
  'aftersale',
  'end',
]

export const lifecycleLabels: Record<ProductLifecycle, string> = {
  concept: '概念',
  design: '设计',
  sourcing: '采购',
  ready: '就绪',
  active: '在售',
  fulfilling: '履约',
  aftersale: '售后',
  end: '下架',
}

export const complianceLabels: Record<string, string> = {
  pending: '待检查',
  checking: '检查中',
  passed: '合规',
  failed: '不合规',
}

export const severityLabels: Record<string, string> = {
  low: '低危',
  medium: '中危',
  high: '高危',
  critical: '严重',
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function eventStage(event: ProductEvent): ProductLifecycle | null {
  if (event.type === 'product:created') return 'concept'
  const raw = event.data?.new_stage || event.data?.lifecycle_stage
  if (typeof raw === 'string' && lifecycleSteps.includes(raw as ProductLifecycle)) {
    return raw as ProductLifecycle
  }
  return null
}

function eventTime(event: ProductEvent): string | undefined {
  return event.created_at || event.timestamp
}

export function buildStageTimes(product: ProductItem, events: ProductEvent[]) {
  const result: Partial<Record<ProductLifecycle, string>> = {}
  if (product.created_at) result.concept = product.created_at

  for (const event of events) {
    const stage = eventStage(event)
    const time = eventTime(event)
    if (stage && time) result[stage] = time
  }

  if (product.lifecycle_stage && product.updated_at) {
    result[product.lifecycle_stage] ||= product.updated_at
  }
  return result
}

export function alertText(alert: RiskAlertItem) {
  return alert.message || alert.description || alert.alert_type
}

export function alertId(alert: RiskAlertItem) {
  return alert.alert_id || alert.id || alert.title
}

export function sortAlerts(alerts: RiskAlertItem[]) {
  const rank: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 }
  return [...alerts]
    .filter((alert) => !alert.dismissed)
    .sort((a, b) => (rank[b.severity] || 0) - (rank[a.severity] || 0))
}
