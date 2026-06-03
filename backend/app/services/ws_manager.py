"""WebSocket 连接管理 — 实时推送风险预警。

全局单例 ws_manager 管理 user_id → WebSocket 连接池。
支持连接/断开/推送/广播操作。

数据流转:
  - 输入端: Risk Alert Engine (create_alert → ws_manager.send_alert)
  - 输出端: 前端 WebSocket 客户端
  - 协议: JSON 消息，{ type: "alert" | "scan_update", payload: {...} }
"""

import json
import logging
from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    """WebSocket 连接管理器。

    管理 user_id → set[WebSocket] 的映射关系。
    每个用户可以同时有多个 WebSocket 连接（多标签页）。
    """

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        """接受 WebSocket 连接并注册。"""
        await ws.accept()
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(ws)
        logger.info(f"WS: user '{user_id}' connected (total: {len(self._connections[user_id])})")

    async def disconnect(self, user_id: str, ws: WebSocket):
        """断开 WebSocket 连接并清理。"""
        if user_id in self._connections:
            self._connections[user_id].discard(ws)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info(f"WS: user '{user_id}' disconnected")

    async def send_alert(self, user_id: str, alert: dict):
        """向指定用户推送预警。"""
        if user_id not in self._connections:
            logger.debug(f"WS: user '{user_id}' has no active connections")
            return
        message = json.dumps({
            "type": "alert",
            "payload": alert,
        }, ensure_ascii=False)
        dead_connections = []
        for ws in self._connections[user_id]:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.warning(f"WS: send failed for user '{user_id}': {e}")
                dead_connections.append(ws)
        for ws in dead_connections:
            await self.disconnect(user_id, ws)

    async def broadcast(self, alert: dict):
        """向所有已连接用户广播预警。"""
        for user_id in list(self._connections.keys()):
            await self.send_alert(user_id, alert)

    async def send_scan_update(self, user_id: str, status: str, detail: str = ""):
        """推送扫描状态更新。"""
        if user_id not in self._connections:
            return
        message = json.dumps({
            "type": "scan_update",
            "payload": {"status": status, "detail": detail},
        }, ensure_ascii=False)
        for ws in list(self._connections.get(user_id, set())):
            try:
                await ws.send_text(message)
            except Exception:
                await self.disconnect(user_id, ws)

    def get_connected_users(self) -> list[str]:
        """获取所有已连接用户 ID。"""
        return list(self._connections.keys())

    def is_connected(self, user_id: str) -> bool:
        """检查用户是否有活跃连接。"""
        return user_id in self._connections and bool(self._connections[user_id])


# 全局单例
ws_manager = WSManager()
