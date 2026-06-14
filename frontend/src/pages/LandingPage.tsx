import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

import LandingNav from '@/components/common/LandingNav'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-cream text-cream-foreground">
      <LandingNav />

      <Hero />
      <Features />
      <Stats />
      <CallToAction />
      <SiteFooter />
    </div>
  )
}

/* ─────────────────────────── Hero ─────────────────────────── */

function Hero() {
  return (
    <section className="pt-32 md:pt-40 pb-24 md:pb-40 px-6 md:px-12">
      <RevealOnScroll>
        <div className="max-w-7xl mx-auto">
          <div className="max-w-5xl">
            <p className="text-xs uppercase tracking-[0.3em] text-cream-foreground/40 mb-8">
              跨境合规智能体
            </p>
            <h1 className="font-serif text-5xl md:text-7xl lg:text-9xl leading-[0.9] tracking-tighter mb-12">
              Your model's
              <br />
              passport to
              <br />
              <span className="italic text-cream-foreground/80">the world</span>
            </h1>
            <div className="max-w-2xl">
              <p className="font-sans text-lg md:text-xl text-cream-foreground/80 leading-relaxed mb-12">
                专为中小出海企业打造的 AI 合规助手。输入产品与目标国家，秒级生成 HS 编码、税率、认证清单和全面的合规报告。
              </p>
              <Link to="/auth/login" className="inline-block group">
                <div className="flex items-center gap-3 text-sm text-cream-foreground/60 hover:text-cream-foreground transition-colors">
                  <span className="relative">
                    开始使用
                    <span className="absolute left-0 bottom-0 w-0 h-px bg-cream-foreground group-hover:w-full transition-all duration-300" />
                  </span>
                  <ArrowRight className="size-4 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>
            </div>
          </div>
        </div>
      </RevealOnScroll>
    </section>
  )
}

/* ─────────────────────────── Features ─────────────────────────── */

const features = [
  {
    title: '智能合规查询',
    description: '输入产品与目标国家，AI 自动生成 HS 编码、税率、认证要求和合规建议。',
  },
  {
    title: 'RAG 知识库',
    description: '内置 EU/US/JP/KR 法规知识，支持 PDF/URL 自定义导入，语义搜索精准定位。',
  },
  {
    title: '新闻监控预警',
    description: '关键词监控配合 AI 风险分析，高风险事件自动推送飞书/企微。',
  },
  {
    title: '风险评估',
    description: '自动扫描店铺产品，分级预警（红/黄/蓝），提供具体整改建议。',
  },
  {
    title: '浏览器控制',
    description: '集成 OpenCLI，一键访问 60+ 热门站点，自动化信息采集。',
  },
  {
    title: '多 Agent 协作',
    description: 'Codex SDK + Skills + MCP 工具，联网搜索，智能决策。',
  },
]

function Features() {
  return (
    <section
      id="features"
      className="py-24 md:py-40 px-6 md:px-12 border-t border-rule/10"
    >
      <div className="max-w-7xl mx-auto">
        <RevealOnScroll>
          <div className="mb-20">
            <p className="text-xs uppercase tracking-[0.3em] text-cream-foreground/40">
              核心能力
            </p>
          </div>
        </RevealOnScroll>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-x-12 gap-y-20">
          {features.map((feature, idx) => (
            <RevealOnScroll key={idx} delay={idx * 60}>
              <article className="group">
                <div className="text-xs text-cream-foreground/40 mb-4 tracking-[0.3em]">
                  {String(idx + 1).padStart(2, '0')}
                </div>
                <h3 className="font-serif text-2xl md:text-3xl tracking-tight mb-4 group-hover:italic transition-all">
                  {feature.title}
                </h3>
                <p className="font-sans text-sm text-cream-foreground/60 leading-relaxed">
                  {feature.description}
                </p>
              </article>
            </RevealOnScroll>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ─────────────────────────── Stats ─────────────────────────── */

const stats = [
  { number: '10,000+', label: '查询次数' },
  { number: '50+', label: '覆盖国家' },
  { number: '99.9%', label: '准确率' },
]

function Stats() {
  return (
    <section className="py-24 md:py-32 px-6 md:px-12 border-t border-rule/10">
      <div className="max-w-7xl mx-auto">
        <div className="grid md:grid-cols-3 gap-16">
          {stats.map((stat, idx) => (
            <RevealOnScroll key={idx} delay={idx * 80}>
              <div>
                <div className="font-serif text-6xl md:text-7xl tracking-tight mb-3">
                  {stat.number}
                </div>
                <div className="text-xs uppercase tracking-[0.3em] text-cream-foreground/40">
                  {stat.label}
                </div>
              </div>
            </RevealOnScroll>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ─────────────────────────── CTA ─────────────────────────── */

function CallToAction() {
  return (
    <section className="py-32 md:py-48 px-6 md:px-12 border-t border-rule/10">
      <div className="max-w-4xl mx-auto text-center">
        <RevealOnScroll>
          <h2 className="font-serif text-5xl md:text-7xl tracking-tight mb-8">
            准备好了吗？
          </h2>
          <p className="font-sans text-lg text-cream-foreground/60 mb-12">
            让 AI 成为您的跨境合规专家
          </p>
          <Link to="/auth/login" className="inline-block group">
            <div className="flex items-center justify-center gap-3 text-sm text-cream-foreground/60 hover:text-cream-foreground transition-colors">
              <span className="relative">
                免费开始
                <span className="absolute left-0 bottom-0 w-0 h-px bg-cream-foreground group-hover:w-full transition-all duration-300" />
              </span>
              <ArrowRight className="size-4 group-hover:translate-x-1 transition-transform" />
            </div>
          </Link>
        </RevealOnScroll>
      </div>
    </section>
  )
}

/* ─────────────────────────── Footer ─────────────────────────── */

function SiteFooter() {
  return (
    <footer className="border-t border-rule/10 py-12 px-6 md:px-12">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-8">
          <div>
            <p className="font-serif text-xl tracking-[0.3em] mb-2">ASTRA</p>
            <p className="text-xs text-cream-foreground/40">避风港</p>
          </div>
          <div className="text-xs uppercase tracking-[0.3em] text-cream-foreground/40">
            © {new Date().getFullYear()}
          </div>
        </div>
      </div>
    </footer>
  )
}

/* ─────────────────────────── Reveal-on-scroll ─────────────────────────── */

/**
 * Passthrough wrapper — preserves the call-site shape (delay / className) for
 * future re-introduction of scroll-triggered animations, but currently renders
 * children directly. The earlier IntersectionObserver + inline-style version
 * was removed after screenshot verification showed a Playwright fullPage
 * capture race: opacity-0 was set during the initial observer fire but the
 * transition back to opacity-1 raced the screenshot timer, leaving lower
 * sections blank in static captures (and on slow devices). Editorial magazine
 * layouts work fine without section-by-section reveal, so the trade is clean.
 */
function RevealOnScroll({
  children,
}: {
  children: React.ReactNode
  delay?: number
  className?: string
}) {
  return <>{children}</>
}
