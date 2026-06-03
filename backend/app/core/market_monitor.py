"""市场监控模块 — 委托 AstraAssistant 全权执行联网搜索和分析。

核心设计：
  - 不自己写爬虫/RSS 读取器，全部委托 AstraAssistant 联网搜索
  - 薄封装层：触发 AstraAssistant → 解析返回结果 → 写入 L5 event_store
  - 支持定时触发（Scheduler）和手动触发（API）

数据流转:
  - 触发者: Scheduler（定时）/ API（手动）
  - 执行者: AstraAssistant（联网搜索 + CLI 浏览 + 推理分析）
  - 读取: L2 project_memory（影响分析时）
  - 写入: L5 event_store（market_event）
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from app.services.astra_assistant import AstraAssistant, AstraAssistantError

logger = logging.getLogger(__name__)


class MarketMonitor:
    """市场监控 — 薄封装层，委托 AstraAssistant 执行。

    用法:
        monitor = MarketMonitor()
        events = await monitor.poll_markets()
    """

    def __init__(self):
        self.agent = AstraAssistant()

    async def poll_markets(self) -> list[dict]:
        """【核心】轮询所有目标市场 — 全部委托给 AstraAssistant。

        AstraAssistant 自主完成：联网搜索 → 浏览监管网站 → 提取变更 → 结构化输出。
        返回解析后的市场事件列表。
        """
        logger.info("MarketMonitor: polling all markets via AstraAssistant...")
        try:
            result = await self.agent.run_task(
                prompt_name="market_monitor",
            )
            events = self._parse_market_events(result)
            logger.info(f"MarketMonitor: found {len(events)} market events")
            return events
        except AstraAssistantError as e:
            logger.error(f"MarketMonitor: AstraAssistant failed: {e}")
            return []
        except Exception as e:
            logger.error(f"MarketMonitor: unexpected error: {e}", exc_info=True)
            return []

    async def poll_market(self, market_code: str) -> list[dict]:
        """轮询单个市场。"""
        logger.info(f"MarketMonitor: polling market '{market_code}'...")
        try:
            result = await self.agent.run_task(
                prompt_name="market_monitor",
                context={"market_code": market_code},
            )
            return self._parse_market_events(result)
        except Exception as e:
            logger.error(f"MarketMonitor: poll market '{market_code}' failed: {e}")
            return []

    async def analyze_impact(self, market_event: dict) -> list[dict]:
        """分析市场事件对用户产品的个性化影响。

        从 L2 project_memory 读取用户产品列表，委托 AstraAssistant 分析影响。

        Args:
            market_event: 市场事件（来自 poll_markets 返回的单条）

        Returns:
            list[dict]: 受影响产品的 impact 列表
        """
        logger.info(f"MarketMonitor: analyzing impact for event: {market_event.get('market', '?')}")
        try:
            # 读取 L2 用户产品列表
            from app.storage.layer_registry import registry
            products_raw = registry.project.list_products()
        except (ImportError, AttributeError):
            products_raw = []

        products = [
            {"id": p.get("product_id", ""), "name": p.get("product_name", "")}
            for p in (products_raw if isinstance(products_raw, list) else [])
        ]

        try:
            result = await self.agent.run_task(
                prompt_name="impact_analysis",
                context={
                    "market_event": json.dumps(market_event, ensure_ascii=False),
                    "user_products": json.dumps(products, ensure_ascii=False),
                },
            )
            return self._parse_impacts(result)
        except Exception as e:
            logger.error(f"MarketMonitor: impact analysis failed: {e}")
            return []

    def _parse_market_events(self, result: dict) -> list[dict]:
        """解析 AstraAssistant 返回的市场事件。"""
        # 可能直接返回 events list
        if "events" in result:
            return self._normalize_events(result["events"])

        # 可能是单市场结果
        if "market" in result:
            return [self._normalize_event(result)]

        # 可能是多市场在根层级
        if isinstance(result, dict):
            events = []
            for key in result:
                if isinstance(result[key], dict) and "market" in result[key]:
                    events.append(self._normalize_event(result[key]))
            if events:
                return events

        # 兜底
        return [self._normalize_event(result)]

    def _normalize_events(self, events: list) -> list[dict]:
        return [self._normalize_event(e) for e in events]

    def _normalize_event(self, event: dict) -> dict:
        """规范化市场事件字段。"""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "event_id": event.get("event_id", f"me_{now}"),
            "market": event.get("market", "unknown"),
            "has_change": event.get("has_change", False),
            "summary": event.get("summary", event.get("description_nl", "")),
            "affected_categories": event.get("affected_categories", []),
            "severity": event.get("severity", "medium"),
            "source": event.get("source", "Astra Market Monitor"),
            "source_url": event.get("source_url", ""),
            "key_points": event.get("key_points", []),
            "timestamp": event.get("timestamp", now),
        }

    def _parse_impacts(self, result: dict) -> list[dict]:
        """解析 AstraAssistant 返回的影响分析结果。"""
        if isinstance(result, list):
            return result
        if "impacts" in result:
            return result["impacts"]
        if "affected_products" in result:
            return result["affected_products"]
        return [result] if result.get("product_id") else []
