import { NavLink } from 'react-router-dom'

const TABS = [
  { to: '/config/agents', label: 'Agent' },
  { to: '/config/skills', label: 'Skills' },
  { to: '/config/tools', label: 'Tools' },
  { to: '/config/oauth', label: 'OAuth' },
  { to: '/config/integrations', label: '集成' },
  { to: '/config/models', label: '模型' },
]

export default function ConfigTabs() {
  return (
    <div className="flex items-center gap-1 mb-6 border-b border-black/6 pb-0">
      {TABS.map(tab => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) =>
            `px-4 py-2.5 text-sm transition-colors border-b-2 -mb-px ${
              isActive
                ? 'font-semibold text-[#1D1D1F] border-[#1D1D1F]'
                : 'text-[#86868B] border-transparent hover:text-[#1D1D1F]'
            }`
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </div>
  )
}
