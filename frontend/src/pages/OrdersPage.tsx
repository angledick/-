/**
 * 销售订单管理 — 对接 /api/v1/orders
 *
 * 功能：
 *  - 订单列表（platform/status 筛选）
 *  - 创建订单（手动/Shopify）
 *  - 订单详情 + 支付记录
 *  - 三单一致性检查
 */
import { useState, useEffect, useCallback } from 'react'
import { ordersApi, type SalesOrder, type ConsistencyCheckResult, type PaymentRecord } from '../api/config'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import {
  Package, Plus, RefreshCw, Search, ShoppingCart, CheckCircle2, AlertCircle, Loader2,
} from 'lucide-react'

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending:    { label: '待处理',  color: 'border-amber-200 bg-amber-50 text-amber-700' },
  paid:       { label: '已支付',  color: 'border-blue-200 bg-blue-50 text-blue-700' },
  fulfilled:  { label: '已发货',  color: 'border-purple-200 bg-purple-50 text-purple-700' },
  completed:  { label: '已完成',  color: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  cancelled:  { label: '已取消',  color: 'border-rose-200 bg-rose-50 text-rose-700' },
  refunded:   { label: '已退款',  color: 'border-gray-200 bg-gray-50 text-gray-700' },
}

const PLATFORM_LABELS: Record<string, string> = {
  shopify: 'Shopify', manual: '手动录入', amazon: 'Amazon', temu: 'Temu',
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<SalesOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [platformFilter, setPlatformFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedOrder, setSelectedOrder] = useState<SalesOrder | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [consistencyResult, setConsistencyResult] = useState<ConsistencyCheckResult | null>(null)
  const [checkingConsistency, setCheckingConsistency] = useState(false)
  const [payments, setPayments] = useState<PaymentRecord[]>([])
  const [paymentSummary, setPaymentSummary] = useState<{ total_paid: number; total_refunded: number; count: number } | null>(null)
  const [showAddPayment, setShowAddPayment] = useState(false)
  const [addingPayment, setAddingPayment] = useState(false)
  const [newPayment, setNewPayment] = useState({ amount: 0, currency: 'USD', status: 'completed', payer_name: '', notes: '' })

  const loadOrders = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (platformFilter !== 'all') params.platform = platformFilter
      if (statusFilter !== 'all') params.status = statusFilter
      const data = await ordersApi.list(params)
      setOrders(Array.isArray(data) ? data : [])
    } catch (e) {
      toast.error('加载订单失败')
      setOrders([])
    } finally {
      setLoading(false)
    }
  }, [platformFilter, statusFilter])

  useEffect(() => { loadOrders() }, [loadOrders])

  const filtered = orders.filter(o => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      o.buyer_name?.toLowerCase().includes(q) ||
      o.id?.toLowerCase().includes(q) ||
      o.platform_order_id?.toLowerCase().includes(q)
    )
  })

  const loadPayments = useCallback(async (orderId: string) => {
    try {
      const data = await ordersApi.getPayments(orderId)
      setPayments(data.payments || [])
      setPaymentSummary(data.summary || null)
    } catch {
      setPayments([])
      setPaymentSummary(null)
    }
  }, [])

  const handleOpenDetail = (order: SalesOrder) => {
    setSelectedOrder(order)
    setConsistencyResult(null)
    setShowAddPayment(false)
    loadPayments(order.id)
  }

  const handleAddPayment = async () => {
    if (!selectedOrder || newPayment.amount <= 0) { toast.error('请输入有效金额'); return }
    setAddingPayment(true)
    try {
      await ordersApi.addPayment(selectedOrder.id, {
        amount: newPayment.amount,
        currency: newPayment.currency,
        status: newPayment.status,
        payer_name: newPayment.payer_name,
        notes: newPayment.notes,
      })
      toast.success('支付记录已添加')
      setNewPayment({ amount: 0, currency: 'USD', status: 'completed', payer_name: '', notes: '' })
      setShowAddPayment(false)
      loadPayments(selectedOrder.id)
    } catch {
      toast.error('添加支付记录失败')
    } finally {
      setAddingPayment(false)
    }
  }

  const handleConsistencyCheck = async (orderId: string) => {
    setCheckingConsistency(true)
    try {
      const result = await ordersApi.consistencyCheck(orderId)
      setConsistencyResult(result)
      toast.success('三单一致性检查完成')
    } catch (e) {
      toast.error('一致性检查失败')
    } finally {
      setCheckingConsistency(false)
    }
  }

  const totalAmount = filtered.reduce((sum, o) => sum + (o.total_amount || 0), 0)

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-[1400px] px-6 py-7 sm:px-8">
          <div className="flex items-end justify-between">
            <div>
              <h1 className="text-[28px] font-semibold tracking-tight">销售订单</h1>
              <p className="mt-1 text-[14px] text-muted-foreground">
                管理销售订单、支付记录与三单一致性检查
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="h-9 text-[13px]" onClick={loadOrders} disabled={loading}>
                <RefreshCw className={loading ? 'mr-2 size-4 animate-spin' : 'mr-2 size-4'} />
                刷新
              </Button>
              <Button className="h-9 text-[13px]" onClick={() => setShowCreate(true)}>
                <Plus className="mr-2 size-4" />
                新建订单
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] space-y-4 px-6 py-6 sm:px-8">
        {/* 汇总卡片 */}
        <div className="grid gap-3 sm:grid-cols-3">
          <SummaryCard label="订单总数" value={filtered.length} icon={ShoppingCart} />
          <SummaryCard label="订单总额" value={`$${totalAmount.toFixed(2)}`} icon={Package} />
          <SummaryCard label="待处理" value={filtered.filter(o => o.status === 'pending').length} icon={AlertCircle} />
        </div>

        {/* 筛选栏 */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索买家、订单号..."
              className="h-9 pl-9"
            />
          </div>
          {['all', 'shopify', 'manual', 'amazon'].map(p => (
            <button
              key={p}
              onClick={() => setPlatformFilter(p)}
              className={`h-9 rounded-md border px-3 text-[12px] font-medium transition-colors ${
                platformFilter === p ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card hover:bg-muted/50'
              }`}
            >
              {p === 'all' ? '全部来源' : (PLATFORM_LABELS[p] || p)}
            </button>
          ))}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-md border border-border bg-card px-3 text-[12px]"
          >
            <option value="all">全部状态</option>
            {Object.entries(STATUS_CONFIG).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
        </div>

        {/* 订单表格 */}
        <div className="overflow-hidden rounded-lg border border-border/60 bg-card shadow-sm">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="mr-2 size-5 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">加载订单...</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center">
              <Package className="mx-auto mb-3 size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">暂无订单数据</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px]">
                <thead>
                  <tr className="border-b border-border/50 bg-muted/30">
                    <th className="px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">订单号</th>
                    <th className="px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">买家</th>
                    <th className="px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">来源</th>
                    <th className="px-4 py-3 text-right text-[12px] font-semibold text-muted-foreground">金额</th>
                    <th className="px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">状态</th>
                    <th className="px-4 py-3 text-left text-[12px] font-semibold text-muted-foreground">创建时间</th>
                    <th className="px-4 py-3 text-right text-[12px] font-semibold text-muted-foreground">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/45">
                  {filtered.map((order) => {
                    const sc = STATUS_CONFIG[order.status] || { label: order.status, color: 'border-gray-200 bg-gray-50 text-gray-700' }
                    return (
                      <tr key={order.id} className="bg-card transition-colors hover:bg-muted/25">
                        <td className="px-4 py-3 text-[13px] font-medium text-foreground">
                          {order.platform_order_id || order.id.slice(0, 12)}
                        </td>
                        <td className="px-4 py-3 text-[13px] text-muted-foreground">
                          {order.buyer_name}
                          {order.buyer_address?.country && (
                            <span className="ml-1 text-[11px] text-muted-foreground/70">{order.buyer_address.country}</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="outline" className="text-[10px]">
                            {PLATFORM_LABELS[order.platform] || order.platform}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-right text-[13px] font-semibold">
                          {order.currency} {(order.total_amount || 0).toFixed(2)}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium ${sc.color}`}>
                            {sc.label}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-[12px] text-muted-foreground">
                          {new Date(order.created_at).toLocaleDateString('zh-CN')}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-[12px]"
                            onClick={() => handleOpenDetail(order)}
                          >
                            详情
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* 订单详情弹窗 */}
      <Dialog open={!!selectedOrder} onOpenChange={(v) => !v && setSelectedOrder(null)}>
        <DialogContent className="max-w-[720px]">
          <DialogHeader>
            <DialogTitle>订单详情 — {selectedOrder?.platform_order_id || selectedOrder?.id.slice(0, 12)}</DialogTitle>
          </DialogHeader>
          {selectedOrder && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <DetailItem label="买家" value={selectedOrder.buyer_name} />
                <DetailItem label="邮箱" value={selectedOrder.buyer_email || '—'} />
                <DetailItem label="国家" value={selectedOrder.buyer_address?.country || '—'} />
                <DetailItem label="城市" value={selectedOrder.buyer_address?.city || '—'} />
                <DetailItem label="金额" value={`${selectedOrder.currency} ${(selectedOrder.total_amount || 0).toFixed(2)}`} />
                <DetailItem label="状态" value={STATUS_CONFIG[selectedOrder.status]?.label || selectedOrder.status} />
              </div>

              {/* 商品明细 */}
              {selectedOrder.items?.length > 0 && (
                <div>
                  <p className="mb-2 text-[13px] font-semibold">商品明细</p>
                  <div className="rounded-md border border-border/60">
                    {selectedOrder.items.map((item, i) => (
                      <div key={i} className="flex items-center justify-between border-b border-border/40 px-3 py-2 last:border-0">
                        <div>
                          <p className="text-[13px] font-medium">{item.name}</p>
                          {item.sku && <p className="text-[11px] text-muted-foreground">SKU: {item.sku}</p>}
                        </div>
                        <div className="text-right text-[12px]">
                          <p>{item.qty} × {item.unit_price.toFixed(2)}</p>
                          <p className="font-semibold">{(item.qty * item.unit_price).toFixed(2)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 支付记录 */}
              <div className="rounded-md border border-border/60">
                <div className="flex items-center justify-between border-b border-border/40 px-3 py-2">
                  <p className="text-[13px] font-semibold">支付记录</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-[12px]"
                    onClick={() => setShowAddPayment(!showAddPayment)}
                  >
                    <Plus className="mr-1 size-3" />
                    {showAddPayment ? '取消' : '添加'}
                  </Button>
                </div>
                {showAddPayment && (
                  <div className="space-y-2 border-b border-border/40 px-3 py-2.5">
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="text-[11px] text-muted-foreground">金额 *</label>
                        <Input type="number" value={newPayment.amount} onChange={(e) => setNewPayment(p => ({ ...p, amount: Number(e.target.value) }))} className="h-8 text-[13px]" />
                      </div>
                      <div>
                        <label className="text-[11px] text-muted-foreground">币种</label>
                        <select value={newPayment.currency} onChange={(e) => setNewPayment(p => ({ ...p, currency: e.target.value }))} className="h-8 w-full rounded-md border border-border bg-card px-2 text-[13px]">
                          <option value="USD">USD</option>
                          <option value="EUR">EUR</option>
                          <option value="CNY">CNY</option>
                          <option value="GBP">GBP</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[11px] text-muted-foreground">状态</label>
                        <select value={newPayment.status} onChange={(e) => setNewPayment(p => ({ ...p, status: e.target.value }))} className="h-8 w-full rounded-md border border-border bg-card px-2 text-[13px]">
                          <option value="completed">已完成</option>
                          <option value="pending">待处理</option>
                          <option value="refunded">已退款</option>
                          <option value="failed">失败</option>
                        </select>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <Input placeholder="付款人" value={newPayment.payer_name} onChange={(e) => setNewPayment(p => ({ ...p, payer_name: e.target.value }))} className="h-8 text-[13px]" />
                      <Input placeholder="备注" value={newPayment.notes} onChange={(e) => setNewPayment(p => ({ ...p, notes: e.target.value }))} className="h-8 text-[13px]" />
                    </div>
                    <Button size="sm" className="h-8 text-[12px]" onClick={handleAddPayment} disabled={addingPayment || newPayment.amount <= 0}>
                      {addingPayment ? <Loader2 className="mr-1 size-3 animate-spin" /> : null}
                      确认添加
                    </Button>
                  </div>
                )}
                {payments.length > 0 ? (
                  <>
                    {payments.map((p) => (
                      <div key={p.id} className="flex items-center justify-between border-b border-border/40 px-3 py-2 last:border-0">
                        <div>
                          <p className="text-[13px] font-medium">{p.currency} {p.amount.toFixed(2)}</p>
                          <p className="text-[11px] text-muted-foreground">
                            {p.payer_name || '—'}
                            {p.paid_at && ` · ${new Date(p.paid_at).toLocaleDateString('zh-CN')}`}
                          </p>
                        </div>
                        <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium ${
                          p.status === 'completed' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' :
                          p.status === 'refunded' ? 'border-rose-200 bg-rose-50 text-rose-700' :
                          p.status === 'pending' ? 'border-amber-200 bg-amber-50 text-amber-700' :
                          'border-gray-200 bg-gray-50 text-gray-700'
                        }`}>
                          {p.status === 'completed' ? '已完成' : p.status === 'refunded' ? '已退款' : p.status === 'pending' ? '待处理' : p.status}
                        </span>
                      </div>
                    ))}
                    {paymentSummary && (
                      <div className="flex items-center justify-between bg-muted/30 px-3 py-2 text-[12px]">
                        <span className="text-muted-foreground">已收 {paymentSummary.count} 笔</span>
                        <span className="font-semibold text-emerald-600">净收 ${paymentSummary.total_paid.toFixed(2)}</span>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="px-3 py-4 text-center text-[12px] text-muted-foreground">
                    暂无支付记录
                  </div>
                )}
              </div>

              {/* 三单一致性检查 */}
              <div className="rounded-md border border-border/60 bg-muted/20 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-[13px] font-semibold">三单一致性检查</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-[12px]"
                    onClick={() => handleConsistencyCheck(selectedOrder.id)}
                    disabled={checkingConsistency}
                  >
                    {checkingConsistency ? <Loader2 className="mr-1 size-3 animate-spin" /> : <CheckCircle2 className="mr-1 size-3" />}
                    {checkingConsistency ? '检查中' : '执行检查'}
                  </Button>
                </div>
                {consistencyResult && (
                  <div className="space-y-1.5">
                    <div className={`flex items-center gap-2 text-[13px] font-medium ${consistencyResult.passed ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {consistencyResult.passed ? <CheckCircle2 className="size-4" /> : <AlertCircle className="size-4" />}
                      {consistencyResult.passed ? '全部通过' : '存在不一致项'}
                    </div>
                    {consistencyResult.checks?.map((check, i) => (
                      <div key={i} className="flex items-start gap-2 text-[12px]">
                        <span className={check.passed ? 'text-emerald-500' : 'text-rose-500'}>
                          {check.passed ? '✓' : '✗'}
                        </span>
                        <div>
                          <span className="font-medium">{check.label}</span>
                          <span className="ml-1 text-muted-foreground">{check.detail}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedOrder(null)}>关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 新建订单弹窗 */}
      <CreateOrderDialog open={showCreate} onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); loadOrders() }} />
    </div>
  )
}

function SummaryCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/60 bg-card px-4 py-3 shadow-sm">
      <span className="flex size-9 items-center justify-center rounded-md bg-muted/40">
        <Icon className="size-4 text-muted-foreground" />
      </span>
      <div>
        <p className="text-[12px] text-muted-foreground">{label}</p>
        <p className="text-[18px] font-semibold">{value}</p>
      </div>
    </div>
  )
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="text-[13px] font-medium">{value}</p>
    </div>
  )
}

function CreateOrderDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [buyerName, setBuyerName] = useState('')
  const [country, setCountry] = useState('')
  const [productName, setProductName] = useState('')
  const [qty, setQty] = useState(1)
  const [unitPrice, setUnitPrice] = useState(0)
  const [currency, setCurrency] = useState('USD')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async () => {
    if (!buyerName.trim()) { toast.error('请填写买家名称'); return }
    setSaving(true)
    try {
      await ordersApi.create({
        platform: 'manual',
        buyer_name: buyerName,
        buyer_address: country ? { country } : {},
        items: productName ? [{ name: productName, qty, unit_price: unitPrice }] : [],
        currency,
        total_amount: productName ? qty * unitPrice : 0,
      })
      toast.success('订单创建成功')
      setBuyerName(''); setCountry(''); setProductName(''); setQty(1); setUnitPrice(0)
      onCreated()
    } catch (e) {
      toast.error('创建订单失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-[480px]">
        <DialogHeader>
          <DialogTitle>新建销售订单</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <label className="text-[12px] font-medium text-muted-foreground">买家名称 *</label>
            <Input value={buyerName} onChange={(e) => setBuyerName(e.target.value)} className="mt-1" placeholder="如：John Smith" />
          </div>
          <div>
            <label className="text-[12px] font-medium text-muted-foreground">目的国</label>
            <Input value={country} onChange={(e) => setCountry(e.target.value)} className="mt-1" placeholder="如：US" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[12px] font-medium text-muted-foreground">商品名称</label>
              <Input value={productName} onChange={(e) => setProductName(e.target.value)} className="mt-1" placeholder="商品名" />
            </div>
            <div>
              <label className="text-[12px] font-medium text-muted-foreground">数量</label>
              <Input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} className="mt-1" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[12px] font-medium text-muted-foreground">单价</label>
              <Input type="number" value={unitPrice} onChange={(e) => setUnitPrice(Number(e.target.value))} className="mt-1" />
            </div>
            <div>
              <label className="text-[12px] font-medium text-muted-foreground">币种</label>
              <select value={currency} onChange={(e) => setCurrency(e.target.value)} className="mt-1 h-9 w-full rounded-md border border-border bg-card px-3 text-[13px]">
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="CNY">CNY</option>
                <option value="GBP">GBP</option>
              </select>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? <Loader2 className="mr-1 size-4 animate-spin" /> : null}
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
