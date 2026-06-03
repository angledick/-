"""
任务拆解器 (TaskDecomposer) — 基于配置的任务分解引擎。

职责:
  1. 将高层任务描述拆解为可执行的子任务列表
  2. 基于业务阶段和事件类型匹配分解模板
  3. 支持用户自定义分解规则（YAML配置）
  4. 为子任务标注优先级、依赖关系和所需Skills

参考:
  - QwenPaw 多智能体架构: 任务拆解 + Worker分配
  - n8n (191k⭐): 工作流编排可视化
  - Temporal (14k⭐): 确定性执行 + 故障自动重试
"""

import uuid
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from app.config import settings

DATA_DIR = Path(settings.data_dir)


@dataclass
class SubTask:
    """子任务定义"""
    task_id: str = ""
    parent_task_id: str = ""
    task_type: str = ""              # 任务类型 (compliance_check/cert_verify/listing_check等)
    description: str = ""            # 任务描述
    business_stage: str = ""         # 业务阶段
    required_skills: List[str] = field(default_factory=list)
    assigned_worker: str = ""        # 分配的Worker编码
    priority: int = 5                # 优先级 (1最高)
    depends_on: List[str] = field(default_factory=list)  # 依赖的子任务ID
    context: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"          # pending/running/done/failed/cancelled
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 2

    def __post_init__(self):
        if not self.task_id:
            self.task_id = f"task_{uuid.uuid4().hex[:10]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "parent_task_id": self.parent_task_id,
            "task_type": self.task_type,
            "description": self.description,
            "business_stage": self.business_stage,
            "required_skills": self.required_skills,
            "assigned_worker": self.assigned_worker,
            "priority": self.priority,
            "depends_on": self.depends_on,
            "context": self.context,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


# ── 内置分解模板 ──────────────────────────────────
# 基于指南§6.15六步执行流水线和10大业务阶段

BUILTIN_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    # 新品上架合规检查（阶段4）
    "product_listing_compliance": [
        {
            "task_type": "metadata_check",
            "description": "检查产品合规元数据完整性（HS编码、认证、原产地）",
            "business_stage": "阶段4",
            "required_skills": ["shopify-custom-data"],
            "priority": 1,
        },
        {
            "task_type": "content_compliance",
            "description": "审查标题/描述广告法合规（禁用词、夸大宣传）",
            "business_stage": "阶段4",
            "required_skills": ["shopify-dev", "shopify-liquid"],
            "priority": 2,
            "depends_on_index": [0],  # 依赖元数据检查
        },
        {
            "task_type": "cert_validation",
            "description": "验证产品认证有效性（CE/FDA/FCC等）",
            "business_stage": "阶段4",
            "required_skills": ["shopify-custom-data", "shopify-admin"],
            "priority": 1,
        },
        {
            "task_type": "publish_product",
            "description": "通过合规检查后发布产品",
            "business_stage": "阶段4",
            "required_skills": ["shopify-admin"],
            "priority": 3,
            "depends_on_index": [0, 1, 2],  # 依赖前面全部
        },
    ],

    # 合规检查流水线（全阶段通用）
    "compliance_pipeline": [
        {
            "task_type": "event_perceive",
            "description": "事件感知 — 接收并标准化事件",
            "business_stage": "全阶段",
            "required_skills": [],
            "priority": 1,
        },
        {
            "task_type": "rule_check",
            "description": "规则检查 — RuleEngine执行规则匹配",
            "business_stage": "全阶段",
            "required_skills": [],
            "priority": 1,
            "depends_on_index": [0],
        },
        {
            "task_type": "rag_lookup",
            "description": "法规检索 — RAG搜索相关法规知识",
            "business_stage": "全阶段",
            "required_skills": [],
            "priority": 2,
            "depends_on_index": [0],
        },
        {
            "task_type": "risk_assessment",
            "description": "风险评估 — 计算风险等级",
            "business_stage": "全阶段",
            "required_skills": [],
            "priority": 1,
            "depends_on_index": [1, 2],
        },
        {
            "task_type": "recommend_actions",
            "description": "推荐操作 — 生成结构化Action推荐",
            "business_stage": "全阶段",
            "required_skills": [],
            "priority": 2,
            "depends_on_index": [3],
        },
        {
            "task_type": "notify_user",
            "description": "用户通知 — 多渠道推送结果",
            "business_stage": "全阶段",
            "required_skills": [],
            "priority": 2,
            "depends_on_index": [3],
        },
    ],

    # 认证到期处理
    "cert_expiry_handling": [
        {
            "task_type": "cert_status_check",
            "description": "确认认证到期状态和受影响产品",
            "business_stage": "全阶段",
            "required_skills": ["shopify-custom-data"],
            "priority": 1,
        },
        {
            "task_type": "impact_analysis",
            "description": "分析认证过期对产品销售的影响",
            "business_stage": "全阶段",
            "required_skills": ["shopify-admin"],
            "priority": 1,
            "depends_on_index": [0],
        },
        {
            "task_type": "renewal_guide",
            "description": "生成认证续期指南和步骤",
            "business_stage": "全阶段",
            "required_skills": ["shopify-dev"],
            "priority": 2,
            "depends_on_index": [1],
        },
        {
            "task_type": "notify_stakeholders",
            "description": "通知相关人员处理认证续期",
            "business_stage": "全阶段",
            "required_skills": [],
            "priority": 2,
            "depends_on_index": [1],
        },
    ],

    # 订单履约检查（阶段6-8）
    "order_fulfillment_check": [
        {
            "task_type": "three_way_match",
            "description": "三单一致性校验（订单/支付/物流）",
            "business_stage": "阶段6",
            "required_skills": ["shopify-admin", "shopify-custom-data"],
            "priority": 1,
        },
        {
            "task_type": "hs_code_verify",
            "description": "HS编码与申报要素核对",
            "business_stage": "阶段7",
            "required_skills": ["shopify-custom-data"],
            "priority": 1,
            "depends_on_index": [0],
        },
        {
            "task_type": "customs_docs",
            "description": "报关单证生成（发票/箱单/提单）",
            "business_stage": "阶段7",
            "required_skills": ["shopify-admin"],
            "priority": 2,
            "depends_on_index": [0, 1],
        },
        {
            "task_type": "vat_iss_check",
            "description": "IOSS/VAT合规检查（欧盟市场）",
            "business_stage": "阶段8",
            "required_skills": ["shopify-admin", "shopify-functions"],
            "priority": 1,
        },
    ],

    # 法规变更影响分析
    "regulation_change_analysis": [
        {
            "task_type": "change_identify",
            "description": "识别法规变更内容和范围",
            "business_stage": "全阶段",
            "required_skills": [],
            "priority": 1,
        },
        {
            "task_type": "affected_products",
            "description": "匹配受影响的在售产品",
            "business_stage": "全阶段",
            "required_skills": ["shopify-admin"],
            "priority": 1,
            "depends_on_index": [0],
        },
        {
            "task_type": "impact_report",
            "description": "生成影响评估报告",
            "business_stage": "全阶段",
            "required_skills": [],
            "priority": 2,
            "depends_on_index": [0, 1],
        },
        {
            "task_type": "recheck_compliance",
            "description": "触发受影响产品合规重检",
            "business_stage": "全阶段",
            "required_skills": [],
            "priority": 1,
            "depends_on_index": [1],
        },
    ],

    # GDPR DSAR请求处理（阶段9）
    "gdpr_dsar_handling": [
        {
            "task_type": "dsar_validate",
            "description": "验证DSAR请求合法性和范围",
            "business_stage": "阶段9",
            "required_skills": ["shopify-customer"],
            "priority": 1,
        },
        {
            "task_type": "data_export",
            "description": "导出客户全量数据",
            "business_stage": "阶段9",
            "required_skills": ["shopify-customer", "shopify-admin"],
            "priority": 1,
            "depends_on_index": [0],
        },
        {
            "task_type": "data_review",
            "description": "审核导出数据，标记需保留的法律依据数据",
            "business_stage": "阶段9",
            "required_skills": [],
            "priority": 2,
            "depends_on_index": [1],
        },
        {
            "task_type": "respond_dsar",
            "description": "在24-48h内响应DSAR请求",
            "business_stage": "阶段9",
            "required_skills": ["shopify-customer"],
            "priority": 1,
            "depends_on_index": [2],
        },
    ],
}


class TaskDecomposer:
    """任务拆解器 — 基于配置模板的任务分解

    用法:
        decomposer = TaskDecomposer()

        # 使用内置模板分解
        subtasks = await decomposer.decompose(
            task="product_listing_compliance",
            context={"product_id": "p_led_de_001", "market": "德国"}
        )

        # 自定义分解
        subtasks = await decomposer.decompose(
            task="custom_task",
            context={"description": "..."},
            template_key="compliance_pipeline"  # 指定模板
        )

        # 查询可用模板
        templates = decomposer.list_templates()

    开源参考:
      - n8n (191k⭐): 可视化工作流编排
      - Temporal (14k⭐): 确定性执行 + 回滚策略
      - 指南§6.15: 六步执行流水线
    """

    def __init__(self, custom_templates_dir: str = None):
        self._templates: Dict[str, List[Dict[str, Any]]] = dict(BUILTIN_TEMPLATES)
        self._custom_dir = Path(custom_templates_dir) if custom_templates_dir else (
            DATA_DIR / "config" / "workflows"
        )
        self._load_custom_templates()

    def _load_custom_templates(self):
        """从配置文件加载自定义分解模板"""
        if not self._custom_dir.exists():
            return

        for yaml_file in self._custom_dir.glob("*.yaml"):
            try:
                import yaml
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict) and "templates" in data:
                    for tpl_key, tpl_steps in data["templates"].items():
                        self._templates[tpl_key] = tpl_steps
            except Exception:
                pass

    async def decompose(
        self,
        task: str,
        context: Dict[str, Any] = None,
        template_key: str = None,
        parent_task_id: str = None,
    ) -> List[SubTask]:
        """将任务拆解为子任务列表

        Args:
            task: 任务标识（匹配模板key）或自由描述
            context: 任务上下文（product_id, market等）
            template_key: 强制指定模板key
            parent_task_id: 父任务ID
        Returns:
            SubTask列表
        """
        context = context or {}
        ctx = context.copy()

        # 查找匹配模板
        key = template_key or task
        template = self._templates.get(key)

        if not template:
            # 尝试模糊匹配
            for tpl_key in self._templates:
                if tpl_key in task or task in tpl_key:
                    template = self._templates[tpl_key]
                    break

        if not template:
            # 无法匹配模板 — 返回单任务
            return [SubTask(
                parent_task_id=parent_task_id or "",
                task_type="generic",
                description=task,
                business_stage=context.get("business_stage", "全阶段"),
                context=ctx,
                priority=int(context.get("priority", 3)),
            )]

        # 实例化子任务
        task_group_id = parent_task_id or f"group_{uuid.uuid4().hex[:8]}"
        subtasks: List[SubTask] = []

        for idx, step in enumerate(template):
            # 解析依赖关系
            depends_on = []
            for dep_idx in step.get("depends_on_index", []):
                if dep_idx < len(subtasks):
                    depends_on.append(subtasks[dep_idx].task_id)

            st = SubTask(
                parent_task_id=task_group_id,
                task_type=step.get("task_type", "generic"),
                description=step.get("description", ""),
                business_stage=step.get("business_stage", context.get("business_stage", "全阶段")),
                required_skills=step.get("required_skills", []),
                priority=step.get("priority", 5),
                depends_on=depends_on,
                context=ctx,
                timeout=step.get("timeout", 300),
                max_retries=step.get("max_retries", 2),
            )
            subtasks.append(st)

        return subtasks

    async def decompose_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> List[SubTask]:
        """基于事件类型自动选择分解模板

        映射指南事件类型到分解模板:
          certification:expiring → cert_expiry_handling
          compliance:check_started → compliance_pipeline
          regulation:updated → regulation_change_analysis
          order:created → order_fulfillment_check
          gdpr:dsar → gdpr_dsar_handling
          product:listing → product_listing_compliance
        """
        EVENT_TEMPLATE_MAP = {
            "certification:expiring": "cert_expiry_handling",
            "certification:expired": "cert_expiry_handling",
            "compliance:check_started": "compliance_pipeline",
            "compliance:check_failed": "compliance_pipeline",
            "regulation:updated": "regulation_change_analysis",
            "regulation:new": "regulation_change_analysis",
            "order:created": "order_fulfillment_check",
            "order:shipped": "order_fulfillment_check",
            "gdpr:dsar": "gdpr_dsar_handling",
            "product:listing": "product_listing_compliance",
            "product:created": "product_listing_compliance",
        }

        template_key = EVENT_TEMPLATE_MAP.get(event_type)
        context = {**event_data, "event_type": event_type}

        return await self.decompose(
            task=event_type,
            context=context,
            template_key=template_key,
        )

    def list_templates(self) -> List[Dict[str, Any]]:
        """列出所有可用分解模板"""
        result = []
        for key, steps in self._templates.items():
            result.append({
                "key": key,
                "step_count": len(steps),
                "steps": [
                    {"task_type": s.get("task_type"), "description": s.get("description")}
                    for s in steps
                ],
                "source": "builtin" if key in BUILTIN_TEMPLATES else "custom",
            })
        return result

    def get_template(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """获取指定模板"""
        return self._templates.get(key)

    async def register_template(self, key: str, steps: List[Dict[str, Any]], persist: bool = True):
        """注册自定义分解模板

        Args:
            key: 模板key
            steps: 步骤列表
            persist: 是否持久化到文件
        """
        self._templates[key] = steps

        if persist:
            self._custom_dir.mkdir(parents=True, exist_ok=True)
            file_path = self._custom_dir / f"{key}.yaml"
            try:
                import yaml
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.dump({"templates": {key: steps}}, f, allow_unicode=True, default_flow_style=False)
            except ImportError:
                # yaml不可用，存为JSON
                file_path = self._custom_dir / f"{key}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump({"templates": {key: steps}}, f, ensure_ascii=False, indent=2)


# ── 单例管理 ──────────────────────────────────

_decomposer_instance: Optional[TaskDecomposer] = None


def get_task_decomposer() -> TaskDecomposer:
    """获取全局TaskDecomposer单例"""
    global _decomposer_instance
    if _decomposer_instance is None:
        _decomposer_instance = TaskDecomposer()
    return _decomposer_instance
