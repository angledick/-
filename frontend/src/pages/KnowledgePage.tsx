import { useMemo, useState } from 'react'
import {
  BookOpenCheck,
  CheckCircle2,
  Database,
  FileText,
  Gavel,
  Globe2,
  Landmark,
  Link2,
  Loader2,
  Search,
  ShieldCheck,
  Star,
  UploadCloud,
} from 'lucide-react'

import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { KnowledgeList } from '@/components/knowledge/KnowledgeList'
import { PdfUpload } from '@/components/knowledge/PdfUpload'
import { SearchPanel } from '@/components/knowledge/SearchPanel'
import { UrlImport } from '@/components/knowledge/UrlImport'
import { useKnowledgeDocs, useKnowledgeStats } from '@/hooks/queries/useKnowledge'
import { cn } from '@/lib/utils'

type CategoryId = 'all' | 'compliance' | 'tax' | 'certification' | 'cases' | 'industry'

const CATEGORIES: Array<{ id: CategoryId; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'compliance', label: '合规法规' },
  { id: 'tax', label: '关税税务' },
  { id: 'certification', label: '认证流程' },
  { id: 'cases', label: '案例分析' },
  { id: 'industry', label: '行业报告' },
]

const FEATURED_ARTICLES = [
  {
    category: 'compliance',
    label: '合规法规',
    title: '美国 FTC 广告合规完整指南',
    description: '涵盖商品描述、星级评价、影响者合作等高频违规点。',
    meta: '12 分钟阅读 · 2026-05',
    Icon: ShieldCheck,
    tone: 'blue',
  },
  {
    category: 'tax',
    label: '关税税务',
    title: '欧盟 IOSS 一站式申报详解',
    description: 'EUR 150 以下小额订单 VAT 申报机制全解析。',
    meta: '8 分钟阅读 · 2026-04',
    Icon: Landmark,
    tone: 'amber',
  },
  {
    category: 'certification',
    label: '认证流程',
    title: '日本 PSE 圆形菱形差异',
    description: '副产品类需要菱形 PSE，违规处罚案例与材料清单。',
    meta: '6 分钟阅读 · 2026-03',
    Icon: Gavel,
    tone: 'red',
  },
  {
    category: 'cases',
    label: '案例分析',
    title: '蓝牙耳机美国市场合规清单',
    description: 'FCC、UL、CA Prop 65 与平台审核常见缺口。',
    meta: '10 分钟阅读 · 2026-02',
    Icon: BookOpenCheck,
    tone: 'emerald',
  },
  {
    category: 'industry',
    label: '行业报告',
    title: '锂电池跨境运输风险要点',
    description: 'UN38.3、MSDS、包装标签和航空承运限制。',
    meta: '9 分钟阅读 · 2026-01',
    Icon: Globe2,
    tone: 'violet',
  },
] satisfies Array<{
  category: CategoryId
  label: string
  title: string
  description: string
  meta: string
  Icon: typeof ShieldCheck
  tone: 'blue' | 'amber' | 'red' | 'emerald' | 'violet'
}>

const PROVIDERS = [
  {
    name: 'XX 国际税务',
    scope: 'VAT / EORI / IOSS 一站式',
    rating: '4.9',
    reviews: '256',
    toneClass: 'bg-indigo-500/80',
  },
  {
    name: 'XX 认证检测',
    scope: 'CE / FCC / PSE / UL 加急',
    rating: '4.7',
    reviews: '189',
    toneClass: 'bg-emerald-500/80',
  },
  {
    name: 'XX 跨境法律',
    scope: '商标 / 专利 / 合规咨询',
    rating: '4.8',
    reviews: '143',
    toneClass: 'bg-orange-500/85',
  },
]

const TONE_CLASS = {
  blue: {
    pill: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/70 dark:bg-blue-950/30 dark:text-blue-300',
    icon: 'text-blue-600',
    ring: 'ring-blue-100 dark:ring-blue-900/60',
  },
  amber: {
    pill: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-300',
    icon: 'text-amber-600',
    ring: 'ring-amber-100 dark:ring-amber-900/60',
  },
  red: {
    pill: 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/70 dark:bg-red-950/30 dark:text-red-300',
    icon: 'text-red-600',
    ring: 'ring-red-100 dark:ring-red-900/60',
  },
  emerald: {
    pill: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/30 dark:text-emerald-300',
    icon: 'text-emerald-600',
    ring: 'ring-emerald-100 dark:ring-emerald-900/60',
  },
  violet: {
    pill: 'border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900/70 dark:bg-violet-950/30 dark:text-violet-300',
    icon: 'text-violet-600',
    ring: 'ring-violet-100 dark:ring-violet-900/60',
  },
}

export default function KnowledgePage() {
  const { data: stats, isLoading: statsLoading } = useKnowledgeStats()
  const { data: docs } = useKnowledgeDocs()
  const [category, setCategory] = useState<CategoryId>('all')
  const [query, setQuery] = useState('')

  const filteredArticles = useMemo(() => {
    const q = query.trim().toLowerCase()
    return FEATURED_ARTICLES.filter((article) => {
      if (category !== 'all' && article.category !== category) return false
      if (!q) return true
      return [article.title, article.description, article.label]
        .join(' ')
        .toLowerCase()
        .includes(q)
    })
  }, [category, query])

  const latestDocs = docs?.slice(0, 3) ?? []

  return (
    <div className="h-full overflow-y-auto bg-muted/40 px-4 py-5 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-7">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-blue-50 text-blue-600 ring-1 ring-blue-100 dark:bg-blue-950/30 dark:text-blue-300 dark:ring-blue-900/70">
              <BookOpenCheck className="size-4" />
            </span>
            <div className="min-w-0">
              <h1 className="truncate text-[22px] font-semibold tracking-normal">知识库</h1>
              <p className="mt-0.5 text-[13px] text-muted-foreground">
                法规、税务、认证与案例索引
              </p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:w-[360px]">
            <MiniMetric label="文档" value={stats?.total_docs} loading={statsLoading} />
            <MiniMetric label="已就绪" value={stats?.done_count} loading={statsLoading} />
            <MiniMetric label="向量" value={stats?.total_vectors} loading={statsLoading} />
          </div>
        </header>

        <section className="rounded-lg border border-border/70 bg-card p-4 shadow-sm">
          <div className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索法规、税务、认证、案例..."
              className="h-14 w-full rounded-lg border border-border/70 bg-background pl-11 pr-4 text-[14px] outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/50 focus:ring-2 focus:ring-primary/15"
            />
          </div>
        </section>

        <nav className="flex flex-wrap gap-2" aria-label="知识库分类">
          {CATEGORIES.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setCategory(item.id)}
              className={cn(
                'h-8 rounded-full px-3 text-[12px] font-medium transition-colors',
                category === item.id
                  ? 'bg-foreground text-background'
                  : 'bg-card text-muted-foreground ring-1 ring-border/70 hover:text-foreground',
              )}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <section className="grid gap-4 lg:grid-cols-3" aria-label="知识条目">
          {filteredArticles.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-card p-8 text-center text-[13px] text-muted-foreground lg:col-span-3">
              未找到匹配内容
            </div>
          ) : (
            filteredArticles.map((article) => (
              <KnowledgeCard key={article.title} article={article} />
            ))
          )}
        </section>

        <section aria-label="推荐服务商">
          <div className="mb-3 flex items-center gap-2">
            <Star className="size-4 fill-warning text-warning" />
            <h2 className="text-[16px] font-semibold tracking-normal">推荐服务商</h2>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            {PROVIDERS.map((provider) => (
              <article
                key={provider.name}
                className="flex min-h-[116px] flex-col justify-between rounded-lg border border-border/70 bg-card p-4 shadow-sm"
              >
                <div className="flex items-start gap-3">
                  <span className={cn('flex size-10 shrink-0 rounded-full', provider.toneClass)} />
                  <div className="min-w-0">
                    <h3 className="truncate text-[14px] font-semibold">{provider.name}</h3>
                    <p className="mt-0.5 truncate text-[12px] text-muted-foreground">{provider.scope}</p>
                  </div>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-1 text-[12px] text-warning">
                    <span aria-hidden="true">★★★★★</span>
                    <span className="text-muted-foreground">
                      {provider.rating} ({provider.reviews})
                    </span>
                  </div>
                  <button className="h-7 rounded-md border border-border/70 px-3 text-[12px] font-medium text-foreground transition-colors hover:bg-muted">
                    联系
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[1fr_340px]">
          <div className="rounded-lg border border-border/70 bg-card p-4 shadow-sm">
            <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-[16px] font-semibold tracking-normal">知识库维护</h2>
                <p className="text-[12px] text-muted-foreground">
                  文档导入、语义搜索与向量状态
                </p>
              </div>
              <span className="text-[12px] text-muted-foreground">
                {statsLoading ? '统计加载中' : `${stats?.indexing_count ?? 0} 个任务处理中`}
              </span>
            </div>
            <Tabs defaultValue="search" className="w-full">
              <TabsList className="mb-5 inline-flex min-h-9 flex-wrap items-center justify-start rounded-md bg-muted p-1 text-muted-foreground">
                <TabsTrigger
                  value="search"
                  className="inline-flex items-center gap-1.5 px-3 py-1 text-sm data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
                >
                  <Search className="size-3.5" />
                  语义搜索
                </TabsTrigger>
                <TabsTrigger
                  value="list"
                  className="inline-flex items-center gap-1.5 px-3 py-1 text-sm data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
                >
                  <FileText className="size-3.5" />
                  文档
                </TabsTrigger>
                <TabsTrigger
                  value="pdf"
                  className="inline-flex items-center gap-1.5 px-3 py-1 text-sm data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
                >
                  <UploadCloud className="size-3.5" />
                  PDF
                </TabsTrigger>
                <TabsTrigger
                  value="url"
                  className="inline-flex items-center gap-1.5 px-3 py-1 text-sm data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
                >
                  <Link2 className="size-3.5" />
                  URL
                </TabsTrigger>
              </TabsList>

              <TabsContent value="search">
                <SearchPanel />
              </TabsContent>
              <TabsContent value="list">
                <KnowledgeList />
              </TabsContent>
              <TabsContent value="pdf">
                <PdfUpload />
              </TabsContent>
              <TabsContent value="url">
                <UrlImport />
              </TabsContent>
            </Tabs>
          </div>

          <aside className="rounded-lg border border-border/70 bg-card p-4 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <Database className="size-4 text-muted-foreground" />
              <h2 className="text-[14px] font-semibold tracking-normal">最近导入</h2>
            </div>
            {latestDocs.length === 0 ? (
              <div className="rounded-md border border-dashed border-border bg-muted/30 p-5 text-[13px] text-muted-foreground">
                暂无导入记录
              </div>
            ) : (
              <div className="space-y-2">
                {latestDocs.map((doc) => (
                  <div
                    key={doc.id}
                    className="rounded-md border border-border/60 bg-background px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-[13px] font-medium">{doc.name}</p>
                      <DocStatus status={doc.status} />
                    </div>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {doc.doc_type.toUpperCase()} · {doc.chunk_count || 0} 个片段
                    </p>
                  </div>
                ))}
              </div>
            )}
          </aside>
        </section>
      </div>
    </div>
  )
}

function MiniMetric({
  label,
  value,
  loading,
}: {
  label: string
  value: number | undefined
  loading: boolean
}) {
  return (
    <div className="rounded-lg border border-border/70 bg-card px-3 py-2 text-right shadow-sm">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-[18px] font-semibold tabular-nums">
        {loading ? '...' : (value ?? 0)}
      </p>
    </div>
  )
}

function KnowledgeCard({
  article,
}: {
  article: (typeof FEATURED_ARTICLES)[number]
}) {
  const tone = TONE_CLASS[article.tone]
  return (
    <article className="flex min-h-[146px] flex-col rounded-lg border border-border/70 bg-card p-5 shadow-sm transition-colors hover:border-border">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className={cn('inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[12px] font-medium', tone.pill)}>
          <article.Icon className={cn('size-3.5', tone.icon)} />
          {article.label}
        </span>
        <span className={cn('flex size-8 items-center justify-center rounded-md bg-background ring-1', tone.ring)}>
          <article.Icon className={cn('size-4', tone.icon)} />
        </span>
      </div>
      <h2 className="text-[15px] font-semibold tracking-normal text-foreground">{article.title}</h2>
      <p className="mt-2 line-clamp-2 text-[12px] leading-5 text-muted-foreground">
        {article.description}
      </p>
      <p className="mt-auto pt-4 text-[12px] text-muted-foreground">{article.meta}</p>
    </article>
  )
}

function DocStatus({ status }: { status: 'indexing' | 'done' | 'error' }) {
  if (status === 'done') {
    return <CheckCircle2 className="size-3.5 shrink-0 text-success" aria-label="已就绪" />
  }
  if (status === 'error') {
    return <span className="text-[11px] font-medium text-destructive">失败</span>
  }
  return <Loader2 className="size-3.5 shrink-0 animate-spin text-warning" aria-label="向量化中" />
}
