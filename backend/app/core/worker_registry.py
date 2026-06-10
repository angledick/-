"""
Worker注册表 (WorkerRegistry) — 配置文件驱动的Worker管理。

职责：
  1. 从 data/workers/ 目录的Markdown文件（YAML front-matter格式）加载Worker定义
  2. 支持QAAgent和用户动态注册/修改/删除Worker
  3. 按业务阶段查询可用Worker
  4. Worker运行时状态追踪

存储:
  - 配置: data/workers/builtin/*.md
  - 归档: data/workers/_archive/
"""

import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import yaml

from app.config import settings
from app.models.schemas import WorkerDefinition, WorkerStatus

logger = logging.getLogger(__name__)

DATA_DIR = Path(settings.data_dir)


class WorkerRegistry:
    """Worker注册表 - 配置文件驱动

    用法:
        registry = WorkerRegistry()

        # 查询Worker
        worker = registry.get_worker("compliance_worker")
        stage_workers = registry.get_workers_by_stage("阶段3")

        # QAAgent管理
        await registry.register_worker(new_worker_def)
        await registry.delete_worker("old_worker")
    """

    def __init__(self, config_dir: str = None):
        self.config_dir = Path(config_dir or (DATA_DIR / "workers" / "builtin"))
        self._workers: Dict[str, WorkerDefinition] = {}
        self._runtime_status: Dict[str, WorkerStatus] = {}
        self._load_all_workers()

    def _load_all_workers(self):
        """加载所有Worker配置。配置目录必须存在。"""
        if not self.config_dir.exists():
            raise FileNotFoundError(
                f"Worker配置目录不存在: {self.config_dir}\n"
                "请确保 data/workers/builtin/ 已创建"
            )
        for md_file in self.config_dir.glob("*.md"):
            if md_file.name.startswith("_") or md_file.name == "README.md":
                continue
            self._load_workers_from_file(md_file)
        if not self._workers:
            raise ValueError(f"Worker配置目录中未找到有效定义: {self.config_dir}")

    def _load_workers_from_file(self, file_path: Path):
        """从Markdown文件加载Worker定义（支持 YAML front-matter 和表格两种格式）。"""
        content = file_path.read_text(encoding="utf-8")
        # YAML front-matter 解析
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if match:
            front_matter = yaml.safe_load(match.group(1))
            if front_matter and isinstance(front_matter, dict):
                workers_data = front_matter.get("workers", [])
                if workers_data:
                    for w in workers_data:
                        w["config_file"] = str(file_path)
                        worker_def = self._create_worker_from_dict(w)
                        if worker_def:
                            self._workers[worker_def.worker_code] = worker_def
                    return
        # 表格解析
        workers = self._parse_worker_table(content)
        for worker_def in workers:
            worker_def.config_file = str(file_path)
            self._workers[worker_def.worker_code] = worker_def

    def _create_worker_from_dict(self, data: dict) -> Optional[WorkerDefinition]:
        """从 YAML front-matter 字典创建 Worker 定义。"""
        worker_code = data.get("worker_code", "")
        if not worker_code:
            return None
        return WorkerDefinition(
            worker_code=worker_code,
            worker_name=data.get("worker_name", ""),
            business_stage=data.get("business_stage", ""),
            description=data.get("description", ""),
            available_skills=data.get("available_skills", []),
            priority=data.get("priority", 5),
            timeout=data.get("timeout", 300),
            config_file=data.get("config_file"),
        )

    def _parse_worker_table(self, content: str) -> List[WorkerDefinition]:
        """解析Markdown表格中的Worker定义"""
        workers = []
        lines = content.split("\n")
        in_table = False
        headers = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|") if c.strip()]

                if not in_table:
                    headers = cells
                    in_table = True
                elif cells and "---" not in cells[0]:
                    worker = self._create_worker_from_row(headers, cells)
                    if worker:
                        workers.append(worker)
            else:
                in_table = False
                headers = []

        return workers

    def _create_worker_from_row(self, headers: List[str], cells: List[str]) -> Optional[WorkerDefinition]:
        """从表格行创建Worker定义"""
        if len(cells) < 4:
            return None

        data = dict(zip(headers, cells))

        worker_code = (
            data.get("Worker编码") or data.get("worker_code") or data.get("Worker Code", "")
        )
        worker_name = (
            data.get("Worker名称") or data.get("worker_name") or data.get("Worker Name", "")
        )
        business_stage = (
            data.get("业务阶段") or data.get("business_stage") or data.get("Business Stage", "")
        )
        description = (
            data.get("职责描述") or data.get("description") or data.get("Description", "")
        )

        if not worker_code:
            return None

        skills_str = (
            data.get("可用Skills") or data.get("available_skills") or data.get("Available Skills", "")
        )
        available_skills = [s.strip() for s in skills_str.split(",") if s.strip()]

        try:
            priority = int(data.get("优先级") or data.get("priority") or data.get("Priority", "5"))
        except ValueError:
            priority = 5

        try:
            timeout = int(data.get("超时(秒)") or data.get("timeout") or data.get("Timeout", "300"))
        except ValueError:
            timeout = 300

        return WorkerDefinition(
            worker_code=worker_code,
            worker_name=worker_name,
            business_stage=business_stage,
            description=description,
            available_skills=available_skills,
            priority=priority,
            timeout=timeout,
        )


    # ── 查询接口 ──────────────────────────────────

    def get_worker(self, worker_code: str) -> Optional[WorkerDefinition]:
        """获取Worker定义"""
        return self._workers.get(worker_code)

    def get_all_workers(self) -> List[WorkerDefinition]:
        """获取所有Worker定义"""
        return list(self._workers.values())

    def get_workers_by_stage(self, stage: str) -> List[WorkerDefinition]:
        """按业务阶段获取Worker"""
        return [
            w for w in self._workers.values()
            if stage in w.business_stage or w.business_stage == "全阶段"
        ]

    def get_worker_status(self, worker_code: str) -> Optional[WorkerStatus]:
        """获取Worker运行时状态"""
        worker = self._workers.get(worker_code)
        if not worker:
            return None
        return self._runtime_status.get(
            worker_code,
            WorkerStatus(
                worker_code=worker.worker_code,
                worker_name=worker.worker_name,
                status="idle",
            ),
        )

    def get_all_statuses(self) -> List[WorkerStatus]:
        """获取所有Worker运行时状态"""
        statuses = []
        for worker in self._workers.values():
            status = self._runtime_status.get(
                worker.worker_code,
                WorkerStatus(
                    worker_code=worker.worker_code,
                    worker_name=worker.worker_name,
                    status="idle",
                ),
            )
            statuses.append(status)
        return statuses

    def update_status(self, worker_code: str, status: WorkerStatus):
        """更新Worker运行时状态"""
        self._runtime_status[worker_code] = status

    # ── 管理接口（QAAgent调用）──────────────────────

    async def register_worker(self, worker_def: WorkerDefinition, file_name: str = "custom_workers.md") -> bool:
        """注册新Worker"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.config_dir / file_name

        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
        else:
            content = (
                "# 自定义Worker定义\n\n"
                "> 由QAAgent维护\n\n"
                "| Worker编码 | Worker名称 | 业务阶段 | 职责描述 | 可用Skills | 优先级 | 超时(秒) |\n"
                "|------------|------------|----------|----------|------------|--------|----------|\n"
            )

        new_row = (
            f"| {worker_def.worker_code} | {worker_def.worker_name} | {worker_def.business_stage} "
            f"| {worker_def.description} | {','.join(worker_def.available_skills)} "
            f"| {worker_def.priority} | {worker_def.timeout} |\n"
        )
        content += new_row
        file_path.write_text(content, encoding="utf-8")

        worker_def.config_file = str(file_path)
        self._workers[worker_def.worker_code] = worker_def
        return True

    async def update_worker(self, worker_def: WorkerDefinition) -> bool:
        """更新Worker定义（持久化到配置文件）"""
        if worker_def.worker_code not in self._workers:
            return False
        worker_def.updated_at = datetime.now(timezone.utc).isoformat()
        self._workers[worker_def.worker_code] = worker_def
        await self._rewrite_worker_file(worker_def)
        return True

    async def _rewrite_worker_file(self, worker_def: WorkerDefinition):
        """将 Worker 定义回写到配置文件。

        如果 Worker 的 config_file 存在则替换对应行，否则写入 custom_workers.md。
        """
        if worker_def.config_file:
            file_path = Path(worker_def.config_file)
        else:
            file_path = self.config_dir / "custom_workers.md"

        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 读取或创建配置文件
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
        else:
            content = (
                "# 自定义Worker定义\n\n"
                "| Worker编码 | Worker名称 | 业务阶段 | 职责描述 | 可用Skills | 优先级 | 超时(秒) |\n"
                "|------------|------------|----------|----------|------------|--------|----------|\n"
            )

        search_pattern = f"| {worker_def.worker_code} |"
        skills_str = ",".join(worker_def.available_skills) if worker_def.available_skills else ""
        new_row = (
            f"| {worker_def.worker_code} | {worker_def.worker_name} | "
            f"{worker_def.business_stage} | {worker_def.description} | "
            f"{skills_str} | {worker_def.priority} | {worker_def.timeout} |\n"
        )

        if search_pattern in content:
            # 替换已有行
            lines = content.split("\n")
            updated_lines = []
            for line in lines:
                if search_pattern in line:
                    updated_lines.append(new_row.rstrip())
                else:
                    updated_lines.append(line)
            content = "\n".join(updated_lines)
        else:
            # 追加新行
            content = content.rstrip() + "\n" + new_row

        file_path.write_text(content, encoding="utf-8")

    async def delete_worker(self, worker_code: str) -> bool:
        """删除Worker（归档）"""
        worker = self._workers.get(worker_code)
        if not worker:
            return False

        # 从配置文件中移除
        for md_file in self.config_dir.glob("*.md"):
            if md_file.name.startswith("_") or md_file.name == "README.md":
                continue
            content = md_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            new_lines = [line for line in lines if worker_code not in line]
            md_file.write_text("\n".join(new_lines), encoding="utf-8")

        # 归档
        archive_dir = self.config_dir / "_archive"
        archive_dir.mkdir(exist_ok=True)
        archive_file = archive_dir / f"{worker_code}.md"
        archive_content = (
            f"# 已归档Worker: {worker_code}\n\n"
            f"归档时间: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"原始定义: {json.dumps(worker.model_dump(), ensure_ascii=False, indent=2, default=str)}\n"
        )
        archive_file.write_text(archive_content, encoding="utf-8")

        del self._workers[worker_code]
        return True

    # ── SDK 执行 ──────────────────────────────────

    async def execute_worker_task(
        self,
        worker_code: str,
        task_name: str,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """通过 Worker 执行定时任务（使用 Claude Agent SDK）。

        这是定时任务绑定 Worker 的核心执行方法。
        Worker 使用 AstraAssistant.run_as_agent() 或 run_task()
        通过 Claude Agent SDK 执行任务，Claude 可使用 Bash/WebSearch/Read
        等原生工具完成工作。

        Args:
            worker_code:  Worker 编码
            task_name:      任务名称
            context:        任务上下文（额外参数）

        Returns:
            执行结果 dict，包含 status、result、worker_code、task_name
        """
        worker = self._workers.get(worker_code)
        if not worker:
            return {"status": "error", "error": f"Worker '{worker_code}' 不存在", "worker_code": worker_code}

        context = context or {}
        result = {
            "worker_code": worker_code,
            "worker_name": worker.worker_name,
            "task_name": task_name,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "sdk_executed": False,
            "status": "pending",
        }

        # 更新状态为忙碌
        self.update_status(worker_code, WorkerStatus(
            worker_code=worker_code,
            worker_name=worker.worker_name,
            status="busy",
            current_task=task_name,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        ))

        try:
            from app.services.astra_assistant import AstraAssistant, check_sdk

            if not check_sdk():
                logger.warning("Worker '%s' SDK 不可用，返回 SDK 未就绪", worker_code)
                result["status"] = "sdk_unavailable"
                result["message"] = "Claude Agent SDK 未安装，请执行: pip install claude-agent-sdk"
                return result

            assistant = AstraAssistant()
            sdk_agent_id = worker.sdk_agent_id

            if sdk_agent_id:
                # 方式 A: 以指定 Agent 身份执行（使用该 Agent 的 system_prompt）
                worker_prompt = (
                    f"你绑定的定时任务 '{task_name}' 已被触发。\n"
                    f"请根据你的职责 '{worker.description}' 执行任务。\n"
                    f"任务上下文: {json.dumps(context, ensure_ascii=False)}\n"
                )
                sdk_result = await assistant.run_as_agent(
                    agent_id=sdk_agent_id,
                    message=worker_prompt,
                )
                raw_text = sdk_result.get("response", "") or json.dumps(sdk_result, ensure_ascii=False)
            else:
                # 方式 B: 使用 run_task() 执行一次性任务
                worker_prompt_context = {
                    "worker_code": worker_code,
                    "worker_name": worker.worker_name,
                    "worker_description": worker.description,
                    "task_name": task_name,
                    "available_skills": worker.available_skills,
                    **context,
                }
                sdk_result = await assistant.run_task(
                    prompt_name=f"worker_{task_name}",
                    context=worker_prompt_context,
                )
                if isinstance(sdk_result, dict):
                    raw_text = (
                        sdk_result.get("raw_text", "") or
                        sdk_result.get("response", "") or
                        json.dumps(sdk_result, ensure_ascii=False)
                    )
                else:
                    raw_text = str(sdk_result)

            result["sdk_executed"] = True
            result["status"] = "completed"
            result["response"] = raw_text[:2000]  # 截断保存
            result["full_response_length"] = len(raw_text)

            # 更新 Worker 成功统计
            existing = self._runtime_status.get(worker_code)
            if existing:
                existing.tasks_completed += 1
                existing.status = "idle"
                existing.current_task = None
                self._runtime_status[worker_code] = existing

            logger.info(
                "Worker '%s' SDK 执行任务 '%s' 完成 (response=%d chars)",
                worker_code, task_name, len(raw_text),
            )

        except Exception as e:
            logger.error("Worker '%s' SDK 执行异常: %s", worker_code, e)
            result["status"] = "error"
            result["error"] = str(e)[:500]

            # 更新 Worker 失败统计
            existing = self._runtime_status.get(worker_code)
            if existing:
                existing.tasks_failed += 1
                existing.status = "error"
                existing.current_task = None
                self._runtime_status[worker_code] = existing

        finally:
            # 确保状态不是 busy
            status = self._runtime_status.get(worker_code)
            if status and status.status == "busy":
                status.status = "idle"
                status.current_task = None
                self._runtime_status[worker_code] = status

        return result


# ── 全局单例 ──────────────────────────────────

_worker_registry: Optional[WorkerRegistry] = None


def get_worker_registry() -> WorkerRegistry:
    """获取Worker注册表单例"""
    global _worker_registry
    if _worker_registry is None:
        _worker_registry = WorkerRegistry()
    return _worker_registry
