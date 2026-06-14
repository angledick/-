/**
 * 物流追踪中心
 *
 * 功能：
 *  - 输入任意运单号 + 承运商 → 实时可视化追踪
 *  - 8 阶段横向进度条（揽收→运输→出口→进口→派送→签收）
 *  - 竖向事件时间轴
 *  - 直跳承运商官网追踪链接
 *  - 历史追踪记录（来自 DB 中已创建的物流单）
 *  - WS 实时接收轨迹推送
 */

import { useState, useEffect, useCallback } from 'react'
import { logisticsApi, type LogisticsOrder } from '../api/config'
import { useWebSocketContext } from '../context/WebSocketContext'

// ─────────────────────────────────────────────────────────────────────────────
// 承运商配置
// ─────────────────────────────────────────────────────────────────────────────

const CARRIERS: Record<string, { name: string; icon: string; color: string; trackingUrl: string }> = {
  dhl:        { name: 'DHL Express',  icon: '🟡', color: '#FFCC00', trackingUrl: 'https://www.dhl.com/tracking?id={num}' },
  fedex:      { name: 'FedEx',        icon: '🟣', color: '#4D148C', trackingUrl: 'https://www.fedex.com/tracking?tracknumbers={num}' },
  ups:        { name: 'UPS',          icon: '🟤', color: '#351C15', trackingUrl: 'https://www.ups.com/track?tracknum={num}' },
  sf_express: { name: '顺丰国际',     icon: '🔴', color: '#E60012', trackingUrl: 'https://www.sf-express.com/cn/tc/dynamic_function/waybill/#search/bill-number:{num}' },
  ems:        { name: 'EMS 国际邮政', icon: '🟢', color: '#009900', trackingUrl: 'https://track.ems.com.cn/?mailNo={num}' },
  cainiao:    { name: '菜鸟国际',     icon: '🔵', color: '#FF6700', trackingUrl: 'https://global.cainiao.com/detail.htm?mailNoList={num}' },
  '17track':  { name: '17TRACK 通用', icon: '⚪', color: '#1890FF', trackingUrl: 'https://www.17track.net/en/track?nums={num}' },
  aftership:  { name: 'AfterShip',    icon: '⚫', color: '#4A90E2', trackingUrl: 'https://track.aftership.com/{num}' },
}

// ─────────────────────────────────────────────────────────────────────────────
// 物流阶段定义
// ─────────────────────────────────────────────────────────────────────────────

const STAGES = [
  { key: 'pending',           label: '待揽收',  icon: '📦' },
  { key: 'picked_up',         label: '已揽收',  icon: '🏭' },
  { key: 'in_transit',        label: '运输中',  icon: '✈️'  },
  { key: 'customs_export',    label: '出口报关', icon: '📋' },
  { key: 'customs_import',    label: '进口清关', icon: '🛃' },
  { key: 'out_for_delivery',  label: '派送中',  icon: '🚚' },
  { key: 'delivered',         label: '已签收',  icon: '✅' },
] as const

type StatusKey = typeof STAGES[number]['key'] | 'exception' | 'returned'

const STATUS_ORDER: Record<string, number> = {
  pending: 0, picked_up: 1, in_transit: 2,
  customs_export: 3, customs_import: 4,
  out_for_delivery: 5, delivered: 6,
  exception: -1, returned: -1,
}

const STATUS_LABELS: Record<string, string> = {
  pending: '待揽收', picked_up: '已揽收', in_transit: '运输中',
  customs_export: '出口报关中', customs_import: '进口清关中',
  out_for_delivery: '派送中', delivered: '已签收',
  exception: '异常', returned: '已退回',
}

function getStageIndex(status: string): number {
  return STATUS_ORDER[status] ?? 0
}

// ─────────────────────────────────────────────────────────────────────────────
// 工具函数
// ─────────────────────────────────────────────────────────────────────────────

function cx(...a: (string | false | null | undefined)[]) {
  return a.filter(Boolean).join(' ')
}

function formatTime(iso: string): { date: string; time: string } {
  if (!iso) return { date: '—', time: '' }
  try {
    const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T'))
    return {
      date: d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }),
      time: d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    }
  } catch {
    return { date: iso.slice(0, 10), time: iso.slice(11, 16) }
  }
}

function buildTrackingUrl(carrier: string, num: string): string {
  const tmpl = CARRIERS[carrier]?.trackingUrl || CARRIERS['17track'].trackingUrl
  return tmpl.replace('{num}', encodeURIComponent(num))
}

// ─────────────────────────────────────────────────────────────────────────────
// 进度条组件
// ─────────────────────────────────────────────────────────────────────────────

function ProgressBar({ status }: { status: string }) {
  const isException = status === 'exception' || status === 'returned'
  const currentIdx = getStageIndex(status)

  if (isException) {
    return (
      <div className="rounded-2xl border border-red-100 bg-red-50 px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <p className="text-sm font-semibold text-red-600">
              {status === 'exception' ? '运输异常' : '包裹已退回'}
            </p>
            <p className="text-xs text-red-400 mt-0.5">
              {status === 'exception'
                ? '货物在途中出现异常，请联系承运商或查看最新轨迹'
                : '包裹因无法投递或拒收已退回发货地'}
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white px-5 py-5">
      <div className="relative flex items-start">
        {/* 连接线 */}
        <div className="absolute top-5 left-[22px] right-[22px] h-0.5 bg-gray-200" />
        <div
          className="absolute top-5 left-[22px] h-0.5 bg-blue-500 transition-all duration-700"
          style={{ width: currentIdx > 0 ? `${(currentIdx / (STAGES.length - 1)) * 100}%` : '0%' }}
        />

        {STAGES.map((stage, idx) => {
          const done = idx < currentIdx
          const active = idx === currentIdx
          const future = idx > currentIdx
          return (
            <div key={stage.key} className="relative flex flex-col items-center flex-1 gap-2">
              {/* 圆圈 */}
              <div className={cx(
                'w-10 h-10 rounded-full flex items-center justify-center text-lg border-2 transition-all z-10 bg-white',
                done   ? 'border-blue-500 bg-blue-500' :
                active ? 'border-blue-500 shadow-[0_0_0_4px_rgba(59,130,246,0.15)]' :
                         'border-gray-200'
              )}>
                {done ? (
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                  </svg>
                ) : (
                  <span className={cx('text-base', active ? 'text-blue-500' : 'text-gray-300')}>{stage.icon}</span>
                )}
              </div>
              {/* 标签 */}
              <p className={cx(
                'text-[11px] font-medium text-center leading-tight',
                done   ? 'text-blue-500' :
                active ? 'text-blue-600 font-semibold' :
                         'text-gray-400'
              )}>{stage.label}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 时间轴组件
// ─────────────────────────────────────────────────────────────────────────────

function EventTimeline({ events }: { events: any[] }) {
  if (!events || events.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 py-12 text-center">
        <p className="text-3xl mb-2">📭</p>
        <p className="text-sm text-gray-400">暂无轨迹事件</p>
        <p className="text-xs text-gray-400 mt-1">点击「刷新轨迹」获取最新状态</p>
      </div>
    )
  }

  const sorted = [...events].sort((a, b) =>
    new Date(b.timestamp || 0).getTime() - new Date(a.timestamp || 0).getTime()
  )

  return (
    <div className="relative">
      {/* 竖线 */}
      <div className="absolute left-[19px] top-6 bottom-0 w-0.5 bg-gray-100" />

      <div className="space-y-1">
        {sorted.map((event, idx) => {
          const { date, time } = formatTime(event.timestamp)
          const isLatest = idx === 0
          const isException = (event.status_code || event.description || '').toLowerCase().includes('exception') ||
                              (event.description || '').includes('异常')

          return (
            <div key={idx} className={cx(
              'flex items-start gap-4 pl-2 pr-4 py-3 rounded-xl transition-colors',
              isLatest ? 'bg-blue-50/60' : 'hover:bg-gray-50/60'
            )}>
              {/* 圆点 */}
              <div className="shrink-0 mt-1 relative z-10">
                <div className={cx(
                  'w-5 h-5 rounded-full flex items-center justify-center',
                  isLatest   ? 'bg-blue-500 shadow-[0_0_0_3px_rgba(59,130,246,0.2)]' :
                  isException? 'bg-red-400' :
                               'bg-gray-300'
                )}>
                  {isLatest && (
                    <div className="w-2 h-2 rounded-full bg-white" />
                  )}
                </div>
              </div>

              {/* 内容 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className={cx(
                    'text-sm leading-snug',
                    isLatest ? 'font-semibold text-gray-900' : 'text-gray-700'
                  )}>
                    {event.description || event.message || '状态更新'}
                  </p>
                  <div className="shrink-0 text-right">
                    <p className={cx('text-[11px] tabular-nums', isLatest ? 'text-blue-500 font-medium' : 'text-gray-400')}>{time}</p>
                    <p className="text-[10px] text-gray-400">{date}</p>
                  </div>
                </div>
                {event.location && (
                  <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                    <span>📍</span>{event.location}
                  </p>
                )}
                {event.status_code && (
                  <span className="inline-block mt-1 text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                    {event.status_code}
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 追踪结果卡片
// ─────────────────────────────────────────────────────────────────────────────

function TrackingResult({
  shipment,
  trackingData,
  onRefresh,
  refreshing,
}: {
  shipment: LogisticsOrder
  trackingData: any
  onRefresh: () => void
  refreshing: boolean
}) {
  const carrier = CARRIERS[shipment.carrier] || CARRIERS['17track']
  const status = shipment.status
  const statusLabel = STATUS_LABELS[status] || status
  const events = trackingData?.events || []
  const latest = events[0]

  const isDelivered = status === 'delivered'
  const isException = status === 'exception' || status === 'returned'

  return (
    <div className="space-y-4">
      {/* 运单概要卡 */}
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        {/* 顶部状态带 */}
        <div className={cx(
          'px-5 py-3 flex items-center justify-between',
          isDelivered  ? 'bg-emerald-50 border-b border-emerald-100' :
          isException  ? 'bg-red-50 border-b border-red-100' :
                        'bg-blue-50 border-b border-blue-100'
        )}>
          <div className="flex items-center gap-3">
            <span className="text-2xl">{isDelivered ? '✅' : isException ? '⚠️' : '🚚'}</span>
            <div>
              <p className={cx('text-base font-bold',
                isDelivered ? 'text-emerald-700' : isException ? 'text-red-600' : 'text-blue-700'
              )}>{statusLabel}</p>
              {latest && (
                <p className="text-xs text-gray-500 mt-0.5">
                  {latest.description && `${latest.description}`}
                  {latest.location && ` · ${latest.location}`}
                </p>
              )}
            </div>
          </div>
          <button onClick={onRefresh} disabled={refreshing}
            className="flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-lg border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 disabled:opacity-40 transition-colors">
            {refreshing ? (
              <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
              </svg>
            ) : (
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
            )}
            刷新
          </button>
        </div>

        {/* 基础信息 */}
        <div className="px-5 py-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">运单号</p>
            <p className="text-sm font-mono font-semibold text-gray-800 mt-1 break-all">
              {shipment.tracking_number || '—'}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">承运商</p>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="text-sm">{carrier.icon}</span>
              <span className="text-sm font-medium text-gray-700">{carrier.name}</span>
            </div>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">路线</p>
            <p className="text-sm font-medium text-gray-700 mt-1">
              {shipment.origin_country} → {shipment.dest_country}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">预计送达</p>
            <p className="text-sm text-gray-700 mt-1">
              {shipment.estimated_delivery
                ? formatTime(shipment.estimated_delivery).date
                : '—'}
            </p>
          </div>
        </div>

        {/* 官网追踪链接 */}
        {shipment.tracking_number && (
          <div className="px-5 pb-4">
            <a
              href={buildTrackingUrl(shipment.carrier, shipment.tracking_number)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-xs text-blue-500 hover:text-blue-700 hover:underline transition-colors"
            >
              <span>↗</span>
              在 {carrier.name} 官网查看完整轨迹
            </a>
          </div>
        )}
      </div>

      {/* 进度条 */}
      <ProgressBar status={status} />

      {/* 事件时间轴 */}
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
          <p className="text-sm font-semibold text-gray-700">物流轨迹</p>
          <span className="text-xs text-gray-400">
            {events.length > 0 ? `${events.length} 条事件` : '暂无事件'}
          </span>
        </div>
        <div className="px-4 py-4">
          <EventTimeline events={events} />
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 历史物流单列表
// ─────────────────────────────────────────────────────────────────────────────

function HistoryList({ onSelect }: { onSelect: (s: LogisticsOrder) => void }) {
  const [shipments, setShipments] = useState<LogisticsOrder[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    logisticsApi.listShipments()
      .then(s => setShipments(s.filter(x => x.tracking_number)))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-xs text-gray-400 py-4 text-center">加载中…</div>
  if (shipments.length === 0) return null

  const statusDot: Record<string, string> = {
    delivered: 'bg-emerald-400', exception: 'bg-red-400', returned: 'bg-red-400',
    in_transit: 'bg-blue-400', out_for_delivery: 'bg-amber-400',
    pending: 'bg-gray-300', picked_up: 'bg-blue-300',
    customs_export: 'bg-purple-400', customs_import: 'bg-purple-400',
  }

  return (
    <div className="space-y-1">
      {shipments.slice(0, 8).map(s => (
        <button
          key={s.id}
          onClick={() => onSelect(s)}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-gray-50 transition-colors text-left"
        >
          <span className={cx('w-2 h-2 rounded-full shrink-0', statusDot[s.status] || 'bg-gray-200')} />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-mono font-medium text-gray-700 truncate">{s.tracking_number}</p>
            <p className="text-[10px] text-gray-400">{CARRIERS[s.carrier]?.name} · {s.dest_country}</p>
          </div>
          <span className="text-[10px] text-gray-400 shrink-0">{STATUS_LABELS[s.status] || s.status}</span>
        </button>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 主页面
// ─────────────────────────────────────────────────────────────────────────────

export default function LogisticsTrackingPage() {
  // 搜索表单
  const [trackingNum, setTrackingNum] = useState('')
  const [carrier, setCarrier] = useState('17track')
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')

  // 追踪结果
  const [currentShipment, setCurrentShipment] = useState<LogisticsOrder | null>(null)
  const [trackingData, setTrackingData] = useState<any>(null)
  const [refreshing, setRefreshing] = useState(false)

  // WS 实时推送
  const { on: wsOn } = useWebSocketContext()
  useEffect(() => {
    const off = wsOn('logistics_updated', (msg) => {
      const p = msg.payload as any
      if (currentShipment && p?.logistics_id === currentShipment.id) {
        // 实时追加最新事件
        if (p?.latest_event) {
          setTrackingData((prev: any) => ({
            ...prev,
            status: p.status || prev?.status,
            events: [p.latest_event, ...(prev?.events || [])],
          }))
        }
        // 同步更新物流单状态
        if (p?.status) {
          setCurrentShipment(prev => prev ? { ...prev, status: p.status } : prev)
        }
      }
    })
    return off
  }, [wsOn, currentShipment])

  const loadTracking = useCallback(async (shipment: LogisticsOrder) => {
    setCurrentShipment(shipment)
    setTrackingData(null)
    try {
      const data = await logisticsApi.getTracking(shipment.id)
      setTrackingData(data)
    } catch {
      setTrackingData({ events: [] })
    }
  }, [])

  const handleRefresh = async () => {
    if (!currentShipment) return
    setRefreshing(true)
    try {
      await logisticsApi.refreshTracking(currentShipment.id)
      const data = await logisticsApi.getTracking(currentShipment.id)
      setTrackingData(data)
      // 刷新物流单状态
      const updated = await logisticsApi.getShipment(currentShipment.id)
      setCurrentShipment(updated)
    } finally {
      setRefreshing(false)
    }
  }

  const handleSearch = async () => {
    const num = trackingNum.trim()
    if (!num) return
    setSearching(true)
    setSearchError('')

    try {
      // 先在 DB 中查找
      const all = await logisticsApi.listShipments()
      const found = all.find(s => s.tracking_number === num)

      if (found) {
        await loadTracking(found)
      } else {
        // 不在 DB 里：创建临时物流单
        const dest = prompt('请输入目的国代码（如 US / DE / UK）：', 'US') || 'US'
        const shipment = await logisticsApi.createShipment({
          product_id: 'manual_track',
          carrier,
          dest_country: dest,
          tracking_number: num,
          service_type: '国际快件',
          incoterm: 'FOB',
        })
        await loadTracking(shipment)
        // 触发 17TRACK 刷新
        try { await logisticsApi.refreshTracking(shipment.id) } catch {}
        const data = await logisticsApi.getTracking(shipment.id)
        setTrackingData(data)
      }
    } catch (e: any) {
      setSearchError('追踪失败：' + (e.message || '请检查运单号是否正确'))
    } finally {
      setSearching(false)
    }
  }

  const handleSelectHistory = async (s: LogisticsOrder) => {
    setTrackingNum(s.tracking_number)
    setCarrier(s.carrier)
    await loadTracking(s)
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50/40">
      <div className="max-w-5xl mx-auto px-6 py-8">

        {/* 页头 */}
        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-900">物流追踪</h1>
          <p className="text-sm text-gray-400 mt-1">
            输入运单号实时查询物流进度 · WS 实时推送轨迹更新
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5">

          {/* 左栏：搜索 + 历史 */}
          <div className="space-y-4">
            {/* 搜索卡 */}
            <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-4">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wide">输入运单号</p>

              {/* 运单号输入 */}
              <div className="space-y-2">
                <input
                  value={trackingNum}
                  onChange={e => setTrackingNum(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                  placeholder="如：JD0000000000000"
                  className="w-full h-11 px-4 text-sm font-mono bg-gray-50 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 focus:bg-white transition"
                />

                {/* 承运商选择 */}
                <select
                  value={carrier}
                  onChange={e => setCarrier(e.target.value)}
                  className="w-full h-10 px-3 text-sm bg-white rounded-xl border border-gray-200 focus:outline-none text-gray-700"
                >
                  {Object.entries(CARRIERS).map(([key, c]) => (
                    <option key={key} value={key}>{c.icon} {c.name}</option>
                  ))}
                </select>
              </div>

              {/* 错误提示 */}
              {searchError && (
                <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{searchError}</p>
              )}

              {/* 查询按钮 */}
              <button
                onClick={handleSearch}
                disabled={searching || !trackingNum.trim()}
                className="w-full h-11 rounded-xl bg-gray-900 text-white text-sm font-semibold hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {searching ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
                    </svg>
                    查询中…
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
                    </svg>
                    查询物流进度
                  </>
                )}
              </button>

              {/* 快捷追踪提示 */}
              <div className="rounded-xl bg-blue-50 border border-blue-100 px-3 py-2.5 text-[11px] text-blue-600 space-y-1">
                <p className="font-semibold">💡 使用说明</p>
                <p>• 输入运单号后点击「查询」，若系统中有记录则直接展示历史轨迹</p>
                <p>• 若系统中无记录，会自动创建追踪任务并刷新</p>
                <p>• 轨迹支持 WS 实时推送，有新事件时自动刷新</p>
              </div>
            </div>

            {/* 历史物流单 */}
            <div className="bg-white rounded-2xl border border-gray-200 p-4">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-3">最近追踪记录</p>
              <HistoryList onSelect={handleSelectHistory} />
            </div>

            {/* 承运商追踪直链 */}
            {trackingNum.trim() && (
              <div className="bg-white rounded-2xl border border-gray-200 p-4">
                <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-3">官网直达</p>
                <div className="space-y-1.5">
                  {Object.entries(CARRIERS).slice(0, 5).map(([key, c]) => (
                    <a
                      key={key}
                      href={buildTrackingUrl(key, trackingNum.trim())}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors text-sm text-gray-600 hover:text-gray-900"
                    >
                      <span className="text-base w-5 text-center">{c.icon}</span>
                      <span className="flex-1 text-xs">{c.name}</span>
                      <svg className="w-3.5 h-3.5 text-gray-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/>
                      </svg>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 右栏：追踪结果 */}
          <div>
            {!currentShipment ? (
              /* 空状态 */
              <div className="h-full flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 bg-white py-20 text-center gap-3">
                <span className="text-6xl">🚢</span>
                <p className="text-base font-semibold text-gray-500">在左侧输入运单号开始追踪</p>
                <p className="text-sm text-gray-400 max-w-xs">
                  支持 DHL / FedEx / 顺丰 / EMS / 菜鸟 等主流承运商<br/>
                  或输入运单号后选择「17TRACK 通用」
                </p>
                <div className="mt-2 flex flex-wrap justify-center gap-2">
                  {Object.entries(CARRIERS).map(([, c]) => (
                    <span key={c.name} className="text-xs bg-gray-100 text-gray-500 px-2.5 py-1 rounded-full">
                      {c.icon} {c.name}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <TrackingResult
                shipment={currentShipment}
                trackingData={trackingData}
                onRefresh={handleRefresh}
                refreshing={refreshing}
              />
            )}
          </div>

        </div>
      </div>
    </div>
  )
}
