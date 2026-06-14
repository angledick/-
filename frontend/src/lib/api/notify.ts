/**
 * 通知渠道 + 修改密码 API 客户端。
 * 最新后端使用 app/api/channels.py，不再提供旧的 /api/v1/notify/*。
 */

const CHANNELS_BASE = '/api/v1/channels'

export type ChannelType = 'feishu' | 'dingtalk' | 'wecom' | 'slack' | 'email' | 'webhook'
export type MinLevel = 'low' | 'medium' | 'high' | 'critical'

export interface NotifyChannel {
  id: string
  user_id?: string
  channel: ChannelType
  name: string
  webhook_url: string
  enabled: boolean
  min_level: MinLevel
  created_at?: number
  status?: string
}

export interface ChannelBody {
  channel: ChannelType
  name: string
  webhook_url: string
  enabled?: boolean
  min_level?: MinLevel
}

export const CHANNEL_LABEL: Record<ChannelType, string> = {
  feishu: '飞书',
  dingtalk: '钉钉',
  wecom: '企业微信',
  slack: 'Slack',
  email: '邮件',
  webhook: 'Webhook',
}

export const LEVEL_LABEL: Record<MinLevel, string> = {
  low: '低',
  medium: '中',
  high: '高',
  critical: '严重',
}

const BASE = '/api/v1'

/** 列出渠道 */
export async function listNotifyChannels(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<NotifyChannel[]> {
  const res = await authFetch(CHANNELS_BASE)
  if (!res.ok) throw new Error(`获取渠道失败: HTTP ${res.status}`)
  const data = await res.json()
  const channels = Array.isArray(data.channels) ? data.channels : []
  return channels.map((item: {
    name: string
    channel: ChannelType
    status: string
    webhook_url?: string
    enabled?: boolean
    min_level?: MinLevel
    config?: Record<string, unknown>
  }) => {
    const cfg = item.config || {}
    return {
      id: item.name,
      name: item.name,
      channel: item.channel,
      webhook_url: item.webhook_url || (cfg.webhook_url as string) || (cfg.webhook as string) || '',
      enabled: item.enabled ?? (cfg.enabled as boolean) ?? (item.status === 'active'),
      min_level: item.min_level || (cfg.min_level as MinLevel) || 'medium',
      status: item.status,
    }
  })
}

function bodyToConfig(body: ChannelBody): Record<string, unknown> {
  const config: Record<string, unknown> = {
    enabled: body.enabled ?? true,
    min_level: body.min_level ?? 'medium',
  }
  if (body.webhook_url) config.webhook_url = body.webhook_url
  if (body.channel === 'dingtalk' && body.webhook_url) {
    config.webhook_token = body.webhook_url.split('access_token=').pop() || body.webhook_url
  }
  return config
}

/** 新建渠道 */
export async function createNotifyChannel(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  body: ChannelBody,
): Promise<NotifyChannel> {
  const res = await authFetch(CHANNELS_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: body.name,
      channel_type: body.channel,
      config: bodyToConfig(body),
    }),
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `创建失败: HTTP ${res.status}`)
  }
  const data = await res.json()
  return {
    id: data.name,
    name: data.name,
    channel: data.channel_type,
    webhook_url: body.webhook_url,
    enabled: true,
    min_level: body.min_level ?? 'medium',
    status: data.status,
  }
}

/** 更新渠道 */
export async function updateNotifyChannel(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  id: string,
  body: ChannelBody,
): Promise<NotifyChannel> {
  const res = await authFetch(`${CHANNELS_BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config: bodyToConfig(body) }),
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `更新失败: HTTP ${res.status}`)
  }
  const data = await res.json()
  return {
    id: data.name,
    name: data.name,
    channel: data.channel_type,
    webhook_url: body.webhook_url,
    enabled: true,
    min_level: body.min_level ?? 'medium',
    status: data.status,
  }
}

/** 删除渠道 */
export async function deleteNotifyChannel(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  id: string,
): Promise<{ ok: boolean }> {
  const res = await authFetch(`${CHANNELS_BASE}/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`删除失败: HTTP ${res.status}`)
  await res.json()
  return { ok: true }
}

/** 启用/禁用 */
export async function toggleNotifyChannel(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  id: string,
  enabled: boolean,
): Promise<{ ok: boolean; enabled: boolean }> {
  const res = await authFetch(`${CHANNELS_BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config: { enabled } }),
  })
  if (!res.ok) throw new Error(`切换失败: HTTP ${res.status}`)
  await res.json()
  return { ok: true, enabled }
}

/** 测试推送 */
export async function testNotifyChannel(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  id: string,
): Promise<{ ok: boolean; channel: string; name: string }> {
  const res = await authFetch(`${CHANNELS_BASE}/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      channel: id,
      target: 'broadcast',
      notification: {
        title: '避风港通知测试',
        message: '这是一条来自通知配置页的测试消息。',
        severity: 'info',
      },
    }),
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `测试失败: HTTP ${res.status}`)
  }
  const data = await res.json()
  return { ok: data.status !== 'failed', channel: id, name: id }
}

/** 修改当前用户密码 */
export async function changePassword(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  oldPassword: string,
  newPassword: string,
): Promise<{ ok: boolean; message: string }> {
  const res = await authFetch(`${BASE}/auth/me/password`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail || `修改失败: HTTP ${res.status}`)
  }
  return res.json()
}
