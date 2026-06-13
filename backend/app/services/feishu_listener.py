"""FeishuListener — 飞书消息监听服务。

通过 lark-cli event consume im.message.receive_v1 实时监听飞书群/私聊消息，
解析后路由到后端 Worker 处理链路。

设计:
  - 后台 asyncio subprocess 持续运行 lark-cli event consume
  - NDJSON 逐行解析消息事件
  - 消息过滤（忽略 bot 自身消息）
  - 路由到 chat_stream API 或 Worker 任务

依赖:
  - lark-cli 已安装且 bot 身份已认证
  - 飞书开发者后台已开启 im.message.receive_v1 事件订阅
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class FeishuListener:
    """飞书消息监听器 — 基于 lark-cli event consume。"""

    def __init__(self):
        self._handler: Optional[Callable] = None
        self._cmd: Optional[list] = None
        self._process: Optional[asyncio.subprocess.Process] = None
        self._listener: Optional[asyncio.Task] = None

    def on_message(self, handler: Callable):
        """注册消息处理器。

        handler 接收解析后的事件字典，格式:
        {
            "event_id": "...",
            "message_id": "om_xxx",
            "chat_id": "oc_xxx",
            "chat_type": "group" | "p2p",
            "sender_id": "ou_xxx",
            "content": "消息文本",
            "message_type": "text",
            "create_time": "1718256000000",
            "type": "im.message.receive_v1",
        }
        """
        self._handler = handler

    async def start(self):
        """启动监听（后台 asyncio task）。"""
        if self._listener and not self._listener.done():
            logger.info("FeishuListener 已在运行")
            return

        self._cmd = self._build_consume_cmd()
        self._listener = asyncio.create_task(self._listen_loop())
        logger.info("FeishuListener 已启动")

    async def stop(self):
        """停止监听。"""
        if self._listener:
            self._listener.cancel()
            try:
                await self._listener
            except asyncio.CancelledError:
                pass
        if self._process:
            try:
                self._process.terminate()
                await self._process.wait()
            except Exception:
                pass
        logger.info("FeishuListener 已停止")

    async def _listen_loop(self):
        """持续监听循环。"""
        while True:
            try:
                await self._consume_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("FeishuListener 异常: %s", e)
                await asyncio.sleep(5)

    async def _consume_events(self):
        """启动 lark-cli event consume 子进程并读取 NDJSON。"""
        cmd = self._cmd
        if not cmd:
            return

        bot_app_id = self._get_bot_app_id()
        logger.info("FeishuListener: 启动 lark-cli event consume (bot=%s)", bot_app_id)

        # Windows ProactorEventLoop 兼容
        self._process = await self._create_subprocess(cmd)

        if not self._process or not self._process.stdout:
            return

        async for line in self._process.stdout:
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue

            try:
                event = json.loads(line_str)
            except json.JSONDecodeError:
                logger.debug("FeishuListener 跳过非 JSON 行: %s", line_str[:100])
                continue

            # 跳过就绪标记
            if event.get("_type") == "ready":
                logger.info("FeishuListener: lark-cli event consume 就绪")
                continue

            await self._dispatch_event(event, bot_app_id)

    async def _create_subprocess(self, cmd: list) -> Optional[asyncio.subprocess.Process]:
        """创建 subprocess（Windows ProactorEventLoop 兼容）。"""
        try:
            return await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except NotImplementedError:
            # Windows ProactorEventLoop 不支持 create_subprocess_exec
            logger.info("FeishuListener: 当前事件循环不支持 subprocess，使用线程池桥接")
            return await asyncio.to_thread(self._create_subprocess_sync, cmd)

    @staticmethod
    def _create_subprocess_sync(cmd: list) -> Optional[asyncio.subprocess.Process]:
        """在新 ProactorEventLoop 中创建 subprocess。"""
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            return loop.run_until_complete(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            )
        except Exception as e:
            logger.error("FeishuListener: 创建 subprocess 失败: %s", e)
            return None
        finally:
            loop.close()

    def _get_bot_app_id(self) -> str:
        """获取 bot app_id（从 lark-cli config）。"""
        try:
            npm_root = Path.home() / "AppData" / "Roaming" / "npm"
            entry = npm_root / "node_modules" / "@larksuite" / "cli" / "scripts" / "run.js"
            if entry.exists():
                cmd = ["node", str(entry), "config", "show", "--json"]
            else:
                cmd = ["lark-cli", "config", "show", "--json"]
            proc = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=10)
            if proc.returncode == 0:
                data = json.loads(proc.stdout)
                return data.get("appId", "unknown")
        except Exception:
            pass
        return "unknown"

    async def _dispatch_event(self, event: dict, bot_app_id: str):
        """分发消息事件到所有处理器。"""
        try:
            body = event.get("body", {}) or event.get("event", {})
            msg = body
            if "event" in body:
                msg = body["event"]

            sender = msg.get("sender", {}) or {}
            sender_id = sender.get("sender_id", {})
            sender_open_id = sender_id.get("open_id", sender_id.get("user_id", ""))

            message = msg.get("message", msg)
            chat_id = message.get("chat_id", message.get("chatId", ""))
            chat_type = message.get("chat_type", message.get("chatType", "p2p"))
            message_id = message.get("message_id", message.get("messageId", ""))
            message_type = message.get("message_type", message.get("msgType", "text"))

            # 解析文本内容
            content_str = message.get("content", "{}")
            if isinstance(content_str, str):
                try:
                    content_obj = json.loads(content_str)
                except json.JSONDecodeError:
                    content_obj = {}
            else:
                content_obj = content_str

            text = content_obj.get("text", "")

            # 忽略 bot 自身消息
            if sender_open_id and sender_open_id == bot_app_id:
                return

            parsed = {
                "event_id": event.get("id", event.get("header", {}).get("event_id", "")),
                "message_id": message_id,
                "chat_id": chat_id,
                "chat_type": chat_type,
                "sender_id": sender_open_id,
                "content": text,
                "message_type": message_type,
                "create_time": message.get("create_time", ""),
                "type": "im.message.receive_v1",
            }

            logger.info(
                "FeishuListener 收到消息: chat=%s sender=%s type=%s content=%s",
                chat_id, sender_open_id, message_type, text[:100],
            )

            if self._handler:
                try:
                    result = self._handler(parsed)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error("FeishuListener 消息处理器异常: %s", e)

            # 同时发布到事件总线
            try:
                from app.core.event_bus import get_event_bus
                bus = get_event_bus()
                parsed["event_code"] = "feishu:message_received"
                parsed["source"] = "feishu_listener"
                await bus.publish_raw("feishu:message_received", parsed)
            except Exception as e:
                logger.debug("事件总线发布失败: %s", e)

        except Exception as e:
            logger.error("FeishuListener 消息解析异常: %s", e)

    @staticmethod
    def _build_consume_cmd() -> list:
        """构建 lark-cli event consume 命令。"""
        npm_root = Path.home() / "AppData" / "Roaming" / "npm"
        entry = npm_root / "node_modules" / "@larksuite" / "cli" / "scripts" / "run.js"
        if entry.exists():
            return ["node", str(entry), "event", "consume", "im.message.receive_v1", "--as", "bot"]
        cmd_path = npm_root / "lark-cli.cmd"
        if cmd_path.exists():
            return ["cmd", "/C", str(cmd_path), "event", "consume", "im.message.receive_v1", "--as", "bot"]
        return ["lark-cli", "event", "consume", "im.message.receive_v1", "--as", "bot"]


async def default_message_handler(event: dict):
    """默认消息处理器 — 将飞书消息转发到 chat_stream 处理。

    工作流:
      1. 收到飞书群消息
      2. 通过 chat_stream API 处理（NLU → Worker → 回复）
      3. 将回复发送回飞书群
    """
    chat_id = event.get("chat_id", "")
    content = event.get("content", "")
    chat_type = event.get("chat_type", "p2p")
    message_id = event.get("message_id", "")

    logger.info("默认处理器: 处理飞书消息 chat=%s content=%s", chat_id, content[:50])

    try:
        from app.core.unified_dispatcher import get_dispatcher
        dispatcher = get_dispatcher()
        await dispatcher.on_external_event("feishu", {
            "event_code": "feishu:message_received",
            "chat_id": chat_id,
            "chat_type": chat_type,
            "content": content,
            "message_id": message_id,
            "source": "feishu",
        })
        logger.info("默认处理器: 飞书消息处理完成 chat=%s", chat_id)
    except Exception as e:
        logger.error("默认处理器处理飞书消息失败: %s", e)
        # 尝试发送错误提示
        try:
            from app.core.unified_dispatcher import _get_lark_cli_direct
            import subprocess as _sp
            cmd = _get_lark_cli_direct()
            _sp.run(
                cmd + [
                    "im", "+messages-send", "--as", "bot",
                    "--chat-id", chat_id,
                    "--text", f"[系统] 消息处理失败: {e}",
                ],
                capture_output=True, encoding="utf-8", timeout=15,
            )
        except Exception:
            pass


# ── 全局单例 ──────────────────────────────────────

_listener: Optional[FeishuListener] = None


def get_feishu_listener() -> FeishuListener:
    """获取全局 FeishuListener 单例。"""
    global _listener
    if _listener is None:
        _listener = FeishuListener()
        _listener.on_message(default_message_handler)
    return _listener


async def start_feishu_listener():
    """启动飞书消息监听（由 main.py lifespan 调用）。"""
    listener = get_feishu_listener()
    await listener.start()


async def stop_feishu_listener():
    """停止飞书消息监听。"""
    listener = get_feishu_listener()
    await listener.stop()
