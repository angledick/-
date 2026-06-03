import type { CLIExecuteResponse } from '../api/config'

interface Props {
  result: CLIExecuteResponse
  onRerun?: () => void
  onCopy?: () => void
}

export default function CLICommandResult({ result, onRerun, onCopy }: Props) {
  const { command, success, output, error, duration_ms } = result

  return (
    <div className="my-2 rounded-lg border border-black/6 overflow-hidden bg-[#1D1D1F]">
      {/* Header: command + status */}
      <div className="flex items-center justify-between px-3 py-2 bg-black/20">
        <div className="flex items-center gap-2 min-w-0">
          <span className={success ? 'text-[#34C759]' : 'text-[#FF3B30]'}>
            {success ? '●' : '✕'}
          </span>
          <code className="text-xs font-mono text-[#E5E5EA] truncate">{command}</code>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {duration_ms !== undefined && (
            <span className="text-[10px] text-[#86868B] font-mono">
              {duration_ms >= 1000
                ? `${(duration_ms / 1000).toFixed(1)}s`
                : `${duration_ms}ms`}
            </span>
          )}
          {onRerun && (
            <button
              onClick={onRerun}
              className="text-[10px] text-[#86868B] hover:text-white transition-colors"
              title="重新执行"
            >
              ↻
            </button>
          )}
          {onCopy && (
            <button
              onClick={onCopy}
              className="text-[10px] text-[#86868B] hover:text-white transition-colors"
              title="复制输出"
            >
              ⎘
            </button>
          )}
        </div>
      </div>

      {/* Output */}
      {output && (
        <pre className="px-3 py-2.5 text-xs font-mono text-[#E5E5EA] leading-relaxed overflow-x-auto whitespace-pre-wrap">
          {output}
        </pre>
      )}

      {/* Error */}
      {error && (
        <div className="mx-3 mb-2.5 px-2.5 py-1.5 rounded bg-[#FF3B30]/10 border border-[#FF3B30]/20">
          <div className="text-xs text-[#FF6B5E] font-mono">{error}</div>
        </div>
      )}
    </div>
  )
}
