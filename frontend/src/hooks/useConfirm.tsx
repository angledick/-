import { useCallback, useState, createContext, useContext, type ReactNode } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface ConfirmOptions {
  title: string
  description: string
  confirmLabel?: string
  variant?: 'default' | 'destructive'
}

type Resolver = (value: boolean) => void

interface ConfirmState extends ConfirmOptions {
  open: boolean
  resolve: Resolver | null
}

const ConfirmContext = createContext<((opts: ConfirmOptions) => Promise<boolean>) | null>(null)

/**
 * 全局 Confirm Provider — 替代 window.confirm() 的 shadcn Dialog 实现。
 * 在 main.tsx 顶层挂载一次，任意子组件通过 useConfirm() 调用。
 */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ConfirmState>({
    open: false,
    title: '',
    description: '',
    confirmLabel: '确认',
    variant: 'default',
    resolve: null,
  })

  const confirm = useCallback((opts: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      setState({
        open: true,
        title: opts.title,
        description: opts.description,
        confirmLabel: opts.confirmLabel || '确认',
        variant: opts.variant || 'default',
        resolve,
      })
    })
  }, [])

  const handleClose = (result: boolean) => {
    state.resolve?.(result)
    setState((s) => ({ ...s, open: false, resolve: null }))
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog open={state.open} onOpenChange={(open: boolean) => !open && handleClose(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{state.title}</DialogTitle>
            <DialogDescription>{state.description}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => handleClose(false)}>
              取消
            </Button>
            <Button
              onClick={() => handleClose(true)}
              variant={state.variant === 'destructive' ? 'destructive' : 'default'}
            >
              {state.confirmLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfirmContext.Provider>
  )
}

/**
 * 返回一个 confirm 函数，行为类似 window.confirm() 但使用 shadcn Dialog。
 *
 * @example
 * const confirm = useConfirm()
 * const ok = await confirm({ title: '删除', description: '确定删除吗？', variant: 'destructive' })
 * if (ok) { ... }
 */
export function useConfirm() {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm must be used inside <ConfirmProvider>')
  return ctx
}
