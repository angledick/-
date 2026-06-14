"""FeishuListener — 飞书消息监听适配器。

基于 lark-cli event consume im.message.receive_v1 实时监听飞书群/私聊消息，
解析后通过 _emit() 回调将事件交给 UnifiedEventDispatcher 进行路由分发。

不自己处理消息——所有路由逻辑由 UnifiedEventDispatcher + 配置文件驱动。

Windows 兼容：使用 subprocess.Popen + 后台守护线程读取 stdout，
避免 asyncio.create_subprocess_exec 在 SelectorEventLoop 上的 NotImplementedError。
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import threading
import time
from typing import Optional

from app.core.event_listeners.base import BaseEventListener

logger = logging.getLogger(__name__)


class FeishuListener(BaseEventListener):
    """飞书消息监听适配器 — 基于 lark-cli event consume。"""

    @property
    def name(self) -> str:
        return "feishu"

    def __init__(self):
        super().__init__()
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self):
        self._main_loop = asyncio.get_running_loop()
        cmd = self._build_cmd()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._sync_consume_loop,
            args=(cmd,),
            daemon=True,
            name="FeishuListener",
        )
        self._thread.start()
        logger.info("FeishuListener 已启动 (thread=%s)", self._thread.name)

    async def stop(self):
        self._stop_event.set()
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("FeishuListener 已停止")

    def _build_cmd(self) -> list:
        """构建 lark-cli event consume 命令。"""
        from pathlib import Path
        npm_root = Path.home() / "AppData" / "Roaming" / "npm"
        entry = npm_root / "node_modules" / "@larksuite" / "cli" / "scripts" / "run.js"
        if entry.exists():
            return ["node", str(entry), "event", "consume", "im.message.receive_v1", "--as", "bot"]
        cmd_path = npm_root / "lark-cli.cmd"
        if cmd_path.exists():
            return ["cmd", "/C", str(cmd_path), "event", "consume", "im.message.receive_v1", "--as", "bot"]
        return ["lark-cli", "event", "consume", "im.message.receive_v1", "--as", "bot"]

    # ── 后台线程：同步 Popen + 逐行读取 ──────────────

    def _sync_consume_loop(self, cmd: list):
        """后台守护线程：反复启动 lark-cli event consume 并读取 NDJSON。

        使用同步 subprocess.Popen，完全绕开 asyncio subprocess
        在 Windows SelectorEventLoop 上的 NotImplementedError。
        """
        while not self._stop_event.is_set():
            try:
                self._sync_consume_once(cmd)
            except Exception as e:
                logger.warning(
                    "FeishuListener 异常: [%s] %s | cmd=%s",
                    type(e).__name__, e, cmd[:3],
                )
            if not self._stop_event.is_set():
                time.sleep(3)

    def _sync_consume_once(self, cmd: list):
        """启动一次 lark-cli event consume 并读取直到进程退出。"""
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        bot_app_id = self._get_bot_app_id()
        logger.info(
            "FeishuListener: 启动 lark-cli event consume (bot=%s) pid=%d",
            bot_app_id, self._process.pid,
        )

        # 后台线程读取 stderr，避免 PIPE 缓冲区满导致死锁
        stderr_lines = []
        def _drain_stderr():
            try:
                for line in self._process.stderr:
                    stderr_lines.append(line.strip())
                    # 检测 ready 标记（lark-cli 输出到 stderr）
                    if "ready" in line.lower() and "event_key" in line:
                        logger.info("FeishuListener: lark-cli event consume 就绪")
            except Exception:
                pass
        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True, name="FeishuStderr")
        stderr_thread.start()

        try:
            for line in self._process.stdout:
                if self._stop_event.is_set():
                    break
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("FeishuListener 跳过非 JSON 行: %s", line[:100])
                    continue

                # 跳过就绪标记（stdout 也可能输出 ready）
                if event.get("_type") == "ready":
                    logger.info("FeishuListener: lark-cli event consume 就绪 (stdout)")
                    continue

                # 解析消息事件
                self._dispatch_event(event, bot_app_id)
        finally:
            self._process.wait()
            stderr_thread.join(timeout=3)
            rc = self._process.returncode
            stderr_tail = " | ".join(stderr_lines[-5:]) if stderr_lines else ""
            logger.warning(
                "FeishuListener: lark-cli 子进程退出 rc=%s stderr_tail=%s",
                rc, stderr_tail[:500],
            )

    # ── 事件解析 ──────────────────────────────────────

    def _get_bot_app_id(self) -> str:
        """获取 bot app_id（从 lark-cli config）。"""
        try:
            from pathlib import Path
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

    def _dispatch_event(self, event: dict, bot_app_id: str):
        """解析并分发消息事件。

        lark-cli event consume 输出扁平 NDJSON 格式：
          {"type", "event_id", "chat_id", "chat_type", "sender_id",
           "message_id", "message_type", "content", ...}
        也兼容嵌套 webhook 格式：
          {"body": {"sender": {...}, "message": {...}}}
        """
        try:
            # ── 扁平格式（lark-cli event consume 实际输出） ──
            chat_id = event.get("chat_id", "")
            chat_type = event.get("chat_type", "p2p")
            message_id = event.get("message_id", "")
            message_type = event.get("message_type", "text")
            sender_open_id = event.get("sender_id", "")
            raw_content = event.get("content", "")

            # ── 嵌套格式兜底（webhook / 其他事件源） ──
            if not chat_id:
                body = event.get("body", {}) or event.get("event", {})
                msg = body
                if isinstance(body, dict) and "event" in body:
                    msg = body["event"]

                sender = msg.get("sender", {}) or {}
                sender_id = sender.get("sender_id", {})
                sender_open_id = sender_id.get("open_id", sender_id.get("user_id", sender_open_id))

                message = msg.get("message", msg)
                chat_id = message.get("chat_id", message.get("chatId", ""))
                chat_type = message.get("chat_type", message.get("chatType", chat_type))
                message_id = message.get("message_id", message.get("messageId", ""))
                message_type = message.get("message_type", message.get("msgType", message_type))
                raw_content = message.get("content", raw_content)

            # ── 解析文本内容 ──
            text = ""
            if isinstance(raw_content, str):
                try:
                    content_obj = json.loads(raw_content)
                    text = content_obj.get("text", "")
                except json.JSONDecodeError:
                    text = raw_content  # 扁平格式 content 直接是文本
            elif isinstance(raw_content, dict):
                text = raw_content.get("text", "")

            if not text and message_type == "post":
                # 富文本提取
                try:
                    if isinstance(raw_content, str):
                        content_obj = json.loads(raw_content)
                    else:
                        content_obj = raw_content
                    content_parts = []
                    for line in content_obj.get("content", []):
                        for part in line:
                            content_parts.append(part.get("text", ""))
                    text = "\n".join(content_parts)
                except Exception:
                    pass

            # 忽略 bot 自身消息
            if sender_open_id and sender_open_id == bot_app_id:
                return

            event_data = {
                "event_code": "feishu:message_received",
                "chat_id": chat_id,
                "chat_type": chat_type,
                "content": text,
                "sender_id": sender_open_id,
                "message_id": message_id,
                "message_type": message_type,
                "event_id": event.get("id", event.get("event_id", "")),
                "type": "im.message.receive_v1",
            }

            logger.info(
                "FeishuListener 收到消息: chat=%s sender=%s type=%s content=%s",
                chat_id, sender_open_id, message_type, text[:100],
            )

            self._emit(event_data)

        except Exception as e:
            logger.error("FeishuListener 消息解析异常: %s", e)
