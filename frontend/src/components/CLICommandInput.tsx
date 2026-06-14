import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { cliApi, type CLICommand } from '../api/config'

interface Props {
  visible: boolean
  onExecute: (command: string) => void
  onClose: () => void
}

// 内置命令（后端 CLI API 不可用时的回退）
const BUILTIN_COMMANDS: CLICommand[] = [
  { cmd: '/help', desc: '查看可用命令', category: '系统' },
  { cmd: '/clear', desc: '清空对话历史', category: '对话' },
  { cmd: '/status', desc: '查看系统状态', category: '系统' },
  { cmd: '/config', desc: '查看当前配置', category: '配置' },
  { cmd: '/history', desc: '查看命令历史', category: '系统' },
  { cmd: '/agent', desc: '切换当前 Agent', usage: '/agent <name>', category: '配置' },
  { cmd: '/export', desc: '导出合规报告', usage: '/export <product_id>', category: '工具' },
]

export default function CLICommandInput({ visible, onExecute, onClose }: Props) {
  const [input, setInput] = useState('')
  const [suggestions, setSuggestions] = useState<CLICommand[]>(BUILTIN_COMMANDS)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [history, setHistory] = useState<string[]>([])
  const [historyIdx, setHistoryIdx] = useState(-1)

  const inputRef = useRef<HTMLInputElement>(null)

  // 自动聚焦
  useEffect(() => {
    if (visible) {
      inputRef.current?.focus()
    }
  }, [visible])

  // 加载远程补全建议
  useEffect(() => {
    if (!input.startsWith('/')) {
      setSuggestions(BUILTIN_COMMANDS)
      setShowSuggestions(false)
      return
    }

    const fetchSuggestions = async () => {
      try {
        const res = await cliApi.complete(input)
        setSuggestions(res.suggestions.length > 0 ? res.suggestions : BUILTIN_COMMANDS)
      } catch {
        // API 不可用，用本地过滤
        const filtered = BUILTIN_COMMANDS.filter(c =>
          c.cmd.toLowerCase().startsWith(input.toLowerCase())
        )
        setSuggestions(filtered.length > 0 ? filtered : BUILTIN_COMMANDS)
      }
    }

    if (input.startsWith('/') && !input.includes(' ')) {
      fetchSuggestions()
      setShowSuggestions(true)
      setSelectedIdx(0)
    } else {
      setShowSuggestions(false)
    }
  }, [input])

  // 加载历史
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const res = await cliApi.history(20)
        setHistory(res.history.map(h => h.command).reverse())
      } catch {
        // API 不可用时保持空
      }
    }
    loadHistory()
  }, [])

  const execute = () => {
    const trimmed = input.trim()
    if (!trimmed) return

    onExecute(trimmed)
    setHistory(prev => [...prev, trimmed].slice(-50))
    setInput('')
    setHistoryIdx(-1)
    setShowSuggestions(false)
  }

  const selectSuggestion = (cmd: string) => {
    setInput(cmd + ' ')
    setShowSuggestions(false)
    inputRef.current?.focus()
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (showSuggestions && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIdx(i => (i + 1) % suggestions.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIdx(i => (i - 1 + suggestions.length) % suggestions.length)
        return
      }
      if (e.key === 'Tab' || e.key === 'Enter') {
        if (selectedIdx >= 0 && selectedIdx < suggestions.length) {
          e.preventDefault()
          const picked = suggestions[selectedIdx]
          if (picked) {
            selectSuggestion(picked.cmd)
          }
          return
        }
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      execute()
      return
    }

    // 命令历史导航
    if (e.key === 'ArrowUp' && !showSuggestions) {
      e.preventDefault()
      if (history.length > 0) {
        const newIdx = Math.min(historyIdx + 1, history.length - 1)
        setHistoryIdx(newIdx)
        const histVal = history[history.length - 1 - newIdx]
        if (histVal !== undefined) setInput(histVal)
      }
      return
    }
    if (e.key === 'ArrowDown' && !showSuggestions) {
      e.preventDefault()
      if (historyIdx > 0) {
        const newIdx = historyIdx - 1
        setHistoryIdx(newIdx)
        const histVal = history[history.length - 1 - newIdx]
        if (histVal !== undefined) setInput(histVal)
      } else {
        setHistoryIdx(-1)
        setInput('')
      }
      return
    }

    if (e.key === 'Escape') {
      if (showSuggestions) {
        setShowSuggestions(false)
      } else {
        onClose()
      }
    }
  }

  if (!visible) return null

  return (
    <div className="border-t border-black/6 bg-[#F5F5F7]">
      {/* Suggestions dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="max-h-48 overflow-y-auto border-b border-black/6 bg-white">
          <div className="px-3 py-1.5 text-[10px] font-semibold text-[#86868B] uppercase tracking-wider">
            命令建议
          </div>
          {suggestions.map((cmd, i) => (
            <button
              key={cmd.cmd}
              onClick={() => selectSuggestion(cmd.cmd)}
              onMouseEnter={() => setSelectedIdx(i)}
              className={`w-full px-3 py-2 flex items-center gap-3 text-left transition-colors ${
                i === selectedIdx ? 'bg-[#0071E3]/10' : 'hover:bg-[#F5F5F7]'
              }`}
            >
              <span className="text-sm font-mono font-semibold text-[#0071E3] min-w-[100px]">
                {cmd.cmd}
              </span>
              <span className="text-xs text-[#86868B] flex-1">{cmd.desc}</span>
              {cmd.usage && (
                <span className="text-[10px] text-[#C7C7CC] font-mono">{cmd.usage}</span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div className="flex items-center gap-2 px-4 py-2.5">
        <span className="text-xs font-mono font-semibold text-[#0071E3] shrink-0">$</span>
        <input
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入命令，按 Enter 执行..."
          className="flex-1 bg-transparent border-none outline-none text-sm text-[#1D1D1F] font-mono placeholder:text-[#C7C7CC]"
        />
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-[#C7C7CC]">Esc 关闭</span>
          <button
            onClick={execute}
            disabled={!input.trim()}
            className="px-3 py-1 text-xs font-medium rounded-md bg-[#1D1D1F] text-white hover:bg-[#2D2D2F] transition-colors disabled:opacity-30"
          >
            执行
          </button>
        </div>
      </div>
    </div>
  )
}
