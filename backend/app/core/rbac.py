"""
RBAC + ApprovalFlow（Phase 4.1）

RBAC权限模型：5种角色
  - admin: 全部权限
  - manager: 产品管理+审批+配置
  - operator: 产品操作+对话+查看
  - viewer: 只读
  - auditor: 审计日志+报表只读

操作守卫：产品上架/下架/删除需权限
审批流引擎：高风险操作需审批
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings


# ── 角色定义 ────────────────────────────────────────


class Role(str, Enum):
    admin = "admin"
    manager = "manager"
    operator = "operator"
    viewer = "viewer"
    auditor = "auditor"


# 角色权限矩阵
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "admin": [
        "product:*", "compliance:*", "event:*", "worker:*",
        "skill:*", "tool:*", "plugin:*", "integration:*",
        "config:*", "user:*", "approval:*", "report:*",
        "memory:*", "metrics:*", "security:*", "code:*",
        "channel:*", "sync:*", "agent:*",
    ],
    "manager": [
        "product:*", "compliance:*", "event:read", "event:create",
        "skill:read", "skill:execute", "tool:*", "integration:read",
        "approval:*", "report:*", "memory:*", "metrics:*",
        "config:read", "user:read", "agent:read",
    ],
    "operator": [
        "product:read", "product:create", "product:update",
        "compliance:read", "compliance:execute",
        "event:read", "skill:read", "skill:execute",
        "tool:read", "tool:execute", "memory:read",
        "metrics:read", "chat:*", "report:read",
    ],
    "viewer": [
        "product:read", "compliance:read", "event:read",
        "skill:read", "tool:read", "memory:read",
        "metrics:read", "report:read", "config:read",
    ],
    "auditor": [
        "product:read", "event:read", "security:read",
        "report:read", "approval:read", "audit:*",
        "compliance:read", "metrics:read",
    ],
}


# ── 操作类型 ────────────────────────────────────────


class Operation(str, Enum):
    create = "create"
    read = "read"
    update = "update"
    delete = "delete"
    execute = "execute"


# 高风险操作（需要审批）
HIGH_RISK_OPERATIONS = [
    {"resource": "product", "action": "delete", "description": "删除产品"},
    {"resource": "product", "action": "lifecycle_change", "description": "产品生命周期状态变更"},
    {"resource": "compliance", "action": "override", "description": "覆盖合规检查结果"},
    {"resource": "config", "action": "update", "description": "修改系统配置"},
    {"resource": "user", "action": "delete", "description": "删除用户"},
    {"resource": "skill", "action": "install", "description": "安装第三方Skill"},
    {"resource": "plugin", "action": "install", "description": "安装插件"},
    {"resource": "integration", "action": "create", "description": "新建第三方连接"},
]


# ── 数据结构 ────────────────────────────────────────


@dataclass
class UserRBAC:
    """用户RBAC信息"""
    user_id: str = ""
    username: str = ""
    role: Role = Role.viewer
    permissions: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role.value
        return d


@dataclass
class ApprovalRequest:
    """审批请求"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    requester_id: str = ""
    requester_name: str = ""
    resource: str = ""
    action: str = ""
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"         # pending / approved / rejected / cancelled
    approver_id: str = ""
    approver_name: str = ""
    approver_comment: str = ""
    priority: str = "medium"        # low / medium / high / critical
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    resolved_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ApprovalRequest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── 持久化 ────────────────────────────────────────

RBAC_FILE = Path(settings.data_dir) / "config" / "rbac_users.json"
APPROVALS_FILE = Path(settings.data_dir) / "config" / "approvals.json"


def _load_json(path: Path) -> Any:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {} if path.name.endswith("users.json") else []


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── RBACManager ───────────────────────────────────


class RBACManager:
    """RBAC权限管理器"""

    def __init__(self):
        self._users: Dict[str, UserRBAC] = {}
        self._load_users()

    def _load_users(self):
        raw = _load_json(RBAC_FILE)
        for uid, udata in raw.items():
            try:
                self._users[uid] = UserRBAC(**{k: v for k, v in udata.items() if k in UserRBAC.__dataclass_fields__})
                self._users[uid].role = Role(udata.get("role", "viewer"))
            except Exception:
                continue

    def _persist(self):
        _save_json(RBAC_FILE, {uid: u.to_dict() for uid, u in self._users.items()})

    def assign_role(self, user_id: str, username: str, role: str) -> Dict:
        """分配角色"""
        try:
            r = Role(role)
        except ValueError:
            raise ValueError(f"Invalid role: {role}. Available: {[e.value for e in Role]}")

        user = UserRBAC(
            user_id=user_id,
            username=username,
            role=r,
            permissions=ROLE_PERMISSIONS.get(role, []),
        )
        self._users[user_id] = user
        self._persist()
        return user.to_dict()

    def get_user(self, user_id: str) -> Optional[Dict]:
        user = self._users.get(user_id)
        return user.to_dict() if user else None

    def list_users(self) -> List[Dict]:
        return [u.to_dict() for u in self._users.values()]

    def check_permission(self, user_id: str, resource: str, action: str) -> bool:
        """检查用户是否有权限执行操作"""
        user = self._users.get(user_id)
        if not user:
            return False

        # 构建权限key
        perm_full = f"{resource}:{action}"
        perm_wildcard = f"{resource}:*"

        for p in user.permissions:
            if p == perm_full or p == perm_wildcard:
                return True

        # admin has all
        if user.role == Role.admin:
            return True

        return False

    def get_permissions(self, user_id: str) -> List[str]:
        user = self._users.get(user_id)
        if not user:
            return []
        return user.permissions

    def get_role_permissions(self, role: str) -> List[str]:
        return ROLE_PERMISSIONS.get(role, [])

    def get_roles(self) -> List[Dict]:
        """获取所有角色定义"""
        return [
            {"role": r, "permissions": perms, "description": {
                "admin": "系统管理员，拥有全部权限",
                "manager": "经理，产品管理+审批+配置权限",
                "operator": "操作员，产品操作+对话+查看权限",
                "viewer": "观察者，只读权限",
                "auditor": "审计员，审计日志+报表只读",
            }.get(r, "")}
            for r, perms in ROLE_PERMISSIONS.items()
        ]


# ── OperationGuard — 操作守卫 ────────────────────


class OperationGuard:
    """操作守卫 — 在执行前检查权限和审批需求"""

    def __init__(self, rbac: RBACManager, approval_engine: "ApprovalEngine"):
        self.rbac = rbac
        self.approval_engine = approval_engine

    async def check_and_execute(self, user_id: str, resource: str, action: str,
                                details: Dict = None, execute_fn=None) -> Dict:
        """检查权限 → 检查审批需求 → 执行或创建审批"""
        # 1. 权限检查
        if not self.rbac.check_permission(user_id, resource, action):
            return {
                "status": "denied",
                "reason": f"Permission denied: {resource}:{action}",
            }

        # 2. 检查是否需要审批
        needs_approval = self._needs_approval(resource, action)
        if needs_approval:
            # 检查是否有已通过的审批
            existing = self.approval_engine.get_pending_approval(user_id, resource, action)
            if existing and existing.get("status") == "approved":
                # 已有审批通过，直接执行
                pass
            else:
                # 创建审批请求
                approval = self.approval_engine.create_request(
                    requester_id=user_id,
                    requester_name=self.rbac.get_user(user_id).get("username", user_id) if self.rbac.get_user(user_id) else user_id,
                    resource=resource,
                    action=action,
                    details=details or {},
                )
                return {
                    "status": "requires_approval",
                    "approval_id": approval["id"],
                    "reason": f"High-risk operation '{resource}:{action}' requires approval",
                }

        # 3. 执行操作
        if execute_fn:
            try:
                result = await execute_fn()
                return {"status": "executed", "result": result}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        return {"status": "authorized", "resource": resource, "action": action}

    def _needs_approval(self, resource: str, action: str) -> bool:
        """检查操作是否需要审批"""
        for op in HIGH_RISK_OPERATIONS:
            if op["resource"] == resource and op["action"] == action:
                return True
        return False

    def get_high_risk_operations(self) -> List[Dict]:
        return HIGH_RISK_OPERATIONS


# ── ApprovalEngine — 审批流引擎 ──────────────────


class ApprovalEngine:
    """审批流引擎"""

    def __init__(self):
        self._requests: List[ApprovalRequest] = []
        self._load_all()

    def _load_all(self):
        raw = _load_json(APPROVALS_FILE)
        if isinstance(raw, list):
            for rd in raw:
                try:
                    self._requests.append(ApprovalRequest.from_dict(rd))
                except Exception:
                    continue

    def _persist(self):
        _save_json(APPROVALS_FILE, [r.to_dict() for r in self._requests])

    def create_request(self, requester_id: str, requester_name: str,
                      resource: str, action: str,
                      details: Dict = None) -> Dict:
        """创建审批请求"""
        # 检查是否有相同待审批请求
        for r in self._requests:
            if (r.requester_id == requester_id and r.resource == resource
                    and r.action == action and r.status == "pending"):
                return r.to_dict()

        req = ApprovalRequest(
            requester_id=requester_id,
            requester_name=requester_name,
            resource=resource,
            action=action,
            description=f"{resource}:{action}",
            details=details or {},
            priority="high" if resource in ("config", "user") else "medium",
        )
        self._requests.append(req)
        self._persist()

        # 触发审批事件
        try:
            from app.core.event_bus import get_event_bus
            import asyncio
            asyncio.create_task(get_event_bus().publish_raw({
                "type": "user_action:approval_requested",
                "source": "rbac",
                "data": {
                    "approval_id": req.id,
                    "requester": requester_name,
                    "resource": resource,
                    "action": action,
                },
            }))
        except Exception:
            pass

        return req.to_dict()

    def approve(self, approval_id: str, approver_id: str, approver_name: str,
               comment: str = "") -> Optional[Dict]:
        """审批通过"""
        for req in self._requests:
            if req.id == approval_id and req.status == "pending":
                req.status = "approved"
                req.approver_id = approver_id
                req.approver_name = approver_name
                req.approver_comment = comment
                req.resolved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._persist()
                return req.to_dict()
        return None

    def reject(self, approval_id: str, approver_id: str, approver_name: str,
              comment: str = "") -> Optional[Dict]:
        """审批驳回"""
        for req in self._requests:
            if req.id == approval_id and req.status == "pending":
                req.status = "rejected"
                req.approver_id = approver_id
                req.approver_name = approver_name
                req.approver_comment = comment
                req.resolved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._persist()
                return req.to_dict()
        return None

    def cancel(self, approval_id: str, requester_id: str) -> Optional[Dict]:
        """取消审批"""
        for req in self._requests:
            if req.id == approval_id and req.status == "pending" and req.requester_id == requester_id:
                req.status = "cancelled"
                req.resolved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._persist()
                return req.to_dict()
        return None

    def list_requests(self, status: str = None, requester_id: str = None,
                     limit: int = 50) -> List[Dict]:
        reqs = self._requests
        if status:
            reqs = [r for r in reqs if r.status == status]
        if requester_id:
            reqs = [r for r in reqs if r.requester_id == requester_id]
        reqs.sort(key=lambda r: r.created_at, reverse=True)
        return [r.to_dict() for r in reqs[:limit]]

    def get_pending_approval(self, user_id: str, resource: str, action: str) -> Optional[Dict]:
        """获取用户的已通过审批（匹配resource+action）"""
        for req in reversed(self._requests):
            if (req.requester_id == user_id and req.resource == resource
                    and req.action == action and req.status == "approved"):
                return req.to_dict()
        return None

    def get_rules(self) -> List[Dict]:
        """获取审批规则（高风险操作清单）"""
        return HIGH_RISK_OPERATIONS

    def get_stats(self) -> Dict:
        """审批统计"""
        pending = sum(1 for r in self._requests if r.status == "pending")
        approved = sum(1 for r in self._requests if r.status == "approved")
        rejected = sum(1 for r in self._requests if r.status == "rejected")
        return {
            "total": len(self._requests),
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "cancelled": len(self._requests) - pending - approved - rejected,
        }


# ── 单例 ──────────────────────────────────────────

_rbac_manager: Optional[RBACManager] = None
_approval_engine: Optional[ApprovalEngine] = None
_operation_guard: Optional[OperationGuard] = None


def get_rbac_manager() -> RBACManager:
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager


def get_approval_engine() -> ApprovalEngine:
    global _approval_engine
    if _approval_engine is None:
        _approval_engine = ApprovalEngine()
    return _approval_engine


def get_operation_guard() -> OperationGuard:
    global _operation_guard
    if _operation_guard is None:
        _operation_guard = OperationGuard(get_rbac_manager(), get_approval_engine())
    return _operation_guard
