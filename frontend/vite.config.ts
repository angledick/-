import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import type { PreRenderedChunk } from 'rollup'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        chunkFileNames: (chunkInfo: PreRenderedChunk) => {
          const facadeId = chunkInfo.facadeModuleId?.split(path.sep).join('/')
          if (facadeId?.includes('/src/pages/')) return 'assets/[name].js'
          return 'assets/[name]-[hash].js'
        },
        manualChunks: {
          // React 核心库
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          // UI 组件库 - Radix UI
          'ui-radix': [
            '@radix-ui/react-accordion',
            '@radix-ui/react-avatar',
            '@radix-ui/react-checkbox',
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-label',
            '@radix-ui/react-popover',
            '@radix-ui/react-select',
            '@radix-ui/react-separator',
            '@radix-ui/react-slot',
            '@radix-ui/react-tabs',
          ],
          // 命令面板
          'cmdk': ['cmdk'],
          // 图标库
          'lucide': ['lucide-react'],
          // 工具库
          'utils': ['clsx', 'tailwind-merge', 'sonner'],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
})
