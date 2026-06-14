/**
 * 新闻监控 TanStack Query hooks。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/context/AuthContext'
import {
  getKeywords,
  getMarketSummary,
  listNews,
  triggerCollect,
  updateKeywords,
} from '@/lib/api/news'
import type { KeywordConfig } from '@/lib/api/news'

const KEYS = {
  news: ['news', 'list'] as const,
  summary: ['news', 'summary'] as const,
  keywords: ['news', 'keywords'] as const,
}

/** 新闻列表 */
export function useNewsList(params?: { hours?: number; limit?: number; direction?: string; level?: string }) {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: [...KEYS.news, params],
    queryFn: () => listNews(authFetch, params),
    staleTime: 30_000,
  })
}

/** 市场摘要 */
export function useMarketSummary(hours = 24) {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: [...KEYS.summary, hours],
    queryFn: () => getMarketSummary(authFetch, hours),
    staleTime: 60_000,
  })
}

/** 手动触发采集 */
export function useNewsCollect() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => triggerCollect(authFetch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['news'] })
    },
  })
}

/** 关键词配置（读） */
export function useNewsKeywords() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.keywords,
    queryFn: () => getKeywords(authFetch),
    staleTime: 120_000,
  })
}

/** 关键词配置（写） */
export function useUpdateKeywords() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (config: KeywordConfig) => updateKeywords(authFetch, config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.keywords })
    },
  })
}
