/**
 * PdfUpload — PDF 文件拖拽上传
 * 选填 regulation_name 与 market，后台向量化
 */
import { useRef, useState, type DragEvent, type ChangeEvent } from 'react'
import { FileText, Upload, X } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { useUploadPdf } from '@/hooks/queries/useKnowledge'
import { MARKET_LABEL, MARKET_VALUES } from '@/lib/api/knowledge'
import { cn } from '@/lib/utils'
import type { KnowledgeMarket } from '@/types'

const MAX_SIZE_MB = 30

export function PdfUpload() {
  const [file, setFile] = useState<File | null>(null)
  const [market, setMarket] = useState<KnowledgeMarket>('eu')
  const [regulationName, setRegulationName] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const upload = useUploadPdf()

  const onPick = (f: File | null) => {
    if (!f) return
    // 与后端 knowledge_import.py 对齐：MIME 优先（MIME 缺失时用 octet-stream 兜底），扩展名最后兜底
    const isPdf =
      f.type === 'application/pdf' ||
      f.type === 'application/octet-stream' ||
      f.name.toLowerCase().endsWith('.pdf')
    if (!isPdf) {
      toast.error('仅支持 PDF 文件')
      return
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      toast.error(`文件超过 ${MAX_SIZE_MB}MB 限制`)
      return
    }
    setFile(f)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    onPick(e.dataTransfer.files?.[0] ?? null)
  }

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    onPick(e.target.files?.[0] ?? null)
  }

  const handleSubmit = async () => {
    if (!file) {
      toast.error('请先选择 PDF')
      return
    }
    try {
      const ack = await upload.mutateAsync({
        file,
        market,
        regulationName: regulationName.trim() || undefined,
      })
      toast.success(ack.message || '已接收，后台向量化中…')
      setFile(null)
      setRegulationName('')
      if (inputRef.current) inputRef.current.value = ''
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '上传失败')
    }
  }

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          'rounded-lg border-2 border-dashed p-10 text-center cursor-pointer transition-colors',
          dragging
            ? 'border-primary bg-primary/5'
            : 'border-border bg-muted/30 hover:border-primary/50 hover:bg-muted/50',
        )}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            // 阻止冒泡到容器 onClick，避免 Space/Enter 后再触发一次 click 开两次 picker
            e.preventDefault()
            e.stopPropagation()
            inputRef.current?.click()
          }
        }}
      >
        <Upload className="mx-auto size-8 text-muted-foreground mb-3" />
        <p className="text-sm text-foreground">
          {file ? (
            <span className="font-medium">{file.name}</span>
          ) : (
            <>拖拽 PDF 到此 或 <span className="text-primary underline">点击选择</span></>
          )}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          最大 {MAX_SIZE_MB}MB · 仅 .pdf
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          onChange={onChange}
          className="sr-only"
        />
      </div>

      {/* Selected file preview */}
      {file && (
        <div className="flex items-center gap-3 rounded-md border border-border bg-card px-3 py-2 text-sm">
          <FileText className="size-4 text-muted-foreground shrink-0" />
          <span className="flex-1 truncate">{file.name}</span>
          <span className="text-xs text-muted-foreground tabular-nums">
            {(file.size / 1024 / 1024).toFixed(2)} MB
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              setFile(null)
              if (inputRef.current) inputRef.current.value = ''
            }}
            className="size-6"
            aria-label="移除文件"
          >
            <X className="size-3.5" />
          </Button>
        </div>
      )}

      {/* Options */}
      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
            法规名称（可选）
          </label>
          <input
            type="text"
            value={regulationName}
            onChange={(e) => setRegulationName(e.target.value)}
            placeholder="如：CE-EMC-2014-30-EU"
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div>
          <label className="block text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
            目标市场
          </label>
          <select
            value={market}
            onChange={(e) => setMarket(e.target.value as KnowledgeMarket)}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {MARKET_VALUES.map((m) => (
              <option key={m} value={m}>
                {MARKET_LABEL[m]}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Button
        onClick={handleSubmit}
        disabled={!file || upload.isPending}
        className="w-full sm:w-auto"
      >
        {upload.isPending ? '上传中…' : '上传并开始向量化'}
      </Button>
    </div>
  )
}
