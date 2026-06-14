import { useEffect, useState } from 'react'

interface TypewriterEffectProps {
  text: string
  speed?: number
  onComplete?: () => void
  className?: string
}

/**
 * 打字机效果组件
 * 参考 ChatGPT 的逐字显示效果
 */
export function TypewriterEffect({
  text,
  speed = 30,
  onComplete,
  className,
}: TypewriterEffectProps) {
  const [displayedText, setDisplayedText] = useState('')
  const [currentIndex, setCurrentIndex] = useState(0)

  useEffect(() => {
    // 重置状态
    setDisplayedText('')
    setCurrentIndex(0)
  }, [text])

  useEffect(() => {
    if (currentIndex >= text.length) {
      onComplete?.()
      return
    }

    const timer = setTimeout(() => {
      setDisplayedText((prev) => prev + text[currentIndex])
      setCurrentIndex((prev) => prev + 1)
    }, speed)

    return () => clearTimeout(timer)
  }, [currentIndex, text, speed, onComplete])

  return (
    <span className={className} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {displayedText}
      {currentIndex < text.length && (
        <span className="inline-block w-[2px] h-[1em] bg-current ml-0.5 animate-pulse" />
      )}
    </span>
  )
}
