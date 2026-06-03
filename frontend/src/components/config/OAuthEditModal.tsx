import { useState, useEffect } from 'react'
import type { OAuthConnection } from '../../api/config'
import { oauthApi } from '../../api/config'

interface Props {
  oauth: OAuthConnection | null  // null = 新建模式
  onClose: () => void
  onSaved: () => void
}

interface ProviderTemplate {
  provider: string
  name: string
  icon?: string
  auth_type?: string
  config_fields?: string[]
  description?: string
}

export default function OAuthEditModal({ oauth, onClose, onSaved }: Props) {
  const isNew = !oauth

  const [provider, setProvider] = useState('')
  const [label, setLabel] = useState('')

  /** Provider 特定的配置键值对 */
  const [configValues, setConfigValues] = useState<Record<string, string>>({})
  const [providerTemplates, setProviderTemplates] = useState<ProviderTemplate[]>([])

  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok?: boolean; message?: string } | null>(null)
  const [error, setError] = useState('')

  // ── 挂载时加载 Provider 模板 ──────────────────────────
  useEffect(() => {
    oauthApi.getProviders().then(r => {
      setProviderTemplates(r.providers || [])
    }).catch(() => {})
  }, [])

  // ── 根据现有 oauth 或首次 provider 填充表单 ─────────
  useEffect(() => {
    if (oauth) {
      setProvider(oauth.provider)
      setLabel(oauth.label || '')
      if (oauth.config) {
        const entries: Record<string, string> = {}
        for (const [k, v] of Object.entries(oauth.config)) {
          // 排除 label（如果被历史数据错误写入了 config）
          if (k === 'label') continue
          entries[k] = typeof v === 'string' ? v : JSON.stringify(v)
        }
        setConfigValues(entries)
      }
    } else if (providerTemplates.length > 0 && !provider) {
      const first = providerTemplates[0].provider
      setProvider(first)
      _initConfigForProvider(first)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [oauth, providerTemplates])

  // ── 新建模式下切换 Provider 时重置 config ────────────
  useEffect(() => {
    if (isNew && provider) {
      _initConfigForProvider(provider)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider])

  function _initConfigForProvider(p: string) {
    const tmpl = providerTemplates.find(t => t.provider === p)
    if (!tmpl?.config_fields) return
    const next: Record<string, string> = {}
    for (const field of tmpl.config_fields) {
      // 敏感性字段提示默认值
      if (field.includes('secret') || field.includes('password') || field.includes('key')) {
        next[field] = ''
      } else {
        next[field] = ''
      }
    }
    setConfigValues(prev => {
      // 保留已有字段，补充缺失字段
      const merged = { ...next }
      for (const k of Object.keys(prev)) {
        if (next[k] !== undefined) merged[k] = prev[k]
      }
      return merged
    })
  }

  const currentTemplate = providerTemplates.find(t => t.provider === provider)
  const configFields = currentTemplate?.config_fields || []

  // ── 保存 ────────────────────────────────────────────
  const handleSave = async () => {
    if (!label.trim()) { setError('请输入名称'); return }
    if (isNew && !provider) { setError('请选择 Provider'); return }
    setSaving(true)
    setError('')
    try {
      // 过滤空值，构建 config
      const config: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(configValues)) {
        if (v.trim()) {
          try { config[k] = JSON.parse(v) } catch { config[k] = v }
        }
      }

      if (isNew) {
        await oauthApi.create({
          provider,
          label: label.trim(),
          config: Object.keys(config).length > 0 ? config : undefined,
        })
      } else {
        // 更新 provider 特定配置
        await oauthApi.updateConfig(oauth!.id, config)
      }
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  // ── 测试连接 ──────────────────────────────────────────
  const handleTest = async () => {
    if (!oauth) return
    setTesting(true)
    setTestResult(null)
    try {
      const result = await oauthApi.test(oauth.id)
      setTestResult({ ok: result.ok ?? false, message: result.message || result.error || '' })
    } catch (e) {
      setTestResult({ ok: false, message: e instanceof Error ? e.message : '测试失败' })
    } finally {
      setTesting(false)
    }
  }

  const handleDelete = async () => {
    if (!oauth || !window.confirm(`确定断开「${oauth.label || oauth.provider}」连接？`)) return
    setSaving(true)
    try {
      await oauthApi.delete(oauth.id)
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    } finally {
      setSaving(false)
    }
  }

  // 判断字段是否敏感（密钥类）
  const isSensitive = (field: string) =>
    /secret|password|token|key/i.test(field) && !/api_key_env|scope/i.test(field)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-[540px] max-h-[90vh] bg-white rounded-2xl shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-black/6 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-lg font-semibold text-[#1D1D1F]">
            {isNew ? '新建集成' : `编辑: ${oauth?.label || oauth?.provider}`}
          </h2>
          <button onClick={onClose} className="text-sm text-[#86868B] hover:text-[#1D1D1F]">✕</button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-lg bg-[#FF3B30]/5 border border-[#FF3B30]/20 text-sm text-[#FF3B30]">{error}</div>
          )}

          {/* Provider + 状态（编辑模式只读） */}
          {isNew ? (
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">Provider</label>
              <select
                value={provider}
                onChange={e => setProvider(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30 bg-white"
              >
                {providerTemplates.length === 0 && (
                  <option value="">加载中...</option>
                )}
                {providerTemplates.map(p => (
                  <option key={p.provider} value={p.provider}>
                    {p.icon || ''} {p.name} ({p.auth_type || 'oauth2'})
                  </option>
                ))}
              </select>
              {currentTemplate?.description && (
                <p className="text-[11px] text-[#86868B] mt-1">{currentTemplate.description}</p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-semibold text-[#86868B] block mb-1.5">Provider</label>
                <div className="text-sm text-[#1D1D1F] px-3 py-2 bg-[#F5F5F7] rounded-lg">
                  {currentTemplate?.icon || ''} {currentTemplate?.name || oauth.provider}
                </div>
              </div>
              <div>
                <label className="text-xs font-semibold text-[#86868B] block mb-1.5">状态</label>
                <div className={`text-sm font-semibold px-3 py-2 rounded-lg ${oauth.status === 'connected' ? 'bg-[#34C759]/10 text-[#34C759]' : 'bg-[#F5F5F7] text-[#86868B]'}`}>
                  {oauth.status === 'connected' ? '已连接' : oauth.status}
                </div>
              </div>
            </div>
          )}

          {/* 名称 */}
          <div>
            <label className="text-xs font-semibold text-[#86868B] block mb-1.5">
              名称 {isNew ? '' : '（仅供展示）'}
            </label>
            <input
              value={label}
              onChange={e => setLabel(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
              placeholder="连接名称"
              disabled={!isNew}
            />
            {!isNew && (
              <p className="text-[10px] text-[#C7C7CC] mt-1">名称创建后不可修改，如需更改请重新创建</p>
            )}
          </div>

          {/* Provider 动态配置字段 */}
          {configFields.length > 0 && (
            <div className="border-t border-black/6 pt-4">
              <label className="text-xs font-semibold text-[#86868B] block mb-3">
                {currentTemplate?.name || provider} 配置
              </label>
              <div className="space-y-3">
                {configFields.map(field => (
                  <div key={field}>
                    <label className="text-xs text-[#86868B] block mb-1">
                      {field.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      {isSensitive(field) && (
                        <span className="text-[#FF9F0A] ml-1">🔒 敏感</span>
                      )}
                    </label>
                    <input
                      type={isSensitive(field) ? 'password' : 'text'}
                      value={configValues[field] ?? ''}
                      onChange={e => setConfigValues(prev => ({ ...prev, [field]: e.target.value }))}
                      className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30 font-mono"
                      placeholder={isSensitive(field) ? '••••••••' : `输入 ${field}`}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 测试结果 */}
          {testResult && (
            <div className={`p-3 rounded-lg text-sm ${testResult.ok ? 'bg-[#34C759]/5 border border-[#34C759]/20 text-[#34C759]' : 'bg-[#FF3B30]/5 border border-[#FF3B30]/20 text-[#FF3B30]'}`}>
              {testResult.ok ? '连接测试成功 ✓' : `测试失败: ${testResult.message}`}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-black/6 px-6 py-4 flex items-center justify-between">
          <div className="flex gap-2">
            {!isNew && (
              <>
                <button
                  onClick={handleTest}
                  disabled={testing}
                  className="px-3 py-2 text-sm font-medium rounded-lg bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors disabled:opacity-40"
                >
                  {testing ? '测试中...' : '测试连接'}
                </button>
                <button
                  onClick={handleDelete}
                  disabled={saving}
                  className="px-3 py-2 text-sm font-medium rounded-lg bg-[#FF3B30]/10 text-[#FF3B30] hover:bg-[#FF3B30]/20 transition-colors disabled:opacity-40"
                >
                  断开
                </button>
              </>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button onClick={onClose} className="px-4 py-2 text-sm font-medium rounded-lg bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors">取消</button>
            <button
              onClick={handleSave}
              disabled={saving || !label.trim()}
              className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors disabled:opacity-40"
            >
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
