"""风险预警引擎 — 预警生成、持久化、查询。

数据流转:
  - Market Monitor / AstraAssistant 生成原始事件
  - Risk Alert Engine 包装为 RiskAlert 模型
  - 写入 data/risk_alerts/{user_id}/alerts.json
  - WebSocket 实时推送 + REST API 轮询拉取（双通道）
"""

import json
import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


def _get_alerts_dir(user_id: str) -> Path:
    """获取用户预警存储目录。"""
    return Path(settings.data_dir).resolve() / "risk_alerts" / user_id


def _ensure_dir(path: Path):
    """确保目录存在。"""
    path.mkdir(parents=True, exist_ok=True)


def create_alert(
    alert_type: str,
    severity: str,
    title: str,
    description: str,
    affected_products: Optional[list[str]] = None,
    affected_markets: Optional[list[str]] = None,
    source: str = "",
    source_url: str = "",
    user_ids: Optional[list[str]] = None,
) -> dict:
    """生成预警并持久化。

    Args:
        alert_type: 预警类型 (regulation_change / market_hotspot / product_impacted)
        severity: 严重度 (low / medium / high / critical)
        title: AstraAssistant 生成的标题
        description: AstraAssistant 生成的描述
        affected_products: 受影响产品 ID 列表
        affected_markets: 受影响市场列表
        source: 数据源
        source_url: 原文链接
        user_ids: 推送到哪些用户的收件箱

    Returns:
        dict: 创建的预警对象
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    alert = {
        "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
        "alert_type": alert_type,
        "severity": severity,
        "title": title,
        "description": description,
        "affected_products": affected_products or [],
        "affected_markets": affected_markets or [],
        "source": source,
        "source_url": source_url,
        "dismissed": False,
        "created_at": now,
    }

    if user_ids:
        for uid in user_ids:
            _save_alert(uid, alert)
        logger.info(f"Alert {alert['alert_id']} saved for {len(user_ids)} users")
    else:
        logger.info(f"Alert {alert['alert_id']} created (no users)")

    return alert


def dismiss_alert(alert_id: str, user_id: str) -> bool:
    """用户忽略预警。"""
    alerts = get_alerts(user_id)
    for alert in alerts:
        if alert["alert_id"] == alert_id:
            alert["dismissed"] = True
            _save_alerts(user_id, alerts)
            logger.info(f"Alert {alert_id} dismissed for user {user_id}")
            return True
    logger.warning(f"Alert {alert_id} not found for user {user_id}")
    return False


def get_alerts(
    user_id: str,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> list[dict]:
    """获取用户预警列表。"""
    alerts_dir = _get_alerts_dir(user_id)
    alerts_file = alerts_dir / "alerts.json"
    if not alerts_file.exists():
        return []

    try:
        with open(alerts_file, "r", encoding="utf-8") as f:
            alerts = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to read alerts for {user_id}: {e}")
        return []

    # 筛选
    if alert_type:
        alerts = [a for a in alerts if a.get("alert_type") == alert_type]
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]

    # 按时间降序
    alerts.sort(key=lambda a: a.get("created_at", ""), reverse=True)

    # 分页
    start = (page - 1) * size
    end = start + size
    return alerts[start:end]


def get_unread_count(user_id: str) -> int:
    """获取未读预警数（未 dismissed 的预警数）。"""
    alerts = get_alerts(user_id)
    return sum(1 for a in alerts if not a.get("dismissed", False))


def get_alerts_for_product(user_id: str, product_id: str) -> list[dict]:
    """获取某产品的关联预警。"""
    all_alerts = get_alerts(user_id, size=1000)
    return [a for a in all_alerts if product_id in a.get("affected_products", [])]


def get_last_scan_time(user_id: str) -> Optional[str]:
    """获取最后一次市场扫描时间。"""
    scan_file = _get_alerts_dir(user_id) / "last_scan.json"
    if scan_file.exists():
        try:
            with open(scan_file, "r") as f:
                return json.load(f).get("last_scan", None)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_last_scan_time(user_id: str):
    """保存市场扫描时间。"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_file = _get_alerts_dir(user_id) / "last_scan.json"
    _ensure_dir(scan_file.parent)
    with open(scan_file, "w", encoding="utf-8") as f:
        json.dump({"last_scan": now}, f, ensure_ascii=False, indent=2)


def _save_alert(user_id: str, alert: dict):
    """将单条预警追加到用户文件。"""
    alerts = get_alerts(user_id, size=1000)
    alerts.insert(0, alert)
    _save_alerts(user_id, alerts)


def _save_alerts(user_id: str, alerts: list[dict]):
    """覆盖写入用户预警列表。"""
    alerts_dir = _get_alerts_dir(user_id)
    _ensure_dir(alerts_dir)
    tmp_file = alerts_dir / "alerts.json.tmp"
    final_file = alerts_dir / "alerts.json"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)
    tmp_file.replace(final_file)
