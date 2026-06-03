"""
Manager Agent — 多Agent调度协调者。

职责:
  1. 接收高层任务并通过TaskDecomposer拆解
  2. 根据Worker注册表为子任务分配最佳Worker
  3. 协调子任务执行顺序（依赖关系、并行度）
  4. 监控任务进度、处理失败重试
  5. 支持群聊式调度（用户可查看和干预）

参考:
  - QwenPaw 多智能体: Manager协调 + Worker隔离 + 群聊式调度
  - Temporal (14k⭐): 确定性执行 + 故障自动重试 + 超时管理
  - 指南§6.15: 四大支柱 MCP/Skill/Cowork/Workflow
  - 开源ERPNext (35.2k⭐): 采购/库存/财务任务分配模式
"""

import uuid
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from app.config import settings
from app.core.task_decomposer import TaskDecomposer, SubTask, get_task_decomposer
from app.core.worker_registry import WorkerRegistry, get_worker_registry
from app.models.schemas import WorkerDefinition, WorkerStatus

DATA_DIR = Path(settings.data_dir)


@dataclass
class AgentMessage:
    """Agent间标准化消息格式"""
    message_id: str = ""
    sender: str = ""              # 发送方 (manager/worker_code/user)
    receiver: str = ""            # 接收方 (manager/worker_code/broadcast)
    message_type: str = ""        # task_assign/task_result/status_update/error/user_intervention
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    conversation_id: str = ""     # 群聊会话ID

    def __post_init__(self):
        if not self.message_id:
            self.message_id = f"msg_{uuid.uuid4().hex[:10]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "conversation_id": self.conversation_id,
        }


@dataclass
class TaskGroup:
    """任务组 — Manager管理的顶层任务单元"""
    group_id: str = ""
    task_description: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    subtasks: List[SubTask] = field(default_factory=list)
    status: str = "pending"       # pending/running/paused/done/failed/cancelled
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_by: str = "system"    # system/user/qa_agent/proactive_engine
    conversation_id: str = ""     # 群聊会话ID
    messages: List[AgentMessage] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.group_id:
            self.group_id = f"group_{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.conversation_id:
            self.conversation_id = f"conv_{self.group_id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "task_description": self.task_description,
            "context": self.context,
            "subtasks": [s.to_dict() for s in self.subtasks],
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_by": self.created_by,
            "conversation_id": self.conversation_id,
            "progress": self._calc_progress(),
        }

    def _calc_progress(self) -> Dict[str, Any]:
        total = len(self.subtasks)
        done = sum(1 for s in self.subtasks if s.status == "done")
        failed = sum(1 for s in self.subtasks if s.status == "failed")
        running = sum(1 for s in self.subtasks if s.status == "running")
        return {
            "total": total,
            "done": done,
            "failed": failed,
            "running": running,
            "pending": total - done - failed - running,
            "percent": round(done / total * 100, 1) if total > 0 else 0,
        }


class ManagerAgent:
    """Manager Agent — 多Agent协调者

    用法:
        manager = ManagerAgent()

        # 提交任务
        group = await manager.submit_task(
            task="product_listing_compliance",
            context={"product_id": "p_led_de_001", "market": "德国"},
            created_by="user"
        )

        # 监控进度
        status = await manager.monitor_progress(group.group_id)

        # 用户干预
        await manager.user_intervention(
            group.group_id,
            action="cancel_subtask",
            subtask_id="task_xxx"
        )

        # 获取所有活跃任务
        active = manager.get_active_groups()

    开源参考:
      - QwenPaw 群聊式调度: 多Agent协作，用户可查看和干预
      - Temporal (14k⭐): 确定性执行 + 故障恢复
      - 指南§6.15: MCP给数据、Skill给规则、Cowork给入口、Workflow给确定性
    """

    def __init__(
        self,
        worker_registry: WorkerRegistry = None,
        task_decomposer: TaskDecomposer = None,
    ):
        self.workers = worker_registry or get_worker_registry()
        self.decomposer = task_decomposer or get_task_decomposer()

        # 活跃任务组
        self._task_groups: Dict[str, TaskGroup] = {}
        # Worker执行状态
        self._worker_tasks: Dict[str, List[str]] = {}  # worker_code -> [task_ids]
        # 消息历史
        self._message_log: List[AgentMessage] = []

    # ── 任务提交与拆解 ──────────────────────────────────

    async def submit_task(
        self,
        task: str,
        context: Dict[str, Any] = None,
        created_by: str = "system",
        template_key: str = None,
    ) -> TaskGroup:
        """提交任务 — 拆解并分配

        Args:
            task: 任务描述或模板key
            context: 任务上下文
            created_by: 创建者 (system/user/qa_agent/proactive_engine)
            template_key: 强制指定分解模板
        Returns:
            TaskGroup
        """
        context = context or {}

        # 1. 拆解任务
        subtasks = await self.decomposer.decompose(
            task=task,
            context=context,
            template_key=template_key,
        )

        # 2. 为每个子任务分配Worker
        for st in subtasks:
            worker = self._find_best_worker(st)
            if worker:
                st.assigned_worker = worker.worker_code

        # 3. 创建任务组
        group = TaskGroup(
            task_description=task,
            context=context,
            subtasks=subtasks,
            created_by=created_by,
        )

        self._task_groups[group.group_id] = group

        # 4. 记录创建消息
        self._record_message(AgentMessage(
            sender="manager",
            receiver="broadcast",
            message_type="task_created",
            payload={
                "group_id": group.group_id,
                "task": task,
                "subtask_count": len(subtasks),
                "assigned_workers": list(set(
                    s.assigned_worker for s in subtasks if s.assigned_worker
                )),
            },
            conversation_id=group.conversation_id,
        ))

        return group

    async def submit_event_task(
        self,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> TaskGroup:
        """基于事件类型提交任务"""
        subtasks = await self.decomposer.decompose_event(event_type, event_data)

        for st in subtasks:
            worker = self._find_best_worker(st)
            if worker:
                st.assigned_worker = worker.worker_code

        group = TaskGroup(
            task_description=f"event:{event_type}",
            context={**event_data, "event_type": event_type},
            subtasks=subtasks,
            created_by="event_bus",
        )

        self._task_groups[group.group_id] = group
        return group

    # ── Worker分配 ──────────────────────────────────

    def _find_best_worker(self, subtask: SubTask) -> Optional[WorkerDefinition]:
        """查找最佳Worker — 基于业务阶段、优先级和负载

        策略:
          1. 按业务阶段匹配Worker
          2. 按优先级排序（数字越小越优先）
          3. 检查Worker当前负载
          4. 回退到全阶段Worker
        """
        stage = subtask.business_stage

        # 尝试按阶段查找
        stage_workers = self.workers.get_workers_by_stage(stage)

        if not stage_workers:
            # 回退到全阶段Worker
            stage_workers = [
                w for w in self.workers.get_all_workers()
                if w.business_stage == "全阶段"
            ]

        if not stage_workers:
            return None

        # 按优先级排序
        stage_workers.sort(key=lambda w: w.priority)

        # 选择负载最低的Worker
        best = stage_workers[0]
        min_load = len(self._worker_tasks.get(best.worker_code, []))

        for w in stage_workers[1:]:
            load = len(self._worker_tasks.get(w.worker_code, []))
            if load < min_load:
                best = w
                min_load = load

        return best

    # ── 任务执行 ──────────────────────────────────

    async def execute_group(self, group_id: str) -> Dict[str, Any]:
        """执行任务组 — 按依赖关系顺序执行

        执行策略:
          1. 识别无依赖的子任务，并行启动
          2. 等待完成后，解锁依赖任务
          3. 支持失败重试（max_retries次）
          4. 失败子任务不阻塞无关子任务
        """
        group = self._task_groups.get(group_id)
        if not group:
            return {"error": f"Task group {group_id} not found"}

        group.status = "running"
        group.started_at = datetime.now(timezone.utc).isoformat()

        self._record_message(AgentMessage(
            sender="manager",
            receiver="broadcast",
            message_type="execution_started",
            payload={"group_id": group_id, "total_subtasks": len(group.subtasks)},
            conversation_id=group.conversation_id,
        ))

        # 构建执行顺序
        executed = set()
        max_iterations = len(group.subtasks) * 3  # 防止死循环
        iteration = 0

        while len(executed) < len(group.subtasks) and iteration < max_iterations:
            iteration += 1
            ready_tasks = []

            for st in group.subtasks:
                if st.task_id in executed:
                    continue
                if st.status == "cancelled":
                    executed.add(st.task_id)
                    continue
                # 检查依赖是否满足
                deps_satisfied = all(dep_id in executed for dep_id in st.depends_on)
                if deps_satisfied:
                    ready_tasks.append(st)

            if not ready_tasks:
                break  # 没有可执行的任务

            # 并行执行就绪任务
            tasks_results = await asyncio.gather(
                *[self._execute_subtask(group, st) for st in ready_tasks],
                return_exceptions=True,
            )

            for st, result in zip(ready_tasks, tasks_results):
                executed.add(st.task_id)
                if isinstance(result, Exception):
                    st.status = "failed"
                    st.error = str(result)
                else:
                    st.status = result.get("status", "done")
                    st.result = result

        # 汇总结果
        group.status = self._determine_group_status(group)
        group.completed_at = datetime.now(timezone.utc).isoformat()

        self._record_message(AgentMessage(
            sender="manager",
            receiver="broadcast",
            message_type="execution_completed",
            payload={
                "group_id": group_id,
                "status": group.status,
                "progress": group._calc_progress(),
            },
            conversation_id=group.conversation_id,
        ))

        return group.to_dict()

    async def _execute_subtask(self, group: TaskGroup, subtask: SubTask) -> Dict[str, Any]:
        """执行单个子任务

        实际执行流程中会调用对应的Worker Agent或Skill。
        当前为框架实现，预留与AstraAssistant的集成点。
        """
        subtask.status = "running"
        subtask.started_at = datetime.now(timezone.utc).isoformat()

        # 注册Worker负载
        worker_code = subtask.assigned_worker
        if worker_code:
            self._worker_tasks.setdefault(worker_code, []).append(subtask.task_id)
            self._record_message(AgentMessage(
                sender="manager",
                receiver=worker_code,
                message_type="task_assign",
                payload=subtask.to_dict(),
                conversation_id=group.conversation_id,
            ))

        try:
            # 执行Worker任务
            result = await self._run_worker(subtask)

            subtask.status = "done"
            subtask.completed_at = datetime.now(timezone.utc).isoformat()

            # 释放Worker负载
            if worker_code and worker_code in self._worker_tasks:
                try:
                    self._worker_tasks[worker_code].remove(subtask.task_id)
                except ValueError:
                    pass

            self._record_message(AgentMessage(
                sender=worker_code or "system",
                receiver="manager",
                message_type="task_result",
                payload={"task_id": subtask.task_id, "status": "done", "result": result},
                conversation_id=group.conversation_id,
            ))

            return {"status": "done", "result": result}

        except Exception as e:
            subtask.status = "failed"
            subtask.error = str(e)
            subtask.completed_at = datetime.now(timezone.utc).isoformat()

            # 释放Worker负载
            if worker_code and worker_code in self._worker_tasks:
                try:
                    self._worker_tasks[worker_code].remove(subtask.task_id)
                except ValueError:
                    pass

            # 重试逻辑
            if subtask.retry_count < subtask.max_retries:
                subtask.retry_count += 1
                subtask.status = "pending"
                subtask.started_at = None
                subtask.completed_at = None
                subtask.error = None
                return await self._execute_subtask(group, subtask)

            self._record_message(AgentMessage(
                sender=worker_code or "system",
                receiver="manager",
                message_type="error",
                payload={"task_id": subtask.task_id, "error": str(e)},
                conversation_id=group.conversation_id,
            ))

            return {"status": "failed", "error": str(e)}

    async def _run_worker(self, subtask: SubTask) -> Dict[str, Any]:
        """执行Worker任务

        执行策略（按优先级）:
          1. SDK 执行: 如果 Worker 的 sdk_enabled=True，使用 Claude Agent SDK
             （通过 AstraAssistant.run_as_agent() 或 run_task()）
          2. Skill 执行: 回退到 SkillExecutor 映射执行
        """
        worker_code = subtask.assigned_worker

        # 优先尝试 SDK 执行
        if worker_code:
            worker_def = self.workers.get_worker(worker_code)
            if worker_def and worker_def.sdk_enabled:
                try:
                    from app.services.astra_assistant import AstraAssistant, check_sdk

                    if check_sdk():
                        assistant = AstraAssistant()
                        sdk_agent_id = worker_def.sdk_agent_id
                        task_context = {
                            "task_id": subtask.task_id,
                            "task_type": subtask.task_type,
                            "business_stage": subtask.business_stage,
                            "description": subtask.description,
                            **(subtask.context or {}),
                        }

                        if sdk_agent_id:
                            # 方式 A: 以 Agent 身份执行
                            sdk_result = await assistant.run_as_agent(
                                agent_id=sdk_agent_id,
                                message=(
                                    f"分配任务: {subtask.description}\n"
                                    f"任务类型: {subtask.task_type}\n"
                                    f"上下文: {json.dumps(task_context, ensure_ascii=False)}"
                                ),
                            )
                            raw_response = sdk_result.get("response", "") or json.dumps(sdk_result, ensure_ascii=False)
                        else:
                            # 方式 B: 使用 run_task()
                            sdk_result = await assistant.run_task(
                                prompt_name=f"manager_{subtask.task_type}",
                                context=task_context,
                            )
                            if isinstance(sdk_result, dict):
                                raw_response = (
                                    sdk_result.get("raw_text", "") or
                                    sdk_result.get("response", "") or
                                    json.dumps(sdk_result, ensure_ascii=False)
                                )
                            else:
                                raw_response = str(sdk_result)

                        logger.info(
                            "ManagerAgent: Worker '%s' SDK 执行 '%s' 完成",
                            worker_code, subtask.task_type,
                        )
                        return {
                            "worker": worker_code,
                            "task_type": subtask.task_type,
                            "sdk_executed": True,
                            "status": "completed",
                            "response": raw_response[:2000],
                            "executed_at": datetime.now(timezone.utc).isoformat(),
                        }

                except Exception as e:
                    logger.warning(
                        "ManagerAgent: Worker '%s' SDK 执行失败 (%s), 回退到 Skill",
                        worker_code, e,
                    )

        # 回退: SkillExecutor 执行
        from app.core.skill_registry import get_skill_executor
        executor = get_skill_executor()

        skill_name = self._map_task_to_skill(subtask)
        args = dict(subtask.context or {})
        args["task_id"] = subtask.task_id
        args["action"] = subtask.task_type

        try:
            result = await executor.execute(skill_name, args, timeout=60)
            result["worker"] = worker_code
            result["task_type"] = subtask.task_type
            result["sdk_executed"] = False
            return result
        except Exception as e:
            return {
                "worker": worker_code,
                "task_type": subtask.task_type,
                "skill": skill_name,
                "status": "failed",
                "sdk_executed": False,
                "error": str(e),
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }

    def _map_task_to_skill(self, subtask: SubTask) -> str:
        """根据子任务类型映射到对应的 Skill 名称"""
        mapping = {
            "compliance_check": "shopify-dev",
            "product_listing": "shopify-admin",
            "order_fetch": "shopify-admin",
            "tax_config": "shopify-admin",
            "customer_notify": "shopify-customer",
            "risk_scan": "skill-vetter",
            "web_search": "web-search",
            "summarize": "summarize",
        }
        return mapping.get(subtask.task_type, "summarize")

    # ── 进度监控 ──────────────────────────────────

    async def monitor_progress(self, group_id: str) -> Dict[str, Any]:
        """监控任务组进度"""
        group = self._task_groups.get(group_id)
        if not group:
            return {"error": f"Task group {group_id} not found"}
        return group.to_dict()

    def get_active_groups(self) -> List[Dict[str, Any]]:
        """获取所有活跃任务组"""
        return [
            g.to_dict() for g in self._task_groups.values()
            if g.status in ("pending", "running", "paused")
        ]

    def get_all_groups(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取全部任务组（最近N个）"""
        groups = sorted(
            self._task_groups.values(),
            key=lambda g: g.created_at,
            reverse=True,
        )
        return [g.to_dict() for g in groups[:limit]]

    def get_worker_status(self) -> List[Dict[str, Any]]:
        """获取所有Worker状态"""
        result = []
        for worker in self.workers.get_all_workers():
            active_tasks = self._worker_tasks.get(worker.worker_code, [])
            ws = self.workers.get_worker_status(worker.worker_code)
            result.append({
                "worker_code": worker.worker_code,
                "worker_name": worker.worker_name,
                "business_stage": worker.business_stage,
                "status": ws.status if ws else "idle",
                "active_task_count": len(active_tasks),
                "active_tasks": active_tasks,
            })
        return result

    # ── 用户干预 ──────────────────────────────────

    async def user_intervention(
        self,
        group_id: str,
        action: str,
        subtask_id: str = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        """用户干预任务执行

        Args:
            group_id: 任务组ID
            action: cancel_group/cancel_subtask/pause/resume/retry
            subtask_id: 子任务ID（cancel_subtask/retry时必填）
            reason: 干预原因
        """
        group = self._task_groups.get(group_id)
        if not group:
            return {"error": f"Task group {group_id} not found"}

        self._record_message(AgentMessage(
            sender="user",
            receiver="manager",
            message_type="user_intervention",
            payload={
                "group_id": group_id,
                "action": action,
                "subtask_id": subtask_id,
                "reason": reason,
            },
            conversation_id=group.conversation_id,
        ))

        if action == "cancel_group":
            group.status = "cancelled"
            for st in group.subtasks:
                if st.status in ("pending", "running"):
                    st.status = "cancelled"
            return {"status": "cancelled", "group_id": group_id}

        elif action == "cancel_subtask" and subtask_id:
            for st in group.subtasks:
                if st.task_id == subtask_id:
                    st.status = "cancelled"
                    return {"status": "cancelled", "subtask_id": subtask_id}
            return {"error": f"Subtask {subtask_id} not found"}

        elif action == "pause":
            group.status = "paused"
            return {"status": "paused", "group_id": group_id}

        elif action == "resume":
            group.status = "running"
            return {"status": "resumed", "group_id": group_id}

        elif action == "retry" and subtask_id:
            for st in group.subtasks:
                if st.task_id == subtask_id and st.status == "failed":
                    st.status = "pending"
                    st.retry_count = 0
                    st.error = None
                    return {"status": "retry_scheduled", "subtask_id": subtask_id}
            return {"error": f"Subtask {subtask_id} not found or not failed"}

        return {"error": f"Unknown action: {action}"}

    # ── 消息与日志 ──────────────────────────────────

    def _record_message(self, msg: AgentMessage):
        """记录消息"""
        self._message_log.append(msg)
        # 同时追加到任务组的消息列表
        if msg.conversation_id:
            for g in self._task_groups.values():
                if g.conversation_id == msg.conversation_id:
                    g.messages.append(msg)
                    break

    def get_conversation(self, group_id: str) -> List[Dict[str, Any]]:
        """获取任务组的群聊消息历史"""
        group = self._task_groups.get(group_id)
        if not group:
            return []
        return [m.to_dict() for m in group.messages]

    # ── 辅助 ──────────────────────────────────

    def _determine_group_status(self, group: TaskGroup) -> str:
        """判断任务组最终状态"""
        statuses = [s.status for s in group.subtasks]
        if all(s == "done" for s in statuses):
            return "done"
        if any(s == "failed" for s in statuses):
            return "failed"
        if all(s == "cancelled" for s in statuses):
            return "cancelled"
        return "done"  # 混合状态视为完成

    def get_stats(self) -> Dict[str, Any]:
        """获取Manager统计信息"""
        groups = list(self._task_groups.values())
        return {
            "total_groups": len(groups),
            "active_groups": len([g for g in groups if g.status in ("pending", "running")]),
            "completed_groups": len([g for g in groups if g.status == "done"]),
            "failed_groups": len([g for g in groups if g.status == "failed"]),
            "total_subtasks": sum(len(g.subtasks) for g in groups),
            "total_messages": len(self._message_log),
            "worker_load": {
                code: len(tasks) for code, tasks in self._worker_tasks.items()
            },
            "templates_available": len(self.decomposer.list_templates()),
        }


# ── 单例管理 ──────────────────────────────────

_manager_instance: Optional[ManagerAgent] = None


def get_manager_agent() -> ManagerAgent:
    """获取全局ManagerAgent单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ManagerAgent()
    return _manager_instance
