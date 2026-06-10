"""
审批管理 API — 审批请求的创建、审批、驳回、规则与统计。

端点:
  GET    /api/v1/approvals               — 审批列表
  POST   /api/v1/approvals               — 创建审批请求
  POST   /api/v1/approvals/{id}/approve  — 审批通过
  POST   /api/v1/approvals/{id}/reject   — 审批驳回
  GET    /api/v1/approvals/rules         — 审批规则
  GET    /api/v1/approvals/stats         — 审批统计
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


class ApproveRequest(BaseModel):
    approver_id: str
    approver_name: str
    comment: str = ""


class CreateApprovalRequest(BaseModel):
    requester_id: str
    requester_name: str
    resource: str
    action: str
    details: Dict[str, Any] = {}


@router.get("", summary="审批列表")
async def list_approvals(status: str = None, requester_id: str = None, limit: int = 50):
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    return {"approvals": engine.list_requests(status=status, requester_id=requester_id, limit=limit)}


@router.post("", summary="创建审批请求")
async def create_approval(req: CreateApprovalRequest):
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    return engine.create_request(req.requester_id, req.requester_name, req.resource, req.action, req.details)


@router.post("/{approval_id}/approve", summary="审批通过")
async def approve(approval_id: str, req: ApproveRequest):
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    result = engine.approve(approval_id, req.approver_id, req.approver_name, req.comment)
    if not result:
        raise HTTPException(status_code=404, detail="Approval not found or already resolved")
    return result


@router.post("/{approval_id}/reject", summary="审批驳回")
async def reject(approval_id: str, req: ApproveRequest):
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    result = engine.reject(approval_id, req.approver_id, req.approver_name, req.comment)
    if not result:
        raise HTTPException(status_code=404, detail="Approval not found or already resolved")
    return result


@router.get("/rules", summary="审批规则")
async def approval_rules():
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    return {"rules": engine.get_rules()}


@router.get("/stats", summary="审批统计")
async def approval_stats():
    from app.core.rbac import get_approval_engine
    engine = get_approval_engine()
    return engine.get_stats()
