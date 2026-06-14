/**
 * 知识库 TanStack Query hooks。
 * 后端：app/api/knowledge_import.py
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/context/AuthContext'
import {
  deleteKnowledgeDoc,
  getKnowledgeStats,
  importKnowledgeUrl,
  listKnowledgeDocs,
  searchKnowledge,
  uploadKnowledgePdf,
} from '@/lib/api/knowledge'
import type {
  KnowledgeMarket,
  KnowledgeSearchRequest,
  KnowledgeSearchResponse,
} from '@/types'

const KEYS = {
  docs: ['knowledge', 'docs'] as const,
  stats: ['knowledge', 'stats'] as const,
}

/** 已导入文档列表
 *
 * - 基础 staleTime 10s（向量化中状态可能很快变化）
 * - 当列表中有 indexing 状态的文档时，每 5s 轮询一次，捕获 → done 的转换
 * - 没有 indexing 文档时停止轮询（节省带宽）
 */
export function useKnowledgeDocs() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.docs,
    queryFn: () => listKnowledgeDocs(authFetch),
    staleTime: 10_000,
    refetchInterval: (q) => {
      const data = q.state.data as Array<{ status: string }> | undefined
      return data?.some((d) => d.status === 'indexing') ? 5_000 : false
    },
  })
}

/** 知识库统计 */
export function useKnowledgeStats() {
  const { authFetch } = useAuth()
  return useQuery({
    queryKey: KEYS.stats,
    queryFn: () => getKnowledgeStats(authFetch),
    staleTime: 15_000,
  })
}

/** 上传 PDF */
export function useUploadPdf() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: {
      file: File
      market?: KnowledgeMarket
      regulationName?: string
    }) => uploadKnowledgePdf(authFetch, args.file, {
      market: args.market,
      regulationName: args.regulationName,
    }),
    onSuccess: () => {
      // 立刻刷新列表（看到 indexing 状态）+ 1.5s 后再刷一次（拿到 done 概率）
      // setTimeout 不需要清理：mutation 完成时定时器已建立；QC 实例全局存在，
      // 即使组件卸载，invalidateQueries 也不影响。后续如改 setState 需注意 cleanup。
      qc.invalidateQueries({ queryKey: KEYS.docs })
      qc.invalidateQueries({ queryKey: KEYS.stats })
      window.setTimeout(() => {
        qc.invalidateQueries({ queryKey: KEYS.docs })
      }, 1500)
    },
  })
}

/** 从 URL 导入 */
export function useImportUrl() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: {
      url: string
      market?: KnowledgeMarket
      regulationName?: string
    }) => importKnowledgeUrl(authFetch, args.url, {
      market: args.market,
      regulationName: args.regulationName,
    }),
    onSuccess: () => {
      // 同上：setTimeout 不需要 cleanup 注释
      qc.invalidateQueries({ queryKey: KEYS.docs })
      qc.invalidateQueries({ queryKey: KEYS.stats })
      window.setTimeout(() => {
        qc.invalidateQueries({ queryKey: KEYS.docs })
      }, 2000)
    },
  })
}

/** 删除文档 */
export function useDeleteDoc() {
  const { authFetch } = useAuth()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (docId: string) => deleteKnowledgeDoc(authFetch, docId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.docs })
      qc.invalidateQueries({ queryKey: KEYS.stats })
    },
  })
}

/**
 * 语义搜索（按需触发）。
 *
 * 注意：当前实现是 mutation 而非 query — 语义搜索结果**不缓存**，每次提交都打后端。
 * 因为：
 *   1. 搜索结果与会话/查询强相关，缓存命中率低
 *   2. 知识库向量化完成后命中集会变化
 *
 * 如未来需缓存，改用 `useQuery({ queryKey: ['knowledge', 'search', req], enabled: false })`。
 */
export function useSearchKnowledge() {
  const { authFetch } = useAuth()
  return useMutation<KnowledgeSearchResponse, Error, KnowledgeSearchRequest>({
    mutationFn: (req) => searchKnowledge(authFetch, req),
  })
}
