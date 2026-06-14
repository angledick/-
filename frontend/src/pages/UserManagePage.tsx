import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '@/hooks/useConfirm'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

const API = '/api/v1'

interface UserInfo {
  id: string
  username: string
  role: 'admin' | 'user'
  created_at: number
}

const ROLE_OPTIONS: Array<{ value: UserInfo['role']; label: string }> = [
  { value: 'user', label: 'user' },
  { value: 'admin', label: 'admin' },
]

export default function UserManagePage() {
  const { authFetch, user: me } = useAuth()
  const confirm = useConfirm()
  const [users, setUsers] = useState<UserInfo[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<'admin' | 'user'>('user')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const loadUsers = useCallback(async () => {
    const res = await authFetch(`${API}/users`)
    if (res.ok) setUsers(await res.json())
  }, [authFetch])

  useEffect(() => { loadUsers() }, [loadUsers])

  const handleCreate = async () => {
    if (!newUsername.trim() || !newPassword.trim()) return
    setCreating(true)
    setError(null)
    try {
      const res = await authFetch(`${API}/auth/register`, {
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
    if (!(await confirm({ title: '删除用户', description: `确认删除用户 ${username}？`, variant: 'destructive' }))) return
    const res = await authFetch(`${API}/users/${userId}`, { method: 'DELETE' })
    if (res.ok) {
      setSuccess(`用户 ${username} 已删除`)
      await loadUsers()
    }
  }

  const handleRoleChange = async (userId: string, newRole: string) => {
    const res = await authFetch(`${API}/users/${userId}/role`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: newRole }),
    })
    if (res.ok) await loadUsers()
  }

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="border-b border-border/60 bg-background">
        <div className="mx-auto max-w-[1400px] px-8 py-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-[28px] font-semibold tracking-tight">用户管理</h1>
              <p className="mt-1 text-[14px] text-muted-foreground/80">{users.length} 个用户</p>
            </div>
            <Button
              onClick={() => { setShowCreate(true); setError(null) }}
              className="h-9 rounded-md px-4 text-[13px] font-medium"
            >
              新建用户
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-[1400px] px-8 py-8">
        {(error || success) && (
          <div className={cn(
            'mb-6 rounded-lg p-3 text-[13px]',
            error && 'bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-400',
            success && 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400',
          )}>
            {error || success}
          </div>
        )}

        {/* Users Table */}
        <div className="overflow-hidden rounded-lg border border-border/60">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border/60 bg-muted/30">
                <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  用户名
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  角色
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  创建时间
                </th>
                <th className="px-4 py-3 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {users.map((u) => (
                <tr key={u.id} className="transition-colors hover:bg-muted/30">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex size-7 items-center justify-center rounded-full bg-muted text-[11px] font-medium">
                        {u.username?.[0]?.toUpperCase() ?? '?'}
                      </div>
                      <div>
                        <div className="text-[13px] font-medium">
                          {u.username}
                          {u.id === me?.id && (
                            <span className="ml-1.5 text-[11px] text-primary">（你）</span>
                          )}
                        </div>
                        <div className="text-[11px] text-muted-foreground">{u.id.slice(0, 12)}…</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {u.id === me?.id ? (
                      <Badge
                        variant="secondary"
                        className={cn(
                          'text-[11px] font-medium',
                          u.role === 'admin' && 'bg-primary/10 text-primary',
                        )}
                      >
                        {u.role}
                      </Badge>
                    ) : (
                      <Select
                        value={u.role}
                        onValueChange={(role) => handleRoleChange(u.id, role)}
                      >
                        <SelectTrigger
                          aria-label={`${u.username} 的角色`}
                          className="h-8 w-[104px] border-border/60 bg-background px-2 text-[12px] font-normal shadow-none transition-colors hover:border-foreground/30 focus:border-foreground/40 focus:ring-0 [&>svg]:size-3.5 [&>svg]:text-muted-foreground [&>svg]:opacity-100"
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent
                          align="start"
                          position="item-aligned"
                          className="w-[104px] rounded-md border-border/70 p-1 shadow-lg shadow-black/5"
                        >
                          {ROLE_OPTIONS.map((role) => (
                            <SelectItem
                              key={role.value}
                              value={role.value}
                              className="h-8 rounded-[5px] pl-2 pr-7 text-[12px] focus:bg-muted"
                            >
                              {role.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[13px] text-muted-foreground">
                    {new Date(u.created_at * 1000).toLocaleDateString('zh-CN', {
                      year: 'numeric',
                      month: '2-digit',
                      day: '2-digit',
                    })}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {u.id !== me?.id && (
                      <button
                        onClick={() => handleDelete(u.id, u.username)}
                        className="text-[13px] text-muted-foreground transition-colors hover:text-destructive"
                      >
                        删除
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {users.length <= 1 && (
          <div className="mt-4 rounded-lg border border-dashed border-border/70 bg-muted/20 px-4 py-3">
            <div className="text-[13px] font-medium">当前只有一个管理员账号</div>
            <p className="mt-1 text-[12px] leading-5 text-muted-foreground">
              可以在需要多人协作时新建普通成员，或保留单账号用于本地开发和演示。
            </p>
          </div>
        )}
      </div>

      {/* Create User Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建用户</DialogTitle>
            <DialogDescription>
              创建可登录避风港后台的成员账号，并分配初始角色。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <div>
              <Label htmlFor="username" className="text-[13px]">用户名</Label>
              <Input
                id="username"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                className="mt-1.5"
                autoFocus
              />
            </div>
            <div>
              <Label htmlFor="password" className="text-[13px]">密码</Label>
              <Input
                id="password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="mt-1.5"
              />
            </div>
            <div>
              <Label htmlFor="role" className="text-[13px]">角色</Label>
              <Select
                value={newRole}
                onValueChange={(role) => setNewRole(role as UserInfo['role'])}
              >
                <SelectTrigger
                  id="role"
                  className="mt-1.5 h-10 w-full border-border/60 bg-background px-3 text-[14px] font-normal shadow-none transition-colors hover:border-foreground/30 focus:border-foreground/40 focus:ring-0 [&>svg]:text-muted-foreground [&>svg]:opacity-100"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent
                  position="item-aligned"
                  className="rounded-md border-border/70 p-1 shadow-lg shadow-black/5"
                >
                  {ROLE_OPTIONS.map((role) => (
                    <SelectItem
                      key={role.value}
                      value={role.value}
                      className="h-8 rounded-[5px] pl-3 pr-8 text-[14px] focus:bg-muted"
                    >
                      {role.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button>
              <Button onClick={handleCreate} disabled={creating || !newUsername.trim() || !newPassword.trim()}>
                {creating ? '创建中...' : '创建'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
