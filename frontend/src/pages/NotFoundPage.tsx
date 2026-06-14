import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

import LandingNav from '@/components/common/LandingNav'

/**
 * 友好 404 页面 — 走 editorial 风格，跟 marketing 页面保持视觉一致。
 * 区分两种情况：未登录引导回首页；已登录引导回工作区。
 * 通过路由 meta 决定目的地，保持组件无副作用。
 */
export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-cream text-cream-foreground">
      <LandingNav />

      <section className="pt-40 md:pt-48 pb-32 px-6 md:px-12">
        <div className="max-w-3xl mx-auto">
          <p className="text-xs uppercase tracking-[0.3em] text-cream-foreground/40 mb-8">
            404
          </p>
          <h1 className="font-serif text-5xl md:text-7xl leading-[0.9] tracking-tighter mb-12">
            Nothing
            <br />
            here, yet.
          </h1>
          <p className="font-sans text-lg text-cream-foreground/80 leading-relaxed mb-12 max-w-xl">
            您访问的页面不存在或已被移走。可以回到首页继续浏览，或前往工作区。
          </p>

          <div className="flex flex-col sm:flex-row gap-8 sm:gap-12">
            <Link to="/" className="group inline-block">
              <div className="flex items-center gap-3 text-sm text-cream-foreground/60 hover:text-cream-foreground transition-colors">
                <span className="relative">
                  返回首页
                  <span className="absolute left-0 bottom-0 w-0 h-px bg-cream-foreground group-hover:w-full transition-all duration-300" />
                </span>
                <ArrowRight className="size-4 group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>

            <Link to="/app" className="group inline-block">
              <div className="flex items-center gap-3 text-sm text-cream-foreground/60 hover:text-cream-foreground transition-colors">
                <span className="relative">
                  前往工作区
                  <span className="absolute left-0 bottom-0 w-0 h-px bg-cream-foreground group-hover:w-full transition-all duration-300" />
                </span>
                <ArrowRight className="size-4 group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
