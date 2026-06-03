"""
NLU: 事件感知意图解析器 (EventAwareIntentParser)

从简单关键词提取升级为事件驱动的意图解析层，集成:
  - GlobalEventBus: 每次解析自动发布 user:query / user:compliance_check 事件
  - 10大业务阶段映射: 根据意图推断 business_stage
  - SkillRecommender: 意图解析后推荐可用 Skills
  - MemoryTree: 从 L1-L3 加载多轮上下文增强解析
  - SecuritySandbox: 对用户输入做安全检查

开源参考:
  - Open WebUI (139k⭐): 对话界面层意图理解模式
  - Chatwoot (29.9k⭐): 全渠道客服意图分类

数据流转:
  用户消息 → NLU.parse_intent() → 结构化意图 → EventBus发布 → 下游流水线
"""

import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.config import settings
from app.services.prompt_loader import render_prompt


# ═══════════════════════════════════════════════════════
# 统一关键词库（消除 chat.py/nlu.py 重复）
# ═══════════════════════════════════════════════════════

COMPLIANCE_KEYWORDS = [
    "出口", "卖到", "发给", "合规", "认证", "清关", "海关",
    "HS编码", "VAT", "税率", "进口税", "报关", "合规检查",
]

KNOWN_COUNTRIES = [
    "德国", "法国", "意大利", "西班牙", "荷兰", "比利时",
    "英国", "日本", "韩国", "美国", "新加坡", "澳大利亚",
    "欧盟", "欧洲", "东南亚", "中东",
]

# 动作关键词 → action 类型映射
ACTION_PATTERNS: Dict[str, List[str]] = {
    "export_check": ["出口", "卖到", "发给", "合规", "清关", "合规检查"],
    "cert_query": ["认证", "证书", "CE", "FDA", "FCC", "UKCA", "ROHS", "WEEE", "REACH", "GPSR"],
    "tax_query": ["税", "VAT", "关税", "税率", "进口税", "Sales Tax"],
    "logistics_query": ["物流", "运输", "发货", "快递", "17TRACK", "追踪"],
    "order_query": ["订单", "退货", "退款", "售后", "拒付"],
    "regulation_query": ["法规", "法律", "条例", "新规", "政策", "DPP", "EPR"],
    "product_manage": ["产品", "上架", "下架", "添加产品", "导入"],
    "system_query": ["状态", "健康", "系统", "配置", "设置"],
}

# 意图 → 事件类型映射
INTENT_EVENT_MAP = {
    "export_check": "user:compliance_check",
    "cert_query": "user:cert_query",
    "tax_query": "user:tax_query",
    "logistics_query": "user:logistics_query",
    "order_query": "user:order_query",
    "regulation_query": "user:regulation_query",
    "product_manage": "user:product_manage",
    "system_query": "user:system_query",
    "general": "user:query",
}

# 意图 → 业务阶段映射（10大阶段）
INTENT_STAGE_MAP = {
    "export_check": "阶段7",       # 出口报关
    "cert_query": "阶段2",         # 选品与样品设计
    "tax_query": "阶段7",          # 出口报关
    "logistics_query": "阶段6",    # 订单处理与境内物流
    "order_query": "阶段9",        # 交付售后与退货
    "regulation_query": "阶段2",   # 选品与样品设计
    "product_manage": "阶段4",     # 商品上架与内容合规
    "system_query": "阶段1",       # 建站与基础环境
    "general": None,
}

# 产品分割词（提取产品名）
_PRODUCT_SEPARATORS = ["出口", "卖到", "发给", "运到", "销往"]


# ═══════════════════════════════════════════════════════
# 核心意图解析
# ═══════════════════════════════════════════════════════

def get_system_prompt() -> str:
    """获取 NLU system prompt。

    优先级：
    1. Agent 配置数据库中 general 类型的 Agent 的 system_prompt
    2. YAML 文件 data/prompts/nlu_fallback.yaml
    3. 硬编码兜底
    """
    try:
        from app.storage.agent_config_store import get_general_system_prompt
        return get_general_system_prompt()
    except Exception:
        pass
    try:
        return render_prompt("nlu_fallback")
    except FileNotFoundError:
        return (
            "你是一个出口合规意图解析器。分析用户消息，提取结构化信息。\n\n"
            "返回严格JSON:\n{\n  \"product\": \"产品中文名称\",\n"
            "  \"target_country\": \"目标出口国家中文名\",\n"
            "  \"action\": \"export_check | cert_query | tax_query | general\",\n"
            "  \"confidence\": 0.0~1.0\n}"
        )


def parse_intent(
    user_input: str,
    history: Optional[List[Dict]] = None,
    user_id: Optional[str] = None,
) -> dict:
    """增强意图解析 — 事件感知的结构化意图提取。

    相比旧版新增:
      - business_stage: 映射到10大业务阶段
      - event_type: 推断的事件类型
      - recommended_skills: 推荐Skills列表
      - context_hints: 记忆树上下文提示

    Args:
        user_input: 用户自然语言输入
        history:    最近N条会话消息（多轮上下文）
        user_id:    当前用户ID（用于记忆树查询）

    Returns:
        结构化意图字典
    """
    msg = user_input.strip()

    # 1. 安全检查（SecuritySandbox 轻量校验）
    _check_input_safety(msg)

    # 2. 基础意图识别
    action, confidence = _classify_action(msg)

    # 3. 提取产品和国家
    product, country = _extract_entities(msg, action)

    # 4. 从多轮历史增强
    if history and action == "general":
        product, country, action = _enrich_from_history(history, product, country, action)
        if action != "general":
            confidence = max(confidence, 0.55)

    # 5. 映射业务阶段
    business_stage = INTENT_STAGE_MAP.get(action)

    # 6. 映射事件类型
    event_type = INTENT_EVENT_MAP.get(action, "user:query")

    # 7. 推荐Skills（桥接SkillRecommender）
    recommended_skills = _get_recommended_skills(action, business_stage)

    # 8. 记忆树上下文提示
    context_hints = _get_context_hints(product, country, user_id)

    return {
        "product": product,
        "target_country": country,
        "action": action,
        "confidence": confidence,
        "business_stage": business_stage,
        "event_type": event_type,
        "recommended_skills": recommended_skills,
        "context_hints": context_hints,
    }


async def publish_intent_event(
    intent: dict,
    user_id: Optional[str] = None,
) -> Optional[Any]:
    """将意图解析结果发布为事件到全局事件总线。

    根据 intent.action 映射到对应的 user_action 事件类型。

    Args:
        intent: parse_intent 返回的结构化意图
        user_id: 用户ID

    Returns:
        EventRecord 或 None（EventBus 不可用时）
    """
    try:
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        event_type = intent.get("event_type", "user:query")
        event = await bus.publish_raw({
            "type": event_type,
            "source": "nlu",
            "product_id": None,
            "business_stage": intent.get("business_stage"),
            "severity": "low",
            "data": {
                "user_id": user_id or "anonymous",
                "action": intent.get("action", "general"),
                "product": intent.get("product", ""),
                "target_country": intent.get("target_country", ""),
                "confidence": intent.get("confidence", 0),
                "recommended_skills": intent.get("recommended_skills", []),
            },
        })
        return event
    except Exception:
        return None


# ═══════════════════════════════════════════════════════
# 内部方法
# ═══════════════════════════════════════════════════════

def _classify_action(msg: str) -> tuple:
    """分类用户动作为 action 类型。

    Returns:
        (action_type, confidence)
    """
    # 不含任何合规/业务关键词 → 通用问题
    has_any_keyword = any(kw in msg for kw in COMPLIANCE_KEYWORDS)
    if not has_any_keyword:
        # 尝试匹配其他动作模式
        for action_type, patterns in ACTION_PATTERNS.items():
            if action_type == "export_check":
                continue
            if any(p in msg for p in patterns):
                return action_type, 0.6
        return "general", 0.4

    # 按优先级匹配
    for action_type, patterns in ACTION_PATTERNS.items():
        if any(p in msg for p in patterns):
            return action_type, 0.7

    return "export_check", 0.5


def _extract_entities(msg: str, action: str) -> tuple:
    """从消息中提取产品名和目标国家。

    Returns:
        (product, country)
    """
    # 提取国家
    country = ""
    for c in KNOWN_COUNTRIES:
        if c in msg:
            country = c
            break

    # 提取产品名
    product = msg
    for sep in _PRODUCT_SEPARATORS:
        if sep in product:
            product = product.split(sep)[0]
            break

    # 清理国家名
    if country and country in product:
        product = product.replace(country, "")

    product = product.strip().rstrip("，。,. ")

    # 通用问题不需要产品/国家
    if action == "general":
        return "", ""

    return product or msg, country or "欧盟"


def _enrich_from_history(
    history: List[Dict], product: str, country: str, action: str
) -> tuple:
    """从多轮历史消息中增强意图（产品和国家继承）。"""
    for msg in reversed(history):
        role = msg.get("role", "")
        content = msg.get("content", "")

        # 从助手回复中提取产品信息
        if role == "assistant":
            intent_data = msg.get("intent")
            if isinstance(intent_data, dict):
                if not product and intent_data.get("product"):
                    product = intent_data["product"]
                if not country and intent_data.get("target_country"):
                    country = intent_data["target_country"]
                if action == "general" and intent_data.get("action") != "general":
                    action = intent_data["action"]

    return product, country, action


def _get_recommended_skills(action: str, business_stage: Optional[str]) -> List[str]:
    """从 SkillRecommender 获取推荐Skills。

    降级: 如果 SkillRecommender 不可用，使用静态映射。
    """
    # 尝试使用 SkillRecommender
    try:
        from app.core.skill_registry import get_skill_recommender
        recommender = get_skill_recommender()
        # 构造伪事件上下文用于推荐
        context = {
            "action": action,
            "business_stage": business_stage,
        }
        recommendations = recommender.recommend_by_event(context)
        if recommendations:
            return [r.get("name", r) if isinstance(r, dict) else str(r)
                    for r in recommendations[:5]]
    except Exception:
        pass

    # 静态降级映射
    _STATIC_SKILL_MAP = {
        "export_check": ["shopify-admin", "shopify-custom-data"],
        "cert_query": ["shopify-custom-data", "shopify-dev"],
        "tax_query": ["shopify-admin", "shopify-functions"],
        "logistics_query": ["shopify-admin", "shopify-custom-data"],
        "order_query": ["shopify-admin", "shopify-customer"],
        "regulation_query": ["shopify-dev", "web-search"],
        "product_manage": ["shopify-admin", "shopify-onboarding-merchant"],
        "system_query": ["shopify-use-shopify-cli"],
    }
    return _STATIC_SKILL_MAP.get(action, ["shopify-dev"])


def _get_context_hints(
    product: str, country: str, user_id: Optional[str]
) -> List[str]:
    """从记忆树获取上下文提示。

    从 MemoryTree L1-L3 层加载与当前产品和市场相关的历史上下文。
    """
    hints = []
    if not product and not country:
        return hints

    try:
        from app.core.memory_tree import MemoryTree
        # 尝试加载产品级记忆
        product_key = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", f"{product}_{country}").strip("_")
        tree = MemoryTree(product_key)
        # L3: 全局索引
        l3_list = tree.get_summaries(level=3)
        l3 = l3_list[0] if l3_list else None
        if l3 and l3.get("content"):
            hints.append(f"历史概况: {l3['content'][:100]}")
        # L2: 领域概览
        l2_list = tree.get_summaries(level=2)
        if isinstance(l2_list, list):
            for item in l2_list[:3]:
                if isinstance(item, dict) and item.get("title"):
                    hints.append(f"{item['title']}")
    except Exception:
        pass

    return hints


def _check_input_safety(msg: str):
    """轻量安全检查 — 检测明显的注入攻击。

    非阻断式: 仅记录警告，不抛异常。
    """
    danger_patterns = [
        r"(?i)ignore\s+(all\s+)?previous\s+instructions",
        r"(?i)you\s+are\s+now\s+(a|an)\s+",
        r"(?i)system\s*:\s*you\s+must",
        r"<script[^>]*>",
        r"(?i)DROP\s+TABLE",
    ]
    for pattern in danger_patterns:
        if re.search(pattern, msg):
            try:
                from app.core.event_bus import get_event_bus
                import asyncio
                bus = get_event_bus()
                # 非阻塞发布安全事件
                asyncio.ensure_future(bus.publish_raw({
                    "type": "risk:security_alert",
                    "source": "nlu",
                    "severity": "medium",
                    "data": {"alert": "potential_prompt_injection", "input_preview": msg[:100]},
                }))
            except Exception:
                pass
            break
