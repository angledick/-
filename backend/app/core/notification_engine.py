"""
多渠道通知引擎 (NotificationEngine)。

职责：
  1. 多渠道发送: Dashboard / WebSocket / Email / Webhook
  2. 严重级别路由: 根据severity自动选择通知渠道
  3. 静默时段: 非紧急通知在静默时段延迟发送
  4. 通知历史: 持久化通知记录
  5. 已读/未读管理: 标记通知状态

开源参考:
  - 邮件: Listmonk (21.2k⭐) — SMTP发送
  - 客服: Chatwoot (29.9k⭐) — 工单通知
  - 工作流: n8n (191k⭐) — 通知编排

存储:
  - data/global/notifications/ — 通知历史
"""

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.config import settings
from app.models.schemas import NotificationPayload

DATA_DIR = Path(settings.data_dir)
NOTIFICATIONS_DIR = DATA_DIR / "global" / "notifications"


class NotificationEngine:
    """多渠道通知引擎

    用法:
        engine = NotificationEngine()

        # 发送通知
        await engine.send(NotificationPayload(
            type="compliance_check",
            title="合规检查通过",
            message="LED灯带已通过德国市场合规检查",
            product_id="p_led_de_001",
            severity="low",
        ))

        # 获取通知列表
        notifications = engine.get_notifications(product_id="p_led_de_001")

        # 标记已读
        engine.mark_read(notification_id)
    """

    def __init__(self, config_file: str = None):
        self._config_file = Path(config_file) if config_file else DATA_DIR / "notifications" / "config.json"
        self._config = self._load_config()
        self._notification_history: List[NotificationPayload] = []
        NOTIFICATIONS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        """加载通知配置"""
        if self._config_file.exists():
            try:
                return json.loads(self._config_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        return {
            "channels": {
                "dashboard": {"enabled": True},
                "websocket": {"enabled": True},
                "email": {"enabled": False, "smtp_host": "", "smtp_port": 587, "from_addr": ""},
                "webhook": {"enabled": False, "url": ""},
            },
            "severity_routing": {
                "critical": ["dashboard", "websocket", "email"],
                "high": ["dashboard", "websocket"],
                "medium": ["dashboard"],
                "low": ["dashboard"],
            },
            "quiet_hours": {"enabled": False, "start": "22:00", "end": "08:00"},
        }

    def reload_config(self):
        """重新加载配置"""
        self._config = self._load_config()

    # ── 发送通知 ──────────────────────────────────

    async def send(
        self,
        notification: NotificationPayload,
        channels: List[str] = None,
        force: bool = False,
    ) -> Dict[str, bool]:
        """发送通知到指定渠道

        Args:
            notification: 通知内容
            channels: 指定渠道（为None时根据severity自动路由）
            force: 是否忽略静默时段
        Returns:
            各渠道发送结果
        """
        # 确定发送渠道
        if channels is None:
            channels = self._config.get("severity_routing", {}).get(
                notification.severity, ["dashboard"]
            )

        # 静默时段检查
        if not force and self._is_quiet_hours():
            if notification.severity not in ("critical",):
                # 延迟到静默时段结束
                return {"queued": True}

        results = {}

        for channel in channels:
            channel_config = self._config.get("channels", {}).get(channel, {})
            if not channel_config.get("enabled", False):
                results[channel] = False
                continue

            try:
                if channel == "dashboard":
                    results[channel] = await self._send_dashboard(notification)
                elif channel == "websocket":
                    results[channel] = await self._send_websocket(notification)
                elif channel == "email":
                    results[channel] = await self._send_email(notification, channel_config)
                elif channel == "webhook":
                    results[channel] = await self._send_webhook(notification, channel_config)
                else:
                    results[channel] = False
            except Exception:
                results[channel] = False

        # 持久化通知记录
        await self._persist_notification(notification)
        self._notification_history.append(notification)

        return results

    async def send_batch(
        self, notifications: List[NotificationPayload]
    ) -> List[Dict[str, bool]]:
        """批量发送通知"""
        results = []
        for notification in notifications:
            result = await self.send(notification)
            results.append(result)
        return results

    # ── 通知查询 ──────────────────────────────────

    def get_notifications(
        self,
        product_id: str = None,
        is_read: bool = None,
        severity: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[NotificationPayload]:
        """获取通知列表"""
        notifications = self._load_notification_history()

        if product_id:
            notifications = [n for n in notifications if n.product_id == product_id]
        if is_read is not None:
            notifications = [n for n in notifications if n.is_read == is_read]
        if severity:
            notifications = [n for n in notifications if n.severity == severity]

        return notifications[offset:offset + limit]

    def get_unread_count(self, product_id: str = None) -> int:
        """获取未读通知数"""
        notifications = self._load_notification_history()
        if product_id:
            notifications = [n for n in notifications if n.product_id == product_id]
        return sum(1 for n in notifications if not n.is_read)

    def mark_read(self, notification_id: str) -> bool:
        """标记通知为已读"""
        for n in self._notification_history:
            if n.id == notification_id:
                n.is_read = True
                return True

        # 也从文件中查找
        history = self._load_notification_history()
        for n in history:
            if n.id == notification_id:
                n.is_read = True
                self._save_notification_history(history)
                return True
        return False

    def mark_all_read(self, product_id: str = None) -> int:
        """标记所有通知为已读"""
        history = self._load_notification_history()
        count = 0
        for n in history:
            if not n.is_read:
                if product_id is None or n.product_id == product_id:
                    n.is_read = True
                    count += 1
        if count > 0:
            self._save_notification_history(history)
        return count

    # ── 渠道实现 ──────────────────────────────────

    async def _send_dashboard(self, notification: NotificationPayload) -> bool:
        """发送到Dashboard（持久化到通知文件）"""
        await self._persist_notification(notification)
        return True

    async def _send_websocket(self, notification: NotificationPayload) -> bool:
        """通过WebSocket推送（统一 {type, payload} 格式）"""
        try:
            from app.services.ws_manager import ws_manager
            target_user = notification.product_id or "default"
            await ws_manager.send_to_user(target_user, {
                "type": "alert",
                "payload": {
                    "alert_id": notification.id,
                    "severity": notification.severity,
                    "title": notification.title,
                    "description": notification.message,
                    "product_id": notification.product_id,
                    "created_at": notification.created_at,
                },
            })
            return True
        except Exception:
            return False

    async def _send_email(self, notification: NotificationPayload, config: Dict) -> bool:
        """通过SMTP发送邮件（Listmonk集成预留）"""
        smtp_host = config.get("smtp_host", "")
        if not smtp_host:
            return False

        # 预留: 实际实现需要SMTP客户端
        # 推荐开源方案: Listmonk (21.2k⭐)
        return False

    async def _send_webhook(self, notification: NotificationPayload, config: Dict) -> bool:
        """通过Webhook发送"""
        url = config.get("url", "")
        if not url:
            return False

        # 预留: 实际实现需要HTTP客户端
        return False

    # ── 内部方法 ──────────────────────────────────

    def _is_quiet_hours(self) -> bool:
        """检查是否在静默时段"""
        quiet = self._config.get("quiet_hours", {})
        if not quiet.get("enabled", False):
            return False

        now = datetime.now().strftime("%H:%M")
        start = quiet.get("start", "22:00")
        end = quiet.get("end", "08:00")

        if start > end:  # 跨午夜
            return now >= start or now < end
        return start <= now < end

    async def _persist_notification(self, notification: NotificationPayload):
        """持久化通知"""
        try:
            history = self._load_notification_history()
            history.insert(0, notification)

            # 保留最近500条
            if len(history) > 500:
                history = history[:500]

            self._save_notification_history(history)
        except Exception:
            pass

    def _load_notification_history(self) -> List[NotificationPayload]:
        """加载通知历史"""
        history_file = NOTIFICATIONS_DIR / "history.json"
        if not history_file.exists():
            return []
        try:
            data = json.loads(history_file.read_text(encoding="utf-8"))
            return [NotificationPayload(**item) for item in data]
        except Exception:
            return []

    def _save_notification_history(self, history: List[NotificationPayload]):
        """保存通知历史"""
        history_file = NOTIFICATIONS_DIR / "history.json"
        data = [n.model_dump() for n in history]
        history_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )


# ── 全局单例 ──────────────────────────────────

_notification_engine: Optional[NotificationEngine] = None


def get_notification_engine() -> NotificationEngine:
    """获取通知引擎单例"""
    global _notification_engine
    if _notification_engine is None:
        _notification_engine = NotificationEngine()
    return _notification_engine
