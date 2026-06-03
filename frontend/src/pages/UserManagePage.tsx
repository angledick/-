import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'

interface UserInfo {
  id: string
  username: string
  role: 'admin' | 'user'
  created_at: number
}

export default function UserManagePage() {
  const { authFetch, user: me } = useAuth()
  const [users, setUsers] = useState<UserInfo[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<'admin' | 'user'>('user')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const loadUsers = useCallback(async () => {
    const res = await authFetch('/api/v1/users')
    if (res.ok) setUsers(await res.json())
  }, [authFetch])

  useEffect(() => { loadUsers() }, [])  // eslint-disable-line

  const handleCreate = async () => {
    if (!newUsername.trim() || !newPassword.trim()) return
    setCreating(true)
    setError(null)
    try {
      const res = await authFetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: newUsername.trim(), password: newPassword, role: newRole }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || '创建失败')
      }
      setSuccess(`用户 ${newUsername} 已创建`)
      setShowCreate(false)
      setNewUsername('')
      setNewPassword('')
      setNewRole('user')
      await loadUsers()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (userId: string, username: string) => {
    if (!window.confirm(`确认删除用户 ${username}？`)) return
    const res = await authFetch(`/api/v1/users/${userId}`, { method: 'DELETE' })
    if (res.ok) {
      setSuccess(`用户 ${username} 已删除`)
      await loadUsers()
    }
  }

  const handleRoleChange = async (userId: string, role: string) => {
    const res = await authFetch(`/api/v1/users/${userId}/role`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    })
    if (res.ok) await loadUsers()
  }

  return (
    <div className="h-full bg-[#F5F5F7] overflow-y-auto">
      {/* 标题栏 */}
      <div className="px-6 py-3.5 bg-white border-b border-black/[0.06] flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-2.5">
          <span className="text-lg">👥</span>
          <div>
            <div className="font-semibold text-[15px] text-[#1D1D1F]">用户管理</div>
            <div className="text-[11px] text-[#86868B]">{users.length} 个用户</div>
          </div>
        </div>
        <button
          onClick={() => { setShowCreate(true); setError(null) }}
          className="px-4 py-2 rounded-lg border-none bg-[#1D1D1F] text-white text-[13px] font-medium cursor-pointer font-[inherit] hover:opacity-90 transition-opacity"
        >
          ＋ 新建用户
        </button>
      </div>

      <div className="p-6">
        {(error || success) && (
          <div className={`mb-4 px-3.5 py-2.5 rounded-lg text-[13px] ${
            error ? 'bg-[rgba(255,59,48,0.08)] text-[#FF3B30]' : 'bg-[rgba(52,199,89,0.08)] text-[#1C7A37]'
          }`}>
            {error || success}
          </div>
        )}

        {/* 用户列表 */}
        <div className="bg-white rounded-xl overflow-hidden shadow-[0_1px_4px_rgba(0,0,0,0.06)]">
          {/* 表头 */}
          <div className="grid grid-cols-[1fr_140px_120px_120px] px-5 py-2.5 border-b border-black/[0.06] text-[11px] font-semibold text-[#86868B] uppercase tracking-wider">
            <span>用户名</span>
            <span>角色</span>
            <span>创建时间</span>
            <span></span>
          </div>

          {users.map(u => (
            <div key={u.id} className="grid grid-cols-[1fr_140px_120px_120px] px-5 py-3.5 border-b border-black/[0.04] items-center">
              <div className="flex items-center gap-2.5">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-semibold ${
                  u.role === 'admin' ? 'bg-[#1D1D1F] text-white' : 'bg-[#E5E5EA] text-[#1D1D1F]'
                }`}>
                  {u.username[0].toUpperCase()}
                </div>
                <div>
                  <div className="text-sm font-medium text-[#1D1D1F]">
                    {u.username}
                    {u.id === me?.id && <span className="ml-1.5 text-[11px] text-[#0071E3]">（你）</span>}
                  </div>
                  <div className="text-[11px] text-[#86868B]">{u.id.slice(0, 8)}…</div>
                </div>
              </div>

              {/* 角色切换 */}
              <div>
                {u.id === me?.id ? (
                  <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                    u.role === 'admin' ? 'bg-black/[0.08] text-[#1D1D1F]' : 'bg-[#0071E3]/[0.08] text-[#0071E3]'
                  }`}>
                    {u.role}
                  </span>
                ) : (
                  <select
                    value={u.role}
                    onChange={e => handleRoleChange(u.id, e.target.value)}
                    className="px-2 py-1 rounded-md border-[1.5px] border-black/10 text-xs font-[inherit] bg-white cursor-pointer"
                  >
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                )}
              </div>

              <div className="text-xs text-[#86868B]">
                {new Date(u.created_at * 1000).toLocaleDateString('zh-CN')}
              </div>

              <div>
                {u.id !== me?.id && (
                  <button
                    onClick={() => handleDelete(u.id, u.username)}
                    className="px-3 py-1 rounded-md border border-[rgba(255,59,48,0.3)] bg-transparent text-[#FF3B30] text-xs cursor-pointer font-[inherit] hover:bg-[rgba(255,59,48,0.05)] transition-colors"
                  >
                    删除
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* 新建用户弹窗 */}
        {showCreate && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[100]">
            <div className="bg-white rounded-[14px] px-8 py-7 w-90 shadow-[0_20px_60px_rgba(0,0,0,0.15)]">
              <div className="font-bold text-[17px] mb-5">新建用户</div>

              <label className="block text-xs font-semibold text-[#86868B] mb-1 mt-3 uppercase tracking-wider">用户名</label>
              <input
                value={newUsername}
                onChange={e => setNewUsername(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border-[1.5px] border-black/10 text-[13px] outline-none font-[inherit] box-border"
                placeholder="输入用户名"
                autoFocus
              />

              <label className="block text-xs font-semibold text-[#86868B] mb-1 mt-3 uppercase tracking-wider">密码</label>
              <input
                type="password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border-[1.5px] border-black/10 text-[13px] outline-none font-[inherit] box-border"
                placeholder="至少 6 位"
              />

              <label className="block text-xs font-semibold text-[#86868B] mb-1 mt-3 uppercase tracking-wider">角色</label>
              <select
                value={newRole}
                onChange={e => setNewRole(e.target.value as 'admin' | 'user')}
                className="w-full px-3 py-2 rounded-lg border-[1.5px] border-black/10 text-[13px] outline-none font-[inherit] box-border"
              >
                <option value="user">user（普通用户）</option>
                <option value="admin">admin（管理员）</option>
              </select>

              {error && <div className="text-[#FF3B30] text-[13px] mt-2.5">{error}</div>}

              <div className="flex gap-2.5 mt-5 justify-end">
                <button
                  onClick={() => { setShowCreate(false); setError(null) }}
                  className="px-4 py-2 rounded-lg border-[1.5px] border-black/[0.12] bg-transparent cursor-pointer font-[inherit] text-[13px] hover:bg-[#F5F5F7] transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleCreate}
                  disabled={creating || !newUsername.trim() || !newPassword.trim()}
                  className="px-4 py-2 rounded-lg border-none bg-[#1D1D1F] text-white cursor-pointer font-[inherit] text-[13px] font-medium hover:opacity-90 transition-opacity disabled:bg-[#E5E5EA] disabled:text-[#86868B] disabled:cursor-not-allowed"
                >
                  {creating ? '创建中…' : '创建'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
