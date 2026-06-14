"""风险情报引擎 — 核心调度器。

职责：
  1. 关键词管理（增删改查 + 推荐）
  2. 主动检索（采集器 + 米塔搜索并发）
  3. 两阶段分析（规则引擎 → LLM 精化）
  4. 预警生成（接 risk_alert + EventBus + WS 推送）
  5. APScheduler 动态任务注册（用户关键词级）
  6. 全局定时扫描（三大域周期巡检）

单例访问：get_risk_intel_engine()
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 路径常量
# ─────────────────────────────────────────────────────────────────────────────

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_COLLECTOR_SCRIPT = (
    _BACKEND_ROOT / "data" / "skills" / "risk-intel-collect"
    / "script" / "risk_intel_collector.py"
)
_ANALYZER_SCRIPT = (
    _BACKEND_ROOT / "data" / "skills" / "risk-intel-analyze"
    / "script" / "risk_intel_analyzer.py"
)

# ─────────────────────────────────────────────────────────────────────────────
# 懒加载辅助
# ─────────────────────────────────────────────────────────────────────────────

def _load_module(path: Path, name: str):
    """从绝对路径动态加载模块（处理目录名含连字符的情况）。"""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None:
        raise ImportError(f"无法加载模块：{path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


# ─────────────────────────────────────────────────────────────────────────────
# 自动关键词推荐模板
# ─────────────────────────────────────────────────────────────────────────────

_KEYWORD_TEMPLATES: dict[str, list[str]] = {
    "tariff": [
        "{market} 关税 {year}",
        "{market} tariff change {year}",
        "import duty {market}",
        "{market} trade restriction",
        "export control {hs_category}",
        "sanction {market}",
    ],
    "conflict": [
        "{market} 地缘政治风险",
        "{market} political instability",
        "OFAC sanction {market}",
        "supply chain disruption {market}",
    ],
    "financial": [
        "{market} 汇率 {year}",
        "{market} exchange rate",
        "inflation {market}",
        "interest rate {year}",
        "market volatility {market}",
    ],
}

_HS_CATEGORY_MAP: dict[str, str] = {
    "84": "machinery electronics",
    "85": "electronics semiconductor",
    "61": "clothing textile",
    "62": "apparel garment",
    "64": "footwear shoe",
    "94": "furniture lighting",
    "95": "toy game",
    "87": "vehicle auto part",
    "30": "pharmaceutical medicine",
}


# ─────────────────────────────────────────────────────────────────────────────
# 核心引擎
# ─────────────────────────────────────────────────────────────────────────────

class RiskIntelEngine:
    """风险情报引擎单例。"""

    def __init__(self):
        from app.storage.risk_intel_store import ensure_tables
        ensure_tables()
        logger.info("[RiskIntelEngine] 初始化完成")

    # ─────────────────────────────────────────────────────────────────────────
    # 关键词管理
    # ─────────────────────────────────────────────────────────────────────────

    def add_keyword(
        self,
        user_id: str,
        keyword: str,
        label: Optional[str] = None,
        domain: str = "all",
        periodic_enabled: bool = False,
        cron_expr: str = "0 */6 * * *",
        auto_suggested: bool = False,
        source_hint: Optional[str] = None,
    ) -> dict:
        """新增用户关键词；periodic=True 时同步注册调度任务。"""
        from app.storage.risk_intel_store import add_keyword as _add
        kw = _add(
            user_id=user_id,
            keyword=keyword,
            label=label,
            domain=domain,
            auto_suggested=auto_suggested,
            source_hint=source_hint,
            periodic_enabled=periodic_enabled,
            cron_expr=cron_expr,
        )
        if kw and periodic_enabled:
            self._register_job(kw["id"], keyword, user_id, cron_expr)
        return kw

    def remove_keyword(self, keyword_id: str, user_id: str) -> bool:
        """删除关键词，同步注销调度任务。"""
        from app.storage.risk_intel_store import delete_keyword
        ok = delete_keyword(keyword_id, user_id)
        if ok:
            self._unregister_job(keyword_id)
        return ok

    def list_keywords(
        self,
        user_id: str,
        domain: Optional[str] = None,
        periodic_only: bool = False,
    ) -> list[dict]:
        from app.storage.risk_intel_store import get_keywords
        return get_keywords(user_id, domain=domain, periodic_only=periodic_only)

    def update_keyword(self, keyword_id: str, user_id: str, updates: dict) -> Optional[dict]:
        from app.storage.risk_intel_store import update_keyword as _upd
        kw = _upd(keyword_id, user_id, updates)
        if kw:
            periodic = updates.get("periodic_enabled")
            if periodic is True:
                self._register_job(kw["id"], kw["keyword"], user_id, kw.get("cron_expr", "0 */6 * * *"))
            elif periodic is False:
                self._unregister_job(kw["id"])
        return kw

    def suggest_keywords(
        self,
        user_id: str,
        product_ids: Optional[list[str]] = None,
        markets: Optional[list[str]] = None,
        domains: Optional[list[str]] = None,
    ) -> list[dict]:
        """基于产品 HS 编码 + 目标市场推荐关键词。"""
        from app.storage.risk_intel_store import get_keywords
        from datetime import datetime

        year = datetime.utcnow().year
        existing_kws = {kw["keyword"] for kw in get_keywords(user_id)}

        target_markets = markets or ["US", "EU"]
        target_domains = domains or ["tariff", "conflict", "financial"]

        # 推导 HS 品类
        hs_categories: list[str] = []
        if product_ids:
            try:
                from app.core.local_store import get_product
                for pid in product_ids[:5]:
                    product = get_product(pid)
                    if product:
                        hs = str(product.get("hs_code", ""))[:2]
                        cat = _HS_CATEGORY_MAP.get(hs, "")
                        if cat and cat not in hs_categories:
                            hs_categories.append(cat)
            except Exception:
                pass

        suggestions = []
        for domain in target_domains:
            templates = _KEYWORD_TEMPLATES.get(domain, [])
            for tpl in templates:
                for market in target_markets:
                    for hs_cat in (hs_categories or ["electronics"]):
                        kw = (
                            tpl
                            .replace("{market}", market)
                            .replace("{year}", str(year))
                            .replace("{hs_category}", hs_cat)
                        )
                        if kw not in existing_kws:
                            suggestions.append({
                                "keyword": kw,
                                "domain": domain,
                                "source_hint": (
                                    f"market:{market}"
                                    if not product_ids
                                    else f"product:{product_ids[0]} × market:{market}"
                                ),
                                "already_tracked": False,
                            })

        # 去重，最多返回 30 条
        seen: set[str] = set()
        unique = []
        for s in suggestions:
            if s["keyword"] not in seen:
                seen.add(s["keyword"])
                unique.append(s)
                if len(unique) >= 30:
                    break
        return unique

    # ─────────────────────────────────────────────────────────────────────────
    # 主动检索（异步）
    # ─────────────────────────────────────────────────────────────────────────

    async def search(
        self,
        keyword: str,
        user_id: str,
        domain: Optional[str] = None,
        save: bool = True,
        run_type: str = "manual",
        keyword_id: Optional[str] = None,
    ) -> dict:
        """主动关键词检索核心方法。

        执行步骤：
        1. 创建执行记录
        2. 调用采集器脚本（subprocess，避免 import 路径问题）
        3. 规则引擎分析（同步快速）
        4. 写库（如 save=True）
        5. 高分条目 → 预警生成 + EventBus 发布 + WS 推送
        6. 更新执行记录
        """
        from app.storage.risk_intel_store import (
            create_run, finish_run, upsert_items, touch_keyword_run,
        )
        from datetime import datetime, timezone

        run_id = create_run(keyword, run_type=run_type, keyword_id=keyword_id, user_id=user_id)
        logger.info("[RiskIntelEngine] 开始检索: keyword=%s run_id=%s", keyword, run_id[:8])

        try:
            # ── Step 1: 调用采集器（subprocess 规避连字符目录 import 问题）
            collect_args = {
                "hours": 48,
                "keyword": keyword,
                "save": False,  # 先不存库，分析后再存
            }
            if domain:
                collect_args["domains"] = [domain]

            collect_result = await asyncio.get_event_loop().run_in_executor(
                None, self._run_collector, collect_args
            )
            raw_items: list[dict] = collect_result.get("items", [])
            logger.info("[RiskIntelEngine] 采集 %d 条", len(raw_items))

            # ── Step 2: 规则引擎分析（同步，快速）
            analyzer_mod = _load_module(_ANALYZER_SCRIPT, "risk_intel_analyzer")
            analyzed_items = [analyzer_mod.rule_engine_analyze(item) for item in raw_items]

            # 标注关键词溯源
            for item in analyzed_items:
                if keyword not in item.get("matched_keywords", []):
                    item.setdefault("matched_keywords", []).append(keyword)
                item["trigger_source"] = f"keyword:{keyword}"
                if user_id and user_id != "default":
                    item["trigger_source"] = f"user:{user_id}:keyword:{keyword}"

            # ── Step 3: 写库
            items_new = 0
            if save and analyzed_items:
                inserted, _ = upsert_items(analyzed_items)
                items_new = inserted

            # ── Step 4: 基于规则引擎分数触发初步预警
            alerts_created = 0
            high_items = [
                i for i in analyzed_items
                if float(i.get("risk_score", 0)) >= 0.6
                   or i.get("severity") in ("high", "critical")
            ]
            for item in high_items[:5]:
                alert_id = await self._maybe_create_alert(item, user_id)
                if alert_id:
                    item["alert_id"] = alert_id
                    alerts_created += 1

            # ── Step 5: 更新执行记录
            finish_run(run_id, items_found=len(raw_items),
                       items_new=items_new, alerts_created=alerts_created)

            # ── Step 6: 更新关键词统计
            if keyword_id:
                touch_keyword_run(keyword_id, hits=alerts_created)

            # ── Step 7: 异步触发 LLM 深度分析（非阻塞，后台进行）
            if save and analyzed_items:
                item_ids = [i["id"] for i in analyzed_items if i.get("id")]
                asyncio.create_task(
                    self._fire_llm_analysis(item_ids, user_id),
                    name=f"llm_analyze_{run_id[:8]}",
                )
                logger.info("[RiskIntelEngine] 已提交 %d 条 LLM 分析任务", len(item_ids))

            return {
                "run_id": run_id,
                "keyword": keyword,
                "total_found": len(raw_items),
                "items_new": items_new,
                "alerts_triggered": alerts_created,
                "items": analyzed_items[:50],
                "duration_ms": 0,
            }

        except Exception as e:
            logger.error("[RiskIntelEngine] 检索异常: %s", e, exc_info=True)
            finish_run(run_id, items_found=0, items_new=0, error_msg=str(e))
            return {"run_id": run_id, "error": str(e), "items": []}

    def _run_collector(self, args: dict) -> dict:
        """同步调用采集器脚本（供 run_in_executor 使用）。"""
        try:
            result = subprocess.run(
                [sys.executable, str(_COLLECTOR_SCRIPT), "--stdin"],
                input=json.dumps(args, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=180,
                cwd=str(_BACKEND_ROOT),
            )
            if result.returncode != 0:
                logger.warning("[collector] 非零返回: %s", result.stderr[:300])
                return {"items": [], "total": 0}
            return json.loads(result.stdout)
        except Exception as e:
            logger.error("[collector] 调用失败: %s", e)
            return {"items": [], "total": 0}

    async def run_global_scan(self, domains: Optional[list[str]] = None) -> dict:
        """全局扫描（三大域），由调度器触发。"""
        domains = domains or ["tariff", "conflict", "financial"]
        results = {}
        for domain in domains:
            result = await self.search(
                keyword=f"global_{domain}_scan",
                user_id="system",
                domain=domain,
                save=True,
                run_type="scheduled",
            )
            results[domain] = {
                "found": result.get("total_found", 0),
                "alerts": result.get("alerts_triggered", 0),
            }
        return results

    async def run_all_periodic_keywords(self) -> dict:
        """执行所有启用周期检索的用户关键词。"""
        from app.storage.risk_intel_store import get_all_periodic_keywords
        keywords = get_all_periodic_keywords()
        if not keywords:
            return {"total": 0, "ran": 0}

        ran = 0
        total_alerts = 0
        for kw in keywords:
            try:
                result = await self.search(
                    keyword=kw["keyword"],
                    user_id=kw["user_id"],
                    save=True,
                    run_type="scheduled",
                    keyword_id=kw["id"],
                )
                total_alerts += result.get("alerts_triggered", 0)
                ran += 1
            except Exception as e:
                logger.error("[RiskIntelEngine] 周期关键词失败: %s %s", kw["keyword"], e)

        return {"total": len(keywords), "ran": ran, "alerts": total_alerts}

    # ─────────────────────────────────────────────────────────────────────────
    # 预警生成 + 事件发布
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # LLM 分析流水线
    # ─────────────────────────────────────────────────────────────────────────

    async def _fire_llm_analysis(
        self,
        item_ids: list[str],
        user_id: str = "system",
    ) -> None:
        """后台触发一批条目的 LLM 分析，并写回数据库。

        数据流：
          item_ids → 从 DB 取条目 → LLM 分析 → 写回 llm_analysis
                  → 高分条目提升/新增预警 → WS 推送更新通知
        """
        from app.storage.risk_intel_store import get_item, update_llm_analysis
        from app.core.risk_intel_analyzer import get_risk_intel_analyzer

        analyzer = get_risk_intel_analyzer()
        items = [get_item(iid) for iid in item_ids]
        items = [i for i in items if i]  # 过滤 None

        if not items:
            return

        logger.info("[RiskIntelEngine] LLM 分析开始: %d 条", len(items))

        async def _on_done(item: dict, result: dict):
            """每条分析完成后的回调：写回 + 预警提升 + WS 推送。"""
            try:
                update_llm_analysis(item["id"], result)

                # LLM 评分比规则引擎高，考虑升级预警
                new_score = float(result.get("risk_score", 0))
                old_score = float(item.get("risk_score", 0))
                if new_score >= 0.6 and not item.get("alert_id"):
                    await self._maybe_create_alert({**item, **result}, user_id)

                # WS 推送：通知前端该条目已分析完成
                try:
                    from app.services.ws_manager import ws_manager
                    await ws_manager.broadcast({
                        "type": "intel_analyzed",
                        "payload": {
                            "intel_id": item["id"],
                            "risk_score": result.get("risk_score"),
                            "severity": result.get("severity"),
                            "headline_summary": result.get("headline_summary"),
                            "llm_analysis": {
                                "summary": result.get("summary", ""),
                                "impact": result.get("impact", ""),
                                "actions": result.get("actions", []),
                                "confidence": result.get("confidence", 0),
                            },
                        },
                    })
                except Exception:
                    pass

            except Exception as e:
                logger.warning("[RiskIntelEngine] _on_done 失败 id=%s: %s",
                               item.get("id", "?")[:8], e)

        await analyzer.analyze_batch(items, on_done=_on_done)
        logger.info("[RiskIntelEngine] LLM 分析完成: %d 条", len(items))

    async def analyze_pending_items(
        self,
        batch_size: int = 20,
        min_score: float = 0.0,
        hours: int = 720,
    ) -> dict:
        """批量分析数据库中所有待 LLM 处理的条目（调度器定期调用）。

        Args:
            batch_size: 单次处理数量（控制 API 成本）
            min_score:  最低规则引擎分数（过滤低质量条目）
            hours:      只处理最近 N 小时的条目

        Returns:
            {"processed": int, "skipped": int, "available": bool}
        """
        from app.storage.risk_intel_store import get_llm_pending_items
        from app.core.risk_intel_analyzer import get_risk_intel_analyzer

        analyzer = get_risk_intel_analyzer()
        if not analyzer.available:
            logger.info("[RiskIntelEngine] LLM 不可用，跳过 analyze_pending_items")
            return {"processed": 0, "skipped": 0, "available": False}

        pending = get_llm_pending_items(
            limit=batch_size, min_score=min_score, hours=hours
        )
        if not pending:
            logger.debug("[RiskIntelEngine] 无待分析条目")
            return {"processed": 0, "skipped": 0, "available": True}

        logger.info("[RiskIntelEngine] 开始批处理 %d 条待分析条目", len(pending))
        await self._fire_llm_analysis([i["id"] for i in pending])

        return {"processed": len(pending), "skipped": 0, "available": True}

    def get_analysis_stats(self) -> dict:
        """返回 LLM 分析队列统计。"""
        from app.storage.risk_intel_store import get_analysis_stats
        return get_analysis_stats()

    async def _maybe_create_alert(self, item: dict, user_id: str) -> Optional[str]:
        """条件触发预警：risk_score >= 0.6 或 severity in (high, critical)。"""
        try:
            from app.core.risk_alert import create_alert
            from app.storage.risk_intel_store import link_alert

            # 构建预警描述
            domain_label = {
                "tariff": "关税/贸易风险",
                "conflict": "冲突/制裁风险",
                "financial": "金融市场风险",
            }.get(item.get("risk_domain", ""), "风险情报")

            score = float(item.get("risk_score", 0))
            desc = (
                f"[{domain_label}] {item.get('headline_summary') or item.get('title', '')[:60]}\n"
                f"来源：{item.get('source_name', '')} | 评分：{score:.2f} | "
                f"市场：{', '.join(item.get('affected_markets', []))}"
            )

            alert = create_alert(
                alert_type="risk_intel",
                severity=item.get("severity", "medium"),
                title=item.get("headline_summary") or item.get("title", "")[:80],
                description=desc,
                affected_markets=item.get("affected_markets", []),
                source=item.get("source_name", ""),
                source_url=item.get("url", ""),
                user_ids=[user_id] if user_id and user_id != "system" else None,
            )
            alert_id = alert.get("alert_id")

            # 回写 alert_id 到数据库
            if alert_id and item.get("id"):
                link_alert(item["id"], alert_id)

            # EventBus 发布
            await self._publish_event(item, alert_id)

            # WS 推送
            await self._push_ws(item, alert_id, user_id)

            # 飞书通知（仅 high/critical 级别）
            severity = item.get("severity", "medium")
            if severity in ("high", "critical"):
                await self._send_feishu_alert(item, alert_id)

            return alert_id

        except Exception as e:
            logger.warning("[RiskIntelEngine] 预警生成失败: %s", e)
            return None

    async def _publish_event(self, item: dict, alert_id: Optional[str]) -> None:
        """向 EventBus 发布风险情报事件。"""
        try:
            from app.core.event_bus import get_event_bus
            bus = get_event_bus()
            await bus.publish_raw({
                "type": "risk:new_intel_alert",
                "source": "risk_intel_engine",
                "severity": item.get("severity", "medium"),
                "data": {
                    "intel_id": item.get("id"),
                    "alert_id": alert_id,
                    "domain": item.get("risk_domain"),
                    "category": item.get("risk_category"),
                    "risk_score": item.get("risk_score", 0.0),
                    "severity": item.get("severity", "medium"),
                    "title": item.get("title", "")[:200],
                    "headline_summary": item.get("headline_summary"),
                    "affected_markets": item.get("affected_markets", []),
                    "affected_hs_codes": item.get("affected_hs_codes", []),
                    "source_name": item.get("source_name", ""),
                    "url": item.get("url", ""),
                    "matched_keywords": item.get("matched_keywords", []),
                },
            })
        except Exception as e:
            logger.debug("[RiskIntelEngine] EventBus 发布失败（非致命）: %s", e)

    async def _push_ws(self, item: dict, alert_id: Optional[str], user_id: str) -> None:
        """向相关用户 WS 推送风险预警通知。"""
        try:
            from app.services.ws_manager import ws_manager
            msg = {
                "type": "alert",
                "payload": {
                    "alert_id": alert_id,
                    "intel_id": item.get("id"),
                    "domain": item.get("risk_domain"),
                    "severity": item.get("severity"),
                    "risk_score": item.get("risk_score"),
                    "title": item.get("headline_summary") or item.get("title", "")[:80],
                    "source_name": item.get("source_name"),
                    "url": item.get("url"),
                },
            }
            if user_id and user_id not in ("system", "default"):
                await ws_manager.send_to_user(user_id, msg)
            else:
                await ws_manager.broadcast(msg)
        except Exception as e:
            logger.debug("[RiskIntelEngine] WS 推送失败（非致命）: %s", e)

    async def _send_feishu_alert(self, item: dict, alert_id: Optional[str]) -> None:
        """严重风险情报事件 → 飞书群通知。

        通过 lark-cli im +messages-send 推送到配置的飞书群，
        使用 asyncio.to_thread 异步执行，不阻塞主流程。
        """
        import os
        chat_id = os.getenv("RISK_INTEL_FEISHU_CHAT_ID", "").strip()
        if not chat_id:
            logger.debug("[RiskIntelEngine] 未配置 RISK_INTEL_FEISHU_CHAT_ID，跳过飞书通知")
            return

        # 构建通知文本
        severity_label = {"critical": "🔴 严重", "high": "🟠 高危"}.get(
            item.get("severity", ""), "⚠️ 风险"
        )
        domain_label = {
            "tariff": "关税/贸易",
            "conflict": "冲突/制裁",
            "financial": "金融市场",
        }.get(item.get("risk_domain", ""), "综合风险")

        score = float(item.get("risk_score", 0))
        title = item.get("headline_summary") or item.get("title", "")[:80]
        markets = ", ".join(item.get("affected_markets", [])) or "未知"
        source = item.get("source_name", "")
        url = item.get("url", "")

        text = (
            f"{severity_label} | 风险情报预警\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"领域：{domain_label}\n"
            f"标题：{title}\n"
            f"评分：{score:.2f} | 市场：{markets}\n"
            f"来源：{source}\n"
        )
        if url:
            text += f"链接：{url}\n"
        if alert_id:
            text += f"预警ID：{alert_id}"

        def _sync():
            from pathlib import Path as _P
            import shutil
            npm_root = _P.home() / "AppData" / "Roaming" / "npm"
            entry = npm_root / "node_modules" / "@larksuite" / "cli" / "scripts" / "run.js"
            if entry.exists():
                cmd = ["node", str(entry)]
            else:
                found = shutil.which("lark-cli")
                cmd = ["cmd", "/C", found] if found and found.endswith(".cmd") else ([found] if found else ["lark-cli"])
            return subprocess.run(
                cmd + [
                    "im", "+messages-send",
                    "--as", "bot",
                    "--chat-id", chat_id,
                    "--text", text,
                ],
                capture_output=True, encoding="utf-8", timeout=15,
            )

        try:
            proc = await asyncio.to_thread(_sync)
            logger.info(
                "[RiskIntelEngine] 飞书风险通知已发送: chat=%s severity=%s rc=%d",
                chat_id, item.get("severity"), proc.returncode,
            )
        except Exception as e:
            logger.warning("[RiskIntelEngine] 飞书风险通知发送失败: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # APScheduler 动态任务注册
    # ─────────────────────────────────────────────────────────────────────────

    def _register_job(
        self,
        keyword_id: str,
        keyword: str,
        user_id: str,
        cron_expr: str,
    ) -> None:
        """在 APScheduler 注册周期检索任务。"""
        try:
            from app.core.scheduler import get_scheduler
            scheduler = get_scheduler()
            if scheduler is None:
                return

            from apscheduler.triggers.cron import CronTrigger

            job_id = f"risk_intel_{keyword_id}"

            async def _job():
                await self.search(
                    keyword=keyword,
                    user_id=user_id,
                    save=True,
                    run_type="scheduled",
                    keyword_id=keyword_id,
                )

            # APScheduler 4.x 同步执行器包装
            def _sync_job():
                asyncio.run(_job())

            scheduler.add_job(
                func=_sync_job,
                trigger=CronTrigger.from_crontab(cron_expr),
                id=job_id,
                name=f"风险情报·{keyword[:20]}",
                replace_existing=True,
                misfire_grace_time=600,
            )
            logger.info("[RiskIntelEngine] 注册调度任务: %s cron=%s", job_id, cron_expr)
        except Exception as e:
            logger.warning("[RiskIntelEngine] 注册调度任务失败: %s", e)

    def _unregister_job(self, keyword_id: str) -> None:
        """注销调度任务。"""
        try:
            from app.core.scheduler import get_scheduler
            scheduler = get_scheduler()
            if scheduler:
                scheduler.remove_job(f"risk_intel_{keyword_id}")
                logger.info("[RiskIntelEngine] 注销调度任务: risk_intel_%s", keyword_id[:8])
        except Exception as e:
            logger.debug("[RiskIntelEngine] 注销任务失败（非致命）: %s", e)

    def restore_periodic_jobs(self) -> int:
        """系统重启后恢复所有持久化的周期任务（在 lifespan 中调用）。"""
        from app.storage.risk_intel_store import get_all_periodic_keywords
        keywords = get_all_periodic_keywords()
        restored = 0
        for kw in keywords:
            try:
                self._register_job(
                    kw["id"], kw["keyword"], kw["user_id"],
                    kw.get("cron_expr", "0 */6 * * *"),
                )
                restored += 1
            except Exception as e:
                logger.warning("[RiskIntelEngine] 恢复任务失败: %s %s", kw["keyword"], e)
        logger.info("[RiskIntelEngine] 恢复 %d 个周期任务", restored)
        return restored

    # ─────────────────────────────────────────────────────────────────────────
    # 统计查询
    # ─────────────────────────────────────────────────────────────────────────

    def get_heatmap(self, hours: int = 168) -> dict:
        from app.storage.risk_intel_store import get_heatmap_data
        return get_heatmap_data(hours=hours)

    def get_feed(self, **kwargs) -> dict:
        from app.storage.risk_intel_store import search_items
        return search_items(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# 单例
# ─────────────────────────────────────────────────────────────────────────────

_engine: Optional[RiskIntelEngine] = None


def get_risk_intel_engine() -> RiskIntelEngine:
    global _engine
    if _engine is None:
        _engine = RiskIntelEngine()
    return _engine
