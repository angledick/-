/**
 * 产品出海生命周期管理中心
 *
 * 涵盖：选品来源 · 供应商审核 · 合同管理 · 支付通道 · 物流报关
 * 对应 10 大业务阶段完整流程
 */

import { useState, useEffect, useCallback } from 'react'
import {
  suppliersApi, contractsApi, paymentChannelsApi, logisticsApi, customsApi,
  type SupplierInfo, type ContractInfo, type PaymentChannel,
  type LogisticsOrder, type CustomsDeclaration, type ContractTemplate,
} from '../api/config'

// ─────────────────────────────────────────────────────────────────────────────
// 业务阶段配置
// ─────────────────────────────────────────────────────────────────────────────

const LIFECYCLE_STAGES = [
  { key: 'concept',    label: '概念',     step: 1, desc: '建站/选品' },
  { key: 'design',     label: '设计',     step: 2, desc: '样品设计' },
  { key: 'sourcing',   label: '采购',     step: 3, desc: '供应商/合同' },
  { key: 'ready',      label: '就绪',     step: 4, desc: '上架/支付' },
  { key: 'active',     label: '在售',     step: 5, desc: '订单处理' },
  { key: 'fulfilling', label: '履约',     step: 6, desc: '发货/报关' },
  { key: 'aftersale',  label: '售后',     step: 7, desc: '退货/纠纷' },
  { key: 'end',        label: '结算',     step: 8, desc: '财务结算' },
] as const

const INCOTERMS = ['EXW', 'FCA', 'FOB', 'CFR', 'CIF', 'DAP', 'DDP']
const INCOTERM_RISK: Record<string, { buyer: string; seller: string; warn?: string }> = {
  EXW: { buyer: '买方承担全程', seller: '出厂交货即可',  warn: '买方需具备出口报关能力' },
  FOB: { buyer: '装船后承担',   seller: '出口清关到港',  },
  CIF: { buyer: '目的港后承担', seller: '运费+保险',     },
  DAP: { buyer: '进口清关',     seller: '运抵目的地',    },
  DDP: { buyer: '全程无忧',     seller: '全包含关税',    warn: '需具备目的国进口资质' },
}

const PROVIDER_META: Record<string, { icon: string; color: string; desc: string }> = {
  stripe:           { icon: '💳', color: 'text-blue-600',   desc: '全球最广泛，PCI DSS 认证' },
  paypal:           { icon: '🅿', color: 'text-blue-500',   desc: '消费者信任度高，买家保护' },
  lianlian:         { icon: '🏦', color: 'text-green-600',  desc: '国内持牌，合规结汇' },
  worldfirst:       { icon: '🌍', color: 'text-emerald-600',desc: '万里汇，低汇损结汇' },
  shopify_payments: { icon: '🛒', color: 'text-purple-600', desc: 'Shopify 原生支付' },
  alipay_global:    { icon: '💰', color: 'text-sky-600',    desc: '支付宝国际版' },
}

const STATUS_COLORS: Record<string, string> = {
  active:       'text-emerald-600 bg-emerald-50 border-emerald-200',
  pending_kyc:  'text-amber-600 bg-amber-50 border-amber-200',
  suspended:    'text-red-500 bg-red-50 border-red-200',
  error:        'text-red-600 bg-red-50 border-red-200',
  draft:        'text-gray-500 bg-gray-50 border-gray-200',
  signed:       'text-emerald-600 bg-emerald-50 border-emerald-200',
  review:       'text-blue-600 bg-blue-50 border-blue-200',
  cancelled:    'text-gray-400 bg-gray-50 border-gray-200',
  submitted:    'text-blue-600 bg-blue-50 border-blue-200',
  cleared:      'text-emerald-600 bg-emerald-50 border-emerald-200',
  exception:    'text-red-600 bg-red-50 border-red-200',
  delivered:    'text-emerald-600 bg-emerald-50 border-emerald-200',
  in_transit:   'text-blue-600 bg-blue-50 border-blue-200',
  pending:      'text-gray-500 bg-gray-50 border-gray-200',
}

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] || 'text-gray-500 bg-gray-50 border-gray-200'
  const labels: Record<string, string> = {
    active: '正常', pending_kyc: '待 KYC', suspended: '暂停', error: '异常',
    draft: '草稿', signed: '已签署', review: '审查中', cancelled: '已取消',
    submitted: '已提交', cleared: '已清关', exception: '异常', delivered: '已交付',
    in_transit: '运输中', pending: '待处理',
  }
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${cls}`}>{labels[status] || status}</span>
}

function cx(...a: (string | false | null | undefined)[]) { return a.filter(Boolean).join(' ') }

function Spinner({ size = 'sm' }: { size?: 'xs' | 'sm' }) {
  return <svg className={cx(size === 'xs' ? 'w-3 h-3' : 'w-4 h-4', 'animate-spin text-current')} viewBox="0 0 24 24" fill="none"><circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/></svg>
}

function EmptyCard({ icon, title, sub, action }: { icon: string; title: string; sub?: string; action?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-6 py-10 text-center">
      <p className="text-3xl mb-2">{icon}</p>
      <p className="text-sm font-medium text-gray-500">{title}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 供应商管理面板
// ─────────────────────────────────────────────────────────────────────────────

function SupplierPanel() {
  const [suppliers, setSuppliers] = useState<SupplierInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [verifying, setVerifying] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', source_type: 'factory', country: 'CN', contact_email: '', has_invoice: false, certifications: '', categories: '' })
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try { setSuppliers(await suppliersApi.list()) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleAdd = async () => {
    setSaving(true)
    try {
      await suppliersApi.create({
        ...form,
        certifications: form.certifications.split(',').map(s => s.trim()).filter(Boolean),
        categories: form.categories.split(',').map(s => s.trim()).filter(Boolean),
      })
      setAdding(false)
      setForm({ name: '', source_type: 'factory', country: 'CN', contact_email: '', has_invoice: false, certifications: '', categories: '' })
      await load()
    } finally { setSaving(false) }
  }

  const handleVerify = async (id: string) => {
    setVerifying(id)
    try { await suppliersApi.verify(id); await load() } finally { setVerifying(null) }
  }

  const riskColors: Record<string, string> = {
    low: 'text-emerald-600', medium: 'text-amber-600', high: 'text-red-500', critical: 'text-red-700', unknown: 'text-gray-400',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={() => setAdding(a => !a)} className="h-9 px-4 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 transition">+ 新增供应商</button>
        <span className="ml-auto text-xs text-gray-400">{suppliers.length} 家供应商</span>
      </div>

      {adding && (
        <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4 space-y-3">
          <p className="text-sm font-semibold text-gray-700">新增供应商</p>
          <div className="grid grid-cols-2 gap-2">
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="供应商名称（必填）" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-400/30 transition"/>
            <input value={form.contact_email} onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))} placeholder="联系邮箱" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
            <select value={form.source_type} onChange={e => setForm(f => ({ ...f, source_type: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none">
              <option value="factory">工厂直采</option><option value="1688">1688 平台</option><option value="platform">其他平台</option><option value="overseas">海外供应商</option>
            </select>
            <select value={form.country} onChange={e => setForm(f => ({ ...f, country: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none">
              <option value="CN">中国</option><option value="US">美国</option><option value="DE">德国</option><option value="JP">日本</option><option value="KR">韩国</option>
            </select>
            <input value={form.certifications} onChange={e => setForm(f => ({ ...f, certifications: e.target.value }))} placeholder="认证（逗号分隔：ISO9001,CE）" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
            <input value={form.categories} onChange={e => setForm(f => ({ ...f, categories: e.target.value }))} placeholder="供应品类 HS 前缀（87,85）" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={form.has_invoice} onChange={e => setForm(f => ({ ...f, has_invoice: e.target.checked }))} className="accent-blue-500"/>
            能开增值税专用发票（影响出口退税资格）
          </label>
          <div className="flex gap-2">
            <button onClick={handleAdd} disabled={saving || !form.name.trim()} className="h-9 px-5 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition flex items-center gap-1.5">{saving ? <><Spinner/>保存中</> : '保存'}</button>
            <button onClick={() => setAdding(false)} className="h-9 px-5 text-sm rounded-xl border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 transition">取消</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12 gap-2 text-gray-400"><Spinner/><span className="text-sm">加载中</span></div>
      ) : suppliers.length === 0 ? (
        <EmptyCard icon="🏭" title="尚无供应商" sub="添加供应商后可触发 AI 资质审核"/>
      ) : (
        <div className="space-y-3">
          {suppliers.map(s => (
            <div key={s.id} className="bg-white rounded-2xl border border-gray-200 p-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-gray-100 flex items-center justify-center text-gray-500 text-lg shrink-0">🏭</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-800">{s.name}</span>
                    <StatusBadge status={s.status}/>
                    {s.has_invoice && <span className="text-[10px] bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded-full border border-emerald-200">可开专票</span>}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-gray-400">
                    <span>{s.country} · {s.source_type}</span>
                    {s.rating > 0 && <span>{'★'.repeat(Math.round(s.rating))}{'☆'.repeat(5 - Math.round(s.rating))} {s.rating.toFixed(1)}</span>}
                    {s.certifications.length > 0 && <span>{s.certifications.slice(0, 3).join(' · ')}</span>}
                    {s.risk_level !== 'unknown' && (
                      <span className={riskColors[s.risk_level] || 'text-gray-400'}>
                        {s.ai_review ? `AI 风险: ${s.risk_level}` : '待 AI 审核'}
                      </span>
                    )}
                  </div>
                  {s.ai_review?.summary && (
                    <p className="mt-1.5 text-xs text-gray-500 bg-gray-50 rounded-lg px-2.5 py-1.5 line-clamp-2">{s.ai_review.summary}</p>
                  )}
                </div>
                <div className="shrink-0">
                  <button onClick={() => handleVerify(s.id)} disabled={verifying === s.id}
                    className="h-7 px-3 text-[11px] font-medium rounded-lg border border-violet-200 bg-violet-50 text-violet-600 hover:bg-violet-100 disabled:opacity-40 transition flex items-center gap-1">
                    {verifying === s.id ? <><Spinner size="xs"/>审核中</> : '✦ AI 审核'}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 合同管理面板
// ─────────────────────────────────────────────────────────────────────────────

function ContractPanel() {
  const [contracts, setContracts] = useState<ContractInfo[]>([])
  const [templates, setTemplates] = useState<ContractTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [showGen, setShowGen] = useState(false)
  const [suppliers, setSuppliers] = useState<SupplierInfo[]>([])
  const [reviewing, setReviewing] = useState<string | null>(null)
  const [form, setForm] = useState({
    template_id: 'purchase_standard', supplier_id: '',
    title: '采购合同', delivery_term: 'FOB', currency: 'USD', total_amount: 0,
    payment_terms: '30%定金，验货合格后支付70%', delivery_date: '',
    vars: {} as Record<string, string>,
  })
  const [saving, setSaving] = useState(false)
  const [expanding, setExpanding] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cs, ts, ss] = await Promise.all([
        contractsApi.list(), contractsApi.listTemplates(), suppliersApi.list(),
      ])
      setContracts(cs); setTemplates(ts); setSuppliers(ss)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const selectedTemplate = templates.find(t => t.id === form.template_id)
  const selectedSupplier = suppliers.find(s => s.id === form.supplier_id)

  const handleGenerate = async () => {
    setSaving(true)
    try {
      const vars = {
        ...form.vars,
        seller_name: selectedSupplier?.name || '',
        delivery_term: form.delivery_term,
        currency: form.currency,
        total_amount: String(form.total_amount),
        payment_terms: form.payment_terms,
        delivery_date: form.delivery_date,
        contract_date: new Date().toISOString().split('T')[0],
      }
      await contractsApi.generate({
        product_id: 'lifecycle', supplier_id: form.supplier_id,
        template_id: form.template_id, title: form.title,
        delivery_term: form.delivery_term, currency: form.currency,
        total_amount: form.total_amount, payment_terms: form.payment_terms,
        delivery_date: form.delivery_date, variables: vars, auto_review: true,
      })
      setShowGen(false)
      await load()
    } finally { setSaving(false) }
  }

  const handleReview = async (id: string) => {
    setReviewing(id)
    try { await contractsApi.review(id); await load() } finally { setReviewing(null) }
  }

  const handleSign = async (id: string) => {
    await contractsApi.sign(id); await load()
  }

  const incotermInfo = INCOTERM_RISK[form.delivery_term]

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={() => setShowGen(g => !g)} className="h-9 px-4 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 transition">+ 生成合同</button>
        <span className="ml-auto text-xs text-gray-400">{contracts.length} 份合同</span>
      </div>

      {showGen && (
        <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4 space-y-3">
          <p className="text-sm font-semibold text-gray-700">生成合同（Jinja2 模板 + AI 合规审查）</p>
          <div className="grid grid-cols-2 gap-2">
            <select value={form.template_id} onChange={e => setForm(f => ({ ...f, template_id: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none">
              {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <select value={form.supplier_id} onChange={e => setForm(f => ({ ...f, supplier_id: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none">
              <option value="">选择供应商…</option>
              {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="合同标题" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
            <select value={form.delivery_term} onChange={e => setForm(f => ({ ...f, delivery_term: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none">
              {INCOTERMS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <input type="number" value={form.total_amount} onChange={e => setForm(f => ({ ...f, total_amount: +e.target.value }))} placeholder="合同金额（USD）" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
            <input type="date" value={form.delivery_date} onChange={e => setForm(f => ({ ...f, delivery_date: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
          </div>

          {/* 贸易术语风险提示 */}
          {incotermInfo?.warn && (
            <div className="flex items-start gap-2 rounded-xl bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700">
              <span className="shrink-0">⚠️</span>
              <span><strong>{form.delivery_term}</strong> 风险提示：{incotermInfo.warn}</span>
            </div>
          )}
          {incotermInfo && (
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
              <div className="bg-white rounded-lg px-3 py-2 border border-gray-100"><span className="font-medium">买方责任</span>：{incotermInfo.buyer}</div>
              <div className="bg-white rounded-lg px-3 py-2 border border-gray-100"><span className="font-medium">卖方责任</span>：{incotermInfo.seller}</div>
            </div>
          )}

          {/* 模板必填变量 */}
          {selectedTemplate?.variables.filter(v => v.required && !['seller_name','delivery_term','currency','total_amount','payment_terms','delivery_date','contract_date'].includes(v.key)).map(v => (
            <input key={v.key} value={form.vars[v.key] || ''} onChange={e => setForm(f => ({ ...f, vars: { ...f.vars, [v.key]: e.target.value } }))}
              placeholder={`${v.label}${v.required ? ' *' : ''}`}
              className="w-full h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-400/30 transition"/>
          ))}

          <div className="flex gap-2">
            <button onClick={handleGenerate} disabled={saving || !form.supplier_id || !form.total_amount}
              className="h-9 px-5 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition flex items-center gap-1.5">
              {saving ? <><Spinner/>生成中</> : '生成合同 + AI 审查'}
            </button>
            <button onClick={() => setShowGen(false)} className="h-9 px-5 text-sm rounded-xl border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 transition">取消</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12 gap-2 text-gray-400"><Spinner/><span className="text-sm">加载中</span></div>
      ) : contracts.length === 0 ? (
        <EmptyCard icon="📄" title="尚无合同" sub="点击「生成合同」选择模板自动生成，含 AI 合规审查"/>
      ) : (
        <div className="space-y-2">
          {contracts.map(c => (
            <div key={c.id} className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition"
                onClick={() => setExpanding(expanding === c.id ? null : c.id)}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-800">{c.title}</span>
                    <StatusBadge status={c.status}/>
                    <span className="text-[10px] text-gray-400">v{c.version}</span>
                    {c.compliance_score > 0 && (
                      <span className={cx('text-[10px] font-semibold px-1.5 py-0.5 rounded-full',
                        c.compliance_score >= 80 ? 'bg-emerald-50 text-emerald-600' : c.compliance_score >= 60 ? 'bg-amber-50 text-amber-600' : 'bg-red-50 text-red-500')}>
                        合规 {c.compliance_score}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
                    <span>{c.delivery_term} · {c.currency} {c.total_amount.toLocaleString()}</span>
                    {c.delivery_date && <span>交货 {c.delivery_date}</span>}
                    {c.compliance_issues.length > 0 && (
                      <span className="text-amber-600">{c.compliance_issues.length} 个合规问题</span>
                    )}
                  </div>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  {c.status === 'draft' && (
                    <>
                      <button onClick={e => { e.stopPropagation(); handleReview(c.id) }} disabled={reviewing === c.id}
                        className="h-7 px-2.5 text-[11px] rounded-lg border border-violet-200 bg-violet-50 text-violet-600 hover:bg-violet-100 disabled:opacity-40 transition flex items-center gap-1">
                        {reviewing === c.id ? <Spinner/> : '✦ 审查'}
                      </button>
                      <button onClick={e => { e.stopPropagation(); handleSign(c.id) }}
                        className="h-7 px-2.5 text-[11px] rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-600 hover:bg-emerald-100 transition">
                        签署
                      </button>
                    </>
                  )}
                  <span className="text-gray-400 text-sm">{expanding === c.id ? '▲' : '▼'}</span>
                </div>
              </div>

              {expanding === c.id && (
                <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/50 space-y-3">
                  {/* 合规问题 */}
                  {c.compliance_issues.length > 0 && (
                    <div>
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-2">合规问题</p>
                      {c.compliance_issues.slice(0, 5).map((issue: any, i) => (
                        <div key={i} className={cx('flex items-start gap-2 rounded-xl px-3 py-2 mb-1.5 text-xs',
                          issue.level === 'error' || issue.level === 'critical' ? 'bg-red-50 border border-red-100 text-red-700' :
                          issue.level === 'warning' ? 'bg-amber-50 border border-amber-100 text-amber-700' :
                          'bg-gray-50 border border-gray-100 text-gray-600')}>
                          <span className="shrink-0">{issue.level === 'error' || issue.level === 'critical' ? '❌' : issue.level === 'warning' ? '⚠️' : 'ℹ️'}</span>
                          <div><p className="font-medium">{issue.message}</p>{issue.recommendation && <p className="text-[11px] mt-0.5 opacity-80">建议：{issue.recommendation}</p>}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  {/* 合同正文预览 */}
                  {c.content_html && (
                    <div>
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-2">合同预览</p>
                      <div className="max-h-48 overflow-y-auto rounded-xl bg-white border border-gray-100 px-3 py-2 text-xs text-gray-600 leading-relaxed"
                        dangerouslySetInnerHTML={{ __html: c.content_html }} />
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 支付通道面板
// ─────────────────────────────────────────────────────────────────────────────

function PaymentPanel() {
  const [channels, setChannels] = useState<PaymentChannel[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [testing, setTesting] = useState<string | null>(null)
  const [form, setForm] = useState({ provider: 'stripe', webhook_url: '', test_mode: true })
  const [dutyCalc, setDutyCalc] = useState({ hs_code: '8703', dest_country: 'US', value: 10000 })
  const [dutyResult, setDutyResult] = useState<any>(null)
  const [calcLoading, setCalcLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try { setChannels(await paymentChannelsApi.list()) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleAdd = async () => {
    await paymentChannelsApi.create(form); setAdding(false); await load()
  }

  const handleTest = async (id: string) => {
    setTesting(id)
    try { await paymentChannelsApi.test(id); await load() } finally { setTesting(null) }
  }

  const handleCalcDuty = async () => {
    setCalcLoading(true)
    try {
      const r = await customsApi.calculateDuty({ hs_code: dutyCalc.hs_code, dest_country: dutyCalc.dest_country, declared_value: dutyCalc.value })
      setDutyResult(r)
    } finally { setCalcLoading(false) }
  }

  return (
    <div className="space-y-4">
      {/* 关税计算器 */}
      <div className="rounded-2xl border border-amber-100 bg-amber-50/40 p-4">
        <p className="text-xs font-bold text-amber-600 uppercase tracking-wide mb-3">快速关税计算器</p>
        <div className="flex gap-2 flex-wrap">
          <input value={dutyCalc.hs_code} onChange={e => setDutyCalc(d => ({ ...d, hs_code: e.target.value }))} placeholder="HS 编码（如 8703）" className="h-8 px-3 text-xs bg-white rounded-lg border border-gray-200 focus:outline-none w-32"/>
          <input value={dutyCalc.dest_country} onChange={e => setDutyCalc(d => ({ ...d, dest_country: e.target.value }))} placeholder="目的国（US/EU/UK）" className="h-8 px-3 text-xs bg-white rounded-lg border border-gray-200 focus:outline-none w-28"/>
          <input type="number" value={dutyCalc.value} onChange={e => setDutyCalc(d => ({ ...d, value: +e.target.value }))} placeholder="申报价值（USD）" className="h-8 px-3 text-xs bg-white rounded-lg border border-gray-200 focus:outline-none w-32"/>
          <button onClick={handleCalcDuty} disabled={calcLoading} className="h-8 px-4 text-xs font-semibold rounded-lg bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-40 transition flex items-center gap-1">{calcLoading ? <Spinner/> : '计算关税'}</button>
        </div>
        {dutyResult && (
          <div className="mt-3 grid grid-cols-3 gap-2">
            <div className="bg-white rounded-lg px-3 py-2 text-center border border-gray-100">
              <p className="text-lg font-bold text-amber-600">{dutyResult.duty_rate_pct}%</p>
              <p className="text-[10px] text-gray-400">税率</p>
            </div>
            <div className="bg-white rounded-lg px-3 py-2 text-center border border-gray-100">
              <p className="text-lg font-bold text-gray-800">${dutyResult.calculated_duty.toLocaleString()}</p>
              <p className="text-[10px] text-gray-400">应缴关税</p>
            </div>
            <div className={cx('rounded-lg px-3 py-2 text-center border', dutyResult.ioss_applicable ? 'bg-orange-50 border-orange-200' : 'bg-emerald-50 border-emerald-200')}>
              <p className={cx('text-sm font-bold', dutyResult.ioss_applicable ? 'text-orange-600' : 'text-emerald-600')}>{dutyResult.ioss_applicable ? '需要 IOSS' : 'IOSS 无需'}</p>
              <p className="text-[10px] text-gray-400">欧盟 VAT</p>
            </div>
          </div>
        )}
        {dutyResult?.ioss_tip && <p className="mt-2 text-xs text-orange-600 bg-orange-50 rounded-lg px-3 py-2">⚠️ {dutyResult.ioss_tip}</p>}
      </div>

      {/* 支付通道列表 */}
      <div className="flex items-center gap-2">
        <button onClick={() => setAdding(a => !a)} className="h-9 px-4 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 transition">+ 配置支付通道</button>
        <span className="ml-auto text-xs text-gray-400">{channels.length} 个通道</span>
      </div>

      {adding && (
        <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4 space-y-3">
          <div className="flex gap-2">
            <select value={form.provider} onChange={e => setForm(f => ({ ...f, provider: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none flex-1">
              {Object.entries(PROVIDER_META).map(([k, v]) => <option key={k} value={k}>{v.icon} {k}</option>)}
            </select>
            <input value={form.webhook_url} onChange={e => setForm(f => ({ ...f, webhook_url: e.target.value }))} placeholder="Webhook URL" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 flex-1 focus:outline-none"/>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={form.test_mode} onChange={e => setForm(f => ({ ...f, test_mode: e.target.checked }))} className="accent-blue-500"/>测试模式
          </label>
          {PROVIDER_META[form.provider] && (
            <p className="text-xs text-gray-500 bg-white rounded-lg px-3 py-2 border border-gray-100">{PROVIDER_META[form.provider].icon} {PROVIDER_META[form.provider].desc}</p>
          )}
          <div className="flex gap-2">
            <button onClick={handleAdd} className="h-9 px-5 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 transition">配置</button>
            <button onClick={() => setAdding(false)} className="h-9 px-5 text-sm rounded-xl border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 transition">取消</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12 gap-2 text-gray-400"><Spinner/><span className="text-sm">加载中</span></div>
      ) : channels.length === 0 ? (
        <EmptyCard icon="💳" title="尚未配置支付通道" sub="支持 Stripe / PayPal / 连连支付 / 万里汇"/>
      ) : (
        <div className="space-y-2">
          {channels.map(c => {
            const meta = PROVIDER_META[c.provider] || { icon: '💳', color: 'text-gray-600', desc: '' }
            return (
              <div key={c.id} className="bg-white rounded-2xl border border-gray-200 p-4">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{meta.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={cx('text-sm font-semibold', meta.color)}>{c.display_name}</span>
                      <StatusBadge status={c.status}/>
                      {c.test_mode && <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">测试模式</span>}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-400">
                      {c.kyc_verified ? <span className="text-emerald-600">✓ KYC 已验证</span> : <span className="text-amber-600">⚠ KYC 待验证</span>}
                      {c.pci_dss ? <span className="text-emerald-600">✓ PCI DSS</span> : <span className="text-gray-400">PCI 未知</span>}
                      <span>拒付率 {c.chargeback_rate.toFixed(2)}% / 阈值 {c.chargeback_limit}%</span>
                    </div>
                    {/* 合规问题提示 */}
                    {c.compliance_notes.filter(n => n.level === 'error').map((n, i) => (
                      <div key={i} className="mt-1.5 flex items-start gap-1.5 rounded-lg bg-red-50 border border-red-100 px-2.5 py-1.5 text-[11px] text-red-700">
                        <span>❌</span><span>{n.message}</span>
                      </div>
                    ))}
                    {c.compliance_notes.filter(n => n.level === 'warning').slice(0, 1).map((n, i) => (
                      <div key={i} className="mt-1.5 flex items-start gap-1.5 rounded-lg bg-amber-50 border border-amber-100 px-2.5 py-1.5 text-[11px] text-amber-700">
                        <span>⚠️</span><span>{n.message}</span>
                      </div>
                    ))}
                  </div>
                  <button onClick={() => handleTest(c.id)} disabled={testing === c.id}
                    className="h-7 px-2.5 text-[11px] rounded-lg border border-gray-200 text-gray-500 hover:border-blue-300 hover:text-blue-500 disabled:opacity-40 transition flex items-center gap-1">
                    {testing === c.id ? <Spinner/> : '测试'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 物流报关面板
// ─────────────────────────────────────────────────────────────────────────────

function LogisticsPanel() {
  const [shipments, setShipments] = useState<LogisticsOrder[]>([])
  const [declarations, setDeclarations] = useState<CustomsDeclaration[]>([])
  const [carriers, setCarriers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [activeSection, setActiveSection] = useState<'shipments' | 'customs'>('shipments')
  const [addingShipment, setAddingShipment] = useState(false)
  const [addingDecl, setAddingDecl] = useState(false)
  const [shipForm, setShipForm] = useState({ carrier: 'dhl', dest_country: '', tracking_number: '', incoterm: 'FOB', freight_cost: 0 })
  const [declForm, setDeclForm] = useState({ hs_code: '', declared_name: '', declared_value: 0, dest_country: '', quantity: 1, mode: '9610' })
  const [refreshing, setRefreshing] = useState<string | null>(null)
  const [checkingDecl, setCheckingDecl] = useState<string | null>(null)
  const [expandTracking, setExpandTracking] = useState<string | null>(null)
  const [trackingData, setTrackingData] = useState<Record<string, any>>({})

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, d, c] = await Promise.all([
        logisticsApi.listShipments(), customsApi.list(), logisticsApi.listCarriers(),
      ])
      setShipments(s); setDeclarations(d); setCarriers(c)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleRefresh = async (id: string) => {
    setRefreshing(id)
    try { await logisticsApi.refreshTracking(id); await load() } finally { setRefreshing(null) }
  }

  const handleViewTracking = async (id: string) => {
    if (expandTracking === id) { setExpandTracking(null); return }
    setExpandTracking(id)
    if (!trackingData[id]) {
      try { const data = await logisticsApi.getTracking(id); setTrackingData(t => ({ ...t, [id]: data })) }
      catch { setTrackingData(t => ({ ...t, [id]: null })) }
    }
  }

  const handleCheckDecl = async (id: string) => {
    setCheckingDecl(id)
    try { await customsApi.check(id); await load() } finally { setCheckingDecl(null) }
  }

  const handleSubmitDecl = async (id: string) => { await customsApi.submit(id); await load() }

  const STATUS_ICONS: Record<string, string> = {
    pending: '⏳', picked_up: '📦', in_transit: '🚢', customs_export: '📋',
    customs_import: '🛃', out_for_delivery: '🚚', delivered: '✅', exception: '❌',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
        <button onClick={() => setActiveSection('shipments')} className={cx('flex-1 h-8 text-sm font-medium rounded-lg transition', activeSection === 'shipments' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700')}>物流单 ({shipments.length})</button>
        <button onClick={() => setActiveSection('customs')} className={cx('flex-1 h-8 text-sm font-medium rounded-lg transition', activeSection === 'customs' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700')}>报关单 ({declarations.length})</button>
      </div>

      {activeSection === 'shipments' ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <button onClick={() => setAddingShipment(a => !a)} className="h-9 px-4 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 transition">+ 创建物流单</button>
          </div>

          {addingShipment && (
            <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4 space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <select value={shipForm.carrier} onChange={e => setShipForm(f => ({ ...f, carrier: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none">
                  {carriers.map(c => <option key={c.code} value={c.code}>{c.name}</option>)}
                </select>
                <input value={shipForm.dest_country} onChange={e => setShipForm(f => ({ ...f, dest_country: e.target.value }))} placeholder="目的国（US/DE/UK）" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
                <input value={shipForm.tracking_number} onChange={e => setShipForm(f => ({ ...f, tracking_number: e.target.value }))} placeholder="运单号" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
                <select value={shipForm.incoterm} onChange={e => setShipForm(f => ({ ...f, incoterm: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none">
                  {INCOTERMS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="flex gap-2">
                <button onClick={async () => { await logisticsApi.createShipment({ ...shipForm, product_id: 'lifecycle' }); setAddingShipment(false); await load() }}
                  disabled={!shipForm.dest_country} className="h-9 px-5 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition">创建</button>
                <button onClick={() => setAddingShipment(false)} className="h-9 px-5 text-sm rounded-xl border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 transition">取消</button>
              </div>
            </div>
          )}

          {loading ? <div className="flex items-center justify-center py-10 gap-2 text-gray-400"><Spinner/></div>
          : shipments.length === 0 ? <EmptyCard icon="🚢" title="尚无物流单" sub="创建物流单后可追踪运输轨迹"/>
          : shipments.map(s => (
            <div key={s.id} className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition"
                onClick={() => handleViewTracking(s.id)}>
                <span className="text-xl">{STATUS_ICONS[s.status] || '📦'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-700">{s.carrier.toUpperCase()} · {s.tracking_number || '待填运单号'}</span>
                    <StatusBadge status={s.status}/>
                    <span className="text-xs text-gray-400">{s.incoterm}</span>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">CN → {s.dest_country}{s.estimated_delivery ? ` · 预计 ${s.estimated_delivery}` : ''}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={e => { e.stopPropagation(); handleRefresh(s.id) }} disabled={refreshing === s.id}
                    className="h-7 px-2.5 text-[11px] rounded-lg border border-gray-200 text-gray-400 hover:text-blue-500 hover:border-blue-300 disabled:opacity-40 transition flex items-center gap-1">
                    {refreshing === s.id ? <Spinner/> : '刷新'}
                  </button>
                  <span className="text-gray-400 text-sm">{expandTracking === s.id ? '▲' : '▼'}</span>
                </div>
              </div>
              {expandTracking === s.id && trackingData[s.id] && (
                <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-3">
                  {trackingData[s.id].events?.length > 0 ? (
                    <div className="space-y-2">
                      {trackingData[s.id].events.slice(0, 6).map((e: any, i: number) => (
                        <div key={i} className="flex items-start gap-3 text-xs">
                          <span className="text-gray-300 shrink-0 w-28">{e.timestamp?.slice(0, 16).replace('T', ' ')}</span>
                          <span className="text-gray-500">{e.location && `[${e.location}] `}{e.description}</span>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-xs text-gray-400">暂无轨迹事件，请刷新获取最新状态</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <button onClick={() => setAddingDecl(a => !a)} className="h-9 px-4 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 transition">+ 生成报关单</button>
          </div>

          {addingDecl && (
            <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4 space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <input value={declForm.hs_code} onChange={e => setDeclForm(f => ({ ...f, hs_code: e.target.value }))} placeholder="HS 编码（8 位）" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
                <input value={declForm.declared_name} onChange={e => setDeclForm(f => ({ ...f, declared_name: e.target.value }))} placeholder="申报品名" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
                <input type="number" value={declForm.declared_value} onChange={e => setDeclForm(f => ({ ...f, declared_value: +e.target.value }))} placeholder="申报价值（USD）" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
                <input value={declForm.dest_country} onChange={e => setDeclForm(f => ({ ...f, dest_country: e.target.value }))} placeholder="目的国（US/DE/UK）" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
                <select value={declForm.mode} onChange={e => setDeclForm(f => ({ ...f, mode: e.target.value }))} className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none">
                  <option value="9610">9610 跨境电商 B2C</option>
                  <option value="一般贸易">一般贸易</option>
                  <option value="保税备货">保税备货</option>
                </select>
                <input type="number" value={declForm.quantity} onChange={e => setDeclForm(f => ({ ...f, quantity: +e.target.value }))} placeholder="数量" className="h-9 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none transition"/>
              </div>
              <div className="flex gap-2">
                <button onClick={async () => { await customsApi.create({ ...declForm, product_id: 'lifecycle', documents: ['invoice','packing_list'] }); setAddingDecl(false); await load() }}
                  disabled={!declForm.hs_code || !declForm.dest_country} className="h-9 px-5 text-sm font-semibold rounded-xl bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition">生成 + 合规检查</button>
                <button onClick={() => setAddingDecl(false)} className="h-9 px-5 text-sm rounded-xl border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 transition">取消</button>
              </div>
            </div>
          )}

          {loading ? <div className="flex items-center justify-center py-10 gap-2 text-gray-400"><Spinner/></div>
          : declarations.length === 0 ? <EmptyCard icon="📋" title="尚无报关单" sub="生成报关单后自动计算关税并执行 AI 合规检查"/>
          : declarations.map(d => {
            const errorChecks = (d.compliance_checks || []).filter((c: any) => c.level === 'error')
            const passChecks = (d.compliance_checks || []).filter((c: any) => c.level === 'pass')
            return (
              <div key={d.id} className="bg-white rounded-2xl border border-gray-200 p-4">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">📋</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-gray-800">{d.declared_name}</span>
                      <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">HS {d.hs_code}</span>
                      <StatusBadge status={d.status}/>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-gray-400">
                      <span>CN → {d.dest_country}</span>
                      <span>申报 ${d.declared_value.toLocaleString()}</span>
                      <span className="text-amber-600 font-medium">关税 {d.duty_rate}% = ${d.calculated_duty.toLocaleString()}</span>
                      {d.vat_applicable && <span className="text-orange-600 font-medium">⚠ 需要 IOSS</span>}
                    </div>
                    {/* 合规检查结果 */}
                    {errorChecks.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {errorChecks.map((c: any, i: number) => (
                          <div key={i} className="flex items-start gap-1.5 rounded-lg bg-red-50 border border-red-100 px-2.5 py-1.5 text-[11px] text-red-700">
                            <span>❌</span><span>{c.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {passChecks.length > 0 && errorChecks.length === 0 && (
                      <p className="mt-1.5 text-[11px] text-emerald-600">✅ {passChecks.length} 项合规检查通过</p>
                    )}
                  </div>
                  <div className="shrink-0 flex flex-col gap-1.5 items-end">
                    <button onClick={() => handleCheckDecl(d.id)} disabled={checkingDecl === d.id}
                      className="h-7 px-2.5 text-[11px] rounded-lg border border-violet-200 bg-violet-50 text-violet-600 hover:bg-violet-100 disabled:opacity-40 transition flex items-center gap-1">
                      {checkingDecl === d.id ? <Spinner/> : '✦ 检查'}
                    </button>
                    {d.status === 'draft' && (
                      <button onClick={() => handleSubmitDecl(d.id)} className="h-7 px-2.5 text-[11px] rounded-lg border border-blue-200 bg-blue-50 text-blue-600 hover:bg-blue-100 transition">提交</button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 主页面
// ─────────────────────────────────────────────────────────────────────────────

type Tab = 'supplier' | 'contract' | 'payment' | 'logistics'

const TABS: { key: Tab; label: string; icon: string; desc: string; stage: string }[] = [
  { key: 'supplier',  label: '供应商',  icon: '🏭', desc: '审核 · 评分 · 选品来源',  stage: '阶段 2-3' },
  { key: 'contract',  label: '合同管理', icon: '📄', desc: '生成 · AI 合规审查 · 签署', stage: '阶段 3' },
  { key: 'payment',   label: '支付通道', icon: '💳', desc: '网关配置 · 关税计算 · 合规', stage: '阶段 5' },
  { key: 'logistics', label: '物流报关', icon: '🚢', desc: '物流追踪 · 报关单 · 清关',  stage: '阶段 6-8' },
]

export default function ProductLifecyclePage() {
  const [tab, setTab] = useState<Tab>('supplier')

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50/40">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* 页头 */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">产品出海生命周期管理</h1>
          <p className="text-sm text-gray-400 mt-1">
            选品采购 · 供应商审核 · 合同生成 · 支付通道 · 物流报关 — 全流程合规管理
          </p>
        </div>

        {/* 生命周期进度条 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-4">
          <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-3">产品出海生命周期（8 阶段）</p>
          <div className="flex items-center gap-0">
            {LIFECYCLE_STAGES.map((s, i) => (
              <div key={s.key} className="flex-1 flex flex-col items-center gap-1">
                <div className="flex items-center w-full">
                  {i > 0 && <div className="flex-1 h-0.5 bg-gray-200"/>}
                  <div className={cx('w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0',
                    i < 3 ? 'bg-blue-500 text-white' : i === 3 ? 'bg-blue-200 text-blue-700' : 'bg-gray-100 text-gray-400')}>
                    {s.step}
                  </div>
                  {i < LIFECYCLE_STAGES.length - 1 && <div className="flex-1 h-0.5 bg-gray-200"/>}
                </div>
                <span className="text-[10px] font-medium text-gray-500">{s.label}</span>
                <span className="text-[9px] text-gray-400 text-center leading-tight">{s.desc}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-3 text-[11px] text-gray-400">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block"/><span>当前阶段（sourcing）</span></span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-blue-200 inline-block"/><span>即将进入</span></span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-gray-100 inline-block"/><span>待解锁</span></span>
          </div>
        </div>

        {/* 四大业务域 Tab */}
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          {/* Tab 导航 */}
          <div className="grid grid-cols-4 border-b border-gray-100">
            {TABS.map(t => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={cx('flex flex-col items-center gap-0.5 py-3.5 px-2 text-center transition border-b-2',
                  tab === t.key ? 'border-blue-500 bg-blue-50/40' : 'border-transparent hover:bg-gray-50')}>
                <span className="text-xl">{t.icon}</span>
                <span className={cx('text-xs font-semibold', tab === t.key ? 'text-blue-600' : 'text-gray-600')}>{t.label}</span>
                <span className="text-[10px] text-gray-400 hidden sm:block">{t.desc}</span>
                <span className="text-[9px] bg-gray-100 text-gray-400 px-1.5 py-0.5 rounded-full mt-0.5">{t.stage}</span>
              </button>
            ))}
          </div>

          {/* Tab 内容 */}
          <div className="p-5">
            {tab === 'supplier'  && <SupplierPanel/>}
            {tab === 'contract'  && <ContractPanel/>}
            {tab === 'payment'   && <PaymentPanel/>}
            {tab === 'logistics' && <LogisticsPanel/>}
          </div>
        </div>

      </div>
    </div>
  )
}
