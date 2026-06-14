"""供应商管理 API — /api/v1/suppliers"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from typing import Optional
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


# ── 请求模型 ──────────────────────────────────────────────────────────────────

class SupplierCreate(BaseModel):
    name: str
    source_type: str = Field("factory", description="1688 | factory | platform | overseas")
    contact_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    address: str = ""
    country: str = "CN"
    business_license: str = ""
    tax_id: str = ""
    has_invoice: bool = False
    certifications: list[str] = []
    categories: list[str] = []
    tags: list[str] = []
    metadata: dict = {}


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    business_license: Optional[str] = None
    tax_id: Optional[str] = None
    has_invoice: Optional[bool] = None
    certifications: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None


class RatingCreate(BaseModel):
    score: float = Field(..., ge=1, le=5)
    dimensions: dict = Field(default={}, description="{'quality':5,'delivery':4,'price':3,'service':4}")
    comment: str = ""


# ── 端点 ──────────────────────────────────────────────────────────────────────

@router.get("")
async def list_suppliers(
    status: Optional[str] = Query(None, description="active|suspended|blacklisted"),
    source_type: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    from app.storage.supplier_store import list_suppliers as _list
    return _list(status=status, source_type=source_type, country=country, limit=limit, offset=offset)


@router.post("", status_code=201)
async def create_supplier(req: SupplierCreate, current_user: dict = Depends(get_current_user)):
    from app.storage.supplier_store import create_supplier as _create
    return _create(req.model_dump())


@router.get("/{supplier_id}")
async def get_supplier(supplier_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.supplier_store import get_supplier as _get
    s = _get(supplier_id)
    if not s:
        raise HTTPException(404, f"供应商 {supplier_id} 不存在")
    return s


@router.put("/{supplier_id}")
async def update_supplier(
    supplier_id: str, req: SupplierUpdate,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.supplier_store import update_supplier as _upd
    updates = req.model_dump(exclude_none=True)
    s = _upd(supplier_id, updates)
    if not s:
        raise HTTPException(404, f"供应商 {supplier_id} 不存在")
    return s


@router.delete("/{supplier_id}", status_code=204)
async def suspend_supplier(supplier_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.supplier_store import update_supplier as _upd
    _upd(supplier_id, {"status": "suspended"})


@router.post("/{supplier_id}/verify")
async def verify_supplier(
    supplier_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """AI 资质审核（后台异步，结果通过 WS 推送）。"""
    from app.storage.supplier_store import get_supplier as _get
    s = _get(supplier_id)
    if not s:
        raise HTTPException(404, f"供应商 {supplier_id} 不存在")

    async def _do_verify():
        from app.core.lifecycle_analyzer import analyze_supplier
        result = await analyze_supplier(s)
        from app.storage.supplier_store import save_ai_review
        save_ai_review(supplier_id, result)
        # WS 推送
        try:
            from app.services.ws_manager import ws_manager
            await ws_manager.broadcast({
                "type": "supplier_verified",
                "payload": {"supplier_id": supplier_id, "risk_level": result.get("risk_level"),
                            "score": result.get("score", 0)},
            })
        except Exception:
            pass

    background_tasks.add_task(_do_verify)
    return {"status": "queued", "supplier_id": supplier_id,
            "message": "AI 审核已提交，结果将通过 WebSocket 推送"}


@router.post("/{supplier_id}/rate")
async def rate_supplier(
    supplier_id: str, req: RatingCreate,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.supplier_store import add_rating, get_supplier as _get
    if not _get(supplier_id):
        raise HTTPException(404, f"供应商 {supplier_id} 不存在")
    user_id = current_user.get("id", "default")
    return add_rating(supplier_id, user_id, req.score, req.dimensions, req.comment)


@router.get("/{supplier_id}/products")
async def get_supplier_products(
    supplier_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取该供应商关联的产品列表。"""
    from app.core.product_storage import get_product_storage
    storage = get_product_storage()
    products = [p for p in storage.list_products(limit=200)
                if (p.metadata or {}).get("supplier_id") == supplier_id
                or getattr(p, "supplier_id", None) == supplier_id]
    return {"products": [p.model_dump() for p in products], "total": len(products)}


@router.get("/{supplier_id}/risk-assessment")
async def get_risk_assessment(supplier_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.supplier_store import get_supplier as _get
    s = _get(supplier_id)
    if not s:
        raise HTTPException(404, f"供应商 {supplier_id} 不存在")
    ai_review = s.get("ai_review")
    if not ai_review:
        return {"supplier_id": supplier_id, "status": "not_reviewed",
                "message": "尚未进行 AI 审核，请调用 POST /{id}/verify"}
    return {"supplier_id": supplier_id, "status": "reviewed",
            "reviewed_at": s.get("ai_review_at"), "assessment": ai_review}
