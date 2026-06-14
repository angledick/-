import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Menu } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'

interface NavLink {
  label: string
  to: string
  variant?: 'link' | 'cta'
  /** When set, intercepts click to smooth-scroll to an in-page anchor */
  anchor?: string
}

const links: NavLink[] = [
  { label: '功能', to: '/#features', anchor: 'features' },
  { label: '登录', to: '/auth/login', variant: 'link' },
  { label: '开始使用', to: '/auth/login', variant: 'cta' },
]

/**
 * LandingPage 顶部导航。
 * - 桌面端（md+）：水平链接
 * - 移动端：汉堡按钮 → Sheet 抽屉
 * - 全部走 design tokens（bg-cream / text-cream-foreground / border-rule）
 */
export default function LandingNav() {
  const [open, setOpen] = useState(false)

  return (
    <nav className="fixed top-0 inset-x-0 z-50 bg-cream/90 backdrop-blur-sm border-b border-rule/10">
      <div className="max-w-7xl mx-auto px-6 md:px-12 h-16 md:h-20 flex items-center justify-between">
        {/* Wordmark */}
        <Link
          to="/"
          className="font-serif text-2xl tracking-[0.3em] text-cream-foreground"
        >
          ASTRA
        </Link>

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-12">
          {links.map((link) => (
            <NavItem key={link.label} link={link} onNavigate={() => {}} />
          ))}
        </div>

        {/* Mobile hamburger */}
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden text-cream-foreground hover:bg-rule/5"
              aria-label="打开菜单"
            >
              <Menu className="size-5" />
            </Button>
          </SheetTrigger>
          <SheetContent
            side="right"
            className="bg-cream border-l border-rule/10 w-72 p-8"
          >
            <div className="flex flex-col gap-8 mt-8">
              {links.map((link) => (
                <NavItem
                  key={link.label}
                  link={link}
                  onNavigate={() => setOpen(false)}
                  mobile
                />
              ))}
            </div>
            <p className="absolute bottom-8 left-8 text-xs uppercase tracking-[0.3em] text-cream-foreground/40">
              避风港
            </p>
          </SheetContent>
        </Sheet>
      </div>
    </nav>
  )
}

function NavItem({
  link,
  onNavigate,
  mobile = false,
}: {
  link: NavLink
  onNavigate: () => void
  mobile?: boolean
}) {
  const base =
    'group relative text-sm tracking-wide transition-colors text-cream-foreground/60 hover:text-cream-foreground'
  const cta =
    'inline-flex items-center gap-2 px-5 py-2.5 text-sm text-cream bg-cream-foreground hover:bg-cream-foreground/85 transition-colors'
  const mobileBase = 'text-2xl font-serif tracking-tight'
  const mobileCta = 'inline-flex items-center justify-center px-6 py-3 text-sm tracking-wide text-cream bg-cream-foreground'

  if (link.variant === 'cta') {
    return (
      <Link
        to={link.to}
        onClick={onNavigate}
        className={cn(mobile ? mobileCta : cta)}
      >
        {link.label}
        <span aria-hidden>→</span>
      </Link>
    )
  }

  if (link.anchor) {
    return (
      <a
        href={`#${link.anchor}`}
        onClick={(e) => {
          e.preventDefault()
          document
            .getElementById(link.anchor!)
            ?.scrollIntoView({ behavior: 'smooth' })
          onNavigate()
        }}
        className={cn(base, mobile && mobileBase)}
      >
        {link.label}
        <span
          className={cn(
            'absolute left-0 -bottom-1 h-px bg-cream-foreground transition-all duration-300 w-0 group-hover:w-full',
            mobile && 'relative bottom-auto left-auto h-px w-0 mt-1'
          )}
        />
      </a>
    )
  }

  return (
    <Link
      to={link.to}
      onClick={onNavigate}
      className={cn(base, mobile && mobileBase)}
    >
      {link.label}
      <span
        className={cn(
          'absolute left-0 -bottom-1 h-px bg-cream-foreground transition-all duration-300 w-0 group-hover:w-full',
          mobile && 'relative bottom-auto left-auto h-px w-0 mt-1'
        )}
      />
    </Link>
  )
}
