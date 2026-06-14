/**
 * SearchPanel — 语义搜索预览（直接查询 ChromaDB）
 * 命中片段 + 元数据（来源 / 市场 / 页码 / 相似度）
 */
import { useState } from 'react'
import { Search, Sparkles, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { useSearchKnowledge } from '@/hooks/queries/useKnowledge'
import { MARKET_LABEL, MARKET_VALUES } from '@/lib/api/knowledge'
import { cn } from '@/lib/utils'
import type { KnowledgeMarket } from '@/types'

const MARKET_OPTIONS: Array<{ value: KnowledgeMarket | ''; label: string }> = [
  { value: '', label: '自动推断' },
  ...MARKET_VALUES.map((m) => ({ value: m, label: MARKET_LABEL[m] })),
]

function truncate(s: string, n = 280): string {
  return s.length > n ? s.slice(0, n) + '…' : s
}

export function SearchPanel() {
  const [query, setQuery] = useState('')
  const [market, setMarket] = useState<KnowledgeMarket | ''>('')
  const [topK, setTopK] = useState(5)
  // 直接用 search.data（mutate 后 TanStack Query 自动存入），无重复 useState
  const search = useSearchKnowledge()
  const result = search.data

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) {
      toast.error('请输入查询')
      return
    }
    try {
      const r = await search.mutateAsync({
        query: query.trim(),
        market: market || '',
        top_k: topK,
      })
      if (r.count === 0) toast.info('未命中相关片段')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '搜索失败')
    }
  }

  return (
    <div className="space-y-5">
      <form onSubmit={handleSearch} className="space-y-3">
        <div>
          <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
            查询
          </label>
          <div className="flex items-center gap-2">
            <Search className="size-4 text-muted-foreground shrink-0" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="如：欧盟 CE 认证 电磁兼容 指令"
              className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-3 items-end">
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
              目标市场
            </label>
            <select
              value={market}
              onChange={(e) => setMarket(e.target.value as KnowledgeMarket | '')}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {MARKET_OPTIONS.map((m) => (
                <option key={m.value || 'auto'} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
              Top K：<span className="text-foreground tabular-nums">{topK}</span>
            </label>
            <input
              type="range"
              min={1}
              max={20}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>
        </div>

        <Button type="submit" disabled={search.isPending}>
          <Sparkles className="size-4" />
          {search.isPending ? '搜索中…' : '语义搜索'}
        </Button>
      </form>

      {/* Results */}
      {result && (
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            命中 <span className="text-foreground tabular-nums">{result.count}</span> 条 ·
            查询：「{result.query}」
          </p>
          {result.results.map((hit, idx) => (
            <article
              key={`${hit.doc_id}-${idx}`}
              className="rounded-lg border border-border bg-card p-4 space-y-2"
            >
              <header className="flex items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2 text-muted-foreground min-w-0">
                  <span className="text-foreground font-medium truncate">
                    {hit.regulation_name || hit.doc_id}
                  </span>
                  <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wider">
                    {MARKET_LABEL[hit.market as KnowledgeMarket] ?? hit.market}
                  </span>
                  {hit.page_hint && (
                    <span className="shrink-0 text-[10px]">p.{hit.page_hint}</span>
                  )}
                </div>
                <span
                  className={cn(
                    'shrink-0 tabular-nums text-[10px] font-medium',
                    hit.score >= 0.7
                      ? 'text-success'
                      : hit.score >= 0.4
                        ? 'text-warning'
                        : 'text-muted-foreground',
                  )}
                >
                  score {hit.score.toFixed(3)}
                </span>
              </header>
              <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-wrap">
                {/* hit.text 视为纯文本，不解析 HTML/Markdown（React 文本节点自动转义）。
                   如未来需支持富文本，改用 react-markdown + DOMPurify。 */}
                {truncate(hit.text, 360)}
              </p>
              {hit.source_url && !hit.source_url.startsWith('file://') && (
                <a
                  href={hit.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  来源 <ExternalLink className="size-3" />
                </a>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
