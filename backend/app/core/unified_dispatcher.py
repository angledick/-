"""UnifiedEventDispatcher — 统一事件分发中枢。

所有外部事件源（飞书、未来钉钉/企微等）统一入口。
外部事件 → 标准化为内部事件 → 注入 EventBus → 配置驱动分发。

分发路由策略（读取事件定义的 worker 字段）:
  "compliance_worker"  → ManagerAgent._route_to_worker() → SDK 执行
  "browser_worker"     → ManagerAgent._route_to_worker() → SDK 执行
  "system_worker"      → ManagerAgent._route_to_worker() → SDK 执行
  "qa_agent"           → QAAgent 处理
  空/无匹配            → AstraAssistant.chat() 通用处理

用法:
    dispatcher = UnifiedEventDispatcher()
    dispatcher.register_listener("feishu", FeishuListener())
    await dispatcher.start_all()    # 启动所有监听器
    ...
    await dispatcher.stop_all()     # 关闭所有监听器
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from app.config import settings
from app.core.event_listeners.base import BaseEventListener

logger = logging.getLogger(__name__)


class UnifiedEventDispatcher:
    """统一事件分发中枢"""

    def __init__(self):
        self._listeners: Dict[str, BaseEventListener] = {}
        self._seen_messages: Dict[str, float] = {}  # message_id → timestamp
        self._progress_sent: list = []
        self._tool_calls: list = []

    # ── 监听器管理 ──────────────────────────────────

    def register_listener(self, name: str, listener: BaseEventListener):
        """注册外部事件源适配器。"""
        self._listeners[name] = listener
        listener.on_event = lambda data, src=name: self.on_external_event(src, data)
        logger.info("UnifiedDispatcher: 注册监听器 '%s'", name)

    async def start_all(self):
        """启动所有已注册的监听器。"""
        for name, listener in self._listeners.items():
            try:
                await listener.start()
                logger.info("UnifiedDispatcher: '%s' 监听器已启动", name)
            except Exception as e:
                logger.warning("UnifiedDispatcher: '%s' 监听器启动失败（非致命）: %s", name, e)

    async def stop_all(self):
        """停止所有已注册的监听器。"""
        for name, listener in self._listeners.items():
            try:
                await listener.stop()
                logger.info("UnifiedDispatcher: '%s' 监听器已停止", name)
            except Exception as e:
                logger.warning("UnifiedDispatcher: '%s' 监听器停止失败: %s", name, e)

    # ── 事件入口 ────────────────────────────────────

    async def on_external_event(self, source: str, event_data: dict):
        """外部事件统一入口。

        处理流程:
          1. 从 event_data 中提取 event_code（如 "feishu:message_received"）
          2. 消息去重（飞书事件可能重复触发）
          3. 注入 source 到 event_data（回复发送时需要）
          4. 发布到全局 EventBus + 配置驱动分发
        """
        event_code = event_data.get("event_code", f"{source}:unknown")
        message_id = event_data.get("message_id", "")

        # 去重：60 秒内相同 message_id 跳过
        if message_id:
            now = time.time()
            if message_id in self._seen_messages and (now - self._seen_messages[message_id]) < 60:
                logger.debug("UnifiedDispatcher: 跳过重复消息 message_id=%s", message_id)
                return
            self._seen_messages[message_id] = now
            # 清理过期记录
            self._seen_messages = {
                k: v for k, v in self._seen_messages.items() if now - v < 120
            }

        event_data["source"] = source
        logger.info(
            "UnifiedDispatcher: 收到外部事件 source=%s event_code=%s",
            source, event_code,
        )

        # 先发布到事件总线
        await self._publish_to_bus(source, event_code, event_data)

        # 再走配置驱动路由
        await self._route_by_config(source, event_code, event_data)

    # ── 事件总线发布 ────────────────────────────────

    async def _publish_to_bus(self, source: str, event_code: str, event_data: dict):
        """将外部事件发布到全局事件总线。"""
        try:
            from app.core.event_bus import get_event_bus
            bus = get_event_bus()
            # publish_raw 接受单个 dict，type 字段为事件类型
            raw_event = {**event_data, "type": event_code}
            await bus.publish_raw(raw_event)
        except Exception as e:
            logger.debug("事件总线发布失败: %s", e)

    # ── 配置驱动路由 ────────────────────────────────

    async def _route_by_config(self, source: str, event_code: str, event_data: dict):
        """根据事件配置定义中的 worker 字段路由到对应处理器。"""
        event_def = self._get_event_definition(event_code)
        if event_def:
            worker = getattr(event_def, "agent_action", None) or ""
            if worker:
                await self._route_to_worker(event_def, event_data)
                logger.info("UnifiedDispatcher: 事件 '%s' 路由到 worker '%s'", event_code, worker)
                return

        # 无匹配 worker → 通用 Agent 处理
        logger.info("UnifiedDispatcher: 事件 '%s' 无匹配 worker，走通用 Agent 处理", event_code)
        await self._route_to_generic_agent(source, event_data)

    @staticmethod
    def _get_event_definition(event_code: str):
        """从 EventRegistry 查找事件定义。"""
        try:
            from app.core.event_bus import get_event_registry
            registry = get_event_registry()
            return registry.get_event(event_code)
        except Exception:
            return None

    async def _route_to_worker(self, event_def, event_data: dict):
        """路由到 ManagerAgent 的 Worker 调度。

        通过 submit_event_task → execute_group 执行，与内部事件流统一。
        危险事件（severity=high/critical）自动暂停，等待人工在飞书回复处理意见。
        """
        try:
            from app.core.manager_agent import get_manager_agent
            manager = get_manager_agent()
            # submit_event_task(event_type: str, event_data: dict)
            event_code = getattr(event_def, 'event_code', '') or str(event_def)
            group = await manager.submit_event_task(
                event_type=event_code,
                event_data=event_data,
            )
            if group:
                # ── 危险事件：已自动暂停，发送飞书通知 ──
                if group.status == "pending_approval":
                    chat_id = event_data.get("chat_id", "")
                    severity = getattr(event_def, 'severity', 'high')
                    if chat_id:
                        await self._send_feishu_direct(chat_id, (
                            f"⚠️ 危险事件需要人工审批\n"
                            f"事件: {event_code}\n"
                            f"严重级别: {severity}\n"
                            f"任务组: {group.group_id}\n"
                            f"原因: {group.context.get('pause_reason', '')}\n\n"
                            f"请回复处理意见（如：执行/取消）"
                        ))
                    logger.info(
                        "UnifiedDispatcher: 危险事件已暂停 group=%s event=%s",
                        group.group_id, event_code,
                    )
                    return

                # 正常执行
                import asyncio
                asyncio.create_task(manager.execute_group(group.group_id))
        except Exception as e:
            logger.error("UnifiedDispatcher: Worker 路由失败 event=%s err=%s",
                         getattr(event_def, 'event_code', '?'), e)

    async def _route_to_qa_agent(self, event_data: dict):
        """路由到 QAAgent 处理。"""
        try:
            from app.core.qa_agent import get_qa_agent
            qa = get_qa_agent()
            content = event_data.get("content", "")
            return await qa.answer(content)
        except Exception as e:
            logger.error("UnifiedDispatcher: QAAgent 路由失败: %s", e)

    async def _route_to_generic_agent(self, source: str, event_data: dict):
        """通用 Agent 处理 — 通过 AstraAssistant.chat_with_progress() 对话。

        流式进度回调：SDK 每产生一条中间消息（工具调用、任务进度），
        通过 lark-cli subprocess.run 实时推送到飞书。

        危险事件闭环：如果有等待人工决策的 pending 任务组，
        飞书回复将被视为处理意见，恢复任务组执行。
        """
        content = event_data.get("content", "")
        chat_id = event_data.get("chat_id", "")

        if not content:
            return

        # 检查是否有 pending 任务组（危险事件闭环）
        try:
            from app.core.manager_agent import get_manager_agent
            manager = get_manager_agent()
            pending = manager.get_pending_groups()
            if pending:
                logger.info(
                    "UnifiedDispatcher: 检测到 %d 个 pending 任务组，将飞书回复视为处理意见",
                    len(pending),
                )
                group = pending[0]
                group_id = group.get("group_id", "")
                instructions = content.strip()
                if any(kw in instructions for kw in ("执行", "继续", "确认", "同意", "resume")):
                    await self._send_feishu_direct(
                        chat_id,
                        f"✅ 处理意见已收到，任务组 `{group_id}` 已开始执行",
                    )
                    await manager.resume_pending_group(group_id, instructions)
                    return
                elif any(kw in instructions for kw in ("取消", "放弃", "跳过", "cancel")):
                    group["status"] = "cancelled"
                    await self._send_feishu_direct(
                        chat_id,
                        f"任务组 `{group_id}` 已取消",
                    )
                    return
        except Exception as e:
            logger.debug("检查 pending 任务组失败: %s", e)

        # 重置进度跟踪
        self._progress_sent = []
        self._tool_calls = []

        def _on_progress(text: str):
            """流式进度回调 — 去重后通过 lark-cli 发送到飞书。"""
            if self._progress_sent and _is_similar(text, self._progress_sent[-1]):
                return
            self._progress_sent.append(text)
            if text.startswith("\U0001f527"):
                self._tool_calls.append(text)
            try:
                import subprocess as _sp
                cmd = _get_lark_cli_direct()
                _sp.run(
                    cmd + [
                        "im", "+messages-send",
                        "--as", "bot",
                        "--chat-id", chat_id,
                        "--text", text,
                    ],
                    capture_output=True, encoding="utf-8", timeout=15,
                )
            except Exception as e:
                logger.debug("流式进度发送失败: %s", e)

        # 调用 SDK
        try:
            from app.services.astra_assistant import AstraAssistant
            assistant = AstraAssistant()
            result = await assistant.chat_with_progress(
                message=content,
                on_progress=_on_progress,
            )

            # 提取回复文本
            response_text = ""
            if isinstance(result, dict):
                response_text = result.get("response", "")
                tools_used = result.get("tools_used", [])

                # 保存调试文件
                try:
                    output_dir = Path(settings.data_dir) / "output"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    debug_file = output_dir / f"feishu_debug_{int(time.time())}.json"
                    with open(debug_file, "w", encoding="utf-8") as f:
                        json.dump({
                            "query": content,
                            "response_text": response_text,
                            "response_len": len(response_text),
                            "tools_used": tools_used,
                            "progress_messages": self._progress_sent,
                            "progress_count": len(self._progress_sent),
                            "tool_calls": self._tool_calls,
                            "result_keys": list(result.keys()),
                            "usage": result.get("usage"),
                            "session_id": result.get("session_id"),
                        }, f, ensure_ascii=False, indent=2)
                    logger.info("[SDK诊断] 调试文件已保存: %s", debug_file)
                except Exception as e:
                    logger.debug("[SDK诊断] 保存调试文件失败: %s", e)

                logger.info(
                    "[SDK诊断] 返回: response_len=%d tools=%s progress=%d",
                    len(response_text), tools_used, len(self._progress_sent),
                )
            elif isinstance(result, str):
                response_text = result

            # 发送最终回复（去重：如果已在进度中发送过则跳过）
            if source == "feishu" and chat_id:
                if response_text:
                    # 检查最终回复是否已通过进度回调发送过
                    already_sent = False
                    for sent in self._progress_sent:
                        if _is_similar(response_text, sent) or (
                            len(response_text) > 50 and response_text.strip() in "".join(self._progress_sent)
                        ):
                            already_sent = True
                            break
                    if already_sent:
                        logger.info("最终回复已通过进度回调发送，跳过重复发送")
                    else:
                        await self._send_feishu_direct(chat_id, response_text)
                elif self._tool_calls:
                    await self._send_feishu_direct(
                        chat_id,
                        f"✅ 已完成，共执行 {len(self._tool_calls)} 次工具调用。",
                    )
                else:
                    logger.warning("SDK 无任何输出: result_keys=%s",
                                   list(result.keys()) if isinstance(result, dict) else "str")

        except Exception as e:
            logger.error("UnifiedDispatcher: 通用 Agent 处理失败: %s", e, exc_info=True)
            if source == "feishu" and chat_id:
                try:
                    await self._send_feishu_direct(chat_id, f"[系统] 消息处理失败: {e}")
                except Exception as e2:
                    logger.error("UnifiedDispatcher: 错误提示发送失败: %s", e2, exc_info=True)

    async def _send_feishu_direct(self, chat_id: str, text: str):
        """通过 asyncio.to_thread + subprocess.run 调 lark-cli 发飞书消息。

        使用 _get_lark_cli_direct() 直接调用 Node.js，绕过 cmd.exe /C，
        避免多行文本中的换行符被截断、| > < 等字符被当作 shell 操作符。
        """
        def _sync():
            import subprocess as _sp
            cmd = _get_lark_cli_direct()
            return _sp.run(
                cmd + [
                    "im", "+messages-send",
                    "--as", "bot",
                    "--chat-id", chat_id,
                    "--text", text,
                ],
                capture_output=True, encoding="utf-8", timeout=30,
            )

        try:
            proc = await asyncio.to_thread(_sync)
            logger.info(
                "最终回复直发: len=%d rc=%d stdout=%.80s",
                len(text), proc.returncode, proc.stdout.strip(),
            )
            return proc.returncode == 0
        except Exception as e:
            logger.error("最终回复直发失败: %s", e)
            return False

    async def _send_reply(self, event_data: dict, text: str):
        """将回复发送回事件来源渠道。"""
        source = event_data.get("source", "")
        chat_id = event_data.get("chat_id", "")

        if source == "feishu" and chat_id:
            await self._send_feishu_direct(chat_id, text)
        else:
            logger.warning("UnifiedDispatcher: 未实现渠道 '%s' 的回复发送", source)


def _get_lark_cli_direct() -> list:
    """获取 lark-cli 的 Node.js 直调命令列表。

    绕过 cmd.exe /C 包装，避免多行文本中的换行符
    被 cmd.exe 当作命令分隔符，以及 | > < & 等 shell 元字符被误解析。

    返回 ["node", "<entry_point>"] 格式，可直接传给 subprocess.run()。
    """
    from pathlib import Path as _P
    import shutil
    npm_root = _P.home() / "AppData" / "Roaming" / "npm"
    entry_point = npm_root / "node_modules" / "@larksuite" / "cli" / "scripts" / "run.js"
    if entry_point.exists():
        return ["node", str(entry_point)]
    # 回退：使用 cmd.exe 包装（多行文本可能被截断）
    cmd_path = npm_root / "lark-cli.cmd"
    if cmd_path.exists():
        return ["cmd", "/C", str(cmd_path)]
    found = shutil.which("lark-cli")
    if found:
        if found.endswith(".cmd") or found.endswith(".bat"):
            return ["cmd", "/C", found]
        return [found]
    return ["cmd", "/C", "lark-cli"]


def _is_similar(a: str, b: str) -> bool:
    """判断两条消息是否高度相似（用于去重）。

    策略：
    - 完全相同
    - 前 100 字符相同（处理截断差异）
    - 短消息（<50字）包含关系
    """
    if a == b:
        return True
    if a[:100] == b[:100]:
        return True
    if len(a) < 50 and len(b) < 50 and (a in b or b in a):
        return True
    return False


# ── 全局单例 ──────────────────────────────────────

_dispatcher: Optional[UnifiedEventDispatcher] = None


def get_dispatcher() -> UnifiedEventDispatcher:
    """获取全局 UnifiedEventDispatcher 单例。"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = UnifiedEventDispatcher()
    return _dispatcher


# 延迟导入需要
from pathlib import Path
