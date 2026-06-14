import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function ShopifyCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const handledRef = useRef(false)
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (handledRef.current) return
    handledRef.current = true

    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const shop = searchParams.get('shop')

    if (!code || !state || !shop) {
      setStatus('error')
      setMessage('缺少必要参数')
      return
    }

    const timestamp = searchParams.get('timestamp') || ''
    const hmac = searchParams.get('hmac') || ''
    const params = new URLSearchParams({ code, state, shop, timestamp, hmac })

    fetch(`/api/v1/shopify/callback?${params}`)
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
      .then(() => {
        setStatus('success')
        setMessage('Shopify 店铺连接成功')
      })
      .catch((err: Error) => {
        setStatus('error')
        setMessage(err.message || '连接失败')
      })
  }, [searchParams])

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md space-y-4 rounded-lg border p-6 text-center">
        {status === 'loading' && (
          <>
            <Loader2 className="mx-auto size-12 animate-spin text-primary" />
            <h2 className="text-lg font-medium">正在连接 Shopify...</h2>
            <p className="text-sm text-muted-foreground">请稍候</p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle2 className="mx-auto size-12 text-green-500" />
            <h2 className="text-lg font-medium">{message}</h2>
            <Button onClick={() => navigate('/app/chat')}>返回首页</Button>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle className="mx-auto size-12 text-destructive" />
            <h2 className="text-lg font-medium">连接失败</h2>
            <p className="text-sm text-muted-foreground">{message}</p>
            <Button variant="outline" onClick={() => navigate('/app/chat')}>
              返回首页
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
