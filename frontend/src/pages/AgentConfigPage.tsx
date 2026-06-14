import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '@/hooks/useConfirm'
import { cn } from '@/lib/utils'

const API = '/api/v1'

interface AgentListItem {
  id: string
  name: string
  type: string
  description: string
  system_prompt_preview: string
  enabled: boolean
  sort_order: number
  created_at: number
  updated_at: number
}

interface AgentDetail extends AgentListItem {
  system_prompt: string
}

// 内置 Agent 类型标签
const TYPE_LABELS: Record<string, { label: string; className: string }> = {
  general:       { label: '通用合规', className: 'text-blue-600 bg-blue-600/10 dark:text-blue-400 dark:bg-blue-400/10' },
  export_law:    { label: '出境法律', className: 'text-red-600 bg-red-600/10 dark:text-red-400 dark:bg-red-400/10' },
  tax:           { label: '税务',     className: 'text-orange-600 bg-orange-600/10 dark:text-orange-400 dark:bg-orange-400/10' },
  culture:       { label: '民俗文化', className: 'text-green-600 bg-green-600/10 dark:text-green-400 dark:bg-green-400/10' },
  certification: { label: '认证标准', className: 'text-purple-600 bg-purple-600/10 dark:text-purple-400 dark:bg-purple-400/10' },
  custom:        { label: '自定义',   className: 'text-muted-foreground bg-muted' },
}

function getTypeInfo(type: string) {
  if (type in TYPE_LABELS) return TYPE_LABELS[type]!
  if (type.startsWith('custom')) return TYPE_LABELS.custom!
  return TYPE_LABELS.custom!
}

// 内置不可删除的 Agent id
const BUILTIN_IDS = new Set(['agent_general','agent_export_law','agent_tax','agent_culture','agent_cert'])

const EMPTY_FORM = {
  name: '',
  type: 'custom',
  description: '',
  system_prompt: '',
  enabled: true,
  sort_order: 99,
}

export default function AgentConfigPage() {
  const { authFetch, isAdmin } = useAuth()
  const confirm = useConfirm()
  const [agents, setAgents] = useState<AgentListItem[]>([])
  const [selected, setSelected] = useState<AgentDetail | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [saving, setSaving] = useState(false)

  const loadAgents = useCallback(async () => {
    const res = await authFetch(`${API}/agents`)
    if (res.ok) setAgents(await res.json())
  }, [authFetch])

  useEffect(() => { loadAgents() }, [])  // eslint-disable-line

  const openAgent = async (id: string) => {
    setIsNew(false)
    const res = await authFetch(`${API}/agents/${id}`)
    if (res.ok) {
      const data: AgentDetail = await res.json()
      setSelected(data)
      setForm({
        name: data.name,
        type: data.type,
        description: data.description,
        system_prompt: data.system_prompt,
        enabled: data.enabled,
        sort_order: data.sort_order,
      })
    }
  }

  const newAgent = () => {
    setIsNew(true)
    setSelected(null)
    setForm({ ...EMPTY_FORM })
  }

  const handleSave = async () => {
    if (!isAdmin) return
    if (!form.name.trim() || !form.system_prompt.trim()) {
      toast.error('名称和 System Prompt 不能为空')
      return
    }
    setSaving(true)
    try {
      const url = isNew ? `${API}/agents` : `${API}/agents/${selected?.id}`
      const method = isNew ? 'POST' : 'PUT'
      const res = await authFetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const e = await res.json().catch(() => ({}))
        throw new Error(e.detail || '保存失败')
      }
      const saved: AgentDetail = await res.json()
      toast.success('保存成功')
      setIsNew(false)
      setSelected(saved)
      await loadAgents()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (id: string, enabled: boolean) => {
    if (!isAdmin) return
    await authFetch(`${API}/agents/${id}/toggle`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
    await loadAgents()
    if (selected?.id === id) setSelected(prev => prev ? { ...prev, enabled } : null)
  }

  const handleDelete = async (id: string, name: string) => {
    if (!isAdmin) return

    // 使用 toast.promise 显示确认对话框
    const confirmed = await confirm({ title: '删除 Agent', description: `确认删除 Agent「${name}」？内置 Agent 无法删除。`, variant: 'destructive' })
    if (!confirmed) return

    toast.promise(
      authFetch(`${API}/agents/${id}`, { method: 'DELETE' }),
      {
        loading: '删除中...',
        success: async (res) => {
          if (res.ok) {
            if (selected?.id === id) {
              setSelected(null)
              setForm({ ...EMPTY_FORM })
            }
            await loadAgents()
            return `已删除 ${name}`
          } else {
            const e = await res.json().catch(() => ({}))
            throw new Error(e.detail || '删除失败（内置 Agent 不可删除）')
          }
        },
        error: (err) => err.message || '删除失败',
      }
    )
  }

  const currentTitle = isNew ? '新建 Agent' : (selected?.name || 'Agent 配置')

  return (
    <div className="flex h-full bg-background">
      {/* 左栏 */}
      <div className="flex w-[280px] shrink-0 flex-col border-r border-border/60 bg-card">
        <div className="px-3 pb-2 pt-4">
          <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Agent 列表
          </div>
          {isAdmin && (
            <button
              onClick={newAgent}
              className="flex h-9 w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-border/80 text-[13px] font-medium text-foreground transition-colors hover:bg-muted/40"
            >
              <span>+</span> 新建自定义 Agent
            </button>
          )}
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px 16px' }}>
          {agents.map(a => {
            const ti = getTypeInfo(a.type)
            const active = !isNew && selected?.id === a.id
            return (
              <div
                key={a.id}
                onClick={() => openAgent(a.id)}
                style={{
                  padding: '10px 12px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  background: active ? '#EBEBED' : 'transparent',
                  marginBottom: 2,
                  transition: 'background 0.12s',
                  opacity: a.enabled ? 1 : 0.5,
                }}
                onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'rgba(0,0,0,0.04)' }}
                onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span className={cn(
                    'px-1.5 py-0.5 rounded text-[10px] font-semibold shrink-0',
                    ti.className
                  )}>
                    {ti.label}
                  </span>
                  <span style={{
                    fontSize: 12, fontWeight: active ? 600 : 400, color: '#1D1D1F',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {a.name}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: '#86868B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {a.system_prompt_preview}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 右栏 */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 标题栏 */}
        <div className="flex shrink-0 items-center justify-between border-b border-border/60 bg-background px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div>
              <h1 className="text-[15px] font-semibold text-foreground">{currentTitle}</h1>
              {selected && (
                <div className="text-[11px] text-muted-foreground">
                  {selected.enabled ? '已启用' : '已禁用'} · {getTypeInfo(selected.type).label}
                </div>
              )}
            </div>
          </div>

          {isAdmin && (selected || isNew) && (
            <div style={{ display: 'flex', gap: 8 }}>
              {selected && (
                <button
                  onClick={() => handleToggle(selected.id, !selected.enabled)}
                  style={{
                    padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 500,
                    border: '1.5px solid rgba(0,0,0,0.12)', background: 'transparent',
                    cursor: 'pointer', fontFamily: 'inherit',
                    color: selected.enabled ? '#FF3B30' : '#34C759',
                  }}
                >
                  {selected.enabled ? '禁用' : '启用'}
                </button>
              )}
              <button
                onClick={handleSave}
                disabled={saving}
                style={{
                  padding: '7px 16px', borderRadius: 8, border: 'none',
                  background: '#1D1D1F', color: '#FFF',
                  fontSize: 13, fontWeight: 500, cursor: saving ? 'wait' : 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                {saving ? '保存中…' : '保存'}
              </button>
              {selected && !BUILTIN_IDS.has(selected.id) && (
                <button
                  onClick={() => handleDelete(selected.id, selected.name)}
                  style={{
                    padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 500,
                    border: '1.5px solid rgba(255,59,48,0.3)', background: 'transparent',
                    cursor: 'pointer', fontFamily: 'inherit', color: '#FF3B30',
                  }}
                >
                  删除
                </button>
              )}
            </div>
          )}
        </div>

        {/* 表单区 */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
          {!(selected || isNew) ? (
            <div style={{ textAlign: 'center', padding: 60, color: '#86868B' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🤖</div>
              <div>从左侧选择 Agent 查看或编辑配置</div>
            </div>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, maxWidth: 800 }}>
                {/* 名称 */}
                <Field label="Agent 名称">
                  <input
                    value={form.name}
                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="如：出境法律 Agent"
                    readOnly={!isAdmin}
                    style={inputStyle}
                  />
                </Field>

                {/* 类型 */}
                <Field label="Agent 类型">
                  {BUILTIN_IDS.has(selected?.id || '') ? (
                    <div style={{
                      ...inputStyle,
                      display: 'flex', alignItems: 'center', gap: 8,
                      background: '#F5F5F7',
                    }}>
                      <span className={cn(
                        'px-2 py-0.5 rounded text-[11px] font-semibold',
                        getTypeInfo(form.type).className
                      )}>
                        {getTypeInfo(form.type).label}
                      </span>
                      <span style={{ fontSize: 13, color: '#86868B' }}>{form.type}</span>
                    </div>
                  ) : (
                    <input
                      value={form.type}
                      onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
                      placeholder="custom_xxx"
                      readOnly={!isAdmin}
                      style={inputStyle}
                    />
                  )}
                </Field>

                {/* 描述 */}
                <Field label="功能描述" span={2}>
                  <input
                    value={form.description}
                    onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                    placeholder="简要描述该 Agent 的职责范围"
                    readOnly={!isAdmin}
                    style={inputStyle}
                  />
                </Field>
              </div>

              {/* System Prompt */}
              <div style={{ maxWidth: 800, marginTop: 16 }}>
                <Field label="System Prompt（发送给大模型的角色指令）">
                  <div style={{ position: 'relative' }}>
                    <textarea
                      value={form.system_prompt}
                      onChange={e => setForm(f => ({ ...f, system_prompt: e.target.value }))}
                      readOnly={!isAdmin}
                      rows={16}
                      placeholder="输入该 Agent 的系统提示词，定义 AI 的角色、专业领域、回答风格和输出格式..."
                      style={{
                        width: '100%',
                        padding: '12px 14px',
                        borderRadius: 10,
                        border: '1.5px solid rgba(0,0,0,0.1)',
                        fontSize: 13,
                        outline: 'none',
                        resize: 'vertical',
                        fontFamily: '"SF Mono", "Cascadia Code", "Fira Code", monospace',
                        lineHeight: 1.6,
                        boxSizing: 'border-box',
                        background: isAdmin ? '#FFF' : '#F9F9FB',
                        color: '#1D1D1F',
                        minHeight: 320,
                      }}
                    />
                    <div style={{
                      position: 'absolute', bottom: 8, right: 12,
                      fontSize: 11, color: '#C7C7CC',
                    }}>
                      {form.system_prompt.length} 字符
                    </div>
                  </div>
                </Field>
              </div>

              {/* 提示说明 */}
              <div style={{
                maxWidth: 800, marginTop: 16,
                padding: '12px 16px',
                borderRadius: 10,
                background: 'rgba(0,113,227,0.05)',
                border: '1px solid rgba(0,113,227,0.12)',
                fontSize: 12,
                color: '#0071E3',
                lineHeight: 1.6,
              }}>
                <strong>💡 System Prompt 编写提示</strong>
                <ul style={{ margin: '6px 0 0 16px', padding: 0 }}>
                  <li><strong>通用合规 Agent</strong>：需在末尾加 JSON 输出格式要求（product / target_country / action / confidence）</li>
                  <li><strong>专项 Agent</strong>：清晰定义专业领域边界，避免越权回答</li>
                  <li><strong>输出格式</strong>：建议明确指定回答语言、结构和详略程度</li>
                  <li>修改通用合规 Agent 的 System Prompt 将影响所有用户的合规查询行为</li>
                </ul>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── 工具组件 ──────────────────────────────────────────────────────────────────

function Field({ label, children, span = 1 }: { label: string; children: React.ReactNode; span?: number }) {
  return (
    <div style={{ gridColumn: `span ${span}` }}>
      <label style={{
        display: 'block', fontSize: 11, fontWeight: 600, color: '#86868B',
        marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em',
      }}>
        {label}
      </label>
      {children}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '9px 12px',
  borderRadius: 8,
  border: '1.5px solid rgba(0,0,0,0.1)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
  fontFamily: 'inherit',
  background: '#FFF',
}
