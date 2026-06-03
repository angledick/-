import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import CLICommandInput from './CLICommandInput'

interface Props {
  onSend: (text: string) => void
  onCLI?: (command: string) => void
  disabled?: boolean
  isStreaming?: boolean
  onAbort?: () => void
  placeholder?: string
}

export default function ChatInput({ onSend, onCLI, disabled, isStreaming, onAbort, placeholder }: Props) {
  const [input, setInput] = useState('')
  const [cliMode, setCliMode] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // 自动聚焦
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // 自动调整高度
  useEffect(() => {
    const el = inputRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`
    }
  }, [input])

  const handleChange = (value: string) => {
    setInput(value)

    // 检测 / 前缀：进入 CLI 模式
    if (value.startsWith('/') && !value.includes(' ') && !cliMode) {
      if (onCLI) {
        setCliMode(true)
      }
    }
  }

  const handleSubmit = () => {
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const executeCLI = (command: string) => {
    onCLI?.(command)
    setCliMode(false)
    setInput('')
  }

  return (
    <div className="relative max-w-3xl mx-auto">
      {cliMode && onCLI ? (
        <CLICommandInput
          visible
          onExecute={executeCLI}
          onClose={() => setCliMode(false)}
        />
      ) : (
        <>
          <div className="flex items-end gap-2">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => handleChange(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder || '输入消息，或 / 查看命令...'}
                disabled={disabled && !isStreaming}
                rows={1}
                className="w-full px-4 py-3 pr-12 rounded-xl border border-black/10 text-[15px] leading-relaxed bg-[#F5F5F7] outline-none resize-none transition-colors focus:border-[#0071E3]/30 focus:bg-white disabled:opacity-50"
              />
              {/* 发送/停止按钮 */}
              <div className="absolute right-2 bottom-2">
                {isStreaming ? (
                  <button
                    onClick={onAbort}
                    className="w-8 h-8 rounded-lg bg-[#FF3B30] text-white flex items-center justify-center hover:bg-[#E0342B] transition-colors"
                    title="停止生成"
                  >
                    <span className="text-xs">■</span>
                  </button>
                ) : (
                  <button
                    onClick={handleSubmit}
                    disabled={!input.trim() || disabled}
                    className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors disabled:opacity-30 disabled:cursor-not-allowed bg-[#1D1D1F] text-white hover:bg-[#2D2D2F]"
                    title="发送"
                  >
                    <span className="text-sm">↑</span>
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Shift+Enter 提示 */}
          <div className="text-[11px] text-[#C7C7CC] mt-1.5 text-center">
            Enter 发送 · Shift+Enter 换行 · / 进入命令模式
          </div>
        </>
      )}
    </div>
  )
}
