import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '@/hooks/useConfirm'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

const API = '/api/v1'

interface ModelConfig {
  id: string
  name: string
  base_url: string
  model: string
  temperature: number
  max_tokens: number
  is_active: boolean
  api_key_masked: string
}

interface ActiveModelConfig {
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

function maskApiKey(value?: string) {
  if (!value) return '未配置'
  return value.length > 12 ? `${value.slice(0, 8)}...${value.slice(-4)}` : '****'
}

export default function ModelConfigPage() {
  const { authFetch, isAdmin } = useAuth()
  const confirm = useConfirm()
  const [configs, setConfigs] = useState<ModelConfig[]>([])
  const [activeConfig, setActiveConfig] = useState<ActiveModelConfig | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('https://api.xiaomimimo.com/v1')
  const [model, setModel] = useState('mimo-v2.5-pro')
  const [temperature, setTemperature] = useState('1.0')
  const [maxTokens, setMaxTokens] = useState('2048')
  const [saving, setSaving] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const handleReloadPrompts = async () => {
    setReloading(true)
    setError(null)
    setSuccess(null)
    try {
      const res = await authFetch(`${API}/prompts/reload`, { method: 'POST' })
      if (!res.ok) throw new Error('热加载失败')
      setSuccess('Prompt 模板已重新加载')
    } catch (e) {
      setError(e instanceof Error ? e.message : '热加载失败')
    } finally {
      setReloading(false)
    }
  }

  const resetForm = useCallback(() => {
    setSelectedId(null)
    setName('')
    setApiKey('')
    setBaseUrl('https://api.xiaomimimo.com/v1')
    setModel('mimo-v2.5-pro')
    setTemperature('1.0')
    setMaxTokens('2048')
    setError(null)
    setSuccess(null)
  }, [])

  const loadConfigs = useCallback(async () => {
    try {
      const [listRes, activeRes] = await Promise.all([
        authFetch(`${API}/model-configs`),
        authFetch(`${API}/model-configs/active`),
      ])
      if (listRes.ok) {
        const data: ModelConfig[] = await listRes.json()
        setConfigs(data)
      }
      if (activeRes.ok) {
        setActiveConfig(await activeRes.json())
      }
    } catch { /* ignore */ }
  }, [authFetch])

  useEffect(() => { loadConfigs() }, [loadConfigs])

  const handleEdit = (cfg: ModelConfig) => {
    setSelectedId(cfg.id)
    setName(cfg.name)
    setApiKey('')
    setBaseUrl(cfg.base_url)
    setModel(cfg.model)
    setTemperature(String(cfg.temperature))
    setMaxTokens(String(cfg.max_tokens))
    setError(null)
    setSuccess(null)
  }

  const handleSave = async () => {
    if (!name.trim() || !apiKey.trim()) return
    setSaving(true)
    setError(null)
    try {
      const endpoint = selectedId
        ? `${API}/model-configs/${selectedId}`
        : `${API}/model-configs`
      const res = await authFetch(endpoint, {
        method: selectedId ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          api_key: apiKey,
          base_url: baseUrl,
          model,
          temperature: parseFloat(temperature),
          max_tokens: parseInt(maxTokens),
        }),
      })
      if (!res.ok) throw new Error('保存失败')
      const message = selectedId ? '配置已更新' : '配置已保存'
      await loadConfigs()
      resetForm()
      setSuccess(message)
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleActivate = async (configId: string) => {
    try {
      const res = await authFetch(`${API}/model-configs/${configId}/activate`, { method: 'POST' })
      if (res.ok) {
        setSuccess('已切换激活配置')
        await loadConfigs()
      }
    } catch { /* ignore */ }
  }

  const handleDelete = async (configId: string) => {
    if (!(await confirm({ title: '删除配置', description: '确认删除这个模型配置？', variant: 'destructive' }))) return
    try {
      const res = await authFetch(`${API}/model-configs/${configId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('删除失败')
      if (selectedId === configId) resetForm()
      await loadConfigs()
      setSuccess('配置已删除')
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    }
  }

  if (!isAdmin) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-[14px] text-muted-foreground">仅管理员可访问</p>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="border-b border-border/60 bg-background">
        <div className="mx-auto max-w-[1400px] px-8 py-8">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-[28px] font-semibold tracking-tight">模型配置</h1>
              <p className="mt-1 text-[14px] text-muted-foreground/80">
                管理 LLM 模型的连接配置
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleReloadPrompts}
              disabled={reloading}
              className="gap-2"
            >
              <RefreshCw className={cn('size-4', reloading && 'animate-spin')} />
              重载 Prompt 模板
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-[1400px] px-8 py-8">
        <section className="mb-6 rounded-lg border border-border/60 bg-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold">当前激活配置</h2>
              <p className="mt-1 text-[12px] text-muted-foreground">
                后续合规问答会优先使用此模型预设
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={loadConfigs} className="h-8 text-[12px]">
              刷新
            </Button>
          </div>
          {activeConfig ? (
            <div className="grid gap-3 text-[12px] md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-md border border-border/60 bg-background px-3 py-2">
                <div className="text-muted-foreground">名称</div>
                <div className="mt-1 truncate font-medium">{activeConfig.name}</div>
              </div>
              <div className="rounded-md border border-border/60 bg-background px-3 py-2">
                <div className="text-muted-foreground">模型</div>
                <div className="mt-1 truncate font-medium">{activeConfig.model}</div>
              </div>
              <div className="rounded-md border border-border/60 bg-background px-3 py-2">
                <div className="text-muted-foreground">Base URL</div>
                <div className="mt-1 truncate font-mono text-[11px]">{activeConfig.base_url}</div>
              </div>
              <div className="rounded-md border border-border/60 bg-background px-3 py-2">
                <div className="text-muted-foreground">API Key</div>
                <div className="mt-1 truncate font-mono text-[11px]">{maskApiKey(activeConfig.api_key)}</div>
              </div>
              <div className="rounded-md border border-border/60 bg-background px-3 py-2">
                <div className="text-muted-foreground">Temperature / Top P</div>
                <div className="mt-1 font-medium">{activeConfig.temperature} / {activeConfig.top_p}</div>
              </div>
              <div className="rounded-md border border-border/60 bg-background px-3 py-2">
                <div className="text-muted-foreground">Max Tokens</div>
                <div className="mt-1 font-medium">{activeConfig.max_tokens}</div>
              </div>
              <div className="rounded-md border border-border/60 bg-background px-3 py-2 md:col-span-2">
                <div className="text-muted-foreground">Embedding 模型</div>
                <div className="mt-1 truncate font-mono text-[11px]">{activeConfig.embed_model}</div>
              </div>
            </div>
          ) : (
            <div className="rounded-md border border-dashed border-border bg-muted/25 px-3 py-6 text-center text-[13px] text-muted-foreground">
              暂无激活模型配置
            </div>
          )}
        </section>

        <div className="grid gap-8 lg:grid-cols-3">
          {/* Configs List */}
          <div>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold">已有配置</h2>
              <button
                onClick={resetForm}
                className="text-[12px] font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                新建
              </button>
            </div>
            <div className="space-y-2">
              {configs.map((cfg) => (
                <div
                  key={cfg.id}
                  className={cn(
                    'rounded-lg border p-3 transition-colors',
                    selectedId === cfg.id
                      ? 'border-foreground/30 bg-muted/40'
                      : cfg.is_active
                        ? 'border-primary bg-primary/5'
                        : 'border-border/60 hover:bg-muted/30',
                  )}
                >
                  <button
                    onClick={() => handleEdit(cfg)}
                    className="w-full text-left"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-[13px] font-medium">{cfg.name}</div>
                        <div className="text-[11px] text-muted-foreground">{cfg.model}</div>
                      </div>
                      {cfg.is_active && (
                        <span className="shrink-0 text-[11px] font-medium text-primary">激活</span>
                      )}
                    </div>
                    <div className="mt-1 text-[11px] text-muted-foreground/80">
                      {cfg.api_key_masked}
                    </div>
                  </button>
                  <div className="mt-3 flex gap-2">
                    {!cfg.is_active && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleActivate(cfg.id)}
                        className="h-7 px-2 text-[11px]"
                      >
                        激活
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDelete(cfg.id)}
                      className="h-7 px-2 text-[11px] text-destructive hover:text-destructive"
                    >
                      删除
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Form */}
          <div className="lg:col-span-2">
            <h2 className="mb-4 text-base font-semibold">
              {selectedId ? '编辑配置' : '新建配置'}
            </h2>
            {(error || success) && (
              <div className={cn(
                'mb-4 rounded-lg p-3 text-[13px]',
                error && 'bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-400',
                success && 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400',
              )}>
                {error || success}
              </div>
            )}
            <div className="space-y-4 rounded-lg border border-border/60 p-6">
              <div>
                <Label className="text-[13px]">配置名称</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="如：MiMo Production"
                  className="mt-1.5"
                />
              </div>
              <div>
                <Label className="text-[13px]">API Key</Label>
                <Input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={selectedId ? '编辑时需重新输入 API Key' : 'sk-...'}
                  className="mt-1.5"
                />
                {selectedId && (
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    为避免用遮蔽内容覆盖真实密钥，更新配置时需要重新输入 API Key。
                  </p>
                )}
              </div>
              <div>
                <Label className="text-[13px]">Base URL</Label>
                <Input
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  className="mt-1.5"
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label className="text-[13px]">模型</Label>
                  <Input
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="mt-1.5"
                  />
                </div>
                <div>
                  <Label className="text-[13px]">Temperature</Label>
                  <Input
                    value={temperature}
                    onChange={(e) => setTemperature(e.target.value)}
                    type="number"
                    step="0.1"
                    className="mt-1.5"
                  />
                </div>
              </div>
              <div>
                <Label className="text-[13px]">Max Tokens</Label>
                <Input
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(e.target.value)}
                  type="number"
                  className="mt-1.5"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                {selectedId && (
                  <Button
                    variant="outline"
                    onClick={resetForm}
                    className="h-9 px-4 text-[13px]"
                  >
                    取消编辑
                  </Button>
                )}
                <Button
                  onClick={handleSave}
                  disabled={saving || !name.trim() || !apiKey.trim()}
                  className="h-9 px-4 text-[13px]"
                >
                  {saving ? '保存中...' : '保存配置'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
