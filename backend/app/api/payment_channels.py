"""支付通道管理 API — /api/v1/payment-channels"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Optional
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/payment-channels", tags=["payment-channels"])


class ChannelCreate(BaseModel):
    provider: str = Field(..., description="stripe|paypal|lianlian|worldfirst|shopify_payments|alipay_global")
    display_name: Optional[str] = None
    currency: Optional[list[str]] = None
    markets: Optional[list[str]] = None
    webhook_url: str = ""
    test_mode: bool = True
    metadata: dict = {}


class ChannelUpdate(BaseModel):
    webhook_url: Optional[str] = None
    test_mode: Optional[bool] = None
    kyc_verified: Optional[bool] = None
    chargeback_limit: Optional[float] = None
    status: Optional[str] = None


# ── 端点 ──────────────────────────────────────────────────────────────────────

@router.get("")
async def list_channels(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.payment_store import list_channels as _lc
    channels = _lc(status=status)
    # 附加合规注意事项
    for c in channels:
        c["compliance_notes"] = _get_compliance_notes(c)
    return channels


@router.post("", status_code=201)
async def create_channel(req: ChannelCreate, current_user: dict = Depends(get_current_user)):
    from app.storage.payment_store import create_channel as _cc
    data = req.model_dump(exclude_none=True)
    c = _cc(data)
    c["compliance_notes"] = _get_compliance_notes(c)
    return c


@router.get("/{channel_id}")
async def get_channel(channel_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.payment_store import get_channel as _gc
    c = _gc(channel_id)
    if not c:
        raise HTTPException(404, f"支付通道 {channel_id} 不存在")
    c["compliance_notes"] = _get_compliance_notes(c)
    return c


@router.put("/{channel_id}")
async def update_channel(
    channel_id: str, req: ChannelUpdate,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.payment_store import update_channel as _uc
    c = _uc(channel_id, req.model_dump(exclude_none=True))
    if not c:
        raise HTTPException(404, f"支付通道 {channel_id} 不存在")
    return c


@router.post("/{channel_id}/test")
async def test_channel(
    channel_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """连通性测试（发送一个空请求验证 webhook 可达）。"""
    from app.storage.payment_store import get_channel as _gc, save_test_result
    c = _gc(channel_id)
    if not c:
        raise HTTPException(404, f"支付通道 {channel_id} 不存在")

    async def _test():
        import httpx
        webhook = c.get("webhook_url", "")
        if not webhook:
            save_test_result(channel_id, False, {"error": "未配置 Webhook URL"})
            return
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.post(webhook, json={"type": "ping", "channel_id": channel_id})
            success = resp.status_code < 400
            save_test_result(channel_id, success, {
                "status_code": resp.status_code, "latency_ms": int(resp.elapsed.total_seconds() * 1000)
            })
        except Exception as e:
            save_test_result(channel_id, False, {"error": str(e)[:200]})
        # WS 推送
        try:
            from app.services.ws_manager import ws_manager
            updated = _gc(channel_id)
            await ws_manager.broadcast({"type": "payment_channel_tested",
                                         "payload": {"channel_id": channel_id,
                                                     "status": updated.get("status")}})
        except Exception:
            pass

    background_tasks.add_task(_test)
    return {"status": "queued", "channel_id": channel_id}


@router.post("/{channel_id}/compliance-check")
async def compliance_check(channel_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.payment_store import get_channel as _gc
    c = _gc(channel_id)
    if not c:
        raise HTTPException(404, f"支付通道 {channel_id} 不存在")
    notes = _get_compliance_notes(c)
    issues = [n for n in notes if n.get("level") == "error"]
    warnings = [n for n in notes if n.get("level") == "warning"]
    return {
        "channel_id": channel_id, "provider": c["provider"],
        "passed": len(issues) == 0, "issues": issues, "warnings": warnings,
        "score": max(0, 100 - len(issues) * 30 - len(warnings) * 10),
    }


@router.get("/{channel_id}/chargeback-stats")
async def chargeback_stats(
    channel_id: str, days: int = 30,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.payment_store import get_chargeback_stats
    return get_chargeback_stats(channel_id, days)


@router.post("/webhook/{provider}")
async def receive_webhook(provider: str, payload: dict):
    """接收第三方支付 Webhook（Stripe/PayPal 等）。"""
    # 解析拒付事件
    try:
        if provider == "stripe" and payload.get("type", "").startswith("charge.dispute"):
            _handle_chargeback_event(provider, payload)
        elif provider == "paypal" and payload.get("event_type", "").startswith("PAYMENT.DISPUTE"):
            _handle_chargeback_event(provider, payload)
    except Exception:
        pass
    return {"received": True}


# ── 合规注意事项生成 ──────────────────────────────────────────────────────────

def _get_compliance_notes(channel: dict) -> list[dict]:
    notes = []
    if not channel.get("kyc_verified"):
        notes.append({"level": "error", "code": "KYC_REQUIRED",
                       "message": "KYC 身份认证未完成。请提交真实企业/个人资料，确保账户主体与店铺主体一致。"})
    if channel.get("chargeback_rate", 0) >= channel.get("chargeback_limit", 0.8):
        notes.append({"level": "error", "code": "CHARGEBACK_HIGH",
                       "message": f"拒付率 {channel['chargeback_rate']:.2f}% 已超阈值 {channel['chargeback_limit']}%，账户有冻结风险。建议开启 3DS 验证。"})
    elif channel.get("chargeback_rate", 0) >= channel.get("chargeback_limit", 0.8) * 0.7:
        notes.append({"level": "warning", "code": "CHARGEBACK_WARN",
                       "message": f"拒付率 {channel['chargeback_rate']:.2f}% 接近阈值，建议排查异常订单。"})
    if not channel.get("pci_dss"):
        notes.append({"level": "warning", "code": "PCI_DSS",
                       "message": "该通道 PCI DSS 认证状态未知。请确认不在系统中明文存储信用卡信息。"})
    if channel.get("provider") in ("lianlian", "worldfirst"):
        notes.append({"level": "info", "code": "SETTLEMENT_COMPLIANCE",
                       "message": "资金链路合规提示：请通过该持牌支付机构合规结汇，勿使用个人账户直接收取大额外汇，以应对金税四期监管。"})
    if not channel.get("webhook_url"):
        notes.append({"level": "warning", "code": "NO_WEBHOOK",
                       "message": "未配置 Webhook URL，将无法实时接收支付事件。"})
    return notes


def _handle_chargeback_event(provider: str, payload: dict):
    from app.storage.payment_store import add_chargeback_event, list_channels
    channels = list_channels()
    ch = next((c for c in channels if c["provider"] == provider), None)
    if ch:
        amount = payload.get("data", {}).get("object", {}).get("amount", 0) / 100
        add_chargeback_event(ch["id"], payload.get("id", ""), amount, "USD",
                              payload.get("type", ""))
