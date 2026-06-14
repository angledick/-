"""报关管理 API — /api/v1/customs"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Optional
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/customs", tags=["customs"])


class DeclarationCreate(BaseModel):
    product_id:        str
    logistics_id:      Optional[str] = None
    mode:              str = Field("9610", description="9610（跨境B2C直邮）|一般贸易|保税备货")
    hs_code:           str
    declared_name:     str
    declared_value:    float
    declared_currency: str = "USD"
    quantity:          int = 1
    unit:              str = "件"
    origin_country:    str = "CN"
    dest_country:      str
    ioss_number:       Optional[str] = None
    documents:         list[str] = []
    # 扩展字段（三单一致性 + 报关要素）
    brand:               str = ""
    model_spec:          str = ""
    unit_price:          float = 0.0
    fx_rate_date:        Optional[str] = None
    shipper_name:        str = ""
    shipper_address:     str = ""
    shipper_eori:        str = ""
    consignee_name:      str = ""
    consignee_address:   str = ""
    order_id:            Optional[str] = None
    contract_no:         str = ""
    invoice_no:          str = ""
    export_license_no:   str = ""
    co_cert_no:          str = ""
    ecommerce_record_no: str = ""


class DutyCalcRequest(BaseModel):
    hs_code: str
    dest_country: str
    declared_value: float
    currency: str = "USD"


# ── 报关单 ────────────────────────────────────────────────────────────────────

@router.post("/declarations", status_code=201)
async def create_declaration(
    req: DeclarationCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.customs_store import create_declaration as _cd
    d = _cd(req.model_dump())
    # 自动触发合规检查
    async def _check():
        await _do_compliance_check(d["id"])
    background_tasks.add_task(_check)
    _publish("customs:declared", {"declaration_id": d["id"],
                                   "product_id": req.product_id,
                                   "hs_code": req.hs_code,
                                   "dest_country": req.dest_country})
    return d


@router.get("/declarations")
async def list_declarations(
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    dest_country: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.customs_store import list_declarations as _ld
    return _ld(product_id=product_id, status=status, dest_country=dest_country, limit=limit)


@router.get("/declarations/{declaration_id}")
async def get_declaration(declaration_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.customs_store import get_declaration as _gd
    d = _gd(declaration_id)
    if not d:
        raise HTTPException(404, f"报关单 {declaration_id} 不存在")
    return d


@router.post("/declarations/{declaration_id}/submit")
async def submit_declaration(declaration_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.customs_store import submit_declaration as _sd, get_declaration as _gd
    if not _gd(declaration_id):
        raise HTTPException(404, f"报关单 {declaration_id} 不存在")
    d = _sd(declaration_id)
    _publish("customs:submitted", {"declaration_id": declaration_id})
    return d


@router.post("/declarations/{declaration_id}/check")
async def check_declaration(
    declaration_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """AI 合规检查（三单一致性 + HS 编码核验 + IOSS 检测）。"""
    from app.storage.customs_store import get_declaration as _gd
    if not _gd(declaration_id):
        raise HTTPException(404, f"报关单 {declaration_id} 不存在")

    async def _check():
        await _do_compliance_check(declaration_id)

    background_tasks.add_task(_check)
    return {"status": "queued", "declaration_id": declaration_id}


@router.post("/declarations/{declaration_id}/clear")
async def clear_declaration(
    declaration_id: str, current_user: dict = Depends(get_current_user),
):
    """标记清关完成。"""
    from app.storage.customs_store import update_status as _us
    d = _us(declaration_id, "cleared")
    if not d:
        raise HTTPException(404, f"报关单 {declaration_id} 不存在")
    _publish("customs:cleared", {"declaration_id": declaration_id,
                                  "product_id": d.get("product_id")})
    return d


@router.post("/declarations/{declaration_id}/exception")
async def mark_exception(
    declaration_id: str,
    reason: str,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.customs_store import update_status as _us
    d = _us(declaration_id, "exception", exception_reason=reason)
    if not d:
        raise HTTPException(404, f"报关单 {declaration_id} 不存在")
    _publish("customs:exception", {"declaration_id": declaration_id,
                                    "reason": reason, "product_id": d.get("product_id")})
    return d


# ── 关税计算 ──────────────────────────────────────────────────────────────────

@router.post("/duty-calculator")
async def calculate_duty(req: DutyCalcRequest, current_user: dict = Depends(get_current_user)):
    from app.storage.customs_store import calculate_duty as _calc
    return _calc(req.hs_code, req.dest_country, req.declared_value, req.currency)


@router.get("/tariff-rates")
async def get_tariff_rates(current_user: dict = Depends(get_current_user)):
    from app.storage.customs_store import get_tariff_rates
    rates = get_tariff_rates()
    countries = [k for k in rates if not k.startswith("_")]
    return {
        "countries": countries,
        "total_entries": sum(len(v) for v in rates.values() if isinstance(v, dict)),
        "last_updated": rates.get("_updated", ""),
        "rates": {k: v for k, v in rates.items() if not k.startswith("_")}
    }


# ── 内部辅助 ──────────────────────────────────────────────────────────────────

async def _do_compliance_check(declaration_id: str):
    """执行报关合规检查（规则 + AI）。"""
    from app.storage.customs_store import get_declaration as _gd, save_compliance_checks
    d = _gd(declaration_id)
    if not d:
        return

    checks = []

    # 规则 1: IOSS 检查
    from app.storage.customs_store import check_ioss_applicable
    needs_ioss = check_ioss_applicable(d["dest_country"], d["declared_value"])
    if needs_ioss and not d.get("ioss_number"):
        checks.append({
            "rule": "IOSS_REQUIRED", "level": "error",
            "message": f"目的国 {d['dest_country']} 单票价值 ≤ €150，必须提供 IOSS 税号。缺失将导致买家二次缴税，引发拒收和投诉。",
            "recommendation": "请在欧盟 OSS 门户注册 IOSS，并在报关时填入税号。",
        })
    elif needs_ioss and d.get("ioss_number"):
        checks.append({"rule": "IOSS_OK", "level": "pass", "message": "IOSS 税号已配置 ✓"})

    # 规则 2: 低申报检测
    if d["declared_value"] < 1:
        checks.append({
            "rule": "ZERO_VALUE", "level": "error",
            "message": "申报价值为 0，存在低申报风险。目的国海关可处 2-5 倍罚款并扣货。",
        })

    # 规则 3: 必填文件检查
    required_docs = ["invoice", "packing_list"]
    missing = [doc for doc in required_docs if doc not in (d.get("documents") or [])]
    if missing:
        checks.append({
            "rule": "MISSING_DOCS", "level": "warning",
            "message": f"缺少必要单据：{', '.join(missing)}。9610 模式需发票（electronic）和装箱单。",
        })
    else:
        checks.append({"rule": "DOCS_OK", "level": "pass", "message": "必要单据齐备 ✓"})

    # 规则 4: HS 编码格式检查
    hs = d.get("hs_code", "")
    if len(hs) < 4 or not hs.replace(".", "").isdigit():
        checks.append({
            "rule": "HS_FORMAT", "level": "error",
            "message": f"HS 编码 '{hs}' 格式异常。标准格式为 4-10 位数字（如 8703、870321）。",
        })
    else:
        checks.append({"rule": "HS_FORMAT_OK", "level": "pass", "message": f"HS 编码格式正常（{hs}）✓"})

    # 规则 5: 管制品检测
    try:
        from app.core.controlled_goods_checker import get_controlled_goods_checker
        cg_checker = get_controlled_goods_checker()
        cg_result = cg_checker.full_check(
            hs_code=hs,
            declared_name=d.get("declared_name", ""),
            dest_country=d.get("dest_country", ""),
            supplier_name=d.get("shipper_name", ""),
            supplier_address=d.get("shipper_address", ""),
        )
        for issue in cg_result.get("errors", []) + cg_result.get("warnings", []):
            checks.append({
                "rule": issue.get("rule", "CONTROLLED_GOODS"),
                "level": issue.get("level", "warning"),
                "message": issue.get("message", ""),
                "recommendation": issue.get("recommendation", ""),
                "code": issue.get("code", ""),
            })
        if not cg_result.get("errors") and not cg_result.get("warnings"):
            checks.append({"rule": "CONTROLLED_GOODS_OK", "level": "pass",
                           "message": "管制品检查通过，未发现高风险 ✓"})
    except Exception:
        pass

    # 规则 6: 三单一致性检查（如果有关联订单）
    order_id = d.get("order_id")
    logistics_id = d.get("logistics_id")
    if order_id or logistics_id:
        try:
            from app.core.three_way_checker import get_three_way_checker
            tw_checker = get_three_way_checker()
            tw_result = tw_checker.check(
                order_id=order_id,
                declaration_id=declaration_id,
                logistics_id=logistics_id,
            )
            for check in tw_result.get("checks", []):
                if check.get("level") not in ("pass", "na"):
                    checks.append({
                        "rule": "3WAY_" + check.get("rule", "CHECK"),
                        "level": check.get("level", "warning"),
                        "message": f"[三单一致性] {check.get('message', '')}",
                        "recommendation": check.get("recommendation", ""),
                        "code": check.get("code", ""),
                    })
            # 将三单检查摘要加入
            if tw_result.get("passed"):
                checks.append({"rule": "THREE_WAY_OK", "level": "pass",
                               "message": f"三单一致性验证通过 ✓（{len(tw_result['checks'])} 项检查）"})
        except Exception:
            pass
    else:
        checks.append({"rule": "THREE_WAY_SKIPPED", "level": "info",
                       "message": "报关单未关联订单，跳过三单一致性检查（建议关联 order_id）"})

    # AI 增强检查（可选，需 ZhipuAI）
    try:
        from app.core.lifecycle_analyzer import analyze_customs_declaration
        ai_result = await analyze_customs_declaration(d)
        if ai_result.get("issues"):
            for issue in ai_result["issues"]:
                checks.append({"rule": "AI_" + issue.get("code", "CHECK"),
                                "level": issue.get("level", "warning"),
                                "message": issue.get("message", "")})
    except Exception:
        pass

    save_compliance_checks(declaration_id, checks)

    # WS 推送结果
    errors = [c for c in checks if c["level"] == "error"]
    try:
        from app.services.ws_manager import ws_manager
        await ws_manager.broadcast({
            "type": "customs_checked",
            "payload": {"declaration_id": declaration_id,
                        "errors": len(errors), "total_checks": len(checks)},
        })
    except Exception:
        pass


@router.get("/controlled-goods/check")
async def check_controlled_goods(
    hs_code: str,
    declared_name: str,
    dest_country: str,
    shipper_name: str = "",
    shipper_address: str = "",
    current_user: dict = Depends(get_current_user),
):
    """管制品快速检查（不创建报关单，用于预检）。"""
    from app.core.controlled_goods_checker import get_controlled_goods_checker
    checker = get_controlled_goods_checker()
    return checker.full_check(
        hs_code=hs_code,
        declared_name=declared_name,
        dest_country=dest_country,
        supplier_name=shipper_name,
        supplier_address=shipper_address,
    )


@router.post("/three-way-check")
async def three_way_check(
    order_id: Optional[str] = None,
    declaration_id: Optional[str] = None,
    logistics_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """三单一致性独立检查接口。"""
    if not order_id and not declaration_id:
        raise HTTPException(400, "order_id 或 declaration_id 至少填写一个")
    from app.core.three_way_checker import get_three_way_checker
    checker = get_three_way_checker()
    return checker.check(
        order_id=order_id,
        declaration_id=declaration_id,
        logistics_id=logistics_id,
    )


def _publish(event_type: str, data: dict):
    try:
        import asyncio
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(bus.publish_raw({"type": event_type, "source": "customs_api",
                                                  "severity": "medium", "data": data}))
    except Exception:
        pass
