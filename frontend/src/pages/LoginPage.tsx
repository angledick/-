import { useState, FormEvent } from 'react'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#F5F5F7] to-[#E8E8ED]">
      <div className="bg-white rounded-2xl shadow-[0_8px_40px_rgba(0,0,0,0.12)] px-10 py-12 w-90">
        {/* Logo */}
        <div className="text-center mb-9">
          <div className="w-[52px] h-[52px] rounded-[14px] bg-gradient-to-br from-[#1D1D1F] to-[#424245] flex items-center justify-center text-white text-2xl font-bold mx-auto mb-3.5">
            A
          </div>
          <div className="font-bold text-xl text-[#1D1D1F]">避风港</div>
          <div className="text-[13px] text-[#86868B] mt-1">跨境合规智能体</div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-[13px] font-medium text-[#1D1D1F] mb-1.5">用户名</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="请输入用户名"
              autoFocus
              className="w-full px-3.5 py-2.5 rounded-[9px] border-[1.5px] border-black/10 text-sm outline-none font-[inherit] transition-colors focus:border-[#1D1D1F] box-border"
            />
          </div>

          <div className="mb-6">
            <label className="block text-[13px] font-medium text-[#1D1D1F] mb-1.5">密码</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="请输入密码"
              className="w-full px-3.5 py-2.5 rounded-[9px] border-[1.5px] border-black/10 text-sm outline-none font-[inherit] transition-colors focus:border-[#1D1D1F] box-border"
            />
          </div>

          {error && (
            <div className="mb-4 px-3.5 py-2.5 rounded-lg bg-[rgba(255,59,48,0.08)] text-[#FF3B30] text-[13px]">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={disabled}
            className={`w-full py-3 rounded-[10px] border-none text-[15px] font-semibold transition-all ${
              disabled
                ? 'bg-[#E5E5EA] text-[#86868B] cursor-not-allowed'
                : 'bg-[#1D1D1F] text-white cursor-pointer hover:opacity-90'
            }`}
          >
            {loading ? '登录中…' : '登录'}
          </button>
        </form>

        <div className="mt-5 text-center text-xs text-[#C7C7CC]">
          默认账号：admin / admin123
        </div>
      </div>
    </div>
  )
}
