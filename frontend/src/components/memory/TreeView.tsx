import { useState } from 'react'

interface TreeNode {
  id: string
  label: string
  icon?: string
  children?: TreeNode[]
  meta?: string
}

interface Props {
  nodes: TreeNode[]
  selectedId?: string
  onSelect: (node: TreeNode) => void
}

export default function TreeView({ nodes, selectedId, onSelect }: Props) {
  return (
    <div className="space-y-0.5">
      {nodes.map(node => (
        <TreeNodeItem
          key={node.id}
          node={node}
          depth={0}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}

function TreeNodeItem({
  node,
  depth,
  selectedId,
  onSelect,
}: {
  node: TreeNode
  depth: number
  selectedId?: string
  onSelect: (node: TreeNode) => void
}) {
  const [expanded, setExpanded] = useState(depth < 1)
  const hasChildren = node.children && node.children.length > 0
  const isSelected = node.id === selectedId

  return (
    <div>
      <div
        className={`flex items-center gap-1.5 px-2 py-1.5 rounded-md cursor-pointer text-sm transition-colors ${
          isSelected
            ? 'bg-[#0071E3]/10 text-[#0071E3] font-medium'
            : 'text-[#424245] hover:bg-[#F5F5F7]'
        }`}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
        onClick={() => {
          if (hasChildren) setExpanded(!expanded)
          onSelect(node)
        }}
      >
        {/* Expand/collapse */}
        {hasChildren ? (
          <span className="text-xs text-[#C7C7CC] w-4 shrink-0">
            {expanded ? '▼' : '▶'}
          </span>
        ) : (
          <span className="w-4 shrink-0" />
        )}

        {/* Icon */}
        {node.icon && <span className="text-sm shrink-0">{node.icon}</span>}

        {/* Label */}
        <span className="truncate flex-1">{node.label}</span>

        {/* Meta */}
        {node.meta && (
          <span className="text-[10px] text-[#C7C7CC] shrink-0">{node.meta}</span>
        )}
      </div>

      {/* Children */}
      {expanded && hasChildren && (
        <div>
          {node.children!.map(child => (
            <TreeNodeItem
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}
