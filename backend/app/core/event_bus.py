"""
全局事件总线 (GlobalEventBus) — 基于 EventChain 升级的跨产品、跨用户事件广播系统。

职责：
  1. 事件标准化管道: raw_event → 类型归类 → 元数据提取 → 格式化 → EventRecord
  2. 跨产品事件广播: 全局事件（法规变更/系统告警）广播到所有相关产品
  3. 产品级事件隔离: 每个产品维护独立事件链，同时同步到全局总线
  4. 事件订阅分发: 支持精准/批量/全局/条件4种订阅方式（对齐指南 §6.3）

存储方式:
  - 全局事件: data/global/events/bus.json
  - 产品事件: data/products/{product_id}/events/chain.json
  - 归档: data/global/events/archive/

数据流转:
  raw_event → GlobalEventBus.publish() → 标准化 → 路由分发 → 产品级+全局存储
                                         ↓
                                    订阅者通知（WebSocket/Webhook/通知引擎）
"""

import json
import re
import uuid
import asyncio
import yaml
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Callable, Awaitable
from collections import defaultdict

from app.config import settings
from app.models.schemas import (
    EventRecord, EventCategory, DataSourceInfo,
    EventDefinition, SubscriptionFilter
)

logger = logging.getLogger(__name__)

# ── 存储目录 ──
DATA_DIR = Path(settings.data_dir)
GLOBAL_EVENTS_DIR = DATA_DIR / "global" / "events"
PRODUCTS_DIR = DATA_DIR / "products"

# 事件处理回调类型
EventHandler = Callable[[EventRecord], Awaitable[None]]


class EventStandardizer:
    """事件标准化管道: raw_event → 类型归类 → 元数据提取 → 格式化 → EventRecord"""

    # 事件类型前缀到分类的映射
    CATEGORY_MAP = {
        "product:": EventCategory.lifecycle,
        "lifecycle:": EventCategory.lifecycle,
        "compliance:": EventCategory.compliance,
        "certification:": EventCategory.certification,
        "cert:": EventCategory.certification,
        "order:": EventCategory.order,
        "fulfillment:": EventCategory.order,
        "regulation:": EventCategory.regulation,
        "market:": EventCategory.regulation,
        "risk:": EventCategory.risk_alert,
        "metric:": EventCategory.risk_alert,
        "system:": EventCategory.system,
        "sync:": EventCategory.system,
        "user:": EventCategory.user_action,
    }

    @classmethod
    def classify_event(cls, event_type: str) -> EventCategory:
        """根据事件类型前缀自动归类到8类事件体系"""
        for prefix, category in cls.CATEGORY_MAP.items():
            if event_type.startswith(prefix):
                return category
        return EventCategory.system

    # 兼容别名
    classify_event_type = classify_event

    @classmethod
    def standardize(
        cls,
        raw_event: Dict[str, Any],
        event_registry: Optional["EventRegistry"] = None,
    ) -> EventRecord:
        """将原始事件标准化为 EventRecord

        Args:
            raw_event: 原始事件数据，至少包含 type 和 source 字段
            event_registry: 事件注册表，用于补充事件定义信息
        """
        event_type = raw_event.get("type", "system:unknown")
        category = cls.classify_event_type(event_type)

        # 从注册表补充信息
        severity = raw_event.get("severity", "low")
        data_sources = raw_event.get("data_sources", {})
        if event_registry:
            event_def = event_registry.get_event(event_type)
            if event_def:
                severity = raw_event.get("severity", event_def.severity)
                if not data_sources:
                    data_sources = event_def.data_sources.model_dump()

        return EventRecord(
            id=raw_event.get("id", uuid.uuid4().hex[:12]),
            type=event_type,
            category=category,
            source=raw_event.get("source", "system"),
            product_id=raw_event.get("product_id"),
            business_stage=raw_event.get("business_stage"),
            data=raw_event.get("data", {}),
            data_sources=DataSourceInfo(**data_sources) if isinstance(data_sources, dict) else data_sources,
            severity=severity,
            error=raw_event.get("error"),
            created_at=raw_event.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


class GlobalEventBus:
    """全局事件总线 — 跨产品、跨用户事件广播

    用法:
        bus = GlobalEventBus()

        # 注册事件处理器
        bus.on("compliance:check_passed", my_handler)

        # 发布事件
        await bus.publish(EventRecord(
            type="compliance:check_passed",
            source="compliance_rules",
            product_id="p_led_de_001",
            data={"risk_level": "low"}
        ))

        # 查询全局事件
        events = bus.get_recent_events(limit=50)
    """

    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._global_handlers: List[EventHandler] = []
        self._recent_events: List[EventRecord] = []
        self._max_recent = 500  # 内存中保留最近500条事件
        self._event_registry: Optional["EventRegistry"] = None
        self._subscriptions: Dict[str, Dict] = {}  # sub_id -> {subscriber, filter, channels}

    def set_event_registry(self, registry: "EventRegistry"):
        """设置事件注册表（用于标准化时补充事件定义信息）"""
        self._event_registry = registry

    # ── 事件发布 ──────────────────────────────────

    async def publish(self, event: EventRecord) -> EventRecord:
        """发布事件到全局总线

        流程:
        1. 标准化事件（补充分类/元数据）
        2. 写入全局事件总线
        3. 路由到产品级事件链（如果关联产品）
        4. 分发给匹配的处理器
        5. 分发给匹配的订阅者
        """
        # 1. 确保事件有标准分类
        if event.category == EventCategory.system and event.type != "system:unknown":
            event.category = EventStandardizer.classify_event_type(event.type)

        # 2. 存入全局事件总线
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_recent:
            self._recent_events = self._recent_events[-self._max_recent:]

        # 3. 持久化到全局事件文件
        await self._persist_global_event(event)

        # 4. 路由到产品级事件链
        if event.product_id:
            await self._persist_product_event(event)

        # 5. 分发给注册的处理器
        await self._dispatch_to_handlers(event)

        # 6. 分发给匹配的订阅者
        await self._dispatch_to_subscribers(event)

        return event

    async def publish_raw(self, raw_event: Dict[str, Any]) -> EventRecord:
        """从原始事件数据发布（自动标准化）"""
        event = EventStandardizer.standardize(raw_event, self._event_registry)
        return await self.publish(event)

    # ── 事件处理器注册 ──────────────────────────────

    def on(self, event_type: str, handler: EventHandler):
        """注册特定事件类型的处理器"""
        self._handlers[event_type].append(handler)

    def on_all(self, handler: EventHandler):
        """注册全局事件处理器（接收所有事件）"""
        self._global_handlers.append(handler)

    def off(self, event_type: str, handler: EventHandler):
        """移除事件处理器"""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    # ── 事件订阅 ──────────────────────────────────

    async def subscribe(
        self,
        subscriber: str,
        subscription_type: str,
        filter_config: SubscriptionFilter,
        channels: List[str] = None,
    ) -> str:
        """创建事件订阅

        Args:
            subscriber: 订阅者标识（WebSocket连接ID/Webhook URL）
            subscription_type: 订阅类型 precise/batch/global/conditional
            filter_config: 订阅过滤器
            channels: 通知渠道列表
        Returns:
            订阅ID
        """
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        self._subscriptions[sub_id] = {
            "id": sub_id,
            "subscriber": subscriber,
            "type": subscription_type,
            "filter": filter_config,
            "channels": channels or ["websocket"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return sub_id

    async def unsubscribe(self, sub_id: str) -> bool:
        """取消订阅"""
        if sub_id in self._subscriptions:
            del self._subscriptions[sub_id]
            return True
        return False

    def get_subscriptions(self) -> List[Dict]:
        """获取所有订阅"""
        return list(self._subscriptions.values())

    # ── 事件查询 ──────────────────────────────────

    def get_recent_events(
        self,
        limit: int = 50,
        category: Optional[EventCategory] = None,
        product_id: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[EventRecord]:
        """查询最近的全局事件"""
        results = self._recent_events

        if category:
            results = [e for e in results if e.category == category]
        if product_id:
            results = [e for e in results if e.product_id == product_id]
        if severity:
            results = [e for e in results if e.severity == severity]

        return list(reversed(results[-limit:]))

    def get_event_timeline(self, limit: int = 20) -> List[str]:
        """获取自然语言事件时间线（用于Dashboard展示）"""
        icons = {"critical": "🚨", "high": "🔴", "medium": "🟡", "low": "🟢"}
        timeline = []
        for e in reversed(self._recent_events[-limit:]):
            icon = icons.get(e.severity, "⚪")
            ts = e.created_at[:19]
            product = f" [{e.product_id}]" if e.product_id else ""
            timeline.append(f"{icon} [{e.severity.title()}] {ts}{product} {e.type}")
        return timeline

    def get_event_stats(self) -> Dict[str, Any]:
        """获取事件统计"""
        total = len(self._recent_events)
        by_category = defaultdict(int)
        by_severity = defaultdict(int)
        for e in self._recent_events:
            by_category[e.category.value] += 1
            by_severity[e.severity] += 1
        return {
            "total_events": total,
            "by_category": dict(by_category),
            "by_severity": dict(by_severity),
            "subscriptions": len(self._subscriptions),
        }

    # ── 内部方法: 持久化 ──────────────────────────────

    async def _persist_global_event(self, event: EventRecord):
        """持久化到全局事件总线文件"""
        try:
            GLOBAL_EVENTS_DIR.mkdir(parents=True, exist_ok=True)
            bus_file = GLOBAL_EVENTS_DIR / "bus.json"

            existing = []
            if bus_file.exists():
                try:
                    existing = json.loads(bus_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, Exception):
                    existing = []

            existing.append(event.model_dump())

            # 保留最近2000条事件，超出的归档
            if len(existing) > 2000:
                archive_dir = GLOBAL_EVENTS_DIR / "archive"
                archive_dir.mkdir(exist_ok=True)
                to_archive = existing[:-1000]
                remaining = existing[-1000:]

                archive_file = archive_dir / f"events_{datetime.now(timezone.utc).strftime('%Y%m')}.json"
                if archive_file.exists():
                    try:
                        archived = json.loads(archive_file.read_text(encoding="utf-8"))
                        archived.extend(to_archive)
                        archive_file.write_text(json.dumps(archived, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                    except Exception:
                        archive_file.write_text(json.dumps(to_archive, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                else:
                    archive_file.write_text(json.dumps(to_archive, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

                existing = remaining

            bus_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.warning("全局事件持久化失败: %s", e)

    async def _persist_product_event(self, event: EventRecord):
        """持久化到产品级事件链"""
        if not event.product_id:
            return
        try:
            product_events_dir = PRODUCTS_DIR / event.product_id / "events"
            product_events_dir.mkdir(parents=True, exist_ok=True)
            chain_file = product_events_dir / "chain.json"

            chain_data = {
                "product_id": event.product_id,
                "events": [],
                "timeline": [],
                "total_events": 0,
            }
            if chain_file.exists():
                try:
                    chain_data = json.loads(chain_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, Exception):
                    pass

            # 追加事件
            chain_data["events"].append(event.model_dump())

            # 更新时间线
            icons = {"critical": "🚨", "high": "🔴", "medium": "🟡", "low": "🟢"}
            icon = icons.get(event.severity, "⚪")
            ts = event.created_at[:19]
            timeline_entry = f"{icon} [{event.severity.title()}] {ts} {event.type}"
            chain_data["timeline"].insert(0, timeline_entry)
            chain_data["total_events"] = len(chain_data["events"])

            # 保留最近500条
            if len(chain_data["events"]) > 500:
                chain_data["events"] = chain_data["events"][-500:]
                chain_data["timeline"] = chain_data["timeline"][:500]

            chain_file.write_text(json.dumps(chain_data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.warning("产品事件持久化失败 product=%s: %s", event.product_id, e)

    # ── 内部方法: 分发 ──────────────────────────────

    async def _dispatch_to_handlers(self, event: EventRecord):
        """分发事件到注册的处理器"""
        handlers_to_call = list(self._global_handlers)
        handlers_to_call.extend(self._handlers.get(event.type, []))

        # 通配符匹配
        for pattern, handlers in self._handlers.items():
            if pattern.endswith("*") and event.type.startswith(pattern[:-1]):
                handlers_to_call.extend(handlers)

        for handler in handlers_to_call:
            try:
                await handler(event)
            except Exception as e:
                logger.warning("事件处理器执行失败: event=%s handler=%s err=%s", event.type, getattr(handler, '__name__', repr(handler)), e)

    async def _dispatch_to_subscribers(self, event: EventRecord):
        """分发事件到匹配的订阅者

        三路分发:
          - WebSocket: 通过 ws_manager 向匹配连接推送
          - notification: 通过 notification_engine 发送通知
          - webhook: 通过 WebhookAdapter 调用订阅者 URL
        """
        import json

        for sub_id, sub in list(self._subscriptions.items()):
            if not self._matches_subscription(event, sub):
                continue

            channels = sub.get("channels", ["websocket"])
            subscriber = sub.get("subscriber", "")

            event_dict = event.model_dump()
            if hasattr(event.category, 'value'):
                event_dict["category"] = event.category.value
            event_dict["sub_id"] = sub_id

            for channel in channels:
                try:
                    if channel == "websocket":
                        from app.services.ws_manager import ws_manager
                        await ws_manager.send_alert(subscriber, {
                            "type": "event",
                            "event": event_dict,
                        })

                    elif channel == "notification":
                        from app.core.notification_engine import get_notification_engine
                        from app.models.schemas import NotificationPayload
                        engine = get_notification_engine()
                        await engine.send(NotificationPayload(
                            type=event.type,
                            title=f"事件: {event.type}",
                            message=str(event.data) if event.data else event.type,
                            product_id=event.product_id,
                            severity=event.severity,
                        ))

                    elif channel == "webhook":
                        from app.core.channel_adapter import WebhookAdapter
                        adapter = WebhookAdapter({})
                        await adapter.send_message(subscriber, json.dumps(
                            event_dict, ensure_ascii=False, default=str
                        ))

                except Exception as e:
                    logger.warning("订阅分发失败: channel=%s subscriber=%s err=%s", channel, subscriber, e)
                    continue  # 单通道失败不影响其他通道

    def _matches_subscription(self, event: EventRecord, sub: Dict) -> bool:
        """检查事件是否匹配订阅条件"""
        filter_config: SubscriptionFilter = sub.get("filter")
        if not filter_config:
            return True

        sub_type = sub.get("type", "global")

        # 精准订阅：匹配产品ID
        if sub_type == "precise" and filter_config.product_ids:
            if event.product_id not in filter_config.product_ids:
                return False

        # 批量订阅：匹配标签
        if sub_type == "batch" and filter_config.tags:
            event_tags = event.data.get("tags", [])
            if not any(t in event_tags for t in filter_config.tags):
                return False

        # 条件订阅：匹配表达式
        if sub_type == "conditional" and filter_config.condition_expr:
            try:
                if not self._eval_condition(filter_config.condition_expr, event):
                    return False
            except Exception:
                return False

        # 事件类型过滤
        if filter_config.event_types:
            if event.type not in filter_config.event_types:
                return False

        # 严重级别过滤
        if filter_config.severity:
            if event.severity not in filter_config.severity:
                return False

        return True

    def _eval_condition(self, expr: str, event: EventRecord) -> bool:
        """安全评估条件表达式 (AST白名单替代eval，防沙箱逃逸)"""
        import ast

        safe_vars = {
            "event_type": event.type,
            "severity": event.severity,
            "category": event.category.value,
            "product_id": event.product_id or "",
            "source": event.source,
        }
        safe_vars.update({k: v for k, v in event.data.items() if isinstance(v, (str, int, float, bool))})
        try:
            tree = ast.parse(expr.strip(), mode='eval')
            # AST节点白名单 — 仅允许比较/布尔运算/常量/变量名
            allowed_nodes = {
                ast.Expression, ast.BoolOp, ast.Compare, ast.BinOp, ast.UnaryOp,
                ast.And, ast.Or, ast.Not,
                ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
                ast.Eq, ast.NotEq, ast.Lt, ast.Gt, ast.LtE, ast.GtE,
                ast.In, ast.NotIn,
                ast.USub, ast.UAdd,
                ast.Name, ast.Constant, ast.Load,
                ast.Tuple, ast.List,
            }
            for node in ast.walk(tree):
                if type(node) not in allowed_nodes:
                    raise ValueError(f"Disallowed AST node: {type(node).__name__}")

            return bool(eval(compile(tree, '<safe_condition>', 'eval'), {"__builtins__": {}}, safe_vars))
        except Exception:
            return False


class EventRegistry:
    """事件注册表 - 配置文件驱动

    从 data/events/builtin/ 目录的Markdown文件加载事件定义，
    支持QAAgent和用户动态增删改事件类型。
    """

    def __init__(self, config_dir: str = None):
        self.config_dir = Path(config_dir or (DATA_DIR / "events" / "builtin"))
        self._events: Dict[str, EventDefinition] = {}
        self._load_all_events()

    def _load_all_events(self):
        """加载所有事件配置。配置目录必须存在。"""
        if not self.config_dir.exists():
            raise FileNotFoundError(
                f"事件配置目录不存在: {self.config_dir}\n"
                "请确保 data/events/builtin/ 已创建"
            )
        for md_file in self.config_dir.glob("*.md"):
            if md_file.name.startswith("_"):
                continue
            self._load_events_from_file(md_file)
        if not self._events:
            raise ValueError(f"事件配置目录中未找到有效事件定义: {self.config_dir}")

    def _load_events_from_file(self, file_path: Path):
        """从Markdown文件解析事件定义（支持 YAML front-matter 和表格两种格式）。"""
        content = file_path.read_text(encoding="utf-8")
        # YAML front-matter 解析
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if match:
            import yaml
            front_matter = yaml.safe_load(match.group(1))
            if front_matter and isinstance(front_matter, dict):
                events_list = front_matter.get("events", [])
                if events_list:
                    for evt in events_list:
                        self._events[evt["event_code"]] = self._create_event_from_dict(evt, str(file_path))
                    return
        # 表格解析
        events = self._parse_event_table(content, str(file_path))
        for event_def in events:
            self._events[event_def.event_code] = event_def

    def _create_event_from_dict(self, data: dict, source_file: str = "") -> EventDefinition:
        """从 YAML front-matter 字典创建 EventDefinition。"""
        from app.models.schemas import EventCategory
        category = EventStandardizer.classify_event_type(data.get("event_code", ""))
        # 兼容 tools 字段：YAML 中可能是 dict 列表（含 name/impl），需提取 name 字符串
        raw_tools = data.get("tools", [])
        tools = [t["name"] if isinstance(t, dict) and "name" in t else t for t in raw_tools]
        return EventDefinition(
            event_code=data.get("event_code", ""),
            event_name=data.get("event_name", ""),
            business_stage=data.get("business_stage", ""),
            category=category,
            trigger_condition=data.get("trigger_condition", ""),
            related_worker=data.get("worker", ""),
            severity=data.get("severity", "low"),
            notify_strategy=data.get("notify_strategy", ["dashboard"]),
            tools=tools,
            skills=data.get("skills", []),
            agent_action=data.get("agent_action", ""),
            description=data.get("description", ""),
            config_file=source_file,
        )

    def _parse_event_table(self, content: str, source_file: str = "") -> List[EventDefinition]:
        """解析Markdown表格中的事件定义"""
        events = []
        lines = content.split("\n")
        in_table = False
        headers = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|") if c.strip()]

                if not in_table:
                    headers = cells
                    in_table = True
                elif cells and "---" not in cells[0]:
                    event = self._create_event_from_row(headers, cells, source_file)
                    if event:
                        events.append(event)
            else:
                in_table = False
                headers = []

        return events

    def _create_event_from_row(
        self, headers: List[str], cells: List[str], source_file: str
    ) -> Optional[EventDefinition]:
        """从表格行创建事件定义"""
        if len(cells) < 4:
            return None

        data = dict(zip(headers, cells))

        # 灵活的列名映射
        event_code = data.get("事件编码") or data.get("event_code") or data.get("Event Code", "")
        event_name = data.get("事件名称") or data.get("event_name") or data.get("Event Name", "")
        business_stage = data.get("业务阶段") or data.get("business_stage") or data.get("Business Stage", "")
        trigger_condition = data.get("触发条件") or data.get("trigger_condition") or data.get("Trigger Condition", "")

        if not event_code:
            return None

        # 分类自动推断
        category = EventStandardizer.classify_event_type(event_code)

        notify_str = data.get("通知策略") or data.get("notify_strategy") or data.get("Notify Strategy", "dashboard")
        notify_strategy = [s.strip() for s in notify_str.split(",") if s.strip()]

        severity = data.get("严重级别") or data.get("severity") or data.get("Severity", "low")

        return EventDefinition(
            event_code=event_code,
            event_name=event_name,
            business_stage=business_stage,
            category=category,
            trigger_condition=trigger_condition,
            related_worker=data.get("关联Worker") or data.get("related_worker") or data.get("Related Worker", ""),
            severity=severity,
            notify_strategy=notify_strategy,
            description=data.get("描述") or data.get("description") or data.get("Description", ""),
            config_file=source_file,
        )


    # ── 查询接口 ──────────────────────────────────

    def get_event(self, event_code: str) -> Optional[EventDefinition]:
        """获取事件定义"""
        return self._events.get(event_code)

    def get_all_events(self) -> List[EventDefinition]:
        """获取所有事件定义"""
        return list(self._events.values())

    def get_events_by_stage(self, stage: str) -> List[EventDefinition]:
        """按业务阶段获取事件"""
        return [e for e in self._events.values() if stage in e.business_stage]

    def get_events_by_category(self, category: EventCategory) -> List[EventDefinition]:
        """按事件分类获取"""
        return [e for e in self._events.values() if e.category == category]

    # ── 管理接口（QAAgent调用）──────────────────────

    async def register_event(self, event_def: EventDefinition, file_name: str = "custom_events.md"):
        """注册新事件类型（写入配置文件+内存缓存）"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.config_dir / file_name

        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
        else:
            content = (
                "# 自定义事件定义\n\n"
                "> 由QAAgent维护，用户可通过前端管理界面或对话添加新事件\n\n"
                "| 事件编码 | 事件名称 | 业务阶段 | 触发条件 | 关联Worker | 严重级别 | 通知策略 |\n"
                "|----------|----------|----------|----------|------------|----------|----------|\n"
            )

        new_row = (
            f"| {event_def.event_code} | {event_def.event_name} | {event_def.business_stage} "
            f"| {event_def.trigger_condition} | {event_def.related_worker} "
            f"| {event_def.severity} | {','.join(event_def.notify_strategy)} |\n"
        )
        content += new_row
        file_path.write_text(content, encoding="utf-8")

        self._events[event_def.event_code] = event_def
        return True

    async def update_event(self, event_def: EventDefinition):
        """更新事件定义"""
        if event_def.event_code not in self._events:
            return False
        event_def.updated_at = datetime.now(timezone.utc).isoformat()
        self._events[event_def.event_code] = event_def
        # 重写对应配置文件
        await self._rewrite_config_file(event_def)
        return True

    async def delete_event(self, event_code: str) -> bool:
        """删除事件类型（归档到_archive目录）"""
        event = self._events.get(event_code)
        if not event:
            return False

        # 从配置文件中移除
        for md_file in self.config_dir.glob("*.md"):
            if md_file.name.startswith("_"):
                continue
            await self._remove_event_from_file(md_file, event_code)

        # 归档
        archive_dir = self.config_dir / "_archive"
        archive_dir.mkdir(exist_ok=True)
        archive_file = archive_dir / f"{event_code.replace(':', '_')}.md"
        archive_content = (
            f"# 已归档事件: {event_code}\n\n"
            f"归档时间: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"原始定义: {json.dumps(event.model_dump(), ensure_ascii=False, indent=2, default=str)}\n"
        )
        archive_file.write_text(archive_content, encoding="utf-8")

        del self._events[event_code]
        return True

    async def _remove_event_from_file(self, file_path: Path, event_code: str):
        """从文件中移除事件行"""
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        new_lines = [line for line in lines if event_code not in line]
        file_path.write_text("\n".join(new_lines), encoding="utf-8")

    async def _rewrite_config_file(self, event_def: EventDefinition):
        """重写事件配置文件

        将事件定义回写到对应的 Markdown 配置文件。
        如果事件已存在则替换行，不存在则追加新行。
        """
        if event_def.config_file:
            file_path = Path(event_def.config_file)
        else:
            file_path = self.config_dir / "custom_events.md"

        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 读取或创建配置文件
        content = ""
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
        else:
            content = (
                "# 自定义事件定义\n\n"
                "| 事件编码 | 事件名称 | 业务阶段 | 触发条件 | 关联Worker | 严重级别 | 通知策略 |\n"
                "|----------|----------|----------|----------|------------|----------|----------|\n"
            )

        search_pattern = f"| {event_def.event_code} |"
        new_row = (
            f"| {event_def.event_code} | {event_def.event_name} | "
            f"{event_def.business_stage} | {event_def.trigger_condition} | "
            f"{event_def.related_worker or ''} | {event_def.severity} | "
            f"{','.join(event_def.notify_strategy)} |\n"
        )

        if search_pattern in content:
            # 替换已有行
            lines = content.split("\n")
            updated_lines = []
            for line in lines:
                if search_pattern in line:
                    updated_lines.append(new_row.rstrip())
                else:
                    updated_lines.append(line)
            content = "\n".join(updated_lines)
        else:
            # 追加新行
            if not content.endswith("\n"):
                content += "\n"
            content += new_row

        file_path.write_text(content, encoding="utf-8")


# ── 全局单例 ──────────────────────────────────

_event_bus: Optional[GlobalEventBus] = None
_event_registry: Optional[EventRegistry] = None


def get_event_bus() -> GlobalEventBus:
    """获取全局事件总线单例"""
    global _event_bus, _event_registry
    if _event_bus is None:
        _event_bus = GlobalEventBus()
        _event_registry = EventRegistry()
        _event_bus.set_event_registry(_event_registry)
    return _event_bus


def get_event_registry() -> EventRegistry:
    """获取事件注册表单例"""
    global _event_registry
    if _event_registry is None:
        _event_registry = EventRegistry()
    return _event_registry
