import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const API = '/api/v1'

export default function RegisterPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    if (!username.trim() || !email.trim() || !password) {
      toast.error('请填写完整注册信息')
      return
    }
    if (!/^[\w.-]+@[\w-]+(\.[\w-]+)+$/.test(email)) {
      toast.error('邮箱格式不正确')
      return
    }
    if (password.length < 8) {
      toast.error('密码至少 8 位')
      return
    }
    if (password !== confirm) {
      toast.error('两次输入的密码不一致')
      return
    }

    const nextUsername = username.trim()
    setSubmitting(true)
    try {
      const res = await fetch(`${API}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: nextUsername,
          email: email.trim(),
          password,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || '注册失败')
      }
      await login(nextUsername, password)
      toast.success('注册成功')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '注册失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

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
            创建您的账户
          </p>
        </div>

        {/* Card */}
        <div className="border border-rule/10 p-8 md:p-12 bg-card">
          <h2 className="font-serif text-3xl tracking-tight mb-2 text-card-foreground">
            注册
          </h2>
          <p className="text-sm text-muted-foreground mb-8">
            几秒钟即可开启跨境合规之旅
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <Field
              id="reg-username"
              label="用户名"
              type="text"
              value={username}
              onChange={setUsername}
              placeholder="3-20 位字母 / 数字 / 下划线"
              autoComplete="username"
            />
            <Field
              id="reg-email"
              label="邮箱"
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="name@company.com"
              autoComplete="email"
              inputMode="email"
            />
            <Field
              id="reg-password"
              label="密码"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="至少 8 位"
              autoComplete="new-password"
            />
            <Field
              id="reg-confirm"
              label="确认密码"
              type="password"
              value={confirm}
              onChange={setConfirm}
              placeholder="再次输入密码"
              autoComplete="new-password"
            />

            <Button
              type="submit"
              disabled={submitting}
              className="w-full bg-cream-foreground text-cream hover:bg-cream-foreground/85"
            >
              {submitting ? '提交中...' : '创建账户'}
            </Button>
          </form>

          <div className="mt-8 text-center text-sm text-muted-foreground">
            已有账户？{' '}
            <Link
              to="/auth/login"
              className="text-cream-foreground hover:underline underline-offset-4"
            >
              直接登录
            </Link>
          </div>
        </div>

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

function Field({
  id,
  label,
  type,
  value,
  onChange,
  placeholder,
  autoComplete,
  inputMode,
}: {
  id: string
  label: string
  type: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  autoComplete?: string
  inputMode?: 'text' | 'numeric' | 'tel' | 'email'
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
        placeholder={placeholder}
        className={cn(
          'w-full border-b border-cream-foreground/20 bg-transparent px-0 py-2 text-sm',
          'focus:outline-none focus:border-cream-foreground transition-colors',
          'placeholder:text-cream-foreground/30',
        )}
      />
    </div>
  )
}
