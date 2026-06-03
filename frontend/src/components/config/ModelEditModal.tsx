import { useState, useEffect } from 'react'
import type { ModelConfigItem } from '../../api/config'
import { modelConfigsApi } from '../../api/config'

interface Props {
  config: ModelConfigItem | null  // null = 新建模式
  onClose: () => void
  onSaved: () => void
}

const ROLE_OPTIONS = ['reasoning', 'fast', 'vision', 'embedding']
const PROVIDER_OPTIONS = ['openai', 'anthropic', 'google', 'azure', 'ollama', 'custom']

export default function ModelEditModal({ config, onClose, onSaved }: Props) {
  const isNew = !config

  const [role, setRole] = useState('fast')
  const [provider, setProvider] = useState('openai')
  const [model, setModel] = useState('')
  const [apiKeyEnv, setApiKeyEnv] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [maxTokens, setMaxTokens] = useState(4096)
  const [temperature, setTemperature] = useState(0.7)
  const [topP, setTopP] = useState(0.9)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (config) {
      setRole(config.role)
      setProvider(config.provider)
      setModel(config.model)
      setApiKeyEnv(config.api_key_env || '')
      setBaseUrl(config.base_url || '')
      setMaxTokens(config.max_tokens)
      setTemperature(config.temperature)
      setTopP(config.top_p ?? 0.9)
    }
  }, [config])

  const handleSave = async () => {
    if (!model.trim()) { setError('请输入模型名称'); return }
    setSaving(true)
    setError('')
    try {
      const payload = {
        role,
        provider,
        model: model.trim(),
        api_key_env: apiKeyEnv.trim(),
        base_url: baseUrl.trim() || undefined,
        max_tokens: maxTokens,
        temperature,
        top_p: topP,
      }
      if (isNew) {
        await modelConfigsApi.create(payload)
      } else {
        await modelConfigsApi.update(config!.role, payload)
      }
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-[520px] max-h-[85vh] bg-white rounded-2xl shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-black/6 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-lg font-semibold text-[#1D1D1F]">
            {isNew ? '新建模型配置' : `编辑模型: ${config?.role}`}
          </h2>
          <button onClick={onClose} className="text-sm text-[#86868B] hover:text-[#1D1D1F]">✕</button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-lg bg-[#FF3B30]/5 border border-[#FF3B30]/20 text-sm text-[#FF3B30]">{error}</div>
          )}

          {/* Role + Provider */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">Role</label>
              <select
                value={role}
                onChange={e => setRole(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30 bg-white"
              >
                {ROLE_OPTIONS.map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">Provider</label>
              <select
                value={provider}
                onChange={e => setProvider(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30 bg-white"
              >
                {PROVIDER_OPTIONS.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Model */}
          <div>
            <label className="text-xs font-semibold text-[#86868B] block mb-1.5">模型</label>
            <input
              value={model}
              onChange={e => setModel(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
              placeholder="gpt-4o, claude-3-opus, ..."
            />
          </div>

          {/* API Key Env + Base URL */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">API Key 环境变量</label>
              <input
                value={apiKeyEnv}
                onChange={e => setApiKeyEnv(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none font-mono focus:border-[#0071E3]/30"
                placeholder="OPENAI_API_KEY"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">Base URL</label>
              <input
                value={baseUrl}
                onChange={e => setBaseUrl(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
                placeholder="https://api.openai.com/v1"
              />
            </div>
          </div>

          {/* Max Tokens + Temperature */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">Max Tokens</label>
              <input
                type="number"
                value={maxTokens}
                onChange={e => setMaxTokens(parseInt(e.target.value) || 4096)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
                min={1}
                max={128000}
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">Temperature</label>
              <input
                type="number"
                step={0.1}
                value={temperature}
                onChange={e => setTemperature(parseFloat(e.target.value) || 0.7)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
                min={0}
                max={2}
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-[#86868B] block mb-1.5">Top P</label>
              <input
                type="number"
                step={0.1}
                value={topP}
                onChange={e => setTopP(parseFloat(e.target.value) || 0.9)}
                className="w-full px-3 py-2 rounded-lg border border-black/10 text-sm outline-none focus:border-[#0071E3]/30"
                min={0}
                max={1}
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-black/6 px-6 py-4 flex items-center justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium rounded-lg bg-[#F5F5F7] text-[#86868B] hover:bg-[#E5E5EA] transition-colors">取消</button>
          <button
            onClick={handleSave}
            disabled={saving || !model.trim()}
            className="px-4 py-2 text-sm font-semibold rounded-lg bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors disabled:opacity-40"
          >
            {saving ? '保存中...' : isNew ? '创建' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}
