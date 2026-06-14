import { useState } from 'react'
import { Check, ChevronDown, ChevronUp, Copy, Link2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import type { SessionMessage } from '@/types'
import { ComplianceCard } from '@/components/chat/ComplianceCard'
import { StreamMessageRenderer } from '@/components/chat/StreamMessageRenderer'
import { TypewriterEffect } from './TypewriterEffect'
import {
  ActionChainPanel,
  ArbitrationPanel,
  BrowserResultCard,
} from './RuntimePanels'

export function MessageBubble({
  msg,
  isLatest = false,
}: {
  msg: SessionMessage
  isLatest?: boolean
}) {
  const isUser = msg.role === 'user'
  const [copied, setCopied] = useState(false)
  const [typingComplete, setTypingComplete] = useState(!isLatest || isUser)
  const [showSources, setShowSources] = useState(false)
  const hasStreamEvents = !isUser && ((msg.stream_events?.length ?? 0) > 0 || msg.streaming)
  const shouldType = !isUser && isLatest && !typingComplete && !hasStreamEvents
  const messageComplete = !isUser && !msg.streaming && (hasStreamEvents || typingComplete)
  const hasSources = Boolean(msg.sources?.length)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(msg.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className={cn(
        'group/bubble mb-8 flex w-full animate-fade-in items-start gap-4',
        isUser ? 'flex-row-reverse' : 'flex-row',
      )}
    >
      <div
        className={cn(
          'flex min-w-0 flex-col',
          isUser ? 'items-end' : 'items-start',
          isUser ? 'w-fit max-w-[min(78%,920px)]' : 'w-full max-w-full',
        )}
      >
        <div
          className={cn(
            'w-full text-[15px] leading-[1.7]',
            isUser
              ? 'rounded-lg bg-muted/50 px-4 py-3 text-foreground'
              : 'px-0 py-1 text-foreground',
          )}
        >
          {isUser ? (
            <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {msg.content}
            </span>
          ) : hasStreamEvents ? (
            <StreamMessageRenderer
              content={msg.content}
              events={msg.stream_events ?? []}
              streaming={msg.streaming}
            />
          ) : shouldType ? (
            <TypewriterEffect
              text={msg.content}
              speed={20}
              onComplete={() => setTypingComplete(true)}
            />
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-3 prose-p:leading-relaxed prose-pre:bg-muted prose-pre:p-4 prose-ul:my-3 prose-ol:my-3 prose-li:my-1 prose-headings:mb-2 prose-headings:mt-4">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {messageComplete && msg.compliance_result && (
          <div className="mt-2 w-full max-w-full">
            <ComplianceCard result={msg.compliance_result} />
          </div>
        )}

        {messageComplete && (
          <div className="mt-2 w-full max-w-full">
            <BrowserResultCard result={msg.browser_result} />
            <ArbitrationPanel conflicts={msg.conflicts} />
            <ActionChainPanel chainId={msg.action_chain_id} />
          </div>
        )}

        {messageComplete && (
          <div className="mt-2 flex gap-2 opacity-0 transition-opacity group-hover/bubble:opacity-100">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
              title={copied ? '已复制' : '复制'}
            >
              {copied ? (
                <>
                  <Check className="size-3" />
                  <span>已复制</span>
                </>
              ) : (
                <>
                  <Copy className="size-3" />
                  <span>复制</span>
                </>
              )}
            </button>
            {hasSources && (
              <button
                onClick={() => setShowSources(!showSources)}
                className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
              >
                {showSources ? (
                  <>
                    <ChevronUp className="size-3" />
                    <span>收起来源</span>
                  </>
                ) : (
                  <>
                    <ChevronDown className="size-3" />
                    <span>查看来源</span>
                  </>
                )}
              </button>
            )}
          </div>
        )}

        {messageComplete && hasSources && showSources && (
          <div className="mt-2 flex w-full max-w-full flex-wrap gap-1.5">
            {msg.sources.slice(0, 3).map((s, i) => (
              <a
                key={s}
                href={s}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex max-w-[220px] items-center gap-1 truncate rounded-md border border-border/60 bg-card px-2 py-0.5 text-[11px] font-medium text-muted-foreground no-underline transition-colors hover:border-primary/30 hover:text-foreground"
              >
                <Link2 className="size-3 shrink-0" />
                来源 {i + 1}
              </a>
            ))}
          </div>
        )}

        <div
          className={cn(
            'mt-1.5 text-[10.5px] text-muted-foreground/50 transition-opacity',
            'opacity-0 group-hover/bubble:opacity-100',
            isUser ? 'text-right' : 'text-left',
          )}
        >
          {new Date(msg.created_at * 1000).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  )
}
