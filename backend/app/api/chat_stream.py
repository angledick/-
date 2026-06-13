"""
SSE 流式对话 — Cowork 层主入口。

端点:
  POST /api/v1/chat/stream          — SSE 流式对话（主入口）
  GET  /api/v1/chat/config          — 获取对话配置
  PUT  /api/v1/chat/config          — 更新对话配置

SSE 消息协议（对齐前端）:
  event: token|skill_start|skill_end|thinking|plan|action_card|error|done
  data: { ... }

四支柱架构 — Cowork 层入口:
  MCP(数据) → Skill(规则) → Workflow(确定性) ← Cowork(入口)
"""

import json
import re
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

import yaml

from app.config import settings
from app.models.schemas import ComplianceQuery, ChatResponse, ComplianceResult
from app.services.prompt_loader import render_prompt

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat-stream"])


# ═════════════════════════════════════════════════════════n# NLU 意图解析 — 内联预处理层（原 nlu.py）
# ═════════════════════════════════════════════════════════n
_NLU_CFG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "config" / "nlu_mappings.yaml"


def _load_nlu_config() -> dict:
    """加载 NLU 映射配置，失败时返回空字典"""
    if _NLU_CFG_PATH.exists():
        return yaml.safe_load(_NLU_CFG_PATH.read_text(encoding="utf-8")) or {}
    return {}


_nlu_cfg = _load_nlu_config()

# 统一关键词库
COMPLIANCE_KEYWORDS: List[str] = _nlu_cfg.get("compliance_keywords", [
    "出口", "卖到", "发给", "合规", "认证", "清关", "海关",
    "HS编码", "VAT", "税率", "进口税", "报关", "合规检查",
])

KNOWN_COUNTRIES: List[str] = _nlu_cfg.get("known_countries", [
    "德国", "法国", "意大利", "西班牙", "荷兰", "比利时",
    "英国", "日本", "韩国", "美国", "新加坡", "澳大利亚",
    "欧盟", "欧洲", "东南亚", "中东",
])

ACTION_PATTERNS: Dict[str, List[str]] = _nlu_cfg.get("action_patterns", {
    "export_check": ["出口", "卖到", "发给", "合规", "清关", "合规检查"],
    "cert_query": ["认证", "证书", "CE", "FDA", "FCC", "UKCA", "ROHS", "WEEE", "REACH", "GPSR"],
    "tax_query": ["税", "VAT", "关税", "税率", "进口税", "Sales Tax"],
    "logistics_query": ["物流", "运输", "发货", "快递", "17TRACK", "追踪"],
    "order_query": ["订单", "退货", "退款", "售后", "拒付"],
    "regulation_query": ["法规", "法律", "条例", "新规", "政策", "DPP", "EPR"],
    "product_manage": ["产品", "上架", "下架", "添加产品", "导入"],
    "system_query": ["状态", "健康", "系统", "配置", "设置"],
})

INTENT_EVENT_MAP: Dict[str, str] = _nlu_cfg.get("intent_event_map", {
    "export_check": "user:compliance_check",
    "cert_query": "user:cert_query",
    "tax_query": "user:tax_query",
    "logistics_query": "user:logistics_query",
    "order_query": "user:order_query",
    "regulation_query": "user:regulation_query",
    "product_manage": "user:product_manage",
    "system_query": "user:system_query",
    "general": "user:query",
})

INTENT_STAGE_MAP: Dict[str, Optional[str]] = _nlu_cfg.get("intent_stage_map", {
    "export_check": "阶段7",
    "cert_query": "阶段2",
    "tax_query": "阶段7",
    "logistics_query": "阶段6",
    "order_query": "阶段9",
    "regulation_query": "阶段2",
    "product_manage": "阶段4",
    "system_query": "阶段1",
    "general": None,
})

_PRODUCT_SEPARATORS: List[str] = _nlu_cfg.get("product_separators", [
    "出口", "卖到", "发给", "运到", "销往",
])

_DANGER_PATTERNS: List[str] = _nlu_cfg.get("danger_patterns", [
    r"(?i)ignore\s+(all\s+)?previous\s+instructions",
    r"(?i)you\s+are\s+now\s+(a|an)\s+",
    r"(?i)system\s*:\s*you\s+must",
    r"<script[^>]*>",
    r"(?i)DROP\s+TABLE",
])

_STATIC_SKILL_MAP: Dict[str, List[str]] = _nlu_cfg.get("static_skill_map", {
    "export_check": ["shopify-admin", "shopify-custom-data"],
    "cert_query": ["shopify-custom-data", "shopify-dev"],
    "tax_query": ["shopify-admin", "shopify-functions"],
    "logistics_query": ["shopify-admin", "shopify-custom-data"],
    "order_query": ["shopify-admin", "shopify-customer"],
    "regulation_query": ["shopify-dev", "web-search"],
    "product_manage": ["shopify-admin", "shopify-onboarding-merchant"],
    "system_query": ["shopify-use-shopify-cli"],
})


# ── NLU 核心函数 ──────────────────────────────────


def parse_intent(
    user_input: str,
    history: Optional[List[Dict]] = None,
    user_id: Optional[str] = None,
) -> dict:
    """意图解析 — 聊天入口预处理步骤。

    从用户消息中提取结构化意图: action类型、产品名、目标国家、
    业务阶段映射、事件类型、推荐Skills、记忆树上下文提示。
    """
    msg = user_input.strip()
    _check_input_safety(msg)
    action, confidence = _classify_action(msg)
    product, country = _extract_entities(msg, action)

    if history and action == "general":
        product, country, action = _enrich_from_history(history, product, country, action)
        if action != "general":
            confidence = max(confidence, 0.55)

    business_stage = INTENT_STAGE_MAP.get(action)
    event_type = INTENT_EVENT_MAP.get(action, "user:query")
    recommended_skills = _get_recommended_skills(action, business_stage)
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
    """将意图解析结果发布为事件到全局事件总线。"""
    try:
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        event_type = intent.get("event_type", "user:query")
        event = await bus.publish_raw({
            "type": event_type,
            "source": "chat_stream",
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


def get_system_prompt() -> str:
    """获取 system prompt。

    优先级:
      1. Agent 配置数据库中 general 类型的 Agent 的 system_prompt
      2. YAML 文件 data/prompts/nlu_fallback.yaml
      3. 硬编码兆底
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


# ── NLU 内部辅助 ──────────────────────────────────


def _classify_action(msg: str) -> tuple:
    """分类用户动作为 action 类型。"""
    has_any_keyword = any(kw in msg for kw in COMPLIANCE_KEYWORDS)
    if not has_any_keyword:
        for action_type, patterns in ACTION_PATTERNS.items():
            if action_type == "export_check":
                continue
            if any(p in msg for p in patterns):
                return action_type, 0.6
        return "general", 0.4
    for action_type, patterns in ACTION_PATTERNS.items():
        if any(p in msg for p in patterns):
            return action_type, 0.7
    return "export_check", 0.5


def _extract_entities(msg: str, action: str) -> tuple:
    """从消息中提取产品名或目标国家。"""
    country = ""
    for c in KNOWN_COUNTRIES:
        if c in msg:
            country = c
            break
    product = msg
    for sep in _PRODUCT_SEPARATORS:
        if sep in product:
            product = product.split(sep)[0]
            break
    if country and country in product:
        product = product.replace(country, "")
    product = product.strip().rstrip("，。,. ")
    if action == "general":
        return "", ""
    return product or msg, country or "欧盟"


def _enrich_from_history(
    history: List[Dict], product: str, country: str, action: str
) -> tuple:
    """从多轮历史消息中增强意图。"""
    for msg in reversed(history):
        role = msg.get("role", "")
        content = msg.get("content", "")
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
    """获取推荐Skills，降级使用静态映射。"""
    try:
        from app.core.skill_registry import get_skill_recommender
        recommender = get_skill_recommender()
        context = {"action": action, "business_stage": business_stage}
        recommendations = recommender.recommend_by_event(context)
        if recommendations:
            return [r.get("name", r) if isinstance(r, dict) else str(r)
                    for r in recommendations[:5]]
    except Exception:
        pass
    return _STATIC_SKILL_MAP.get(action, ["shopify-dev"])


def _get_context_hints(
    product: str, country: str, user_id: Optional[str]
) -> List[str]:
    """从记忆树获取上下文提示。"""
    hints = []
    if not product and not country:
        return hints
    try:
        from app.core.memory_tree import MemoryTree
        product_key = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", f"{product}_{country}").strip("_")
        tree = MemoryTree(product_key)
        l3_list = tree.get_summaries(level=3)
        l3 = l3_list[0] if l3_list else None
        if l3 and l3.get("content"):
            hints.append(f"历史概况: {l3['content'][:100]}")
        l2_list = tree.get_summaries(level=2)
        if isinstance(l2_list, list):
            for item in l2_list[:3]:
                if isinstance(item, dict) and item.get("title"):
                    hints.append(f"{item['title']}")
    except Exception:
        pass
    return hints


def _check_input_safety(msg: str):
    """轻量安全检查 — 检测明显的注入攻击（非阻断式）。"""
    for pattern in _DANGER_PATTERNS:
        if re.search(pattern, msg):
            try:
                from app.core.event_bus import get_event_bus
                bus = get_event_bus()
                asyncio.ensure_future(bus.publish_raw({
                    "type": "risk:security_alert",
                    "source": "chat_stream",
                    "severity": "medium",
                    "data": {"alert": "potential_prompt_injection", "input_preview": msg[:100]},
                }))
            except Exception:
                pass
            break


# ── 请求模型 ──────────────────────────────────

class ChatStreamRequest(BaseModel):
    message: str
    agent_id: Optional[str] = None
    skill_ids: Optional[List[str]] = None
    session_id: Optional[str] = None


class ChatConfig(BaseModel):
    agent_id: Optional[str] = None
    tools: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    pipeline_mode: str = "6step"
    model_role: str = "reasoning"


# ── Optional Auth ──────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


async def _optional_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    if not creds:
        return None
    try:
        from app.core.auth import _decode_token
        from app.storage.user_store import get_user_by_id
        payload = _decode_token(creds.credentials)
        uid = payload.get("sub")
        return get_user_by_id(uid) if uid else None
    except Exception:
        return None


# ── 对话配置管理 ──────────────────────────────────

_chat_config: Dict[str, Any] = {}
_CHAT_CONFIG_PATH = Path("data/chat_config.json")


def _load_chat_config() -> Dict[str, Any]:
    """从文件加载对话配置，不存在时返回默认值"""
    defaults = {
        "agent_id": "agent_qa",
        "tools": [],
        "skills": [],
        "pipeline_mode": "6step",
        "model_role": "reasoning",
    }
    try:
        if _CHAT_CONFIG_PATH.exists():
            data = json.loads(_CHAT_CONFIG_PATH.read_text(encoding="utf-8"))
            return {**defaults, **data}
    except Exception as e:
        logger.warning("Failed to load chat config, using defaults: %s", e)
    return defaults


def _save_chat_config(config: Dict[str, Any]) -> None:
    """持久化对话配置到文件"""
    try:
        _CHAT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CHAT_CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


# 模块加载时初始化
_chat_config.update(_load_chat_config())


@router.get("/api/v1/chat/config", summary="获取对话配置")
async def get_chat_config():
    return _chat_config


@router.put("/api/v1/chat/config", summary="更新对话配置")
async def update_chat_config(req: ChatConfig):
    global _chat_config
    if req.agent_id is not None:
        _chat_config["agent_id"] = req.agent_id
    if req.tools is not None:
        _chat_config["tools"] = req.tools
    if req.skills is not None:
        _chat_config["skills"] = req.skills
    if req.pipeline_mode:
        _chat_config["pipeline_mode"] = req.pipeline_mode
    if req.model_role:
        _chat_config["model_role"] = req.model_role
    _save_chat_config(_chat_config)
    return _chat_config


# ═══════════════════════════════════════════════════════
# SSE 流式对话主入口
# ═══════════════════════════════════════════════════════

@router.post("/api/v1/chat/stream", summary="SSE流式对话")
async def chat_stream(req: ChatStreamRequest, current_user: dict = Depends(_optional_user)):
    """SSE流式对话 — Cowork层主入口。

    管线: 用户消息 → RBAC检查 → NLU解析 → EventBus发布 →
      ├─ 合规查询: ComplianceFlow六阶段 → Skill推荐 → RAG补充 → 记忆树写入 → SSE
      ├─ 通用问题: AstraAssistant对话 → 记忆树写入 → SSE
      └─ 命令操作: SkillExecutor执行 → EventBus发布 → SSE
    """

    async def event_generator():
        user_id = current_user["id"] if current_user else None
        user_role = current_user.get("role", "admin") if current_user else "admin"
        start_time = datetime.now(timezone.utc)

        try:
            # ── Step 1: RBAC 权限检查 ──────────────
            rbac_allowed, rbac_reason = await _check_rbac(user_id, user_role, req.message)
            if not rbac_allowed:
                yield _sse_event("error", {
                    "code": "rbac_denied",
                    "message": rbac_reason,
                })
                yield _sse_event("done", {"finish_reason": "rbac_denied"})
                return

            # ── Step 2: Thinking — NLU意图解析 ──────
            yield _sse_event("thinking", {
                "content": f"正在分析您的问题...",
                "depth": 1,
            })

            from app.storage import session_store

            # 加载多轮历史
            history = []
            sid = req.session_id
            if sid:
                history = session_store.get_recent_messages(sid, n=6)
                if not history:
                    sid = None
            if not sid:
                sid = session_store.create_session(req.message[:40], user_id=user_id)
                # 发布会话创建事件
                try:
                    from app.core.event_bus import get_event_bus
                    await get_event_bus().publish_raw({
                        "type": "session:created",
                        "source": "chat_stream",
                        "data": {"session_id": sid, "user_id": user_id},
                    })
                except Exception:
                    pass

            # 保存用户消息
            session_store.add_message(sid, "user", req.message)

            # NLU 解析
            intent = parse_intent(req.message, history=history, user_id=user_id)
            product = intent.get("product", "")
            country = intent.get("target_country", "")
            action = intent.get("action", "general")

            # 发布意图事件到 EventBus
            await publish_intent_event(intent, user_id=user_id)

            # ── Step 3: Plan — 执行计划 ──────────────
            force_sdk = bool(req.agent_id)
            if action == "general" or force_sdk:
                plan_steps = _build_plan("general", "", "")
            else:
                plan_steps = _build_plan(action, product, country)
            yield _sse_event("plan", {"steps": plan_steps, "current": 0})

            # ── 分支路由 ────────────────────────────
            if action == "general" or force_sdk:
                async for event in _handle_general_stream(req, intent, sid, user_id, plan_steps):
                    yield event
                return

            # ── 合规查询/专业查询分支 ──────────────
            async for event in _handle_compliance_stream(
                req, intent, product, country, action, sid, user_id, plan_steps
            ):
                yield event

        except Exception as e:
            yield _sse_event("error", {
                "code": "internal_error",
                "message": f"处理异常: {str(e)[:200]}",
            })
            yield _sse_event("done", {"finish_reason": "error"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════
# 合规查询流式处理
# ═══════════════════════════════════════════════════════

async def _handle_compliance_stream(
    req: ChatStreamRequest,
    intent: dict,
    product: str,
    country: str,
    action: str,
    session_id: str,
    user_id: Optional[str],
    plan_steps: List[Dict],
):
    """合规查询的完整SSE事件流。"""

    # ── Step 4: 合规数据检查 ─────────────────
    plan_steps[1]["status"] = "running"
    yield _sse_event("plan", {"steps": plan_steps, "current": 1})

    from app.services.compliance import (
        build_compliance_report, persist_compliance_memory,
    )

    report_data = await build_compliance_report(
        product=product,
        country=country,
        intent=intent,
        include_rag=False,
    )
    compliance_dict = report_data["compliance_dict"]
    compliance_result = report_data["compliance_result"]
    report = report_data["report"]
    product_id = report_data["product_id"]

    plan_steps[1]["status"] = "done"

    # ── Step 5: Skills 推荐 ─────────────────
    plan_steps[2]["status"] = "running"
    yield _sse_event("plan", {"steps": plan_steps, "current": 2})

    recommended_skills = intent.get("recommended_skills", [])
    for sk in recommended_skills:
        yield _sse_event("skill_start", {
            "skill": sk,
            "args": {"reason": f"基于{action}意图推荐"},
        })
        yield _sse_event("skill_end", {
            "skill": sk,
            "result": {},
            "status": "success",
        })
    plan_steps[2]["status"] = "done"

    # ── Step 6: RAG 补充 ─────────────────
    plan_steps[3]["status"] = "running"
    yield _sse_event("plan", {"steps": plan_steps, "current": 3})

    rag_results = []
    try:
        from app.knowledge.store import retrieve_context, format_context_for_assistant
        rag_results = retrieve_context(f"{product} 出口 {country} 合规要求")
        if rag_results:
            report += f"\n\n---\n{format_context_for_assistant(rag_results)}"
    except Exception:
        pass
    plan_steps[3]["status"] = "done"

    # ── Step 7: 流式输出报告 ─────────────
    plan_steps[4]["status"] = "running"
    yield _sse_event("plan", {"steps": plan_steps, "current": 4})

    for line in report.split("\n"):
        yield _sse_event("token", {"content": line + "\n"})
        await asyncio.sleep(0.02)

    plan_steps[4]["status"] = "done"

    # ── Step 8: Action Card（推荐操作） ────
    actions = _build_action_cards(product, country, compliance_dict, intent)
    if actions:
        yield _sse_event("action_card", {"actions": actions})

    # ── Step 9: 记忆持久化 ─────────────────
    await persist_compliance_memory(
        product=product,
        country=country,
        compliance_dict=compliance_dict,
        report=report,
        session_id=session_id,
        user_id=user_id or "default",
        product_id=product_id,
    )

    # 保存助手回复到会话
    from app.storage import session_store
    session_store.add_message(
        session_id, "assistant", report,
        compliance_result=compliance_dict,
        intent=intent,
        sources=[r.get("source_url", "") for r in rag_results],
    )
    # 发布新消息事件
    try:
        from app.core.event_bus import get_event_bus
        await get_event_bus().publish_raw({
            "type": "message:created",
            "source": "chat_stream",
            "data": {
                "session_id": session_id,
                "user_id": user_id,
                "content_preview": report[:100],
            },
        })
    except Exception:
        pass

    # ── Step 10: 发布合规事件 ─────────────
    try:
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        risk_level = compliance_dict.get("risk_level", "low")
        event_type = "compliance:check_passed" if risk_level != "high" else "compliance:check_failed"
        await bus.publish_raw({
            "type": event_type,
            "source": "chat_stream",
            "product_id": product_id,
            "business_stage": intent.get("business_stage"),
            "severity": "high" if risk_level == "high" else "low",
            "data": {
                "product": product,
                "country": country,
                "risk_level": risk_level,
                "risk_score": compliance_dict.get("risk_score", 0),
                "certifications": len(compliance_dict.get("certifications", [])),
                "session_id": session_id,
            },
        })
    except Exception:
        pass

    # ── Done ──────────────────────────────
    yield _sse_event("done", {
        "finish_reason": "complete",
        "session_id": session_id,
        "intent": intent,
        "usage": {
            "prompt_tokens": len(req.message),
            "completion_tokens": len(report),
        },
    })


# ═══════════════════════════════════════════════════════
# 通用问题流式处理
# ═══════════════════════════════════════════════════════

async def _handle_general_stream(
    req: ChatStreamRequest,
    intent: dict,
    session_id: str,
    user_id: Optional[str],
    plan_steps: List[Dict],
):
    """通用问题的SSE事件流（使用AstraAssistant或降级回复）。

    若指定了 agent_id，则加载该 Agent 的 system_prompt 通过 SDK 驱动。
    """
    from app.services.astra_assistant import AstraAssistant
    assistant = AstraAssistant()

    # 尝试 AstraAssistant SDK 对话
    if settings.sdk_enabled and settings.anthropic_api_key:
        plan_steps[0]["status"] = "done"
        plan_steps[1]["status"] = "running"
        yield _sse_event("plan", {"steps": plan_steps, "current": 1})

        try:
            # 如果指定了 agent_id，用该 Agent 的身份执行
            if req.agent_id:
                async for event in assistant.run_as_agent_stream(
                    agent_id=req.agent_id,
                    message=req.message,
                    session_id=session_id,
                ):
                    if event["type"] == "text":
                        yield _sse_event("token", {"content": event["content"]})
                    elif event["type"] == "tool_use":
                        yield _sse_event("skill_start", {"skill": event["tool_name"], "args": event["tool_input"]})
                    elif event["type"] == "tool_result":
                        yield _sse_event("skill_end", {"skill": event["tool_name"], "result": event.get("content"), "status": "success"})
                    elif event["type"] == "thinking":
                        yield _sse_event("thinking", {"content": event["content"]})
                    elif event["type"] == "error":
                        yield _sse_event("error", {"code": "agent_error", "message": event["error"]})
                        return
                    elif event["type"] == "usage":
                        pass
                yield _sse_event("done", {"finish_reason": "complete"})
                return

            # 未指定 agent_id，使用默认 system_prompt
            result = await assistant.chat(
                session_id=session_id,
                message=req.message,
            )
            response_text = result["response"]

            plan_steps[1]["status"] = "done"

            for line in response_text.split("\n"):
                yield _sse_event("token", {"content": line + "\n"})
                await asyncio.sleep(0.02)

            from app.storage import session_store
            session_store.add_message(session_id, "assistant", response_text, intent=intent)
            # 发布新消息事件
            try:
                from app.core.event_bus import get_event_bus
                await get_event_bus().publish_raw({
                    "type": "message:created",
                    "source": "chat_stream",
                    "data": {
                        "session_id": session_id,
                        "user_id": user_id,
                        "content_preview": response_text[:100],
                    },
                })
            except Exception:
                pass

            yield _sse_event("done", {
                "finish_reason": "complete",
                "session_id": session_id,
                "intent": intent,
                "usage": result.get("usage", {}),
            })
            return

        except Exception:
            plan_steps[1]["status"] = "failed"

    # 降级回复
    reply = (
        "我是避风港跨境合规智能体。\n\n"
        "**可用功能：**\n"
        "- 合规查询：输入「产品 出口 国家」，如「手机出口德国」\n"
        "- 认证查询：输入「认证 CE 德国」\n"
        "- 税率查询：输入「VAT 法国」\n"
        "- 法规查询：输入「欧盟 GPSR 法规」\n"
        "- 物流查询：输入「物流 追踪」\n\n"
        "如需深入分析，请确保已配置 ANTHROPIC_API_KEY 以使用 Claude Agent SDK 的全部能力。"
    )

    for line in reply.split("\n"):
        yield _sse_event("token", {"content": line + "\n"})

    from app.storage import session_store
    session_store.add_message(session_id, "assistant", reply, intent=intent)
    # 发布新消息事件
    try:
        from app.core.event_bus import get_event_bus
        await get_event_bus().publish_raw({
            "type": "message:created",
            "source": "chat_stream",
            "data": {
                "session_id": session_id,
                "user_id": user_id,
                "content_preview": reply[:100],
            },
        })
    except Exception:
        pass

    yield _sse_event("done", {
        "finish_reason": "complete",
        "session_id": session_id,
        "intent": intent,
    })


# ═══════════════════════════════════════════════════════
# 辅助方法
# ═══════════════════════════════════════════════════════

async def _check_rbac(
    user_id: Optional[str], role: str, message: str
) -> tuple:
    """查询级RBAC检查。"""
    if not user_id:
        return True, ""
    try:
        from app.core.rbac import get_rbac_manager
        rbac = get_rbac_manager()
        user_info = rbac.get_user(user_id)
        if not user_info:
            return True, ""
        user_role = user_info.get("role", "admin")
        if user_role == "viewer":
            if any(kw in message for kw in ["执行", "批量", "删除", "修改", "上架"]):
                return False, "viewer角色不允许执行写操作，请联系管理员升级权限"
    except Exception:
        pass
    return True, ""


def _build_plan(action: str, product: str, country: str) -> List[Dict]:
    """构建执行计划步骤（展示给前端）。"""
    if action == "general":
        return [
            {"id": "nlu", "action": "理解意图", "status": "done"},
            {"id": "chat", "action": "生成回复", "status": "running"},
        ]
    return [
        {"id": "nlu", "action": f"意图解析: {product}→{country}" if product else "意图解析", "status": "done"},
        {"id": "rule", "action": "合规数据检查", "status": "pending"},
        {"id": "skill", "action": "Skills推荐", "status": "pending"},
        {"id": "rag", "action": "RAG法规检索", "status": "pending"},
        {"id": "report", "action": "生成合规报告", "status": "pending"},
    ]


def _build_action_cards(
    product: str, country: str, compliance_dict: dict, intent: dict
) -> List[Dict[str, Any]]:
    """构建推荐操作卡片（含 product_id 深度链接）。"""
    actions = []
    product_id = intent.get("product_id", "")
    risk_level = compliance_dict.get("risk_level", "low")

    if compliance_dict.get("certifications"):
        actions.append({
            "id": "action_check_certs",
            "label": "查看认证状态",
            "description": f"查看{product}在{country}的{len(compliance_dict['certifications'])}项认证",
            "skill": "shopify-custom-data",
            "confidence": 0.9,
            "risk_level": "low",
            "product_id": product_id,
            "stage": intent.get("business_stage"),
        })

    if risk_level in ("medium", "high"):
        actions.append({
            "id": "action_remediate",
            "label": "执行整改",
            "description": f"风险等级{risk_level}，建议立即执行整改",
            "skill": "shopify-admin",
            "confidence": 0.85,
            "risk_level": risk_level,
            "product_id": product_id,
            "stage": intent.get("business_stage"),
        })

    if compliance_dict.get("hs_code"):
        actions.append({
            "id": "action_hs_detail",
            "label": "HS编码详情",
            "description": f"HS编码: {compliance_dict['hs_code']}",
            "skill": "shopify-admin",
            "confidence": 0.95,
            "risk_level": "low",
            "product_id": product_id,
        })

    return actions


def _sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """格式化SSE事件。"""
    json_data = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {json_data}\n\n"
