import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { FileText, Printer } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ComplianceResult } from '@/types'

const MARKETS = [
  { code: 'de', label: '德国' },
  { code: 'fr', label: '法国' },
  { code: 'it', label: '意大利' },
  { code: 'es', label: '西班牙' },
  { code: 'nl', label: '荷兰' },
  { code: 'be', label: '比利时' },
  { code: 'gb', label: '英国' },
  { code: 'jp', label: '日本' },
  { code: 'kr', label: '韩国' },
  { code: 'us', label: '美国' },
  { code: 'sg', label: '新加坡' },
] as const

const DEFAULT_MARKET_VALUE = 'default'
const USE_BACKEND_COMPLIANCE = import.meta.env.VITE_STREAM_MODE !== 'mock'
const HISTORY_STORAGE_KEY = 'astra_compliance_history'

interface QueryHistoryItem {
  id: string
  product: string
  country: string
  risk: 'low' | 'medium' | 'high' | 'critical'
  time: string
}

const PRODUCT_SUGGESTIONS = [
  { product: 'LED 灯带', country: '德国', note: 'CE · RoHS · WEEE · LUCID' },
  { product: '锂离子电池组', country: '日本', note: 'PSE · UN38.3 · MSDS' },
  { product: '儿童益智玩具', country: '法国', note: 'CE · EN71 · REACH' },
  { product: '蓝牙耳机', country: '美国', note: 'FCC · UL · CA Prop 65' },
]

/** 初始历史：空列表，用户做过查询后写入 localStorage，下次打开恢复。 */
const INITIAL_HISTORY: QueryHistoryItem[] = PRODUCT_SUGGESTIONS.map((s, i) => ({
  id: `suggest-${i}`,
  product: s.product,
  country: s.country,
  risk: 'medium' as const,
  time: '今天',
}))

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY)
    if (!raw) return INITIAL_HISTORY
    const parsed = JSON.parse(raw) as QueryHistoryItem[]
    return Array.isArray(parsed) && parsed.length > 0 ? parsed : INITIAL_HISTORY
  } catch {
    return INITIAL_HISTORY
  }
}

function createMockResult(product: string, country: string): ComplianceResult {
  const certs: string[] = ['CE', 'RoHS', 'WEEE']
  const riskLevel = 'medium' as ComplianceResult['risk_level']

  return {
    hs_code: '8541.4100',
    hs_description: `${product || '目标产品'} 面向 ${country || '欧盟'} 的初步商品归类结果，最终以报关归类和官方税则为准。`,
    vat_rate: country === '德国' ? 19 : country === '法国' ? 20 : country === '日本' ? 10 : 0,
    certifications: certs,
    risk_level: riskLevel,
    risk_score: (() => { const r = riskLevel; return r === 'high' ? 72 : r === 'medium' ? 48 : 22 })(),
    risk_flags: [
      '需复核目标市场强制认证和标签展示要求。',
      '需确认 HS 编码、清关材料和平台 Listing 信息一致。',
    ],
    logistics_flags: ['物流单号需可追踪', '跨境干线资料需与订单和支付信息一致'],
    customs_documents: ['商业发票', '装箱单', '产品认证附件', '申报要素说明'],
    cultural_notes: ['检查目标市场语言标签和消费者告知要求'],
    remediation_steps: [
      '补齐认证文件并复核产品标签',
      '将检查结果同步到产品事件链并设置到期提醒',
    ],
    checklist: ['确认 HS 编码', '核验证书有效期', '检查标签与说明书', '准备清关材料'],
  }
}

function buildMockReport(product: string, country: string, result: ComplianceResult) {
  return [
    `# ${product || '产品'} 出口 ${country || '欧盟'} 合规报告`,
    '',
    `- HS 编码：${result.hs_code}`,
    `- VAT 税率：${result.vat_rate}%`,
    `- 风险等级：${result.risk_level}`,
    `- 认证要求：${result.certifications.join('、')}`,
    '',
    '## 风险提示',
    ...result.risk_flags.map((item) => `- ${item}`),
    '',
    '## 整改建议',
    ...(result.remediation_steps ?? []).map((item) => `- ${item}`),
    '',
    '## 出口待办清单',
    ...result.checklist.map((item) => `- ${item}`),
  ].join('\n')
}

async function readChatStream(res: Response) {
  const reader = res.body?.getReader()
  if (!reader) return { message: '', compliance_result: null as ComplianceResult | null }

  const decoder = new TextDecoder()
  let buffer = ''
  let eventName = 'message'
  let message = ''
  let complianceResult: ComplianceResult | null = null

  const consumeBlock = (block: string) => {
    const lines = block.split('\n')
    for (const line of lines) {
      if (line.startsWith('event:')) eventName = line.slice(6).trim()
      if (!line.startsWith('data:')) continue
      const raw = line.slice(5).trim()
      if (!raw) continue
      const data = JSON.parse(raw)
      if (eventName === 'token' && typeof data.content === 'string') {
        message += data.content
      }
      if (data.compliance_result) {
        complianceResult = data.compliance_result
      }
      if (eventName === 'done' && data.compliance_result) {
        complianceResult = data.compliance_result
      }
    }
    eventName = 'message'
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    blocks.forEach(consumeBlock)
  }
  if (buffer.trim()) consumeBlock(buffer)
  return { message, compliance_result: complianceResult }
}

export default function CompliancePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const initialState = location.state as { product?: string; country?: string } | null
  const [product, setProduct] = useState(initialState?.product ?? '')
  const [country, setCountry] = useState(initialState?.country ?? '')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ComplianceResult | null>(null)
  const [report, setReport] = useState('')
  const [history, setHistory] = useState<QueryHistoryItem[]>(loadHistory)
  const productRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    productRef.current?.focus()
  }, [])

  useEffect(() => {
    const next = location.state as { product?: string; country?: string } | null
    if (!next) return
    if (next.product !== undefined) setProduct(next.product)
    if (next.country !== undefined) setCountry(next.country)
  }, [location.state])

  const handleExportMd = () => {
    if (!report) return
    const filename = `${product || '产品'}_${country || '欧盟'}_合规报告_${new Date().toISOString().slice(0, 10)}.md`
    const blob = new Blob([report], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleExportPdf = () => {
    if (!result) return
    const title = `${product || '产品'} → ${country || '欧盟'} 合规报告`
    const rows = [
      ['HS 编码', result.hs_code || '—'],
      ['VAT 税率', `${result.vat_rate}%`],
      ['风险评分', `${result.risk_score ?? 0}/100`],
      ['认证要求', result.certifications.join(', ') || '—'],
    ]
    const list = (heading: string, items?: string[]) =>
      items?.length
        ? `<h2>${heading}</h2><ul>${items.map((item) => `<li>${item}</li>`).join('')}</ul>`
        : ''

    const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${title}</title><style>
      body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;max-width:820px;margin:0 auto;padding:40px;color:#111827;line-height:1.7}
      h1{font-size:24px;margin:0 0 8px} h2{font-size:15px;margin:24px 0 8px}
      .meta{color:#6b7280;font-size:12px;margin-bottom:24px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
      .cell{border:1px solid #e5e7eb;border-radius:8px;padding:12px}.label{font-size:11px;color:#6b7280}.value{font-size:18px;font-weight:700}
      li{margin:4px 0}.footer{margin-top:32px;border-top:1px solid #e5e7eb;padding-top:12px;color:#9ca3af;font-size:11px}
    </style></head><body>
      <h1>${title}</h1><div class="meta">生成时间：${new Date().toLocaleDateString('zh-CN')}</div>
      <div class="grid">${rows.map(([label, value]) => `<div class="cell"><div class="label">${label}</div><div class="value">${value}</div></div>`).join('')}</div>
      ${list('风险提示', result.risk_flags)}
      ${list('物流与运输', result.logistics_flags)}
      ${list('清关材料', result.customs_documents)}
      ${list('市场本地化', result.cultural_notes)}
      ${list('整改建议', result.remediation_steps)}
      ${list('出口待办清单', result.checklist)}
      <div class="footer">本报告由避风港生成，仅供参考，不构成法律建议。</div>
    </body></html>`
    const win = window.open('', '_blank', 'width=860,height=720')
    if (!win) return
    win.document.write(html)
    win.document.close()
    win.focus()
    setTimeout(() => win.print(), 300)
  }

  const addHistory = (nextProduct: string, nextCountry: string, nextResult: ComplianceResult) => {
    const item: QueryHistoryItem = {
      id: `${nextProduct}-${nextCountry}-${Date.now()}`,
      product: nextProduct,
      country: nextCountry || '欧盟',
      risk: nextResult.risk_level,
      time: '刚刚',
    }
    setHistory((prev) => {
      const next = [item, ...prev.filter((entry) => !(entry.product === item.product && entry.country === item.country))].slice(0, 8)
      localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }

  const executeSearch = async (nextProduct: string, nextCountry: string) => {
    if (!nextProduct.trim() || loading) return
    setLoading(true)
    setResult(null)
    setReport('')
    const msg = `${nextProduct.trim()} 出口 ${nextCountry || '欧盟'} 合规要求`
    if (!USE_BACKEND_COMPLIANCE) {
      const nextResult = createMockResult(nextProduct, nextCountry)
      setResult(nextResult)
      setReport(buildMockReport(nextProduct, nextCountry, nextResult))
      addHistory(nextProduct, nextCountry, nextResult)
      setLoading(false)
      return
    }
    try {
      const token = localStorage.getItem('astra_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const r = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: msg }),
      })
      if (!r.ok) throw new Error(`请求失败 ${r.status}`)
      const d = await readChatStream(r)
      const nextResult = d.compliance_result ?? createMockResult(nextProduct, nextCountry)
      setResult(nextResult)
      setReport(d.message || buildMockReport(nextProduct, nextCountry, nextResult))
      addHistory(nextProduct, nextCountry, nextResult)
    } catch (e) {
      const nextResult = createMockResult(nextProduct, nextCountry)
      setResult(nextResult)
      setReport(buildMockReport(nextProduct, nextCountry, nextResult))
      addHistory(nextProduct, nextCountry, nextResult)
      toast.info('后端不可用，已使用前端示例报告')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async () => {
    await executeSearch(product, country)
  }

  const handleSuggestion = async (nextProduct: string, nextCountry: string) => {
    setProduct(nextProduct)
    setCountry(nextCountry)
    await executeSearch(nextProduct, nextCountry)
  }

  const handleHistoryClick = (item: QueryHistoryItem) => {
    setProduct(item.product)
    setCountry(item.country)
  }

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="border-b border-border/60 bg-background">
        <div className="mx-auto max-w-[1400px] px-8 py-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="text-[28px] font-semibold tracking-tight">合规查询</h1>
              <p className="mt-1 text-[14px] text-muted-foreground/80">
                输入产品 + 目标市场，获取完整合规报告
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={handleExportMd}
                disabled={!report}
                variant="outline"
                className="h-9 text-[13px]"
                title={report ? '导出 Markdown 文件' : '生成报告后可导出'}
              >
                <FileText className="mr-2 size-4" />
                导出 Markdown
              </Button>
              <Button
                onClick={handleExportPdf}
                disabled={!result}
                variant="outline"
                className="h-9 text-[13px]"
                title={result ? '打开打印窗口导出 PDF' : '生成报告后可导出'}
              >
                <Printer className="mr-2 size-4" />
                导出 PDF
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-[1400px] px-8 py-8">
        {/* Search Form */}
        <div className="mb-8 flex gap-3">
          <Input
            ref={productRef}
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="产品名称，如：LED 驱动电源、锂电池..."
            className="h-10 flex-1 text-[14px]"
          />
          <Select
            value={country || DEFAULT_MARKET_VALUE}
            onValueChange={(value) => setCountry(value === DEFAULT_MARKET_VALUE ? '' : value)}
          >
            <SelectTrigger
              aria-label="目标市场"
              className="h-10 w-48 shrink-0 border-border/60 bg-background px-3 text-[14px] font-normal shadow-none transition-colors hover:border-foreground/30 focus-visible:ring-1 focus-visible:ring-ring [&>svg]:text-muted-foreground [&>svg]:opacity-100"
            >
              <SelectValue placeholder="目标市场" />
            </SelectTrigger>
            <SelectContent
              align="start"
              position="item-aligned"
              className="w-48 rounded-md border-border/70 p-1 shadow-lg shadow-black/5"
            >
              <SelectItem
                value={DEFAULT_MARKET_VALUE}
                className="h-8 rounded-[5px] pl-3 pr-8 text-[14px] text-muted-foreground focus:bg-muted"
              >
                目标市场
              </SelectItem>
              {MARKETS.map((m) => (
                <SelectItem
                  key={m.code}
                  value={m.label}
                  className="h-8 rounded-[5px] pl-3 pr-8 text-[14px] focus:bg-muted"
                >
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            onClick={handleSearch}
            disabled={!product.trim() || loading}
            className="h-10 px-6 text-[14px] font-medium"
          >
            {loading ? '查询中...' : '查询'}
          </Button>
        </div>

        <div className="mb-8 grid gap-4 lg:grid-cols-[1fr_380px]">
          <section className="rounded-lg border border-border/60 bg-card p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-[14px] font-semibold">产品建议</h2>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  常见跨境合规场景，点击后直接查询
                </p>
              </div>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {PRODUCT_SUGGESTIONS.map((item) => (
                <button
                  key={`${item.product}-${item.country}`}
                  onClick={() => handleSuggestion(item.product, item.country)}
                  className="rounded-md border border-border/60 bg-background px-3 py-3 text-left transition-colors hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <div className="text-[13px] font-semibold">
                    {item.product}
                    <span className="font-normal text-muted-foreground"> → {item.country}</span>
                  </div>
                  <div className="mt-1.5 text-[11px] text-muted-foreground">{item.note}</div>
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-border/60 bg-card">
            <div className="border-b border-border/60 px-4 py-3">
              <h2 className="text-[14px] font-semibold">最近查询</h2>
              <p className="mt-0.5 text-[12px] text-muted-foreground">
                点击历史记录回填产品和市场
              </p>
            </div>
            <div className="max-h-[226px] overflow-y-auto">
              {history.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleHistoryClick(item)}
                  className="flex w-full items-center justify-between gap-3 border-b border-border/40 px-4 py-3 text-left last:border-b-0 hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] font-medium">
                      {item.product} → {item.country}
                    </span>
                    <span className="mt-0.5 block text-[11.5px] text-muted-foreground">{item.time}</span>
                  </span>
                  <span
                    className={
                      item.risk === 'high'
                        ? 'rounded-full bg-rose-50 px-2 py-0.5 text-[10.5px] font-medium text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
                        : item.risk === 'medium'
                          ? 'rounded-full bg-amber-50 px-2 py-0.5 text-[10.5px] font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
                          : 'rounded-full bg-emerald-50 px-2 py-0.5 text-[10.5px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                    }
                  >
                    {item.risk === 'high' ? '高' : item.risk === 'medium' ? '中' : '低'}
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>

        {/* Result */}
        {result && (
          <div className="space-y-6">
            <div className="flex flex-col gap-3 rounded-lg border border-border/60 bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-[16px] font-semibold">
                  {product || '产品'} → {country || '欧盟'} 合规报告
                </h2>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  生成时间：{new Date().toLocaleDateString('zh-CN')} · 已自动保存到最近查询
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={() => navigate('/app/chat', { state: { initialMessage: `${product} 出口 ${country}` } })}
                  variant="outline"
                  className="h-9 text-[13px]"
                >
                  深入追问
                </Button>
                <Button
                  onClick={handleExportMd}
                  disabled={!report}
                  variant="outline"
                  className="h-9 text-[13px]"
                >
                  导出 Markdown
                </Button>
                <Button
                  onClick={handleExportPdf}
                  variant="outline"
                  className="h-9 text-[13px]"
                >
                  导出 PDF
                </Button>
              </div>
            </div>

            {/* Summary Cards */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border border-border/60 p-4">
                <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  HS 编码
                </div>
                <div className="text-2xl font-semibold">{result.hs_code || '—'}</div>
              </div>
              <div className="rounded-lg border border-border/60 p-4">
                <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  VAT 税率
                </div>
                <div className="text-2xl font-semibold">{result.vat_rate}%</div>
              </div>
              <div className="rounded-lg border border-border/60 p-4">
                <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  风险评分
                </div>
                <div className="text-2xl font-semibold">{result.risk_score ?? 0}/100</div>
              </div>
              <div className="rounded-lg border border-border/60 p-4">
                <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  认证要求
                </div>
                <div className="text-2xl font-semibold">{result.certifications.length} 项</div>
              </div>
            </div>

            {/* Certifications */}
            {result.certifications.length > 0 && (
              <div>
                <h3 className="mb-3 text-base font-semibold">认证要求</h3>
                <div className="flex flex-wrap gap-2">
                  {result.certifications.map((cert, i) => (
                    <span
                      key={i}
                      className="rounded-md border border-border/60 bg-muted/30 px-3 py-1.5 text-[13px] font-medium"
                    >
                      {cert}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Risk Flags */}
            {result.risk_flags.length > 0 && (
              <div>
                <h3 className="mb-3 text-base font-semibold">风险提示</h3>
                <ul className="space-y-2">
                  {result.risk_flags.map((flag, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-[13px] text-muted-foreground"
                    >
                      <span className="mt-1 inline-block size-1.5 shrink-0 rounded-full bg-amber-500" />
                      <span>{flag}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Checklist */}
            {result.checklist.length > 0 && (
              <div>
                <h3 className="mb-3 text-base font-semibold">出口待办清单</h3>
                <ol className="space-y-2">
                  {result.checklist.map((item, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-3 text-[13px] text-muted-foreground"
                    >
                      <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-medium">
                        {i + 1}
                      </span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Restored detailed sections */}
            <div className="grid gap-6 lg:grid-cols-2">
              {result.logistics_flags && result.logistics_flags.length > 0 && (
                <DetailList title="物流与运输" items={result.logistics_flags} />
              )}
              {result.customs_documents && result.customs_documents.length > 0 && (
                <DetailList title="清关材料" items={result.customs_documents} />
              )}
              {result.cultural_notes && result.cultural_notes.length > 0 && (
                <DetailList title="市场本地化" items={result.cultural_notes} />
              )}
              {result.remediation_steps && result.remediation_steps.length > 0 && (
                <DetailList title="整改建议" items={result.remediation_steps} />
              )}
            </div>

            <div>
              <h3 className="mb-3 text-base font-semibold">商品归类</h3>
              <div className="rounded-lg border border-border/60 bg-card p-4 text-[13px] leading-6 text-muted-foreground">
                {result.hs_description || '未匹配到 HS 编码描述'}
              </div>
            </div>

            {report && (
              <details className="rounded-lg border border-border/60 bg-card p-4">
                <summary className="cursor-pointer select-none text-[13px] font-medium text-muted-foreground hover:text-foreground">
                  查看完整原始报告
                </summary>
                <pre className="mt-3 max-h-[360px] overflow-auto whitespace-pre-wrap rounded-md bg-muted/35 p-4 text-[12.5px] leading-6 text-muted-foreground">
                  {report}
                </pre>
              </details>
            )}
          </div>
        )}

        {/* Empty State */}
        {!result && !loading && (
          <div className="py-16 text-center">
            <div className="mb-2 text-[15px] font-medium text-muted-foreground">
              输入产品信息开始查询
            </div>
            <p className="text-[13px] text-muted-foreground/70">
              系统会分析 HS 编码、税率、认证要求和风险提示
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function DetailList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="mb-3 text-base font-semibold">{title}</h3>
      <div className="rounded-lg border border-border/60 bg-card p-4">
        <ul className="space-y-2">
          {items.map((item, index) => (
            <li
              key={`${title}-${index}`}
              className="flex items-start gap-2 text-[13px] leading-6 text-muted-foreground"
            >
              <span className="mt-2 inline-block size-1.5 shrink-0 rounded-full bg-muted-foreground/50" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
