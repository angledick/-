"""新闻监控 API 路由。

GET  /api/v1/news-monitor/news          最新已分析新闻列表
GET  /api/v1/news-monitor/summary       市场风险摘要
POST /api/v1/news-monitor/collect       手动触发采集 + 分析
GET  /api/v1/news-monitor/keywords      获取关键词配置
PUT  /api/v1/news-monitor/keywords      更新关键词配置
"""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.storage.news_store import (
    get_recent_news, get_keywords, set_keywords, upsert_news
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/news-monitor", tags=["news-monitor"])

# 脚本 Skill 路径
_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "skills"


# ── 模型 ──────────────────────────────────────────────────────────────

class KeywordConfig(BaseModel):
    keywords: list[str]
    high_words: list[str]


# ── 端点 ──────────────────────────────────────────────────────────────

@router.get("/news")
async def list_news(
    hours: int = Query(48, ge=1, le=168, description="最近 N 小时"),
    limit: int = Query(50, ge=1, le=200),
    direction: str | None = Query(None, description="利多|利空|中性 筛选"),
    level: str | None = Query(None, description="high|medium|low 筛选"),
    current_user: dict = Depends(get_current_user),
):
    """获取最近已分析的新闻列表，支持方向/风险等级筛选。"""
    news = get_recent_news(hours=hours, limit=limit)
    if direction:
        news = [n for n in news if n.get("risk_direction") == direction]
    if level:
        news = [n for n in news if n.get("risk_level") == level]
    return {"news": news, "total": len(news)}


@router.get("/summary")
async def market_summary(
    hours: int = Query(24, ge=1, le=168),
    current_user: dict = Depends(get_current_user),
):
    """市场风险方向汇总：利多/利空计数 + 高风险头条。"""
    news_list = get_recent_news(hours=hours, limit=50)
    high_risk = [
        n for n in news_list
        if n.get("risk_level") == "high" and n.get("risk_direction") in ("利多", "利空")
    ]
    bullish = [n for n in news_list if n.get("risk_direction") == "利多"]
    bearish = [n for n in news_list if n.get("risk_direction") == "利空"]

    overall = "中性"
    if len(bearish) > len(bullish) * 1.5:
        overall = "利空偏向"
    elif len(bullish) > len(bearish) * 1.5:
        overall = "利多偏向"

    return {
        "overall_direction": overall,
        "bullish_count": len(bullish),
        "bearish_count": len(bearish),
        "neutral_count": len(news_list) - len(bullish) - len(bearish),
        "high_risk_news": high_risk[:5],
        "period_hours": hours,
    }


@router.post("/collect")
async def trigger_collect(
    background_tasks: BackgroundTasks,
    hours: int = Query(48),
    current_user: dict = Depends(get_current_user),
):
    """手动触发新闻采集 + AI 分析（后台异步执行）。

    调用 data/skills/news-collect/ 和 news-analyze/ 下的脚本 Skill。
    """
    user_id = current_user.get("id", "default")

    def _run():
        log.info("开始采集新闻 user_id=%s", user_id)
        # 1. 采集
        try:
            collector_script = str(_SKILLS_DIR / "news-collect" / "script" / "news_collector.py")
            proc = subprocess.run(
                [sys.executable, collector_script,
                 "--hours", str(hours), "--user-id", user_id, "--save"],
                capture_output=True, text=True, timeout=60,
                cwd=str(Path(__file__).resolve().parent.parent.parent),
            )
            if proc.returncode == 0:
                import json
                result = json.loads(proc.stdout)
                log.info("采集完成：%d 条", result.get("total_collected", 0))
            else:
                log.warning("采集脚本异常: %s", proc.stderr[:200])
        except Exception as e:
            log.warning("采集异常: %s", e)

        # 2. 分析
        try:
            analyzer_script = str(_SKILLS_DIR / "news-analyze" / "script" / "news_analyzer.py")
            proc = subprocess.run(
                [sys.executable, analyzer_script, "--limit", "20"],
                capture_output=True, text=True, timeout=120,
                cwd=str(Path(__file__).resolve().parent.parent.parent),
            )
            if proc.returncode == 0:
                import json
                result = json.loads(proc.stdout)
                log.info("分析完成：%d 条", result.get("analyzed", 0))
            else:
                log.warning("分析脚本异常: %s", proc.stderr[:200])
        except Exception as e:
            log.warning("分析异常: %s", e)

    background_tasks.add_task(_run)
    return {"status": "collecting", "message": "采集任务已在后台启动"}


@router.get("/keywords")
async def get_keyword_config(
    current_user: dict = Depends(get_current_user),
):
    """获取当前用户的关键词监控配置。"""
    user_id = current_user.get("id", "default")
    return get_keywords(user_id)


@router.put("/keywords")
async def update_keywords(
    config: KeywordConfig,
    current_user: dict = Depends(get_current_user),
):
    """更新关键词监控配置。"""
    user_id = current_user.get("id", "default")
    set_keywords(user_id, config.keywords, config.high_words)
    return {"ok": True, "keywords": config.keywords, "high_words": config.high_words}
