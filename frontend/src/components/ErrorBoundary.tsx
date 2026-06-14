import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

const CHUNK_RETRY_KEY = 'astra:chunk-load-retry-at'

function isChunkLoadError(error: Error | null) {
  const message = error?.message || ''
  return /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Loading chunk .* failed/i.test(message)
}

function reloadWithFreshAssets() {
  const url = new URL(window.location.href)
  url.searchParams.set('_r', String(Date.now()))
  window.location.replace(url.toString())
}

/**
 * 顶层 Error Boundary — 捕获渲染时异常，防止白屏。
 * 用法：包裹 Route 或整个 App。
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
    if (!isChunkLoadError(error)) return

    const lastRetryAt = Number(window.sessionStorage.getItem(CHUNK_RETRY_KEY) || 0)
    const now = Date.now()
    if (now - lastRetryAt > 10_000) {
      window.sessionStorage.setItem(CHUNK_RETRY_KEY, String(now))
      reloadWithFreshAssets()
    }
  }

  handleReset = () => {
    if (isChunkLoadError(this.state.error)) {
      reloadWithFreshAssets()
      return
    }
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div className="flex min-h-[400px] flex-col items-center justify-center gap-4 px-6 text-center">
          <div className="flex size-14 items-center justify-center rounded-full bg-destructive/10">
            <AlertTriangle className="size-7 text-destructive" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">页面出现了意外错误</h2>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">
              {this.state.error?.message || '渲染组件时发生未知错误'}
            </p>
          </div>
          <Button
            variant="outline"
            onClick={this.handleReset}
            className="gap-2"
          >
            <RefreshCw className="size-4" />
            {isChunkLoadError(this.state.error) ? '刷新页面' : '重试'}
          </Button>
        </div>
      )
    }
    return this.props.children
  }
}
