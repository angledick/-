import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Bell,
  Bot,
  CalendarClock,
  KeyRound,
  PlugZap,
  ShieldCheck,
  SlidersHorizontal,
  UserCircle,
  Users,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/AuthContext'

const userItems = [
  {
    title: '账号资料',
    description: '用户名、角色和登录状态',
    to: '/app/settings/profile',
    Icon: UserCircle,
  },
  {
    title: '通知偏好',
    description: '风险提醒和渠道推送配置',
    to: '/app/notify-config',
    Icon: Bell,
  },
]

const adminItems = [
  {
    title: '店铺连接',
    description: 'Shopify 和第三方平台授权',
    to: '/app/integrations',
    Icon: PlugZap,
  },
  {
    title: '团队成员',
    description: '用户、角色与访问控制',
    to: '/app/user-manage',
    Icon: Users,
  },
  {
    title: '模型配置',
    description: '模型供应商、密钥和路由',
    to: '/app/model-config',
    Icon: SlidersHorizontal,
  },
  {
    title: 'Agent 配置',
    description: '技能、工具和智能体参数',
    to: '/app/agent-config',
    Icon: Bot,
  },
  {
    title: '定时任务',
    description: '合规扫描、新闻抓取和同步计划',
    to: '/app/scheduler',
    Icon: CalendarClock,
  },
]

const complianceItems = [
  { label: '店铺合规', to: '/app/compliance/system' },
  { label: '产品合规', to: '/app/products' },
  { label: '合规查询', to: '/app/compliance' },
  { label: '新闻监控', to: '/app/news-monitor' },
  { label: '记忆库', to: '/app/nl-store' },
]

export default function SettingsPage() {
  const { user, isAdmin } = useAuth()
  const items = isAdmin ? [...userItems, ...adminItems] : userItems

  return (
    <div className="min-h-full bg-background">
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-[1200px] px-6 py-7 sm:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-2 text-[12px] font-medium text-muted-foreground">
                <span className="h-px w-6 bg-border" />
                系统管理
              </div>
              <h1 className="text-[28px] font-semibold tracking-tight">账号与工作区</h1>
              <p className="mt-1 max-w-2xl text-[14px] leading-6 text-muted-foreground">
                管理个人账号、连接渠道、通知规则和工作区配置入口。
              </p>
            </div>
            <Button asChild variant="outline" className="h-9 text-[13px]">
              <Link to="/app/chat">
                返回对话 <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1200px] space-y-6 px-6 py-8 sm:px-8">
        <section className="rounded-lg border border-border/60 bg-card p-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-foreground text-[14px] font-semibold text-background">
                {user?.username?.[0]?.toUpperCase() ?? '?'}
              </div>
              <div className="min-w-0">
                <div className="truncate text-[15px] font-semibold">
                  {user?.username ?? '未登录'}
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
                  <span>{isAdmin ? '管理员' : '成员'}</span>
                  <span className="h-1 w-1 rounded-full bg-muted-foreground/50" />
                  <span>避风港工作区</span>
                </div>
              </div>
            </div>
            <Button asChild size="sm" variant="secondary" className="h-8 text-[12px]">
              <Link to="/app/settings/profile">
                <KeyRound className="size-3.5" />
                账号安全
              </Link>
            </Button>
          </div>
        </section>

        <section>
          <div className="mb-3 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-[16px] font-semibold tracking-tight">常用设置</h2>
              <p className="mt-1 text-[13px] text-muted-foreground">
                {isAdmin ? '包含管理员配置入口' : '管理员配置入口按角色隐藏'}
              </p>
            </div>
            {isAdmin && <ShieldCheck className="size-4 text-muted-foreground" />}
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {items.map(({ title, description, to, Icon }) => (
              <Link
                key={title}
                to={to}
                className="group rounded-lg border border-border/60 bg-card p-4 transition-colors hover:border-foreground/20 hover:bg-muted/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Icon className="size-4 text-muted-foreground" />
                    <span className="text-[14px] font-semibold">{title}</span>
                  </div>
                  <ArrowRight className="size-3.5 text-muted-foreground transition-colors group-hover:text-foreground" />
                </div>
                <p className="mt-2 text-[12px] leading-5 text-muted-foreground">
                  {description}
                </p>
              </Link>
            ))}
          </div>
        </section>

        <section>
          <div className="mb-3">
            <h2 className="text-[16px] font-semibold tracking-tight">合规工具</h2>
            <p className="mt-1 text-[13px] text-muted-foreground">
              店铺合规、产品合规、合规查询、新闻监控和记忆库面向所有成员开放。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {complianceItems.map((item) => (
              <Button key={item.to} asChild variant="outline" size="sm" className="h-8 text-[12px]">
                <Link to={item.to}>{item.label}</Link>
              </Button>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
