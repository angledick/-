import { useState, useEffect, useCallback } from 'react'
import { knowledgeApi, type KnowledgeSection } from '../api/config'

// 静态回退内容（API 不可用时使用）
const FALLBACK_SECTIONS: Record<string, string> = {
  'CE 认证': `### CE 认证 (欧盟)
CE标志是产品进入欧盟市场的强制性安全标志，适用于约70%的工业产品。

**适用产品类别**
- 电子产品：需符合EMC指令(2014/30/EU)、LVD指令(2014/35/EU)
- 玩具：需符合玩具安全指令(2009/48/EC)
- 医疗器械：需符合MDR法规(2017/745)
- 个人防护装备：需符合PPE法规(2016/425)
- 无线电设备：需符合RED指令(2014/53/EU)

**LED灯具出口德国 CE 要求**
- 适用指令: LVD 2014/35/EU + EMC 2014/30/EU + RoHS 2011/65/EU
- 还需满足 ERP 能效要求(EU 2019/2020)
- 需要德国授权代表(EC-REP)`,

  'GDPR': `### GDPR 通用数据保护条例
**适用范围**
- 在欧盟境内设立机构处理个人数据
- 向欧盟境内个人提供商品/服务并处理其个人数据
- 监控欧盟境内个人的行为

**核心要求**
- 合法性、公平性和透明性
- 目的限制 · 数据最小化
- 准确性 · 存储限制
- 完整性和保密性

**罚款**：最高 2000万欧元 或 全球年营业额4%`,

  'WEEE': `### WEEE 电子废弃物回收指令
**德国 WEEE (ElektroG)**
- 所有电子电气设备出口德国必须在EAR基金会注册
- 获得WEEE注册号后方可销售
- 需提供回收担保
- 产品标签须含打叉带轮垃圾桶符号`,

  '包装法': `### 德国包装法 (VerpackG)
- 所有销售到德国的商品包装必须在LUCID系统注册
- 需加入双轨回收系统(Dual System)
- 申报包装材料类型和重量`,

  'GPSR': `### GPSR 通用产品安全法规
2024年12月正式生效，取代原GPSD指令。

**新要求**
- 强化在线市场产品安全责任
- 要求指定欧盟境内负责人
- 产品召回流程更严格
- 适用于所有面向消费者的产品`,

  '美国 FCC': `### FCC 认证 (美国)
- 电子产品需FCC认证
- Part 15: 无线电频率设备
- 分为 Verification / DoC / Certification 三级

**FDA (食品接触/医疗器械)**
- 食品接触材料需FDA注册
- 医疗器械需510(k)或PMA

**UL 安全认证**
- 非强制但市场必备`,

  '日本 PSE': `### 日本 PSE 认证
- 电气用品安全法
- 特定电气用品(菱形PSE) + 非特定(圆形PSE)
- LED灯具属于圆形PSE范围`,

  '韩国 KC': `### 韩国 KC 认证
- KC认证(安全) — 韩国产品安全标志
- KCC认证(电磁兼容) — 通讯设备
- 韩国无线电研究所(RRA)负责管理`,

  'REACH': `### REACH 化学品法规 (欧盟)
- 含化学物质的商品（如电池、塑料部件）需注册
- 高度关注物质(SVHC)清单持续更新
- LED灯具需确保符合RoHS有害物质限制`,
}

export default function KnowledgePage() {
  const [sections, setSections] = useState<KnowledgeSection[]>([])
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState<string>('CE 认证')

  const loadSections = useCallback(async () => {
    setLoading(true)
    try {
      const data = await knowledgeApi.list()
      setSections(data.sections)
    } catch {
      setSections([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadSections() }, [loadSections])

  // 合并 API 数据与静态回退
  const allKeys = loading
    ? Object.keys(FALLBACK_SECTIONS)
    : sections.length > 0
      ? sections.map(s => s.title)
      : Object.keys(FALLBACK_SECTIONS)

  const getContent = (key: string): string => {
    if (sections.length > 0) {
      const section = sections.find(s => s.title === key)
      if (section) return section.content
    }
    return FALLBACK_SECTIONS[key] || ''
  }

  return (
    <div className="p-10 px-12 max-w-[1100px]">
      <h1 className="text-[28px] font-semibold text-[#1D1D1F] tracking-tight mb-2">
        合规知识库
      </h1>
      <p className="text-[15px] text-[#86868B] mb-8">
        查阅主要目标市场的合规法规摘要
      </p>

      <div className="flex gap-6">
        {/* Tabs */}
        <div className="w-[200px] shrink-0 flex flex-col gap-0.5">
          {loading ? (
            <div className="text-sm text-[#86868B] py-4">加载中...</div>
          ) : (
            allKeys.map(key => (
              <button
                key={key}
                onClick={() => setActive(key)}
                className={`text-left px-3.5 py-2.5 rounded-lg border-none text-sm cursor-pointer font-[inherit] transition-all ${
                  active === key
                    ? 'bg-[#F5F5F7] text-[#1D1D1F] font-semibold'
                    : 'bg-transparent text-[#86868B] font-normal hover:bg-[#F5F5F7]/50'
                }`}
              >
                {key}
              </button>
            ))
          )}
        </div>

        {/* Content */}
        <div className="flex-1 bg-white rounded-[14px] border border-black/[0.06] px-8 py-7 text-sm leading-relaxed text-[#424245] whitespace-pre-wrap font-[inherit] min-h-[400px]">
          {loading ? (
            <div className="text-sm text-[#86868B]">加载中...</div>
          ) : (
            getContent(active)
          )}
        </div>
      </div>
    </div>
  )
}
