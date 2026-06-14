/**
 * 模型配置 API 客户端。
 * 后端：app/api/model_config.py
 */

const BASE = '/api/v1/model-configs'

export interface ModelConfigItem {
  id: string
  name: string
  base_url: string
  model: string
  temperature: number
  max_tokens: number
  is_active: boolean
  api_key_masked: string
}

export interface ModelConfigRequest {
  name: string
  api_key: string
  base_url: string
  model: string
  temperature?: number
  top_p?: number
  max_tokens?: number
  embed_model?: string
}

export interface ActiveConfig {
  id: string
  name: string
  api_key: string
  base_url: string
  model: string
  temperature: number
  top_p: number
  max_tokens: number
  embed_model: string
}

/** 获取所有模型配置列表 */
export async function listModelConfigs(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<ModelConfigItem[]> {
  const res = await authFetch(BASE)
  if (!res.ok) throw new Error(`获取模型配置失败: HTTP ${res.status}`)
  return res.json()
}

/** 获取当前激活的配置（含完整 API Key） */
export async function getActiveConfig(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
): Promise<ActiveConfig | null> {
  const res = await authFetch(`${BASE}/active`)
  if (!res.ok) throw new Error(`获取激活配置失败: HTTP ${res.status}`)
  return res.json()
}

/** 创建模型配置（admin） */
export async function createModelConfig(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  body: ModelConfigRequest,
): Promise<ModelConfigItem> {
  const res = await authFetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`创建配置失败: HTTP ${res.status}`)
  return res.json()
}

/** 更新模型配置（admin） */
export async function updateModelConfig(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  configId: string,
  body: ModelConfigRequest,
): Promise<ModelConfigItem> {
  const res = await authFetch(`${BASE}/${configId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`更新配置失败: HTTP ${res.status}`)
  return res.json()
}

/** 删除模型配置（admin） */
export async function deleteModelConfig(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  configId: string,
): Promise<{ ok: boolean }> {
  const res = await authFetch(`${BASE}/${configId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`删除配置失败: HTTP ${res.status}`)
  return res.json()
}

/** 激活模型配置（admin） */
export async function activateModelConfig(
  authFetch: (input: RequestInfo, init?: RequestInit) => Promise<Response>,
  configId: string,
): Promise<{ ok: boolean; message: string }> {
  const res = await authFetch(`${BASE}/${configId}/activate`, { method: 'POST' })
  if (!res.ok) throw new Error(`激活配置失败: HTTP ${res.status}`)
  return res.json()
}
