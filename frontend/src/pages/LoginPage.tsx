import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-cream text-cream-foreground flex items-center justify-center px-6 py-20">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-12">
          <Link to="/" className="inline-block">
            <h1 className="font-serif text-4xl tracking-[0.3em] mb-2 text-cream-foreground">
              避风港
            </h1>
          </Link>
          <p className="text-xs uppercase tracking-[0.2em] text-cream-foreground/40">
            跨境合规智能体
          </p>
        </div>

        {/* Card */}
        <div className="border border-rule/10 p-8 md:p-12 bg-card">
          <h2 className="font-serif text-3xl tracking-tight mb-2 text-card-foreground">
            登录
          </h2>
          <p className="text-sm text-muted-foreground mb-8">
            输入您的凭据以访问您的账户
          </p>

          <AccountForm />

          <div className="mt-8 text-center text-sm text-muted-foreground">
            没有账户？{' '}
            <Link
              to="/auth/signup"
              className="text-cream-foreground hover:underline underline-offset-4"
            >
              创建账户
            </Link>
          </div>
        </div>

        {/* Back to home */}
        <div className="mt-8 text-center">
          <Link
            to="/"
            className="text-xs uppercase tracking-[0.2em] text-cream-foreground/60 hover:text-cream-foreground transition-colors"
          >
            返回首页
          </Link>
        </div>
      </div>
    </div>
  )
}

/* ─────────────────────────── Account form ─────────────────────────── */

function AccountForm() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) {
      toast.error('请输入用户名和密码')
      return
    }
    setLoading(true)
    try {
      await login(username.trim(), password)
      toast.success('登录成功')
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : '登录失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Field
        id="username"
        label="用户名"
        type="text"
        value={username}
        onChange={setUsername}
        placeholder="输入用户名"
        autoComplete="username"
      />
      <Field
        id="password"
        label="密码"
        type="password"
        value={password}
        onChange={setPassword}
        placeholder="输入密码"
        autoComplete="current-password"
      />

      <Button
        type="submit"
        disabled={loading}
        className="w-full bg-cream-foreground text-cream hover:bg-cream-foreground/85"
      >
        {loading ? '登录中...' : '登录'}
      </Button>
    </form>
  )
}

/* ─────────────────────────── Shared field ─────────────────────────── */

function Field({
  id,
  label,
  type,
  value,
  onChange,
  placeholder,
  autoComplete,
  inputMode,
  maxLength,
}: {
  id: string
  label: string
  type: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  autoComplete?: string
  inputMode?: 'text' | 'numeric' | 'tel' | 'email'
  maxLength?: number
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-xs uppercase tracking-[0.2em] text-cream-foreground/60 mb-2"
      >
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        inputMode={inputMode}
        maxLength={maxLength}
        placeholder={placeholder}
        className={cn(
          'w-full border-b border-cream-foreground/20 bg-transparent px-0 py-2 text-sm',
          'focus:outline-none focus:border-cream-foreground focus-visible:ring-1 focus-visible:ring-ring transition-colors',
          'placeholder:text-cream-foreground/30',
        )}
      />
    </div>
  )
}
