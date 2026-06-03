import StreamChat from '../components/StreamChat'
import AgentSelector from '../components/AgentSelector'
import ToolPanel from '../components/ToolPanel'
import SkillPanel from '../components/SkillPanel'

export default function ChatWorkspacePage() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Top toolbar: Agent / Tool / Skill selectors */}
      <div className="shrink-0 px-4 py-2.5 border-b border-black/6 bg-white flex items-center gap-3">
        <AgentSelector />
        <div className="w-px h-5 bg-[#E5E5EA]" />
        <ToolPanel />
        <SkillPanel />
        <div className="flex-1" />
        <span className="text-[11px] text-[#C7C7CC]">通用对话工作台</span>
      </div>

      {/* Chat area */}
      <div className="flex-1 min-h-0">
        <StreamChat
          title="对话工作台"
          subtitle="通用问答 / 系统配置 / 合规咨询"
          placeholder="输入任何问题，或使用 / 查看命令..."
        />
      </div>
    </div>
  )
}
