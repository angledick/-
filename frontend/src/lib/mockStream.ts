import type { StreamEvent } from '@/types'

const delay = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

function inferProduct(message: string) {
  const normalized = message.trim()
  const exportMatch = normalized.match(/(.+?)出口(.+?)(需要|合规|认证|$)/)
  if (exportMatch) {
    return {
      product: (exportMatch[1]?.trim() as string) || '目标产品',
      market: (exportMatch[2]?.trim().replace(/[，。？！?]/g, '') as string) || '目标市场',
    }
  }
  return {
    product: normalized.slice(0, 16) || '目标产品',
    market: normalized.includes('德国') ? '德国' : '目标市场',
  }
}

const textChunks = (text: string, size = 16) => {
  const chunks: string[] = []
  for (let i = 0; i < text.length; i += size) {
    chunks.push(text.slice(i, i + size))
  }
  return chunks
}

export async function* createMockStream(message: string): AsyncGenerator<StreamEvent> {
  const { product, market } = inferProduct(message)
  const browserUrl = message.match(/https?:\/\/\S+/)?.[0]

  if (message.includes('浏览器') || message.includes('打开') || browserUrl) {
    yield {
      type: 'browser_result',
      result: {
        ok: true,
        action_type: browserUrl ? 'navigate' : 'site_command',
        url: browserUrl ?? 'https://example.com',
        title: browserUrl ? '目标网页' : '示例站点命令',
        data: browserUrl ? [] : [{ title: '示例结果', status: 'mock' }],
        raw: { mode: 'mock_stream', message },
      },
    }
    await delay(240)
    yield { type: 'token', content: browserUrl ? `已打开 ${browserUrl}。` : '浏览器命令已执行。' }
    yield {
      type: 'done',
      finish_reason: 'stop',
      usage: {
        mode: 'mock_browser',
        events: 2,
      },
    }
    return
  }

  yield {
    type: 'thinking',
    content: `先识别产品与目标市场，再按 HS 归类、认证准入、税率、标签和平台上架风险逐项核验。当前输入识别为：${product} / ${market}。`,
    depth: 1,
  }
  await delay(420)

  yield {
    type: 'agent_status',
    agents: [
      { agent: 'NLU', status: 'complete', result: { product, target_country: market } },
      { agent: 'RuleEngine', status: 'running' },
      { agent: 'RAG', status: 'pending' },
      { agent: 'ConflictArbiter', status: 'pending' },
    ],
  }
  await delay(220)

  yield {
    type: 'plan',
    current: 1,
    steps: [
      { id: 'identify', action: '识别产品与目标市场', status: 'done' },
      { id: 'classify', action: '检索 HS 编码与品类规则', status: 'running', skill: 'knowledge_search' },
      { id: 'certs', action: '匹配认证与市场准入要求', status: 'pending', skill: 'compliance-checker' },
      { id: 'actions', action: '生成风险分级、待办清单与建议动作', status: 'pending' },
    ],
  }
  await delay(520)

  yield {
    type: 'skill_start',
    skill: 'knowledge_search',
    args: {
      product,
      market,
      corpus: ['hs_codes', 'certifications', 'vat_rates'],
    },
  }
  await delay(680)

  yield {
    type: 'skill_end',
    skill: 'knowledge_search',
    status: 'success',
    duration_ms: 642,
    result: {
      hs_code: '8541.4100',
      category: 'LED lighting products',
      vat_rate: market.includes('德国') ? '19%' : '需按目标市场确认',
      risk_level: 'low',
    },
  }
  await delay(360)

  yield {
    type: 'plan',
    current: 2,
    steps: [
      { id: 'identify', action: '识别产品与目标市场', status: 'done' },
      { id: 'classify', action: '检索 HS 编码与品类规则', status: 'done', skill: 'knowledge_search', duration_ms: 642 },
      { id: 'certs', action: '匹配认证与市场准入要求', status: 'running', skill: 'compliance-checker' },
      { id: 'actions', action: '生成风险分级、待办清单与建议动作', status: 'pending' },
    ],
  }
  await delay(360)

  yield {
    type: 'skill_start',
    skill: 'compliance-checker',
    args: {
      hs_code: '8541.4100',
      market,
      checks: ['CE', 'RoHS', 'WEEE', 'labeling', 'VAT'],
    },
  }
  await delay(760)

  yield {
    type: 'skill_end',
    skill: 'compliance-checker',
    status: 'success',
    duration_ms: 718,
    result: {
      required: ['CE', 'RoHS', 'WEEE'],
      risk_level: 'medium',
      risk_score: 62,
      blockers: ['WEEE 注册状态需要确认', '德文标签与说明书需要核对'],
    },
  }
  await delay(300)

  yield {
    type: 'conflict',
    conflicts: [
      {
        type: 'certification',
        sources: {
          RuleEngine: 'CE、RoHS、WEEE',
          RAG: 'CE、RoHS、WEEE、LUCID',
        },
        resolution: market.includes('德国') ? '补充 LUCID' : '以目标市场规则为准',
        reason: '法规检索命中目标市场包装注册要求，优先级高于通用认证清单。',
      },
    ],
  }
  await delay(220)

  yield {
    type: 'agent_status',
    agents: [
      { agent: 'NLU', status: 'complete', result: { product, target_country: market } },
      { agent: 'RuleEngine', status: 'complete', result: { hs_code: '8541.4100', vat_rate: market.includes('德国') ? 19 : undefined } },
      { agent: 'RAG', status: 'complete', result: { citations: ['CE', 'RoHS', 'WEEE'] } },
      { agent: 'ConflictArbiter', status: 'complete', result: { conflicts: 1, resolution: '已仲裁' } },
    ],
  }
  await delay(240)

  const answer = [
    `初步判断：${product} 出口 ${market}，需要重点关注 **CE、RoHS、WEEE** 三类要求。`,
    '',
    '- 风险等级：中风险。主要原因是 WEEE 注册状态和本地化标签仍需核验。',
    '- HS 编码建议先按 `8541.4100` 方向核验，最终以报关归类为准。',
    '- 如果目标市场是德国，VAT 通常按 19% 处理，但还要结合销售主体与清关模式确认。',
    '- 下一步建议先核对证书有效期、产品标签、德文说明书和包装法/LUCID 注册状态。',
  ].join('\n')

  for (const chunk of textChunks(answer)) {
    yield { type: 'token', content: chunk }
    await delay(90)
  }

  yield {
    type: 'action_card',
    actions: [
      {
        id: 'run-full-check',
        label: '生成完整检查清单',
        description: '按 HS 编码、认证、标签、税率和清关材料生成可执行清单。',
        skill: 'compliance-checker',
        confidence: 0.86,
        expected_result: '得到逐项待办与风险分级。',
        risk_level: 'low',
        status: 'pending',
      },
      {
        id: 'verify-weee',
        label: '核验 WEEE 注册状态',
        description: '检查当前产品或品牌是否已完成德国 WEEE 注册。',
        skill: 'cert-manager',
        confidence: 0.78,
        expected_result: '确认是否需要补注册或续期。',
        risk_level: 'medium',
        status: 'pending',
      },
    ],
  }
  await delay(240)

  yield {
    type: 'plan',
    current: 4,
    steps: [
      { id: 'identify', action: '识别产品与目标市场', status: 'done' },
      { id: 'classify', action: '检索 HS 编码与品类规则', status: 'done', skill: 'knowledge_search', duration_ms: 642 },
      { id: 'certs', action: '匹配认证与市场准入要求', status: 'done', skill: 'compliance-checker', duration_ms: 718 },
      { id: 'actions', action: '生成风险分级、待办清单与建议动作', status: 'done' },
    ],
  }
  await delay(160)

  yield {
    type: 'done',
    finish_reason: 'stop',
    usage: {
      mode: 'mock_stream',
      events: 10,
    },
  }
}
