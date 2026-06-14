import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Send, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

interface Props {
  onSend: (text: string) => Promise<void> | void
  sending: boolean
  placeholder?: string
  footer?: string
}

export function ChatComposer({ onSend, sending, placeholder, footer }: Props) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const t = setTimeout(() => ref.current?.focus(), 80)
    return () => clearTimeout(t)
  }, [])

  const canSend = text.trim().length > 0 && !sending

  const handleSend = async () => {
    if (!canSend) return
    const value = text.trim()
    setText('')
    requestAnimationFrame(() => {
      if (ref.current) {
        ref.current.style.height = '32px'
      }
    })
    await onSend(value)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e: React.FormEvent<HTMLTextAreaElement>) => {
    const el = e.currentTarget
    el.style.height = 'auto'
    el.style.height = Math.min(Math.max(el.scrollHeight, 32), 112) + 'px'
  }

  return (
    <div className="mx-auto w-full max-w-[660px] space-y-1.5">
      <div
        className={cn(
          'relative flex min-h-[52px] items-end gap-2 rounded-full border bg-background px-4 py-2 shadow-sm transition-colors',
          'border-muted-foreground/30 focus-within:border-muted-foreground/55',
        )}
      >
        <Textarea
          ref={ref}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={placeholder ?? '问问 LED 灯出口德国需要哪些认证'}
          rows={1}
          className={cn(
            '!min-h-[32px] flex-1 resize-none overflow-y-auto border-0 bg-transparent px-0 py-[5px] text-[14px] leading-[22px] placeholder:text-muted-foreground/55',
            'shadow-none focus-visible:ring-0',
          )}
          style={{ height: 32, maxHeight: 112 }}
        />

        <Button
          variant="ghost"
          size="icon"
          onClick={handleSend}
          disabled={!canSend}
          aria-label={sending ? '停止' : '发送'}
          className={cn(
            'size-8 shrink-0 rounded-full transition-colors disabled:opacity-100',
            canSend
              ? 'text-foreground hover:bg-muted'
              : 'cursor-not-allowed text-muted-foreground/35 hover:bg-transparent',
          )}
        >
          {sending ? (
            <Square className="size-3.5 fill-current" />
          ) : (
            <Send className="size-3.5" />
          )}
        </Button>
      </div>
      {footer && (
        <div className="text-center text-[10.5px] leading-4 text-muted-foreground/55">
          {footer}
        </div>
      )}
    </div>
  )
}
