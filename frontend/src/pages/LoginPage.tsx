import { useState, FormEvent } from 'react'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin123')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    setLoading(true)
    setError('')
    try {
      await login(username.trim(), password)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '登录失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const disabled = loading || !username.trim() || !password.trim()

  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,#0F1720_0%,#16202C_42%,#EEF2F6_42%,#F6F8FA_100%)]">
      <div className="mx-auto grid min-h-screen max-w-[1280px] items-center gap-10 px-6 py-10 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="hidden lg:block text-white">
          <div className="max-w-[520px]">
            <div className="inline-flex rounded-full border border-white/12 bg-white/6 px-3 py-1 text-xs font-medium tracking-[0.12em] text-white/72 uppercase">
              SafeHarbor Console
            </div>
            <h1 className="mt-6 text-[56px] font-semibold tracking-[-0.06em] leading-[0.98]">
              跨境合规工作台
            </h1>
            <p className="mt-5 max-w-[54ch] text-[15px] leading-7 text-white/70">
              在一个控制台里查看产品状态、风险预警、关键词监控、知识库和 Agent 配置。先保证信息清晰，再做自动化执行。
            </p>
            <div className="mt-10 grid grid-cols-2 gap-4">
              {[
                ['产品合规', '管理产品、证书、健康度和生命周期状态'],
                ['风险监控', '查看情报流、预警列表和市场热力分布'],
                ['知识与记忆', '沉淀法规、上下文与系统推理依据'],
                ['配置中心', '统一管理 Agent、工具、技能和任务'],
              ].map(([title, desc]) => (
                <div key={title} className="rounded-3xl border border-white/10 bg-white/6 p-4 backdrop-blur-sm">
                  <div className="text-sm font-semibold text-white">{title}</div>
                  <div className="mt-2 text-sm leading-6 text-white/64">{desc}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="flex justify-center lg:justify-end">
          <div className="w-full max-w-[420px] rounded-[32px] border border-black/[0.06] bg-white px-7 py-8 shadow-[0_30px_80px_rgba(15,23,42,0.14)]">
            <div className="mb-8 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#111827] text-xl font-bold text-white shadow-[0_12px_24px_rgba(17,24,39,0.18)]">
                A
              </div>
              <div className="mt-4 text-[22px] font-semibold tracking-[-0.03em] text-[#111827]">登录避风港</div>
              <div className="mt-1 text-sm text-[#6B7280]">继续进入跨境合规工作台</div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-[#111827]">用户名</label>
                <input
                  type="text"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="请输入用户名"
                  autoFocus
                  className="h-12 w-full rounded-2xl border border-black/[0.08] bg-[#F9FAFB] px-4 text-sm outline-none transition focus:border-[#94A3B8] focus:bg-white focus:ring-4 focus:ring-[#E2E8F0]"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-[#111827]">密码</label>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  className="h-12 w-full rounded-2xl border border-black/[0.08] bg-[#F9FAFB] px-4 text-sm outline-none transition focus:border-[#94A3B8] focus:bg-white focus:ring-4 focus:ring-[#E2E8F0]"
                />
              </div>

              {error && (
                <div className="rounded-2xl border border-[#F5D0D6] bg-[#FFF5F7] px-4 py-3 text-sm text-[#B42318]">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={disabled}
                className={`inline-flex h-12 w-full items-center justify-center rounded-2xl text-sm font-semibold transition-all ${
                  disabled
                    ? 'cursor-not-allowed bg-[#E5E7EB] text-[#9CA3AF]'
                    : 'bg-[#111827] text-white hover:-translate-y-[1px] hover:bg-[#1F2937] hover:shadow-[0_16px_28px_rgba(17,24,39,0.16)]'
                }`}
              >
                {loading ? '登录中' : '进入系统'}
              </button>
            </form>

            <div className="mt-6 rounded-2xl border border-black/[0.06] bg-[#F9FAFB] px-4 py-3 text-sm text-[#6B7280]">
              默认账号 <span className="font-semibold text-[#111827]">admin</span> / <span className="font-semibold text-[#111827]">admin123</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
