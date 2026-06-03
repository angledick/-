"""
ChannelAdapter — 频道适配器（Phase 3.1）

参考开源选型：
- Chatwoot（指南 §3.5.1）全渠道消息接入模式
- Listmonk（指南 §3.5.2）邮件营销

抽象基类 + 具体实现:
  - FeishuAdapter   : 飞书机器人（Webhook + Bot API）
  - DingTalkAdapter  : 钉钉机器人（Webhook + 工作通知）
  - SlackAdapter     : Slack Bot（Webhook + Bot API）
  - EmailAdapter     : Listmonk SMTP 邮件
  - WebhookAdapter   : 通用Webhook

通知payload包含 product_id 深度链接（对齐指南 §6.12.3）
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings


# ── 数据结构 ────────────────────────────────────────


@dataclass
class ChannelMessage:
    """频道消息"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    channel: str = ""           # feishu / dingtalk / slack / email / webhook
    target: str = ""            # 目标ID（群ID / 用户ID / 邮箱）
    content: str = ""           # 文本内容
    title: str = ""
    msg_type: str = "text"      # text / card / notification / markdown
    attachments: List[Dict] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    sent_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    status: str = "pending"     # pending / sent / failed
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NotificationCard:
    """交互式通知卡片（含 product_id 深度链接）"""
    title: str = ""
    description: str = ""
    severity: str = "info"      # info / warning / error / success
    product_id: str = ""        # ★ 深度链接跳转目标
    stage: str = ""             # ★ 业务阶段
    actions: List[Dict] = field(default_factory=list)  # [{label, url, style}]
    fields: List[Dict] = field(default_factory=list)    # [{label, value}]

    def to_dict(self) -> dict:
        return asdict(self)


# ── 抽象基类 ──────────────────────────────────────


class ChannelAdapter(ABC):
    """频道适配器抽象基类"""

    channel_name: str = "base"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._message_log: List[ChannelMessage] = []

    @abstractmethod
    async def send_message(self, target: str, content: str,
                          attachments: List[Dict] = None) -> ChannelMessage:
        """发送文本消息"""
        pass

    @abstractmethod
    async def send_card(self, target: str, card: NotificationCard) -> ChannelMessage:
        """发送交互式卡片消息"""
        pass

    async def send_notification(self, target: str, notification: Dict) -> ChannelMessage:
        """发送通知（含 product_id 深度链接）"""
        card = NotificationCard(
            title=notification.get("title", ""),
            description=notification.get("message", ""),
            severity=notification.get("severity", "info"),
            product_id=notification.get("product_id", ""),
            stage=notification.get("stage", ""),
        )
        return await self.send_card(target, card)

    async def broadcast(self, targets: List[str], content: str) -> List[ChannelMessage]:
        """向多个频道广播"""
        results = []
        for t in targets:
            msg = await self.send_message(t, content)
            results.append(msg)
        return results

    def get_message_log(self) -> List[Dict]:
        return [m.to_dict() for m in self._message_log[-100:]]

    def _log_message(self, msg: ChannelMessage):
        self._message_log.append(msg)
        if len(self._message_log) > 500:
            self._message_log = self._message_log[-200:]


# ── 飞书适配器 ────────────────────────────────────


class FeishuAdapter(ChannelAdapter):
    """
    飞书机器人频道适配器

    参考: Chatwoot（指南 §3.5.1）全渠道消息模型
    配置: app_id, app_secret, webhook_url, encrypt_key, verification_token
    """

    channel_name = "feishu"

    async def send_message(self, target: str, content: str,
                          attachments: List[Dict] = None) -> ChannelMessage:
        import httpx

        msg = ChannelMessage(channel=self.channel_name, target=target, content=content, msg_type="text")

        webhook_url = self.config.get("webhook_url", "")
        if not webhook_url:
            msg.status = "failed"
            msg.error = "webhook_url not configured"
            self._log_message(msg)
            return msg

        try:
            payload = {
                "msg_type": "text",
                "content": {"text": content},
            }

            # 签名校验（如配置了encrypt_key）
            encrypt_key = self.config.get("encrypt_key", "")
            if encrypt_key:
                timestamp = str(int(time.time()))
                string_to_sign = f"{timestamp}\n{encrypt_key}"
                hmac_code = hmac.new(encrypt_key.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
                import base64
                payload["timestamp"] = timestamp
                payload["sign"] = base64.b64encode(hmac_code).decode("utf-8")

            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload, timeout=15)
                data = resp.json()
                if data.get("code") == 0 or data.get("StatusCode") == 0:
                    msg.status = "sent"
                else:
                    msg.status = "failed"
                    msg.error = data.get("msg", str(data))
        except Exception as e:
            msg.status = "failed"
            msg.error = str(e)

        self._log_message(msg)
        return msg

    async def send_card(self, target: str, card: NotificationCard) -> ChannelMessage:
        import httpx

        msg = ChannelMessage(channel=self.channel_name, target=target,
                            content=card.title, msg_type="card")

        webhook_url = self.config.get("webhook_url", "")
        if not webhook_url:
            msg.status = "failed"
            msg.error = "webhook_url not configured"
            self._log_message(msg)
            return msg

        # 飞书交互式卡片
        severity_color = {"info": "blue", "warning": "orange", "error": "red", "success": "green"}
        color = severity_color.get(card.severity, "blue")

        card_body = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": card.title},
                    "template": color,
                },
                "elements": [],
            },
        }

        if card.description:
            card_body["card"]["elements"].append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": card.description},
            })

        # 字段展示
        if card.fields:
            field_elements = []
            for f in card.fields:
                field_elements.append({
                    "is_short": True,
                    "text": {"tag": "lark_md", "content": f"**{f.get('label', '')}**\n{f.get('value', '')}"},
                })
            card_body["card"]["elements"].append({"tag": "div", "fields": field_elements})

        # 深度链接信息
        if card.product_id:
            card_body["card"]["elements"].append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": f"产品ID: {card.product_id} | 阶段: {card.stage}"}],
            })

        # 操作按钮
        if card.actions:
            action_elements = []
            for a in card.actions:
                action_elements.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": a.get("label", "Action")},
                    "url": a.get("url", ""),
                    "type": a.get("style", "default"),
                })
            card_body["card"]["elements"].append({"tag": "action", "actions": action_elements})

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=card_body, timeout=15)
                data = resp.json()
                msg.status = "sent" if (data.get("code") == 0 or data.get("StatusCode") == 0) else "failed"
                if msg.status == "failed":
                    msg.error = data.get("msg", str(data))
        except Exception as e:
            msg.status = "failed"
            msg.error = str(e)

        self._log_message(msg)
        return msg


# ── 钉钉适配器 ────────────────────────────────────


class DingTalkAdapter(ChannelAdapter):
    """
    钉钉机器人频道适配器

    参考: Chatwoot（指南 §3.5.1）全渠道消息模型
    配置: webhook_token, secret, app_key, app_secret, agent_id
    """

    channel_name = "dingtalk"

    async def send_message(self, target: str, content: str,
                          attachments: List[Dict] = None) -> ChannelMessage:
        import httpx

        msg = ChannelMessage(channel=self.channel_name, target=target, content=content, msg_type="text")

        webhook_url = self._build_webhook_url()
        if not webhook_url:
            msg.status = "failed"
            msg.error = "webhook_token not configured"
            self._log_message(msg)
            return msg

        try:
            payload = {
                "msgtype": "text",
                "text": {"content": content},
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload, timeout=15)
                data = resp.json()
                msg.status = "sent" if data.get("errcode") == 0 else "failed"
                if msg.status == "failed":
                    msg.error = data.get("errmsg", str(data))
        except Exception as e:
            msg.status = "failed"
            msg.error = str(e)

        self._log_message(msg)
        return msg

    async def send_card(self, target: str, card: NotificationCard) -> ChannelMessage:
        import httpx

        msg = ChannelMessage(channel=self.channel_name, target=target,
                            content=card.title, msg_type="card")

        webhook_url = self._build_webhook_url()
        if not webhook_url:
            msg.status = "failed"
            msg.error = "webhook_token not configured"
            self._log_message(msg)
            return msg

        # 钉钉ActionCard消息
        markdown_lines = [f"### {card.title}", ""]
        if card.description:
            markdown_lines.append(card.description)
            markdown_lines.append("")

        if card.product_id:
            markdown_lines.append(f"> **产品ID**: {card.product_id} | **阶段**: {card.stage}")
            markdown_lines.append("")

        for f in card.fields:
            markdown_lines.append(f"- **{f.get('label', '')}**: {f.get('value', '')}")

        payload = {
            "msgtype": "actionCard",
            "actionCard": {
                "title": card.title,
                "text": "\n".join(markdown_lines),
                "btnOrientation": "0",
                "btns": [],
            },
        }

        for a in card.actions:
            payload["actionCard"]["btns"].append({
                "title": a.get("label", "Action"),
                "actionURL": a.get("url", ""),
            })

        if not payload["actionCard"]["btns"]:
            payload["msgtype"] = "markdown"
            payload["markdown"] = {"title": card.title, "text": "\n".join(markdown_lines)}
            del payload["actionCard"]

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload, timeout=15)
                data = resp.json()
                msg.status = "sent" if data.get("errcode") == 0 else "failed"
                if msg.status == "failed":
                    msg.error = data.get("errmsg", str(data))
        except Exception as e:
            msg.status = "failed"
            msg.error = str(e)

        self._log_message(msg)
        return msg

    def _build_webhook_url(self) -> str:
        token = self.config.get("webhook_token", "")
        if not token:
            return ""
        url = f"https://oapi.dingtalk.com/robot/send?access_token={token}"

        secret = self.config.get("secret", "")
        if secret:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"),
                                digestmod=hashlib.sha256).digest()
            import base64
            from urllib.parse import quote_plus
            sign = quote_plus(base64.b64encode(hmac_code).decode("utf-8"))
            url = f"{url}&timestamp={timestamp}&sign={sign}"
        return url


# ── Slack适配器 ───────────────────────────────────


class SlackAdapter(ChannelAdapter):
    """
    Slack Bot频道适配器

    参考: Chatwoot（指南 §3.5.1）全渠道消息模型
    配置: bot_token, signing_secret, webhook_url
    """

    channel_name = "slack"

    async def send_message(self, target: str, content: str,
                          attachments: List[Dict] = None) -> ChannelMessage:
        import httpx

        msg = ChannelMessage(channel=self.channel_name, target=target, content=content, msg_type="text")
        bot_token = self.config.get("bot_token", "")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {bot_token}"},
                    json={"channel": target, "text": content},
                    timeout=15,
                )
                data = resp.json()
                msg.status = "sent" if data.get("ok") else "failed"
                if not data.get("ok"):
                    msg.error = data.get("error", "Unknown error")
        except Exception as e:
            msg.status = "failed"
            msg.error = str(e)

        self._log_message(msg)
        return msg

    async def send_card(self, target: str, card: NotificationCard) -> ChannelMessage:
        import httpx

        msg = ChannelMessage(channel=self.channel_name, target=target,
                            content=card.title, msg_type="card")
        bot_token = self.config.get("bot_token", "")

        severity_color = {"info": "#36a64f", "warning": "#ff9900", "error": "#ff0000", "success": "#36a64f"}

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": card.title}},
        ]

        if card.description:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": card.description}})

        fields_list = []
        if card.product_id:
            fields_list.append({"type": "mrkdwn", "text": f"*产品ID*\n{card.product_id}"})
            fields_list.append({"type": "mrkdwn", "text": f"*阶段*\n{card.stage}"})
        for f in card.fields:
            fields_list.append({"type": "mrkdwn", "text": f"*{f.get('label', '')}*\n{f.get('value', '')}"})
        if fields_list:
            blocks.append({"type": "section", "fields": fields_list})

        if card.actions:
            elements = []
            for a in card.actions:
                elements.append({
                    "type": "button",
                    "text": {"type": "plain_text", "text": a.get("label", "Action")},
                    "url": a.get("url", ""),
                })
            blocks.append({"type": "actions", "elements": elements})

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {bot_token}"},
                    json={
                        "channel": target,
                        "text": card.title,
                        "blocks": blocks,
                    },
                    timeout=15,
                )
                data = resp.json()
                msg.status = "sent" if data.get("ok") else "failed"
                if not data.get("ok"):
                    msg.error = data.get("error", "Unknown error")
        except Exception as e:
            msg.status = "failed"
            msg.error = str(e)

        self._log_message(msg)
        return msg


# ── Email适配器（Listmonk）────────────────────────


class EmailAdapter(ChannelAdapter):
    """
    Listmonk邮件适配器

    参考: Listmonk（指南 §3.5.2）单二进制邮件营销
    配置: base_url, username, password, from_email, list_ids
    """

    channel_name = "email"

    async def send_message(self, target: str, content: str,
                          attachments: List[Dict] = None) -> ChannelMessage:
        import httpx

        msg = ChannelMessage(channel=self.channel_name, target=target, content=content, msg_type="text")

        base_url = self.config.get("base_url", "")
        if not base_url:
            msg.status = "failed"
            msg.error = "Listmonk base_url not configured"
            self._log_message(msg)
            return msg

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base_url}/api/tx",
                    auth=(self.config.get("username", ""), self.config.get("password", "")),
                    json={
                        "subscriber_email": target,
                        "template_id": self.config.get("template_id", 1),
                        "from_email": self.config.get("from_email", "noreply@astra.local"),
                        "data": {"content": content, "title": "Astra Notification"},
                    },
                    timeout=15,
                )
                data = resp.json()
                msg.status = "sent" if data.get("data", {}).get("id") else "failed"
                if msg.status == "failed":
                    msg.error = data.get("message", str(data))
        except Exception as e:
            msg.status = "failed"
            msg.error = str(e)

        self._log_message(msg)
        return msg

    async def send_card(self, target: str, card: NotificationCard) -> ChannelMessage:
        # Email uses HTML rendering
        html_parts = [f"<h2>{card.title}</h2>"]
        if card.description:
            html_parts.append(f"<p>{card.description}</p>")
        if card.product_id:
            html_parts.append(f"<p><strong>产品ID</strong>: {card.product_id} | <strong>阶段</strong>: {card.stage}</p>")
        for f in card.fields:
            html_parts.append(f"<p><strong>{f.get('label', '')}</strong>: {f.get('value', '')}</p>")
        if card.actions:
            html_parts.append("<p>")
            for a in card.actions:
                html_parts.append(f'<a href="{a.get("url", "#")}" style="margin-right:8px">{a.get("label", "Action")}</a>')
            html_parts.append("</p>")

        return await self.send_message(target, "\n".join(html_parts))


# ── 通用Webhook适配器 ────────────────────────────


class WebhookAdapter(ChannelAdapter):
    """通用Webhook适配器"""

    channel_name = "webhook"

    async def send_message(self, target: str, content: str,
                          attachments: List[Dict] = None) -> ChannelMessage:
        import httpx

        msg = ChannelMessage(channel=self.channel_name, target=target, content=content, msg_type="text")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    target,
                    json={"content": content, "attachments": attachments or []},
                    timeout=15,
                )
                msg.status = "sent" if resp.status_code < 400 else "failed"
                if msg.status == "failed":
                    msg.error = f"HTTP {resp.status_code}"
        except Exception as e:
            msg.status = "failed"
            msg.error = str(e)

        self._log_message(msg)
        return msg

    async def send_card(self, target: str, card: NotificationCard) -> ChannelMessage:
        import httpx

        msg = ChannelMessage(channel=self.channel_name, target=target,
                            content=card.title, msg_type="card")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(target, json=card.to_dict(), timeout=15)
                msg.status = "sent" if resp.status_code < 400 else "failed"
                if msg.status == "failed":
                    msg.error = f"HTTP {resp.status_code}"
        except Exception as e:
            msg.status = "failed"
            msg.error = str(e)

        self._log_message(msg)
        return msg


# ── ChannelRegistry — 频道注册表 ─────────────────


class ChannelRegistry:
    """频道注册表 — 管理所有已配置的频道适配器"""

    def __init__(self):
        self._adapters: Dict[str, ChannelAdapter] = {}
        self._config_file = Path(settings.data_dir) / "config" / "channels.json"
        self._load_config()

    def _load_config(self):
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    configs = json.load(f)
                for ch_name, ch_config in configs.items():
                    self._create_adapter(ch_name, ch_config)
            except Exception:
                pass

    def _save_config(self):
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for name, adapter in self._adapters.items():
            data[name] = {"channel": adapter.channel_name, "config": adapter.config}
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _create_adapter(self, name: str, config: Dict[str, Any]):
        channel_type = config.get("channel", name)
        adapter_config = config.get("config", {})
        adapter_map = {
            "feishu": FeishuAdapter,
            "dingtalk": DingTalkAdapter,
            "slack": SlackAdapter,
            "email": EmailAdapter,
            "webhook": WebhookAdapter,
        }
        cls = adapter_map.get(channel_type)
        if cls:
            self._adapters[name] = cls(adapter_config)

    def register(self, name: str, channel_type: str, config: Dict[str, Any]) -> Dict:
        self._create_adapter(name, {"channel": channel_type, "config": config})
        self._save_config()
        return {"name": name, "channel_type": channel_type, "status": "registered"}

    def unregister(self, name: str) -> bool:
        if name in self._adapters:
            del self._adapters[name]
            self._save_config()
            return True
        return False

    def get_adapter(self, name: str) -> Optional[ChannelAdapter]:
        return self._adapters.get(name)

    def list_channels(self) -> List[Dict]:
        return [
            {"name": name, "channel": adapter.channel_name, "status": "active"}
            for name, adapter in self._adapters.items()
        ]

    async def broadcast(self, content: str, channels: List[str] = None) -> List[Dict]:
        """广播到指定或全部频道"""
        targets = channels or list(self._adapters.keys())
        results = []
        for t in targets:
            adapter = self._adapters.get(t)
            if adapter:
                msg = await adapter.send_message("broadcast", content)
                results.append(msg.to_dict())
        return results

    async def send_notification(self, channel_name: str, target: str,
                                notification: Dict) -> Optional[Dict]:
        """发送含product_id深度链接的通知"""
        adapter = self._adapters.get(channel_name)
        if not adapter:
            return None
        msg = await adapter.send_notification(target, notification)
        return msg.to_dict()


# ── 单例 ──────────────────────────────────────────

_channel_registry: Optional[ChannelRegistry] = None


def get_channel_registry() -> ChannelRegistry:
    global _channel_registry
    if _channel_registry is None:
        _channel_registry = ChannelRegistry()
    return _channel_registry
