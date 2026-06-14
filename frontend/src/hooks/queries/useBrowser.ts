/**
 * Browser 自动化 TanStack Query hooks。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/context/AuthContext'
import {
  getBrowserSnapshot,
  getBrowserStatus,
  runSiteCommand,
  runBrowserAction,
  browserNavigate,
  type SiteCommandRequest,
  type BrowserActionRequest,
  type NavigateRequest,
} from '@/lib/api/browser'

const KEYS = {
  status: ['browser', 'status'] as const,
  snapshot: ['browser', 'snapshot'] as const,
}

/** 浏览器状态（不自动轮询，手动 refetch） */
export function useBrowserStatus() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.status,
    queryFn: () => getBrowserStatus(authFetch),
    enabled: false, // 手动触发
    staleTime: 0,
  })
}

/** 浏览器快照（不自动轮询，手动 refetch） */
export function useBrowserSnapshot() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.snapshot,
    queryFn: () => getBrowserSnapshot(authFetch),
    enabled: false, // 手动触发
    staleTime: 0,
  })
}

/** 执行站点适配器命令 */
export function useSiteCommand() {
  const { authFetch } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (req: SiteCommandRequest) => runSiteCommand(authFetch, req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.status })
    },
  })
}

/** 执行浏览器自动化命令 */
export function useBrowserAction() {
  const { authFetch } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (req: BrowserActionRequest) => runBrowserAction(authFetch, req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.status })
      queryClient.invalidateQueries({ queryKey: KEYS.snapshot })
    },
  })
}

/** 导航到指定 URL */
export function useBrowserNavigate() {
  const { authFetch } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (req: NavigateRequest) => browserNavigate(authFetch, req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.status })
      queryClient.invalidateQueries({ queryKey: KEYS.snapshot })
    },
  })
}
