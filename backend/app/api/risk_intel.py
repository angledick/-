"""风险情报引擎 API — /api/v1/risk-intel

端点：
  POST   /search                 主动关键词检索（实时）
  GET    /feed                   历史情报流（过滤+分页）
  GET    /heatmap                风险热力图数据
  GET    /keywords               用户关键词列表
  POST   /keywords               新增关键词
  PUT    /keywords/{id}          更新关键词
  DELETE /keywords/{id}          删除关键词
  POST   /keywords/suggest       系统推荐关键词
  POST   /keywords/{id}/run      手动触发单关键词检索
  GET    /runs                   检索执行记录
  GET    /runs/{run_id}          单次执行详情
"""

import asyncio
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["risk-intel"])


# ─────────────────────────────────────────────────────────────────────────────
# 请求/响应模型
# ─────────────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200, description="检索关键词")
    domain: Optional[str] = Field(None, description="tariff | conflict | financial")
    markets: Optional[List[str]] = Field(None, description="市场过滤（ISO 两字母码）")
    save: bool = Field(True, description="是否持久化结果")
    count: int = Field(10, ge=1, le=20, description="检索数量")


class KeywordCreateRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    label: Optional[str] = Field(None, max_length=100)
    domain: str = Field("all", description="tariff | conflict | financial | all")
    periodic_enabled: bool = Field(False, description="是否开启周期检索")
    cron_expr: str = Field("0 */6 * * *", description="cron 表达式")


class KeywordUpdateRequest(BaseModel):
    label: Optional[str] = None
    domain: Optional[str] = None
    periodic_enabled: Optional[bool] = None
    cron_expr: Optional[str] = None
    enabled: Optional[bool] = None


class SuggestRequest(BaseModel):
    product_ids: Optional[List[str]] = Field(None, description="产品 ID 列表")
    markets: Optional[List[str]] = Field(None, description="目标市场")
    domains: Optional[List[str]] = Field(None, description="域过滤")


# ─────────────────────────────────────────────────────────────────────────────
# 辅助
# ─────────────────────────────────────────────────────────────────────────────

def _get_engine():
    from app.core.risk_intel_engine import get_risk_intel_engine
    return get_risk_intel_engine()


# ─────────────────────────────────────────────────────────────────────────────
# 检索端点
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/search")
async def search_risk_intel(
    req: SearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """主动关键词检索（实时联网 + RSS 采集 + 规则引擎分析）。

    前端轮询建议：提交后可通过 GET /runs/{run_id} 检查完成状态。
    """
    engine = _get_engine()
    user_id = current_user.get("id") or current_user.get("username", "default")

    start = time.time()
    try:
        result = await engine.search(
            keyword=req.keyword,
            user_id=user_id,
            domain=req.domain,
            save=req.save,
            run_type="manual",
        )
        result["duration_ms"] = int((time.time() - start) * 1000)
        return result
    except Exception as e:
        logger.error("[risk_intel API] search 失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"检索失败: {e}")


@router.get("/feed")
async def get_feed(
    q: Optional[str] = Query(None, description="全文检索"),
    domain: Optional[str] = Query(None, description="tariff|conflict|financial"),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None, description="逗号分隔，如 high,critical"),
    markets: Optional[str] = Query(None, description="逗号分隔，如 US,EU"),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    hours: int = Query(168, ge=1, le=720, description="时间窗口（小时）"),
    source_name: Optional[str] = Query(None, description="信源过滤，如 jin10"),
    jin10_only: bool = Query(False, description="仅金十数据"),
    important_only: bool = Query(False, description="仅金十重要新闻"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """历史情报流，支持多维过滤 + 全文检索 + 分页。"""
    from app.storage.risk_intel_store import search_items
    markets_list = [m.strip() for m in markets.split(",")] if markets else None
    return search_items(
        query=q,
        domain=domain,
        category=category,
        severity=severity,
        markets=markets_list,
        min_score=min_score,
        hours=hours,
        page=page,
        size=size,
        source_name=source_name,
        jin10_only=jin10_only,
        important_only=important_only,
    )


@router.get("/heatmap")
async def get_heatmap(
    hours: int = Query(168, ge=1, le=720),
    current_user: dict = Depends(get_current_user),
):
    """风险热力图聚合数据（按域/按严重度/时序趋势/Top市场）。"""
    return _get_engine().get_heatmap(hours=hours)


# ─────────────────────────────────────────────────────────────────────────────
# 关键词管理端点
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/keywords")
async def list_keywords(
    domain: Optional[str] = Query(None),
    periodic_only: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """列出当前用户的关键词配置。"""
    user_id = current_user.get("id") or current_user.get("username", "default")
    return _get_engine().list_keywords(user_id, domain=domain, periodic_only=periodic_only)


@router.post("/keywords", status_code=201)
async def add_keyword(
    req: KeywordCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """新增关键词（可选开启周期检索）。"""
    user_id = current_user.get("id") or current_user.get("username", "default")
    engine = _get_engine()

    # 关键词数量上限
    existing = engine.list_keywords(user_id)
    limit = 100 if current_user.get("role") == "admin" else 20
    if len(existing) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"关键词数量已达上限（{limit}），请删除不用的关键词后再添加",
        )

    result = engine.add_keyword(
        user_id=user_id,
        keyword=req.keyword,
        label=req.label,
        domain=req.domain,
        periodic_enabled=req.periodic_enabled,
        cron_expr=req.cron_expr,
    )
    if not result:
        raise HTTPException(status_code=500, detail="添加关键词失败")
    return result


@router.put("/keywords/{keyword_id}")
async def update_keyword(
    keyword_id: str,
    req: KeywordUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新关键词配置（cron/domain/label/periodic_enabled）。"""
    user_id = current_user.get("id") or current_user.get("username", "default")
    updates = req.model_dump(exclude_none=True)
    result = _get_engine().update_keyword(keyword_id, user_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="关键词不存在或无权限修改")
    return result


@router.delete("/keywords/{keyword_id}", status_code=204)
async def delete_keyword(
    keyword_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除关键词（软删除）。"""
    user_id = current_user.get("id") or current_user.get("username", "default")
    ok = _get_engine().remove_keyword(keyword_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="关键词不存在或无权限删除")


@router.post("/keywords/suggest")
async def suggest_keywords(
    req: SuggestRequest,
    current_user: dict = Depends(get_current_user),
):
    """根据产品 HS 编码 + 目标市场自动推荐关键词。"""
    user_id = current_user.get("id") or current_user.get("username", "default")
    return {
        "suggestions": _get_engine().suggest_keywords(
            user_id=user_id,
            product_ids=req.product_ids,
            markets=req.markets,
            domains=req.domains,
        )
    }


@router.post("/keywords/{keyword_id}/run")
async def run_keyword(
    keyword_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """手动触发单关键词检索（异步后台执行，立即返回 run_id）。"""
    user_id = current_user.get("id") or current_user.get("username", "default")
    engine = _get_engine()

    keywords = engine.list_keywords(user_id)
    kw_record = next((k for k in keywords if k["id"] == keyword_id), None)
    if not kw_record:
        raise HTTPException(status_code=404, detail="关键词不存在")

    from app.storage.risk_intel_store import create_run
    run_id = create_run(
        keyword=kw_record["keyword"],
        run_type="manual",
        keyword_id=keyword_id,
        user_id=user_id,
    )

    async def _bg_search():
        await engine.search(
            keyword=kw_record["keyword"],
            user_id=user_id,
            save=True,
            run_type="manual",
            keyword_id=keyword_id,
        )

    background_tasks.add_task(_bg_search)
    return {
        "run_id": run_id,
        "keyword": kw_record["keyword"],
        "status": "queued",
        "message": "检索任务已提交后台，通过 GET /runs/{run_id} 查询进度",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 执行记录端点
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/runs")
async def list_runs(
    keyword_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """检索执行记录列表。"""
    from app.storage.risk_intel_store import get_runs
    user_id = current_user.get("id") or current_user.get("username", "default")
    return get_runs(user_id=user_id, keyword_id=keyword_id, limit=limit)


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    """单次执行记录详情（含 items_found / items_new / alerts_created / status）。"""
    from app.storage.risk_intel_store import get_run as _get_run
    run = _get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return run


# ─────────────────────────────────────────────────────────────────────────────
# 内部调度触发（仅 Admin）
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/admin/global-scan")
async def trigger_global_scan(
    domains: Optional[str] = Query(None, description="逗号分隔，如 tariff,conflict"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user),
):
    """手动触发全局三大域扫描（Admin 专用）。"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要 Admin 权限")
    domain_list = [d.strip() for d in domains.split(",")] if domains else None
    engine = _get_engine()

    async def _scan():
        await engine.run_global_scan(domains=domain_list)

    background_tasks.add_task(_scan)
    return {"status": "queued", "domains": domain_list or ["tariff", "conflict", "financial"]}


# ─────────────────────────────────────────────────────────────────────────────
# LLM 分析管理端点
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analyze/status")
async def get_analyze_status(
    current_user: dict = Depends(get_current_user),
):
    """LLM 分析队列统计（total/done/pending/errors）。"""
    return _get_engine().get_analysis_stats()


@router.post("/analyze/trigger")
async def trigger_analyze(
    batch_size: int = Query(20, ge=1, le=100, description="单批次条数"),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="最低规则引擎分数"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user),
):
    """手动触发 LLM 批量分析（立即执行一批，非全量）。"""
    engine = _get_engine()
    stats = engine.get_analysis_stats()

    async def _run():
        await engine.analyze_pending_items(
            batch_size=batch_size,
            min_score=min_score,
        )

    background_tasks.add_task(_run)
    return {
        "status": "queued",
        "batch_size": batch_size,
        "queue_before": stats.get("pending", 0),
    }


@router.post("/analyze/item/{item_id}")
async def analyze_single_item(
    item_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """对指定条目立即触发 LLM 分析（后台异步）。"""
    from app.storage.risk_intel_store import get_item
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="情报条目不存在")

    user_id = current_user.get("id") or current_user.get("username", "system")

    async def _run():
        await _get_engine()._fire_llm_analysis([item_id], user_id)

    background_tasks.add_task(_run)
    return {
        "status": "queued",
        "item_id": item_id,
        "llm_analyzed": item.get("llm_analyzed", 0),
        "message": "LLM 分析已提交，结果将通过 WebSocket 推送",
    }
