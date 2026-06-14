/**
 * 新闻监控 — 关键词监控 + AI 风险分析 + 市场摘要
 */
import { useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  ExternalLink,
  Loader2,
  Newspaper,
  Plus,
  RefreshCw,
  Settings2,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  useMarketSummary,
  useNewsCollect,
  useNewsKeywords,
  useNewsList,
  useUpdateKeywords,
} from '@/hooks/queries/useNews'
import { DIRECTION_LABEL, LEVEL_LABEL } from '@/lib/api/news'
import type { KeywordConfig, NewsItem } from '@/lib/api/news'
import { cn } from '@/lib/utils'

/* ─────────────────────────── Helpers ─────────────────────────── */

function directionTone(d: string) {
  if (d === '利多') return 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800'
  if (d === '利空') return 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800'
  return 'bg-muted text-muted-foreground border-border'
}

function levelTone(l: string) {
  if (l === 'high') return 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800'
  if (l === 'medium') return 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800'
  return 'bg-muted text-muted-foreground border-border'
}

/* ─────────────────────────── Page ─────────────────────────── */

export default function NewsMonitorPage() {
  const [tab, setTab] = useState('news')
  const [filterDir, setFilterDir] = useState<string | undefined>()
  const [filterLevel, setFilterLevel] = useState<string | undefined>()

  const { data: newsData, isLoading: newsLoading } = useNewsList({
    direction: filterDir,
    level: filterLevel,
  })
  const { data: summary, isLoading: sumLoading } = useMarketSummary()
  const { data: kwConfig, isLoading: kwLoading } = useNewsKeywords()
  const collect = useNewsCollect()
  const updateKw = useUpdateKeywords()

  const handleCollect = async () => {
    try {
      await collect.mutateAsync()
      toast.success('采集任务已启动，稍后刷新查看结果')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '采集失败')
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-background">
      {/* Header */}
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-[1400px] px-6 py-7 sm:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="text-[28px] font-semibold tracking-tight">新闻监控</h1>
              <p className="mt-1 max-w-2xl text-[14px] leading-6 text-muted-foreground">
                关键词自动采集 + AI 风险分析，实时了解目标市场政策动态
              </p>
            </div>
            <Button onClick={handleCollect} disabled={collect.isPending}>
              {collect.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 size-4" />
              )}
              {collect.isPending ? '采集中…' : '手动采集'}
            </Button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] space-y-6 px-6 py-8 sm:px-8">
        {/* Summary cards — 利多/利空/中性 + 高风险数 */}
        <section className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          {sumLoading ? (
            <div className="col-span-full flex items-center justify-center py-4 text-sm text-muted-foreground">
              <Loader2 className="mr-2 size-4 animate-spin" /> 摘要加载中…
            </div>
          ) : summary ? (
            <>
              <SummaryCard
                icon={TrendingUp}
                label="利多信号"
                value={summary.bullish_count}
                tone="emerald"
              />
              <SummaryCard
                icon={TrendingDown}
                label="利空信号"
                value={summary.bearish_count}
                tone="rose"
              />
              <SummaryCard
                icon={BarChart3}
                label="中性分析"
                value={summary.neutral_count}
                tone="muted"
              />
              <SummaryCard
                icon={AlertTriangle}
                label="高风险头条"
                value={summary.high_risk_news.length}
                tone="warning"
              />
            </>
          ) : (
            <div className="col-span-full text-sm text-muted-foreground py-4">暂无摘要数据</div>
          )}
        </section>

        {/* Tabs: 新闻 / 高风险 / 关键词配置 */}
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="mb-5">
            <TabsTrigger value="news" className="gap-1.5">
              <Newspaper className="size-3.5" /> 新闻列表
            </TabsTrigger>
            <TabsTrigger value="high-risk" className="gap-1.5">
              <AlertTriangle className="size-3.5" /> 高风险
            </TabsTrigger>
            <TabsTrigger value="keywords" className="gap-1.5">
              <Settings2 className="size-3.5" /> 关键词
            </TabsTrigger>
          </TabsList>

          <TabsContent value="news">
            <NewsTab
              items={newsData?.news}
              total={newsData?.total ?? 0}
              loading={newsLoading}
              filterDir={filterDir}
              filterLevel={filterLevel}
              onFilterDir={setFilterDir}
              onFilterLevel={setFilterLevel}
            />
          </TabsContent>

          <TabsContent value="high-risk">
            {sumLoading ? (
              <Loader />
            ) : (
              <HighRiskTab items={summary?.high_risk_news} />
            )}
          </TabsContent>

          <TabsContent value="keywords">
            {kwLoading ? (
              <Loader />
            ) : (
              <KeywordsTab
                config={kwConfig ?? { keywords: [], high_words: [] }}
                onSave={(cfg) =>
                  updateKw.mutateAsync(cfg).then(() => toast.success('关键词已更新'))
                }
                saving={updateKw.isPending}
              />
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

/* ─────────────────────────── Summary Card ─────────────────────────── */

function SummaryCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof TrendingUp
  label: string
  value: number
  tone: 'emerald' | 'rose' | 'muted' | 'warning'
}) {
  return (
    <div
      className={cn(
        'rounded-lg border bg-card p-4',
        tone === 'emerald' && 'border-emerald-200 dark:border-emerald-800',
        tone === 'rose' && 'border-rose-200 dark:border-rose-800',
        tone === 'warning' && 'border-amber-200 dark:border-amber-800',
        tone === 'muted' && 'border-border',
      )}
    >
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
        <Icon
          className={cn(
            'size-3.5',
            tone === 'emerald' && 'text-emerald-600',
            tone === 'rose' && 'text-rose-600',
            tone === 'warning' && 'text-amber-600',
          )}
        />
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  )
}

/* ─────────────────────────── News Tab ─────────────────────────── */

const FILTER_DIRS = ['利多', '利空', '中性']
const FILTER_LEVELS = ['high', 'medium', 'low']

function NewsTab({
  items,
  total,
  loading,
  filterDir,
  filterLevel,
  onFilterDir,
  onFilterLevel,
}: {
  items: NewsItem[] | undefined
  total: number
  loading: boolean
  filterDir: string | undefined
  filterLevel: string | undefined
  onFilterDir: (v: string | undefined) => void
  onFilterLevel: (v: string | undefined) => void
}) {
  if (loading) return <Loader />

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">筛选：</span>
        <button
          onClick={() => onFilterDir(undefined)}
          className={cn(
            'rounded-md px-2 py-1 text-xs border transition-colors',
            !filterDir ? 'bg-foreground text-background' : 'border-border text-muted-foreground hover:bg-muted',
          )}
        >
          全部方向
        </button>
        {FILTER_DIRS.map((d) => (
          <button
            key={d}
            onClick={() => onFilterDir(filterDir === d ? undefined : d)}
            className={cn(
              'rounded-md px-2 py-1 text-xs border transition-colors',
              filterDir === d ? 'bg-foreground text-background' : 'border-border text-muted-foreground hover:bg-muted',
            )}
          >
            {DIRECTION_LABEL[d]}
          </button>
        ))}
        <span className="mx-1 text-border">|</span>
        {FILTER_LEVELS.map((l) => (
          <button
            key={l}
            onClick={() => onFilterLevel(filterLevel === l ? undefined : l)}
            className={cn(
              'rounded-md px-2 py-1 text-xs border transition-colors',
              filterLevel === l ? 'bg-foreground text-background' : 'border-border text-muted-foreground hover:bg-muted',
            )}
          >
            {LEVEL_LABEL[l]}
          </button>
        ))}
        <span className="text-xs text-muted-foreground ml-auto">{total} 条</span>
      </div>

      {!items || items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-muted/30 p-12 text-center">
          <Newspaper className="mx-auto size-8 text-muted-foreground mb-3" />
          <p className="text-sm text-muted-foreground">暂无新闻。点击「手动采集」触发采集。</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

/* ─────────────────────────── News Card ─────────────────────────── */

function NewsCard({ item }: { item: NewsItem }) {
  return (
    <article className="rounded-lg border border-border bg-card p-4 space-y-3">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Badge
              variant="outline"
              className={cn('text-[10px] uppercase tracking-wider', directionTone(item.risk_direction))}
            >
              {item.risk_direction}
            </Badge>
            <Badge
              variant="outline"
              className={cn('text-[10px] uppercase tracking-wider', levelTone(item.risk_level))}
            >
              {LEVEL_LABEL[item.risk_level] ?? item.risk_level}
            </Badge>
          </div>
          <h3 className="text-[14px] font-semibold leading-5">{item.title}</h3>
        </div>
        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ExternalLink className="size-4" />
          </a>
        )}
      </header>

      <p className="text-[13px] leading-5 text-foreground/85">{item.content}</p>

      {item.logic && (
        <div className="rounded-md bg-muted/40 px-3 py-2 text-[12px] leading-5 text-muted-foreground">
          <span className="font-medium text-foreground/70">AI 分析：</span>
          {item.logic}
        </div>
      )}

      <footer className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span>{item.source}</span>
        <span>
          {item.keywords?.slice(0, 4).map((k) => (
            <span key={k} className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px]">
              {k}
            </span>
          ))}
        </span>
      </footer>
    </article>
  )
}

/* ─────────────────────────── High Risk Tab ─────────────────────────── */

function HighRiskTab({ items }: { items: NewsItem[] | undefined }) {
  if (!items || items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/30 p-12 text-center">
        <AlertTriangle className="mx-auto size-8 text-muted-foreground mb-3" />
        <p className="text-sm text-muted-foreground">暂无高风险头条</p>
      </div>
    )
  }
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <NewsCard key={item.id} item={item} />
      ))}
    </div>
  )
}

/* ─────────────────────────── Keywords Tab ─────────────────────────── */

function KeywordsTab({
  config,
  onSave,
  saving,
}: {
  config: KeywordConfig
  onSave: (cfg: KeywordConfig) => void
  saving: boolean
}) {
  const [keywords, setKeywords] = useState(config.keywords.join(', '))
  const [highWords, setHighWords] = useState(config.high_words.join(', '))
  const [kwInput, setKwInput] = useState('')

  const addKw = () => {
    const kw = kwInput.trim()
    if (!kw) return
    const current = keywords ? keywords.split(',').map((s) => s.trim()).filter(Boolean) : []
    if (current.includes(kw)) return toast.error('关键词已存在')
    setKeywords([...current, kw].join(', '))
    setKwInput('')
  }

  const handleSave = () => {
    onSave({
      keywords: keywords
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      high_words: highWords
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    })
  }

  return (
    <div className="space-y-6">
      {/* Keywords */}
      <div>
        <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
          监控关键词（逗号分隔）
        </label>
        <div className="flex items-end gap-2 mb-2">
          <input
            type="text"
            value={kwInput}
            onChange={(e) => setKwInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addKw())}
            placeholder="输入关键词后回车添加"
            className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <Button variant="outline" size="sm" onClick={addKw} type="button">
            <Plus className="size-3.5" /> 添加
          </Button>
        </div>
        <textarea
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          rows={2}
          placeholder="如：关税, 欧盟CE, 反倾销, 电池指令"
          className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>

      {/* High words */}
      <div>
        <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
          高优先级词（命中自动升级为高风险）
        </label>
        <textarea
          value={highWords}
          onChange={(e) => setHighWords(e.target.value)}
          rows={2}
          placeholder="如：禁止, 开征, 加税, 召回, 通报"
          className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>

      <Button onClick={handleSave} disabled={saving}>
        {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
        {saving ? '保存中…' : '保存关键词'}
      </Button>
    </div>
  )
}

/* ─────────────────────────── Shared ─────────────────────────── */

function Loader() {
  return (
    <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
      <Loader2 className="mr-2 size-4 animate-spin" /> 加载中…
    </div>
  )
}
