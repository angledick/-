/**
 * ActionChain 与 EventChain TanStack Query hooks。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/context/AuthContext'
import {
  createEventChainEvent,
  getActionChain,
  getActionChainTrail,
  getEventChain,
  getEventChainTimeline,
  filterEventChain,
  listActionChains,
  listEventChains,
  type EventFilterParams,
} from '@/lib/api/chains'
import type { EventCreateRequest } from '@/types'

const KEYS = {
  actionChains: ['chains', 'actions'] as const,
  actionChain: (id: string) => ['chains', 'actions', id] as const,
  actionTrail: (id: string) => ['chains', 'actions', id, 'trail'] as const,
  eventChains: ['chains', 'events'] as const,
  eventChain: (id: string) => ['chains', 'events', id] as const,
  eventTimeline: (id: string) => ['chains', 'events', id, 'timeline'] as const,
  eventFilter: (id: string, params: EventFilterParams) =>
    ['chains', 'events', id, 'filter', params] as const,
}

/** 操作链列表 */
export function useActionChains() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.actionChains,
    queryFn: () => listActionChains(authFetch),
    staleTime: 30_000,
  })
}

/** 单个操作链详情 */
export function useActionChain(chainId: string | null) {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.actionChain(chainId ?? ''),
    queryFn: () => getActionChain(authFetch, chainId!),
    enabled: !!chainId,
  })
}

/** 操作链路 NL 描述 */
export function useActionChainTrail(chainId: string | null) {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.actionTrail(chainId ?? ''),
    queryFn: () => getActionChainTrail(authFetch, chainId!),
    enabled: !!chainId,
  })
}

/** 事件链列表 */
export function useEventChains() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.eventChains,
    queryFn: () => listEventChains(authFetch),
    staleTime: 30_000,
  })
}

/** 单个事件链详情 */
export function useEventChain(chainId: string | null) {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.eventChain(chainId ?? ''),
    queryFn: () => getEventChain(authFetch, chainId!),
    enabled: !!chainId,
  })
}

/** 事件链时间线 NL 描述 */
export function useEventChainTimeline(chainId: string | null) {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.eventTimeline(chainId ?? ''),
    queryFn: () => getEventChainTimeline(authFetch, chainId!),
    enabled: !!chainId,
  })
}

/** 按条件筛选事件链中的事件 */
export function useFilterEvents(chainId: string | null, params: EventFilterParams = {}) {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.eventFilter(chainId ?? '', params),
    queryFn: () => filterEventChain(authFetch, chainId!, params),
    enabled: !!chainId,
  })
}

/** 创建或追加事件 */
export function useCreateEvent() {
  const { authFetch } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: EventCreateRequest) => createEventChainEvent(authFetch, body),
    onSuccess: (event) => {
      queryClient.invalidateQueries({ queryKey: KEYS.eventChains })
      queryClient.invalidateQueries({ queryKey: KEYS.eventChain(event.chain_id) })
      queryClient.invalidateQueries({ queryKey: KEYS.eventTimeline(event.chain_id) })
    },
  })
}
