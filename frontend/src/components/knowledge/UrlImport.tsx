/**
 * UrlImport — 从 URL 导入网页或 PDF
 * 后台抓取 + 向量化
 */
import { useState } from 'react'
import { Link2, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { useImportUrl } from '@/hooks/queries/useKnowledge'
import { MARKET_LABEL, MARKET_VALUES } from '@/lib/api/knowledge'
import type { KnowledgeMarket } from '@/types'

function isValidUrl(s: string): boolean {
  try {
    const u = new URL(s)
    return u.protocol === 'https:' || u.protocol === 'http:'
  } catch {
    return false
  }
}

export function UrlImport() {
  const [url, setUrl] = useState('')
  const [market, setMarket] = useState<KnowledgeMarket>('eu')
  const [regulationName, setRegulationName] = useState('')
  const importUrl = useImportUrl()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = url.trim()
    if (!isValidUrl(trimmed)) {
      toast.error('URL 必须以 http:// 或 https:// 开头')
      return
    }
    try {
      const ack = await importUrl.mutateAsync({
        url: trimmed,
        market,
        regulationName: regulationName.trim() || undefined,
      })
      toast.success(ack.message || '已接收，后台抓取中…')
      setUrl('')
      setRegulationName('')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '导入失败')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
          URL
        </label>
        <div className="flex items-center gap-2">
          <Link2 className="size-4 text-muted-foreground shrink-0" />
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://eur-lex.europa.eu/..."
            className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            required
          />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          支持网页与 PDF 链接。后台异步抓取并向量化。
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
            法规名称（可选）
          </label>
          <input
            type="text"
            value={regulationName}
            onChange={(e) => setRegulationName(e.target.value)}
            placeholder="如：GDPR 2016-679"
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div>
          <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
            目标市场
          </label>
          <select
            value={market}
            onChange={(e) => setMarket(e.target.value as KnowledgeMarket)}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {MARKET_VALUES.map((m) => (
              <option key={m} value={m}>
                {MARKET_LABEL[m]}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Button type="submit" disabled={!url.trim() || importUrl.isPending}>
        {importUrl.isPending && <Loader2 className="size-4 animate-spin" />}
        {importUrl.isPending ? '提交中…' : '导入并开始向量化'}
      </Button>
    </form>
  )
}
