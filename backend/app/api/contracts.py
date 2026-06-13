"""合同管理 API — /api/v1/contracts"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Optional
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])


class ContractGenerate(BaseModel):
    product_id: str
    supplier_id: str
    template_id: str
    title: str = "采购合同"
    variables: dict = Field(default={}, description="模板变量，如 buyer_name/total_amount 等")
    delivery_term: str = "FOB"
    currency: str = "USD"
    total_amount: float = 0.0
    payment_terms: str = ""
    delivery_date: str = ""
    quality_terms: str = ""
    parties: list[str] = []
    auto_review: bool = True  # 生成后自动触发 AI 合规审查


class ContractUpdate(BaseModel):
    title: Optional[str] = None
    delivery_term: Optional[str] = None
    currency: Optional[str] = None
    total_amount: Optional[float] = None
    payment_terms: Optional[str] = None
    delivery_date: Optional[str] = None
    quality_terms: Optional[str] = None
    content_vars: Optional[dict] = None


# ── 模板 ──────────────────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates(current_user: dict = Depends(get_current_user)):
    from app.storage.contract_store import list_templates as _lt
    return _lt()


@router.get("/templates/{template_id}")
async def get_template(template_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.contract_store import get_template as _gt
    t = _gt(template_id)
    if not t:
        raise HTTPException(404, f"模板 {template_id} 不存在")
    return t


# ── 合同 CRUD ─────────────────────────────────────────────────────────────────

@router.post("/generate", status_code=201)
async def generate_contract(
    req: ContractGenerate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """生成合同（Jinja2 渲染 + 可选 AI 合规审查）。"""
    from app.storage.contract_store import render_template, create_contract

    # 渲染 HTML
    try:
        html = render_template(req.template_id, req.variables)
    except ValueError as e:
        raise HTTPException(400, str(e))

    contract_data = {
        "product_id": req.product_id,
        "supplier_id": req.supplier_id,
        "template_id": req.template_id,
        "title": req.title,
        "delivery_term": req.delivery_term,
        "currency": req.currency,
        "total_amount": req.total_amount,
        "payment_terms": req.payment_terms,
        "delivery_date": req.delivery_date,
        "quality_terms": req.quality_terms,
        "content_vars": req.variables,
        "parties": req.parties,
    }
    contract = create_contract(contract_data, html)

    # 发布事件
    _publish_event("contract:draft_created", {
        "contract_id": contract["id"], "product_id": req.product_id,
        "supplier_id": req.supplier_id,
    })

    # 异步 AI 合规审查
    if req.auto_review:
        async def _review():
            await _do_compliance_review(contract["id"])
        background_tasks.add_task(_review)

    return contract


@router.get("")
async def list_contracts(
    product_id: Optional[str] = None,
    supplier_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.contract_store import list_contracts as _lc
    return _lc(product_id=product_id, supplier_id=supplier_id, status=status, limit=limit)


@router.get("/{contract_id}")
async def get_contract(contract_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.contract_store import get_contract as _gc
    c = _gc(contract_id)
    if not c:
        raise HTTPException(404, f"合同 {contract_id} 不存在")
    return c


@router.put("/{contract_id}")
async def update_contract(
    contract_id: str, req: ContractUpdate,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.contract_store import update_contract as _uc, get_template, render_template
    updates = req.model_dump(exclude_none=True)
    # 如果更新了变量，重新渲染 HTML
    if "content_vars" in updates:
        from app.storage.contract_store import get_contract as _gc
        c = _gc(contract_id)
        if c:
            try:
                html = render_template(c["template_id"], updates["content_vars"])
                updates["content_html"] = html
            except Exception:
                pass
    c = _uc(contract_id, updates)
    if not c:
        raise HTTPException(404, f"合同 {contract_id} 不存在")
    return c


@router.post("/{contract_id}/review")
async def review_contract(
    contract_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """触发 AI 合规审查。"""
    from app.storage.contract_store import get_contract as _gc
    if not _gc(contract_id):
        raise HTTPException(404, f"合同 {contract_id} 不存在")

    async def _run():
        await _do_compliance_review(contract_id)

    background_tasks.add_task(_run)
    return {"status": "queued", "contract_id": contract_id,
            "message": "AI 合规审查已提交，结果将实时推送"}


@router.post("/{contract_id}/sign")
async def sign_contract(contract_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.contract_store import sign_contract as _sc, get_contract as _gc
    if not _gc(contract_id):
        raise HTTPException(404, f"合同 {contract_id} 不存在")
    c = _sc(contract_id)
    _publish_event("contract:signed", {"contract_id": contract_id,
                                        "product_id": c.get("product_id"),
                                        "supplier_id": c.get("supplier_id")})
    return c


@router.get("/{contract_id}/versions")
async def get_versions(contract_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.contract_store import get_versions as _gv
    return {"versions": _gv(contract_id)}


# ── 内部辅助 ──────────────────────────────────────────────────────────────────

async def _do_compliance_review(contract_id: str):
    """AI 合规审查主流程。"""
    from app.storage.contract_store import get_contract as _gc, save_compliance_review
    from app.core.lifecycle_analyzer import analyze_contract
    c = _gc(contract_id)
    if not c:
        return
    result = await analyze_contract(c)
    save_compliance_review(contract_id, result.get("issues", []), result.get("score", 0))
    # WS 推送
    try:
        from app.services.ws_manager import ws_manager
        await ws_manager.broadcast({
            "type": "contract_reviewed",
            "payload": {"contract_id": contract_id,
                        "score": result.get("score", 0),
                        "issues_count": len(result.get("issues", []))},
        })
    except Exception:
        pass


def _publish_event(event_type: str, data: dict):
    try:
        import asyncio
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(bus.publish_raw({"type": event_type, "source": "contract_api",
                                                  "severity": "medium", "data": data}))
    except Exception:
        pass
