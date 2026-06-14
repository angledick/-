import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    container: {
      center: true,
      padding: '1rem',
      screens: {
        '2xl': '1280px',
      },
    },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        success: {
          DEFAULT: 'hsl(var(--success))',
          foreground: 'hsl(var(--success-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          foreground: 'hsl(var(--warning-foreground))',
        },
        cream: {
          DEFAULT: 'hsl(var(--cream) / <alpha-value>)',
          foreground: 'hsl(var(--cream-foreground) / <alpha-value>)',
        },
        rule: 'hsl(var(--rule) / <alpha-value>)',
      },
      fontFamily: {
        sans: [
          'DM Sans',
          'Manrope',
          '-apple-system',
          'BlinkMacSystemFont',
          'PingFang SC',
          'Hiragino Sans GB',
          'Microsoft YaHei',
          'sans-serif',
        ],
        display: ['DM Sans', 'sans-serif'],
        body: ['DM Sans', 'sans-serif'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontSize: {
        // 统一 Type Scale（设计令牌）
        // 优先使用以下语义名称，避免任意值 text-[Npx]
        caption:  ['0.6875rem', { lineHeight: '1.4' }],  // 11px  辅助信息
        label:    ['0.75rem',   { lineHeight: '1.4' }],  // 12px  标签/元数据
        'body-sm':['0.8125rem', { lineHeight: '1.5' }],  // 13px  小正文
        body:     ['0.875rem',  { lineHeight: '1.6' }],  // 14px  正文
        'body-lg':['0.9375rem', { lineHeight: '1.6' }],  // 15px  大正文
        section:  ['1rem',      { lineHeight: '1.5' }],  // 16px  段落标题
        h4:       ['1.125rem',  { lineHeight: '1.4' }],  // 18px 卡片标题
        h3:       ['1.25rem',   { lineHeight: '1.3' }],  // 20px 小标题
        h2:       ['1.5rem',    { lineHeight: '1.3' }],  // 24px 章节标题
        h1:       ['1.75rem',   { lineHeight: '1.2' }],  // 28px 页面标题
        hero:     ['2.25rem',   { lineHeight: '1.1' }],  // 36px 首屏大标题
      },
      boxShadow: {
        sm: '0 1px 3px rgb(0 0 0 / 0.06)',
        DEFAULT: '0 2px 8px rgb(0 0 0 / 0.06)',
        md: '0 4px 12px rgb(0 0 0 / 0.08)',
        lg: '0 10px 30px rgb(0 0 0 / 0.10)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-down': {
          from: { opacity: '0', transform: 'translateY(-8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-left': {
          from: { opacity: '0', transform: 'translateX(8px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'slide-right': {
          from: { opacity: '0', transform: 'translateX(-8px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.95)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'pulse-once': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
        'slide-down': 'slide-down 0.3s ease-out',
        'slide-left': 'slide-left 0.3s ease-out',
        'slide-right': 'slide-right 0.3s ease-out',
        'scale-in': 'scale-in 0.2s ease-out',
        'pulse-once': 'pulse-once 0.5s ease-out',
      },
    },
  },
  plugins: [require('tailwindcss-animate'), require('@tailwindcss/typography')],
}

export default config
