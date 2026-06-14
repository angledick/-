/**
 * NL Store TanStack Query hooks。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/context/AuthContext'
import {
  createNLRecord,
  deleteNLRecord,
  getNLRecord,
  listNLNamespace,
  searchNL,
  updateNLRecord,
} from '@/lib/api/nlstore'
import type { NLRecordCreateRequest } from '@/types'

const KEYS = {
  all: ['nlstore'] as const,
  namespace: (ns: string) => ['nlstore', ns] as const,
  record: (ns: string, key: string) => ['nlstore', ns, key] as const,
}

/** 列出 namespace 记录摘要 */
export function useNLRecords(namespace: string) {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.namespace(namespace),
    queryFn: () => listNLNamespace(authFetch, namespace),
    staleTime: 30_000,
    enabled: !!namespace,
  })
}

/** 获取单条 */
export function useNLRecord(namespace: string, key: string) {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.record(namespace, key),
    queryFn: () => getNLRecord(authFetch, namespace, key),
    enabled: !!namespace && !!key,
  })
}

/** 全文搜索 */
export function useNLSearch() {
  const { authFetch } = useAuth()
  return useMutation({
    mutationFn: (params: { q: string; namespace?: string; maxResults?: number }) =>
      searchNL(authFetch, params.q, params.namespace, params.maxResults),
  })
}

/** 创建记录 */
export function useCreateNLRecord(namespace: string) {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: NLRecordCreateRequest) => createNLRecord(authFetch, namespace, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.namespace(namespace) }),
  })
}

/** 更新记录 */
export function useUpdateNLRecord(namespace: string) {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, ...req }: { key: string } & Partial<NLRecordCreateRequest>) =>
      updateNLRecord(authFetch, namespace, key, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.namespace(namespace) }),
  })
}

/** 删除记录 */
export function useDeleteNLRecord(namespace: string) {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (key: string) => deleteNLRecord(authFetch, namespace, key),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.namespace(namespace) }),
  })
}
