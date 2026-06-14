import { useState, useEffect, useCallback } from 'react'
import { memoryApi, cliApi } from '../api/config'
import TreeView from '../components/memory/TreeView'
import MarkdownViewer from '../components/memory/MarkdownViewer'
import type { NLRecord } from '../types'

type MemoryNode = {
  id: string
  label: string
  icon?: string
  children?: MemoryNode[]
  meta?: string
}

function buildTree(namespaces: string[], records: Record<string, NLRecord[]>): MemoryNode[] {
  const root: MemoryNode[] = []
  const nsMap = new Map<string, MemoryNode>()

  for (const ns of namespaces.sort()) {
    const node: MemoryNode = {
      id: ns,
      label: ns,
      icon: '▤',
      children: [],
      meta: `${records[ns]?.length ?? 0}`,
    }
    nsMap.set(ns, node)
    root.push(node)
  }

  for (const [ns, items] of Object.entries(records)) {
    for (const item of items) {
      const nsNode = nsMap.get(ns)
      if (nsNode && nsNode.children) {
        nsNode.children.push({
          id: `${ns}/${item.record_id}`,
          label: item.title || item.key,
          icon: '📄',
          meta: item.updated_at ? new Date(item.updated_at).toLocaleDateString('zh-CN') : undefined,
        })
      }
    }
  }

  return root
}

export default function MemoryTreePage() {
  const [namespaces, setNamespaces] = useState<string[]>([])
  const [records, setRecords] = useState<Record<string, NLRecord[]>>({})
  const [selectedNode, setSelectedNode] = useState<MemoryNode | null>(null)
  const [selectedRecord, setSelectedRecord] = useState<NLRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  // CLI 历史（加载但不渲染，预留扩展）
  const [, setExecHistory] = useState<unknown[]>([])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const nsRes = await memoryApi.listNamespaces()
      setNamespaces(nsRes.namespaces)

      const recordsMap: Record<string, NLRecord[]> = {}
      // Load CLI history as a special namespace
      try {
        const hist = await cliApi.history(5)
        setExecHistory(hist.history)
      } catch { /* ignore */ }

      for (const ns of nsRes.namespaces) {
        try {
          const recRes = await memoryApi.listRecords(ns)
          recordsMap[ns] = recRes.records as NLRecord[]
        } catch {
          recordsMap[ns] = []
        }
      }
      setRecords(recordsMap)
    } catch {
      setNamespaces([])
      setRecords({})
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleSelect = useCallback(async (node: MemoryNode) => {
    setSelectedNode(node)

    // If it's a leaf node (has path), fetch record content
    if (node.id.includes('/') && !node.children) {
      const [ns, recordId] = node.id.split('/', 2)
      if (!ns || !recordId) { setSelectedRecord(null); return }
      try {
        const record = await memoryApi.getRecord(ns, recordId) as NLRecord
        setSelectedRecord(record)
      } catch {
        setSelectedRecord(null)
      }
    } else {
      setSelectedRecord(null)
    }
  }, [])

  const tree = buildTree(namespaces, records)

  // Filter by search
  const filteredTree = searchQuery
    ? tree
        .map(ns => ({
          ...ns,
          children: ns.children?.filter(c =>
            c.label.toLowerCase().includes(searchQuery.toLowerCase())
          ),
        }))
        .filter(ns => ns.children && ns.children.length > 0)
    : tree

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Left: Tree navigation */}
      <div className="w-64 shrink-0 border-r border-black/6 bg-white overflow-y-auto">
        <div className="px-3 py-3.5 border-b border-black/6">
          <h2 className="text-sm font-semibold text-[#1D1D1F]">记忆树</h2>
          <p className="text-[11px] text-[#86868B] mt-0.5">浏览知识库与记忆</p>
        </div>

        {/* Search */}
        <div className="px-3 py-2">
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="搜索..."
            className="w-full px-2.5 py-1.5 rounded-md border border-black/10 text-xs outline-none"
          />
        </div>

        {loading ? (
          <div className="px-3 py-6 text-xs text-[#86868B] text-center">加载中...</div>
        ) : filteredTree.length === 0 ? (
          <div className="px-3 py-6 text-xs text-[#86868B] text-center">
            {searchQuery ? '无匹配结果' : '暂无记忆数据'}
          </div>
        ) : (
          <div className="px-2 py-1">
            <TreeView
              nodes={filteredTree}
              selectedId={selectedNode?.id}
              onSelect={handleSelect}
            />
          </div>
        )}
      </div>

      {/* Right: Content */}
      <div className="flex-1 overflow-y-auto bg-[#FAFAFA]">
        {selectedRecord ? (
          <div className="p-6 max-w-4xl">
            <MarkdownViewer
              content={selectedRecord.content_nl}
              title={selectedRecord.title || selectedRecord.key}
              tags={selectedRecord.tags}
              updatedAt={selectedRecord.updated_at}
              onClose={() => setSelectedRecord(null)}
            />
          </div>
        ) : selectedNode ? (
          <div className="p-6 max-w-4xl">
            <div className="bg-white rounded-xl border border-black/6 p-6 text-center">
              <div className="text-3xl mb-2">📂</div>
              <div className="text-sm font-semibold text-[#1D1D1F]">{selectedNode.label}</div>
              {selectedNode.children && (
                <div className="text-xs text-[#86868B] mt-1">
                  {selectedNode.children.length} 条记录
                </div>
              )}
              {!selectedNode.children && (
                <div className="text-xs text-[#86868B] mt-1">请选择一条记录查看详情</div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-[#86868B]">
            <div className="text-center">
              <div className="text-5xl mb-3">🌳</div>
              <div className="font-semibold text-[#1D1D1F] mb-1">记忆树浏览器</div>
              <div className="text-xs">在左侧选择一个命名空间或记录</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
