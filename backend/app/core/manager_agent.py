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
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from app.config import settings
from app.core.task_decomposer import TaskDecomposer, SubTask, get_task_decomposer
from app.core.worker_registry import WorkerRegistry, get_worker_registry
from app.models.schemas import WorkerDefinition, WorkerStatus

logger = logging.getLogger(__name__)

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
        """基于事件类型提交任务

        危险事件自动暂停: 如果事件定义的 severity 为 high/critical，
        任务组自动设为 pending_approval，等待人工在飞书回复处理意见后恢复。
        """
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

        # ── 危险事件自动暂停 ──
        event_def = self._event_registry.get_event(event_type) if self._event_registry else None
        if event_def and event_def.severity in ("high", "critical"):
            group.status = "pending_approval"
            group.context["pause_reason"] = f"危险事件 [{event_type}] severity={event_def.severity}"
            logger.info(
                "ManagerAgent: 危险事件自动暂停 group=%s event=%s severity=%s",
                group.group_id, event_type, event_def.severity,
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

        # ── 完成后通知飞书（如果有 chat_id） ──
        chat_id = group.context.get("chat_id", "") if isinstance(group.context, dict) else ""
        if chat_id:
            await self._send_feishu_notification(chat_id, (
                f"✅ 任务执行完成\n"
                f"任务: {group.task_description}\n"
                f"状态: {group.status}\n"
                f"子任务: {group._calc_progress()}"
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
                        # 注入事件分配的 tools/skills 到 task_context
                        event_tools = (subtask.context or {}).get("event_tools", [])
                        event_skills = (subtask.context or {}).get("event_skills", [])
                        agent_action = (subtask.context or {}).get("agent_action", "")
                        task_context = {
                            "task_id": subtask.task_id,
                            "task_type": subtask.task_type,
                            "business_stage": subtask.business_stage,
                            "description": subtask.description,
                            "tools": event_tools,
                            "skills": event_skills or subtask.required_skills,
                            "agent_action": agent_action,
                            **(subtask.context or {}),
                        }

                        if sdk_agent_id:
                            # 方式 A: 以 Agent 身份执行
                            message_parts = [
                                f"分配任务: {subtask.description}",
                                f"任务类型: {subtask.task_type}",
                            ]
                            if agent_action:
                                message_parts.append(f"执行指令: {agent_action}")
                            if event_tools:
                                message_parts.append(f"可用工具: {', '.join(event_tools)}")
                            if event_skills or subtask.required_skills:
                                skills = event_skills or subtask.required_skills
                                message_parts.append(f"所需技能: {', '.join(skills)}")
                            message_parts.append(f"上下文: {json.dumps(task_context, ensure_ascii=False)}")
                            sdk_result = await assistant.run_as_agent(
                                agent_id=sdk_agent_id,
                                message="\n".join(message_parts),
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

        # 优先从子任务的 required_skills / event_skills 中获取技能名
        event_skills = (subtask.context or {}).get("event_skills", [])
        if event_skills:
            skill_name = event_skills[0]
        elif subtask.required_skills:
            skill_name = subtask.required_skills[0]
        else:
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

    def get_pending_groups(self) -> List[Dict[str, Any]]:
        """获取等待人工决策的任务组（危险事件闭环）。

        返回 status == 'pending_approval' 的任务组列表。
        """
        return [
            g.to_dict() for g in self._task_groups.values()
            if g.status == "pending_approval"
        ]

    async def resume_pending_group(self, group_id: str, instructions: str) -> bool:
        """恢复等待人工决策的任务组（危险事件闭环）。

        用户在飞书回复处理意见后调用，恢复任务组执行。
        """
        group = self._task_groups.get(group_id)
        if not group:
            logger.warning("ManagerAgent: 恢复失败，任务组不存在: %s", group_id)
            return False

        group.status = "running"
        # 将处理意见注入任务组上下文
        if isinstance(group.context, dict):
            group.context["human_instructions"] = instructions

        logger.info(
            "ManagerAgent: 任务组 %s 已恢复执行，处理意见: %s",
            group_id, instructions[:50],
        )

        # 异步执行任务组
        import asyncio
        asyncio.create_task(self.execute_group(group_id))
        return True

    async def pause_group_for_approval(self, group_id: str, reason: str = "") -> bool:
        """暂停任务组等待人工审批（危险事件闭环）。

        高风险事件触发后，暂停执行并通知飞书等待处理意见。
        """
        group = self._task_groups.get(group_id)
        if not group:
            return False

        group.status = "pending_approval"
        if isinstance(group.context, dict):
            group.context["pause_reason"] = reason

        logger.info(
            "ManagerAgent: 任务组 %s 已暂停等待人工审批，原因: %s",
            group_id, reason[:100],
        )
        return True

    async def _send_feishu_notification(self, chat_id: str, text: str):
        """通过 lark-cli 发送飞书通知（异步，不阻塞主流程）。

        使用 Node.js 直调模式绕过 cmd.exe，支持多行文本。
        """
        def _sync():
            import subprocess as _sp
            from pathlib import Path as _P
            npm_root = _P.home() / "AppData" / "Roaming" / "npm"
            entry = npm_root / "node_modules" / "@larksuite" / "cli" / "scripts" / "run.js"
            if entry.exists():
                cmd = ["node", str(entry)]
            else:
                import shutil
                found = shutil.which("lark-cli")
                cmd = ["cmd", "/C", found] if found and found.endswith(".cmd") else ([found] if found else ["lark-cli"])
            return _sp.run(
                cmd + [
                    "im", "+messages-send",
                    "--as", "bot",
                    "--chat-id", chat_id,
                    "--text", text,
                ],
                capture_output=True, encoding="utf-8", timeout=15,
            )

        try:
            proc = await asyncio.to_thread(_sync)
            logger.info(
                "飞书通知已发送: chat=%s rc=%d stdout=%.80s",
                chat_id, proc.returncode, proc.stdout.strip(),
            )
        except Exception as e:
            logger.warning("飞书通知发送失败: chat=%s err=%s", chat_id, e)

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

    # ── 事件驱动中枢 ─────────────────────────────────

    @property
    def _event_registry(self):
        """懒加载事件注册表"""
        if not hasattr(self, "__event_registry") or self.__event_registry is None:
            try:
                from app.core.event_bus import get_event_registry
                self.__event_registry = get_event_registry()
            except Exception:
                self.__event_registry = None
        return self.__event_registry

    async def on_event(self, event):
        """事件驱动中枢 — 接收所有事件，路由到 WS推送 / Worker调度 / 指标更新

        注册方式: bus.on_all(manager.on_event)
        参数 event: EventRecord (来自 event_bus.publish)
        """
        try:
            await self._route_to_websocket(event)
        except Exception as e:
            logger.error("ManagerAgent._route_to_websocket 失败: event=%s err=%s", event.type, e)

        try:
            await self._route_to_worker(event)
        except Exception as e:
            logger.error("ManagerAgent._route_to_worker 失败: event=%s err=%s", event.type, e)

        try:
            await self._route_to_product_metrics(event)
        except Exception as e:
            logger.error("ManagerAgent._route_to_product_metrics 失败: event=%s err=%s", event.type, e)

        try:
            await self._route_to_custom_metrics(event)
        except Exception as e:
            logger.error("ManagerAgent._route_to_custom_metrics 失败: event=%s err=%s", event.type, e)

    async def _route_to_websocket(self, event):
        """事件 → WS 消息推送

        映射规则:
          session:created/deleted → {type:"session_update", payload:{}}
          message:created         → {type:"new_message", payload:{session_id, message}}
          severity high/critical  → {type:"alert", payload:{...}}
          scan:*                  → {type:"scan_update", payload:{...}}
        """
        from app.services.ws_manager import ws_manager

        event_type = event.type
        event_data = event.data or {}
        user_id = event_data.get("user_id")

        # session 事件
        if event_type in ("session:created", "session:deleted"):
            if user_id:
                await ws_manager.send_to_user(user_id, {
                    "type": "session_update",
                    "payload": {},
                })
            return

        # message 事件
        if event_type == "message:created":
            if user_id:
                await ws_manager.send_to_user(user_id, {
                    "type": "new_message",
                    "payload": {
                        "session_id": event_data.get("session_id", ""),
                        "message": {
                            "id": event_data.get("message_id", ""),
                            "role": "assistant",
                            "content": event_data.get("content_preview", ""),
                            "created_at": event.created_at,
                        },
                    },
                })
            return

        # scan 事件
        if event_type.startswith("scan:"):
            if user_id:
                await ws_manager.send_to_user(user_id, {
                    "type": "scan_update",
                    "payload": {
                        "scan_id": event_data.get("scan_id", event.id),
                        "status": event_data.get("status", "running"),
                        "progress": event_data.get("progress", 0),
                        "total": event_data.get("total", 0),
                        "current_item": event_data.get("current_item", ""),
                    },
                })
            return

        # risk 事件或高严重级别 → alert
        if event_type.startswith("risk:") or event.severity in ("high", "critical"):
            target_user = user_id or "default"
            await ws_manager.send_alert(target_user, {
                "alert_id": event.id,
                "severity": event.severity,
                "title": f"[{event_type}] {event.source}",
                "description": str(event_data)[:500] if event_data else event.type,
                "affected_markets": event_data.get("affected_markets", []),
                "created_at": event.created_at,
            })

    async def _route_to_worker(self, event):
        """事件 → Worker 调度（SDK 底座）

        从事件定义查找 related_worker，分配 tools/skills/context 后执行。
        危险事件（severity=high/critical）自动暂停等待人工审批。
        """
        event_def = self._event_registry.get_event(event.type) if self._event_registry else None
        if not event_def or not event_def.related_worker:
            return

        logger.info(
            "ManagerAgent: 事件 '%s' 触发 Worker '%s'",
            event.type, event_def.related_worker,
        )

        # 通过 submit_event_task 拆解为子任务
        group = await self.submit_event_task(event.type, event.data or {})

        # 为每个子任务注入事件定义中的 worker/skills/tools/agent_action
        # （覆盖 submit_event_task 中的自动分配，强制使用事件定义指定的 Worker）
        for st in group.subtasks:
            st.assigned_worker = event_def.related_worker
            st.required_skills = event_def.skills or st.required_skills
            st.context["event_tools"] = event_def.tools or []
            st.context["event_skills"] = event_def.skills or []
            st.context["agent_action"] = event_def.agent_action or ""

        # ── 危险事件：暂停并通知飞书，等待人工审批 ──
        if group.status == "pending_approval":
            event_data = event.data or {}
            chat_id = event_data.get("chat_id", "")
            if chat_id:
                await self._send_feishu_notification(chat_id, (
                    f"⚠️ 危险事件需要人工审批\n"
                    f"事件: {event.type}\n"
                    f"严重级别: {event_def.severity}\n"
                    f"任务组: {group.group_id}\n"
                    f"原因: {group.context.get('pause_reason', '')}\n\n"
                    f"请回复处理意见（如：执行/取消）"
                ))
            logger.info(
                "ManagerAgent: 危险事件已暂停等待审批 group=%s event=%s",
                group.group_id, event.type,
            )
            return

        # 正常执行任务组
        await self.execute_group(group.group_id)

    async def _route_to_product_metrics(self, event):
        """事件 → 产品指标更新

        传输: event.product_id + event.type + event.created_at
        目标: data/products/{product_id}/metrics/metrics.json
        更新: event_count 递增, last_event_type, last_event_time
        """
        if not event.product_id:
            return

        metrics_path = DATA_DIR / "products" / event.product_id / "metrics" / "metrics.json"
        metrics_path.parent.mkdir(parents=True, exist_ok=True)

        metrics = {}
        if metrics_path.exists():
            try:
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.error("产品指标文件加载失败 product=%s: %s", event.product_id, e)

        # 更新指标
        event_count = metrics.get("event_count", 0) + 1
        metrics["event_count"] = event_count
        metrics["last_event_type"] = event.type
        metrics["last_event_time"] = event.created_at
        metrics["snapshot_time"] = datetime.now(timezone.utc).isoformat()

        # 按事件类型分组计数
        type_counts = metrics.get("event_type_counts", {})
        type_counts[event.type] = type_counts.get(event.type, 0) + 1
        metrics["event_type_counts"] = type_counts

        metrics_path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def _route_to_custom_metrics(self, event):
        """事件 → 自定义指标更新

        传输: 读取 data/global/metrics/custom_metrics.json 中所有指标
        匹配: 每个指标的 scope 与 event.data 比对
        计算: 匹配时按 formula 重算当前值
        告警: 超阈值时通过 WS 推送 alert
        """
        from app.services.ws_manager import ws_manager

        custom_path = DATA_DIR / "global" / "metrics" / "custom_metrics.json"
        if not custom_path.exists():
            return

        try:
            data = json.loads(custom_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("自定义指标文件加载失败: %s", e)
            return

        metrics = data.get("metrics", [])
        event_data = event.data or {}

        for metric in metrics:
            scope = metric.get("scope", {})
            if not self._scope_matches(scope, event_data):
                continue

            # 匹配，重新计算当前值
            current_value = self._evaluate_formula(metric.get("formula", ""), event_data, metric)
            metric["current_value"] = current_value
            metric["last_updated"] = event.created_at

            # 检查阈值
            threshold_critical = metric.get("threshold_critical", 0)
            threshold_warning = metric.get("threshold_warning", 0)

            if threshold_critical and current_value >= threshold_critical:
                if metric.get("notify_on_critical", True):
                    await ws_manager.send_to_user("default", {
                        "type": "alert",
                        "payload": {
                            "alert_id": f"metric_{metric.get('key', '')}_critical",
                            "severity": "critical",
                            "title": f"指标预警: {metric.get('name', metric.get('key'))}",
                            "description": f"当前值 {current_value} 超过临界阈值 {threshold_critical}",
                            "created_at": event.created_at,
                        },
                    })
                # 阈值超限 → 发布事件触发 Worker 调度（事件-指标-Worker闭环）
                try:
                    from app.core.event_bus import get_event_bus
                    bus = get_event_bus()
                    await bus.publish_raw({
                        "type": "metric:threshold_exceeded",
                        "source": "manager_agent",
                        "data": {
                            "metric_key": metric.get("key", ""),
                            "metric_name": metric.get("name", ""),
                            "current_value": current_value,
                            "threshold_critical": threshold_critical,
                            "severity": "critical",
                        },
                        "severity": "critical",
                        "product_id": event.product_id,
                    })
                except Exception as e:
                    logger.error("指标阈值事件发布失败: %s", e)

            elif threshold_warning and current_value >= threshold_warning:
                if metric.get("notify_on_warning", True):
                    await ws_manager.send_to_user("default", {
                        "type": "alert",
                        "payload": {
                            "alert_id": f"metric_{metric.get('key', '')}_warning",
                            "severity": "medium",
                            "title": f"指标警告: {metric.get('name', metric.get('key'))}",
                            "description": f"当前值 {current_value} 超过警告阈值 {threshold_warning}",
                            "created_at": event.created_at,
                        },
                    })
                # 警告阈值超限 → 发布事件
                try:
                    from app.core.event_bus import get_event_bus
                    bus = get_event_bus()
                    await bus.publish_raw({
                        "type": "metric:threshold_exceeded",
                        "source": "manager_agent",
                        "data": {
                            "metric_key": metric.get("key", ""),
                            "metric_name": metric.get("name", ""),
                            "current_value": current_value,
                            "threshold_warning": threshold_warning,
                            "severity": "warning",
                        },
                        "severity": "medium",
                        "product_id": event.product_id,
                    })
                except Exception as e:
                    logger.error("指标阈值事件发布失败: %s", e)

        # 写回文件
        data["metrics"] = metrics
        custom_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _scope_matches(self, scope: Dict, event_data: Dict) -> bool:
        """检查指标的 scope 是否与事件数据匹配"""
        if not scope:
            return True  # 空 scope 匹配所有事件
        for key, value in scope.items():
            # 支持嵌套字段匹配
            event_value = event_data.get(key)
            if event_value is None:
                # 尝试从 market/country 字段匹配
                if key == "market":
                    event_value = event_data.get("country") or event_data.get("target_country")
                elif key == "country":
                    event_value = event_data.get("market")
            if event_value is None:
                return False
            # 支持大小写不敏感匹配
            if isinstance(value, str) and isinstance(event_value, str):
                if value.upper() != event_value.upper():
                    return False
            elif value != event_value:
                return False
        return True

    def _evaluate_formula(self, formula: str, event_data: Dict, metric: Dict) -> float:
        """简单公式求值（支持 count 和 sum 类公式）

        支持格式:
          count(risk>N)  — 风险计数
          count(*)       — 事件计数
          sum(field)     — 字段求和
        """
        current = metric.get("current_value", 0)
        try:
            if not formula:
                return current + 1

            if formula.startswith("count("):
                inner = formula[6:-1].strip()
                if inner == "*":
                    return current + 1
                # count(risk>N) 格式
                import re
                m = re.match(r'(\w+)\s*([><=!]+)\s*(\d+)', inner)
                if m:
                    field, op, threshold = m.group(1), m.group(2), float(m.group(3))
                    val = float(event_data.get(field, 0))
                    if op == ">" and val > threshold:
                        return current + 1
                    elif op == ">=" and val >= threshold:
                        return current + 1
                    elif op == "<" and val < threshold:
                        return current + 1
                    elif op == "==" and val == threshold:
                        return current + 1
                return current

            elif formula.startswith("sum("):
                field = formula[4:-1].strip()
                return current + float(event_data.get(field, 0))

            return current + 1
        except Exception as e:
            logger.error("指标公式求值失败 formula=%s: %s", formula, e)
            return current


# ── 单例管理 ──────────────────────────────────

_manager_instance: Optional[ManagerAgent] = None


def get_manager_agent() -> ManagerAgent:
    """获取全局ManagerAgent单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ManagerAgent()
    return _manager_instance
