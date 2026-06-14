/**
 * 通知配置 — 推送渠道 CRUD（飞书 / 企业微信）
 */
import { useState } from 'react'
import { useConfirm } from '@/hooks/useConfirm'
import {
  BellRing,
  Loader2,
  Plus,
  Send,
  Settings2,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  useCreateChannel,
  useDeleteChannel,
  useNotifyChannels,
  useTestChannel,
  useToggleChannel,
  useUpdateChannel,
} from '@/hooks/queries/useNotify'
import { CHANNEL_LABEL, LEVEL_LABEL } from '@/lib/api/notify'
import type { ChannelBody, ChannelType, MinLevel, NotifyChannel } from '@/lib/api/notify'
import { cn } from '@/lib/utils'

const CHANNEL_TYPES: ChannelType[] = ['feishu', 'wecom']
const MIN_LEVELS: MinLevel[] = ['low', 'medium', 'high', 'critical']

const emptyForm: ChannelBody = {
  channel: 'feishu',
  name: '',
  webhook_url: '',
  enabled: true,
  min_level: 'medium',
}

export default function NotifyConfigPage() {
  const { data: channels, isLoading, isError } = useNotifyChannels()
  const [editing, setEditing] = useState<NotifyChannel | null>(null)
  const confirm = useConfirm()
  const [adding, setAdding] = useState(false)
  const createCh = useCreateChannel()
  const updateCh = useUpdateChannel()
  const deleteCh = useDeleteChannel()
  const toggleCh = useToggleChannel()
  const testCh = useTestChannel()

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-[1100px] px-6 py-7 sm:px-8 flex items-end justify-between">
          <div>
            <h1 className="text-[28px] font-semibold tracking-tight">通知配置</h1>
            <p className="mt-1 text-[14px] text-muted-foreground">
              配置飞书 / 企业微信推送渠道，风险预警自动推送
            </p>
          </div>
          <Button onClick={() => setAdding(true)} size="sm">
            <Plus className="mr-2 size-4" /> 添加渠道
          </Button>
        </div>
      </div>

      <div className="mx-auto max-w-[1100px] px-6 py-8 sm:px-8 space-y-4">
        {isLoading && <Loader />}
        {isError && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            加载渠道失败
          </div>
        )}
        {channels && channels.length === 0 && !isLoading && (
          <div className="rounded-lg border border-dashed border-border bg-muted/30 p-12 text-center">
            <BellRing className="mx-auto size-8 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground mb-4">暂无推送渠道。添加飞书或企业微信 Webhook 接收风险预警。</p>
            <Button onClick={() => setAdding(true)} size="sm">
              <Plus className="mr-2 size-3.5" /> 添加渠道
            </Button>
          </div>
        )}
        {channels?.map((ch) => (
          <ChannelRow
            key={ch.id}
            channel={ch}
            onEdit={() => setEditing(ch)}
            onToggle={() =>
              toggleCh
                .mutateAsync({ id: ch.id, enabled: !ch.enabled })
                .then(() => toast.success(ch.enabled ? '已禁用' : '已启用'))
                .catch((e) => toast.error(e.message))
            }
            onTest={() =>
              testCh
                .mutateAsync(ch.id)
                .then((r) =>
                  toast.success(r.ok ? `测试消息已发送到 ${r.name}` : '测试失败')
                )
                .catch((e) => toast.error(e.message))
            }
            onDelete={async () => {
              if (!(await confirm({ title: '删除渠道', description: `确认删除「${ch.name}」？`, variant: 'destructive' }))) return
              deleteCh
                .mutateAsync(ch.id)
                .then(() => toast.success('已删除'))
                .catch((e) => toast.error(e.message))
            }}
            busy={toggleCh.isPending || testCh.isPending || deleteCh.isPending}
          />
        ))}

        {/* Add / Edit dialog */}
        <ChannelDialog
          open={adding || !!editing}
          onClose={() => { setAdding(false); setEditing(null) }}
          initial={editing ? {
            channel: editing.channel,
            name: editing.name,
            webhook_url: editing.webhook_url,
            enabled: editing.enabled,
            min_level: editing.min_level,
          } : emptyForm}
          onSubmit={(body) => {
            const p = editing
              ? updateCh.mutateAsync({ id: editing.id, body })
              : createCh.mutateAsync(body)
            return p
              .then(() => { setAdding(false); setEditing(null); toast.success(editing ? '已更新' : '已创建') })
              .catch((e) => toast.error(e.message))
          }}
          saving={createCh.isPending || updateCh.isPending}
        />
      </div>
    </div>
  )
}

/* ─────────────────────────── Channel Row ─────────────────────────── */

function ChannelRow({
  channel,
  onEdit,
  onToggle,
  onTest,
  onDelete,
  busy,
}: {
  channel: NotifyChannel
  onEdit: () => void
  onToggle: () => void
  onTest: () => void
  onDelete: () => void
  busy: boolean
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 flex flex-col sm:flex-row sm:items-center gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn('size-2 rounded-full', channel.enabled ? 'bg-emerald-500' : 'bg-muted-foreground/30')} />
          <span className="font-semibold text-[14px]">{channel.name}</span>
          <Badge variant="outline" className="text-[10px] uppercase">
            {CHANNEL_LABEL[channel.channel]}
          </Badge>
          <Badge variant="outline" className="text-[10px] text-muted-foreground">
            最低 {LEVEL_LABEL[channel.min_level]}风险
          </Badge>
        </div>
        <p className="mt-1 text-[12px] text-muted-foreground truncate">{channel.webhook_url}</p>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <Button variant="ghost" size="sm" onClick={onEdit} disabled={busy} className="h-8 text-xs">
          <Settings2 className="size-3.5 mr-1" /> 编辑
        </Button>
        <Button variant="ghost" size="sm" onClick={onToggle} disabled={busy} className="h-8 text-xs">
          {channel.enabled ? '禁用' : '启用'}
        </Button>
        <Button variant="ghost" size="sm" onClick={onTest} disabled={busy} className="h-8 text-xs">
          <Send className="size-3.5 mr-1" /> 测试
        </Button>
        <Button variant="ghost" size="sm" onClick={onDelete} disabled={busy} className="h-8 text-xs text-destructive">
          <Trash2 className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}

/* ─────────────────────────── Dialog ─────────────────────────── */

function ChannelDialog({
  open,
  onClose,
  initial,
  onSubmit,
  saving,
}: {
  open: boolean
  onClose: () => void
  initial: ChannelBody
  onSubmit: (body: ChannelBody) => Promise<unknown>
  saving: boolean
}) {
  const [form, setForm] = useState<ChannelBody>(initial)

  // Sync initial when opening
  const wasOpen = useState(false)
  if (open && !wasOpen[0]) {
    wasOpen[0] = true
    setForm(initial)
  }
  if (!open) wasOpen[0] = false

  const handle = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) return toast.error('名称不能为空')
    if (!form.webhook_url.startsWith('http')) return toast.error('Webhook 需以 http 开头')
    await onSubmit(form)
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initial.name ? '编辑渠道' : '添加渠道'}</DialogTitle>
          <DialogDescription>配置飞书或企业微信 Webhook 推送</DialogDescription>
        </DialogHeader>
        <form onSubmit={handle} className="space-y-4">
          <Field label="名称" value={form.name} onChange={(v) => setForm({ ...form, name: v })} placeholder="如：风险预警群" />
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">渠道</label>
            <select
              value={form.channel}
              onChange={(e) => setForm({ ...form, channel: e.target.value as ChannelType })}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {CHANNEL_TYPES.map((t) => (
                <option key={t} value={t}>{CHANNEL_LABEL[t]}</option>
              ))}
            </select>
          </div>
          <Field label="Webhook URL" value={form.webhook_url} onChange={(v) => setForm({ ...form, webhook_url: v })} placeholder="https://..." />
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
              最低推送等级
            </label>
            <select
              value={form.min_level}
              onChange={(e) => setForm({ ...form, min_level: e.target.value as MinLevel })}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {MIN_LEVELS.map((l) => (
                <option key={l} value={l}>{LEVEL_LABEL[l]} 及以上</option>
              ))}
            </select>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function Field({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
      />
    </div>
  )
}

function Loader() {
  return (
    <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
      <Loader2 className="mr-2 size-4 animate-spin" /> 加载中…
    </div>
  )
}
