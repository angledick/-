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

配置源:
  - data/config/workflows/*.yaml — 分解模板（每个模板一个文件）
  - data/config/workflows/_event_map.yaml — 事件类型→模板映射
"""

import uuid
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

import yaml

from app.config import settings

logger = logging.getLogger(__name__)

DATA_DIR = Path(settings.data_dir)
_WORKFLOWS_DIR = DATA_DIR / "config" / "workflows"


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


# ── 配置加载 ──────────────────────────────────

def _load_builtin_templates() -> Dict[str, List[Dict[str, Any]]]:
    """从 data/config/workflows/*.yaml 加载所有分解模板。

    每个 YAML 文件格式:
        templates:
          template_key:
            - task_type: ...
              description: ...
              ...

    跳过以 _ 开头的文件（如 _event_map.yaml）。
    """
    templates: Dict[str, List[Dict[str, Any]]] = {}
    if not _WORKFLOWS_DIR.exists():
        return templates

    for yaml_file in sorted(_WORKFLOWS_DIR.glob("*.yaml")):
        if yaml_file.stem.startswith("_"):
            continue
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "templates" in data:
                for tpl_key, tpl_steps in data["templates"].items():
                    if isinstance(tpl_steps, list):
                        templates[tpl_key] = tpl_steps
        except Exception:
            pass
    return templates


def _load_event_template_map() -> Dict[str, str]:
    """从 data/config/workflows/_event_map.yaml 加载事件→模板映射"""
    map_path = _WORKFLOWS_DIR / "_event_map.yaml"
    if map_path.exists():
        try:
            data = yaml.safe_load(map_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "event_template_map" in data:
                return data["event_template_map"] or {}
        except Exception as e:
            logger.warning("事件模板映射文件加载失败: %s", e)
    return {}


# 模块加载时读取配置
BUILTIN_TEMPLATES: Dict[str, List[Dict[str, Any]]] = _load_builtin_templates()
EVENT_TEMPLATE_MAP: Dict[str, str] = _load_event_template_map()


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
        self._builtin_keys = set(BUILTIN_TEMPLATES.keys())
        self._custom_dir = Path(custom_templates_dir) if custom_templates_dir else (
            DATA_DIR / "config" / "workflows"
        )
        self._load_custom_templates()

    def _load_custom_templates(self):
        """从配置文件加载自定义分解模板（覆盖同名内置模板）"""
        if not self._custom_dir.exists():
            return

        for yaml_file in self._custom_dir.glob("*.yaml"):
            # 跳过 _event_map.yaml 和内置模板文件（已在模块加载时读取）
            if yaml_file.stem.startswith("_"):
                continue
            # 内置模板已在 __init__ 时加载，这里只加载非内置的额外模板
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "templates" in data:
                    for tpl_key, tpl_steps in data["templates"].items():
                        if isinstance(tpl_steps, list) and tpl_key not in self._builtin_keys:
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
                "source": "builtin" if key in self._builtin_keys else "custom",
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
