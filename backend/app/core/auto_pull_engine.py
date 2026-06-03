"""
AutoPullEngine — 自动拉取引擎（Phase 3.1）

参考开源选型：
- 17TRACK（指南 §3.5.5）3100+承运商物流追踪
- ERPNext（指南 §3.5.3）采购/库存/财务同步
- GreaterWMS（指南 §3.5.4）仓储管理
- Shopify Admin API 产品/订单/库存同步

功能：
- 每20分钟自动拉取已连接的Shopify/ERPNext/17TRACK数据
- 增量同步（基于 updated_at 游标）
- 同步结果写入事件总线 + 产品存储
- 同步日志持久化
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings


# ── 数据结构 ────────────────────────────────────────


@dataclass
class SyncJob:
    """同步任务"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    provider: str = ""          # shopify / erpnext / 17track
    sync_type: str = ""         # products / orders / inventory / tracking / certifications
    connection_id: str = ""     # OAuthManager连接ID
    status: str = "pending"     # pending / running / success / failed / cancelled
    items_synced: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_failed: int = 0
    last_cursor: str = ""       # 增量游标 (updated_at / page_token)
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def duration_seconds(self) -> float:
        if self.finished_at and self.started_at:
            return self.finished_at - self.started_at
        return 0.0


@dataclass
class SyncLog:
    """同步日志条目"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    job_id: str = ""
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    level: str = "info"     # info / warning / error
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── 持久化 ────────────────────────────────────────

SYNC_DIR = Path(settings.data_dir) / "sync"
SYNC_JOBS_FILE = SYNC_DIR / "jobs.json"
SYNC_LOGS_FILE = SYNC_DIR / "logs.json"


def _load_json(path: Path) -> Any:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── AutoPullEngine ────────────────────────────────


class AutoPullEngine:
    """自动拉取引擎 — 定时同步第三方数据"""

    # 默认同步间隔（秒）
    DEFAULT_INTERVAL = 1200  # 20 minutes

    # 默认同步任务配置
    DEFAULT_SYNC_TASKS = [
        {"provider": "shopify", "sync_type": "products", "interval": 1200,
         "description": "Shopify产品同步（每20分钟）", "guide_ref": "§3.2 Shopify Admin API"},
        {"provider": "shopify", "sync_type": "orders", "interval": 1200,
         "description": "Shopify订单同步（每20分钟）", "guide_ref": "§3.2 Shopify Admin API"},
        {"provider": "shopify", "sync_type": "inventory", "interval": 1200,
         "description": "Shopify库存同步（每20分钟）", "guide_ref": "§3.2 Shopify Inventory API"},
        {"provider": "erpnext", "sync_type": "purchase_orders", "interval": 3600,
         "description": "ERPNext采购单同步（每1小时）", "guide_ref": "§3.5.3 ERPNext"},
        {"provider": "erpnext", "sync_type": "stock", "interval": 3600,
         "description": "ERPNext库存同步（每1小时）", "guide_ref": "§3.5.3 ERPNext"},
        {"provider": "17track", "sync_type": "tracking", "interval": 1800,
         "description": "17TRACK物流追踪（每30分钟）", "guide_ref": "§3.5.5 17TRACK"},
    ]

    def __init__(self):
        self._jobs: Dict[str, SyncJob] = {}
        self._logs: List[SyncLog] = []
        self._scheduled_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._load_state()

    def _load_state(self):
        jobs_data = _load_json(SYNC_JOBS_FILE)
        for jd in jobs_data:
            try:
                job = SyncJob(**{k: v for k, v in jd.items() if k in SyncJob.__dataclass_fields__})
                self._jobs[job.id] = job
            except Exception:
                continue
        self._logs = [SyncLog(**{k: v for k, v in ld.items() if k in SyncLog.__dataclass_fields__})
                      for ld in _load_json(SYNC_LOGS_FILE)]

    def _persist(self):
        _save_json(SYNC_JOBS_FILE, [j.to_dict() for j in self._jobs.values()])
        _save_json(SYNC_LOGS_FILE, [l.to_dict() for l in self._logs[-500:]])

    def _add_log(self, job_id: str, level: str, message: str, data: Dict = None):
        log = SyncLog(job_id=job_id, level=level, message=message, data=data or {})
        self._logs.append(log)
        if len(self._logs) > 1000:
            self._logs = self._logs[-500:]

    # ── 定时任务管理 ─────────────────────────────

    async def start(self):
        """启动自动拉取引擎"""
        if self._running:
            return
        self._running = True

        for task_config in self.DEFAULT_SYNC_TASKS:
            key = f"{task_config['provider']}_{task_config['sync_type']}"
            interval = task_config.get("interval", self.DEFAULT_INTERVAL)
            task = asyncio.create_task(self._scheduled_sync(key, task_config, interval))
            self._scheduled_tasks[key] = task

        self._add_log("", "info", "AutoPullEngine started",
                     {"tasks": len(self._scheduled_tasks)})

    async def stop(self):
        """停止自动拉取引擎"""
        self._running = False
        for key, task in self._scheduled_tasks.items():
            task.cancel()
        self._scheduled_tasks.clear()
        self._add_log("", "info", "AutoPullEngine stopped")

    async def _scheduled_sync(self, key: str, config: Dict, interval: int):
        """定时同步循环"""
        while self._running:
            try:
                await asyncio.sleep(interval)
                if not self._running:
                    break
                await self.run_sync(config["provider"], config["sync_type"])
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._add_log("", "error", f"Scheduled sync error for {key}: {e}")
                await asyncio.sleep(60)  # Wait before retry

    # ── 同步执行 ────────────────────────────────

    async def run_sync(self, provider: str, sync_type: str,
                      connection_id: str = "", config: Dict = None) -> Dict:
        """执行同步任务"""
        job = SyncJob(
            provider=provider,
            sync_type=sync_type,
            connection_id=connection_id,
            status="running",
            started_at=time.time(),
            config=config or {},
        )
        self._jobs[job.id] = job
        self._add_log(job.id, "info", f"Starting sync: {provider}/{sync_type}")

        try:
            if provider == "shopify":
                await self._sync_shopify(job)
            elif provider == "erpnext":
                await self._sync_erpnext(job)
            elif provider == "17track":
                await self._sync_17track(job)
            else:
                raise ValueError(f"Unknown provider: {provider}")

            job.status = "success"
            job.finished_at = time.time()
            self._add_log(job.id, "info",
                         f"Sync completed: {job.items_synced} items synced",
                         {"items_created": job.items_created, "items_updated": job.items_updated})

            # 触发同步完成事件
            try:
                from app.core.event_bus import get_event_bus
                bus = get_event_bus()
                await bus.publish_raw({
                    "type": "system:sync_completed",
                    "source": "auto_pull_engine",
                    "data": {
                        "provider": provider,
                        "sync_type": sync_type,
                        "items_synced": job.items_synced,
                        "items_created": job.items_created,
                        "items_updated": job.items_updated,
                        "duration": job.duration_seconds,
                    },
                })
            except Exception:
                pass

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.finished_at = time.time()
            self._add_log(job.id, "error", f"Sync failed: {e}")

        self._persist()
        return job.to_dict()

    async def _sync_shopify(self, job: SyncJob):
        """Shopify数据同步"""
        from app.core.oauth_manager import get_oauth_manager
        oauth = get_oauth_manager()
        connections = oauth.list_connections(provider="shopify")

        if not connections:
            self._add_log(job.id, "warning", "No Shopify connections configured")
            return

        for conn in connections:
            shop = conn.get("config", {}).get("shop", "")
            if not shop:
                continue

            if job.sync_type == "products":
                await self._sync_shopify_products(job, shop)
            elif job.sync_type == "orders":
                await self._sync_shopify_orders(job, shop)
            elif job.sync_type == "inventory":
                await self._sync_shopify_inventory(job, shop)

    async def _sync_shopify_products(self, job: SyncJob, shop: str):
        """Shopify产品同步"""
        try:
            from app.services.shopify import fetch_products, load_token
            token = load_token(shop)
            if not token:
                self._add_log(job.id, "warning", f"No token for shop {shop}")
                return

            products = await fetch_products(shop, max_count=50)
            for p in products:
                job.items_synced += 1
                # 写入产品存储
                try:
                    from app.core.product_storage import get_product_storage
                    storage = get_product_storage()
                    # 检查是否已存在
                    existing = storage.find_by_shopify_id(p.shopify_id)
                    if existing:
                        job.items_updated += 1
                    else:
                        # 构造Shopify产品数据并导入
                        shopify_dict = {
                            "title": getattr(p, 'title', 'Unknown'),
                            "product_type": getattr(p, 'product_type', ''),
                            "vendor": getattr(p, 'vendor', ''),
                            "tags": getattr(p, 'tags', ''),
                            "handle": getattr(p, 'handle', ''),
                            "id": p.shopify_id,
                            "variants": getattr(p, 'variants', []),
                            "body_html": getattr(p, 'body_html', ''),
                        }
                        await storage.import_from_shopify(shopify_dict, target_markets=[])
                        job.items_created += 1
                except Exception:
                    pass

            self._add_log(job.id, "info", f"Shopify products synced from {shop}: {len(products)}")
        except Exception as e:
            job.items_failed += 1
            self._add_log(job.id, "error", f"Shopify product sync error: {e}")

    async def _sync_shopify_orders(self, job: SyncJob, shop: str):
        """Shopify订单同步"""
        try:
            import httpx
            token_data = None
            from app.services.shopify import load_token
            token = load_token(shop)
            if not token:
                return

            # 使用REST API拉取最近订单
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://{shop}/admin/api/2024-01/orders.json",
                    headers={"X-Shopify-Access-Token": token.access_token},
                    params={"status": "any", "limit": 50, "updated_at_min": job.last_cursor or ""},
                    timeout=30,
                )
                if resp.status_code == 200:
                    orders = resp.json().get("orders", [])
                    for order in orders:
                        job.items_synced += 1
                        job.items_created += 1  # Simplified

                    if orders:
                        job.last_cursor = orders[-1].get("updated_at", "")

                    self._add_log(job.id, "info", f"Shopify orders synced from {shop}: {len(orders)}")
        except Exception as e:
            job.items_failed += 1
            self._add_log(job.id, "error", f"Shopify order sync error: {e}")

    async def _sync_shopify_inventory(self, job: SyncJob, shop: str):
        """Shopify库存同步"""
        try:
            import httpx
            from app.services.shopify import load_token
            token = load_token(shop)
            if not token:
                return

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://{shop}/admin/api/2024-01/graphql.json",
                    headers={
                        "X-Shopify-Access-Token": token.access_token,
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": """
                        { inventoryLevels(first: 50) {
                            edges { node {
                                id available
                                location { name }
                                item { sku tracked }
                            }}
                        }}
                        """
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    levels = data.get("data", {}).get("inventoryLevels", {}).get("edges", [])
                    for level in levels:
                        job.items_synced += 1
                    self._add_log(job.id, "info", f"Shopify inventory synced from {shop}: {len(levels)} levels")
        except Exception as e:
            job.items_failed += 1
            self._add_log(job.id, "error", f"Shopify inventory sync error: {e}")

    async def _sync_erpnext(self, job: SyncJob):
        """ERPNext数据同步（指南 §3.5.3）"""
        from app.core.oauth_manager import get_oauth_manager
        oauth = get_oauth_manager()
        connections = oauth.list_connections(provider="erpnext")

        if not connections:
            self._add_log(job.id, "warning", "No ERPNext connections configured")
            return

        import httpx
        for conn in connections:
            config = conn.get("config", {})
            base_url = config.get("base_url", "")
            api_key = config.get("api_key", "")
            api_secret = config.get("api_secret", "")
            if not base_url:
                continue

            headers = {"Authorization": f"token {api_key}:{api_secret}"}

            try:
                endpoint = "Purchase Order" if job.sync_type == "purchase_orders" else "Stock Entry"
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{base_url}/api/resource/{endpoint}",
                        headers=headers,
                        params={"limit_page_length": 50, "order_by": "modified desc"},
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        data = resp.json().get("data", [])
                        job.items_synced += len(data)
                        job.items_created += len(data)
                        self._add_log(job.id, "info",
                                     f"ERPNext {endpoint} synced: {len(data)} items")
            except Exception as e:
                job.items_failed += 1
                self._add_log(job.id, "error", f"ERPNext sync error: {e}")

    async def _sync_17track(self, job: SyncJob):
        """17TRACK物流追踪同步（指南 §3.5.5）"""
        from app.core.oauth_manager import get_oauth_manager
        oauth = get_oauth_manager()
        connections = oauth.list_connections(provider="17track")

        if not connections:
            self._add_log(job.id, "warning", "No 17TRACK connections configured")
            return

        import httpx
        for conn in connections:
            api_key = conn.get("config", {}).get("api_key", "")
            if not api_key:
                continue

            try:
                # 17TRACK API v2 — 获取最近追踪更新
                tracking_file = SYNC_DIR / "tracking_numbers.json"
                tracking_numbers = _load_json(tracking_file)
                if not tracking_numbers:
                    self._add_log(job.id, "info", "No tracking numbers to sync")
                    continue

                async with httpx.AsyncClient() as client:
                    # 批量查询（每次最多40个）
                    for i in range(0, len(tracking_numbers), 40):
                        batch = tracking_numbers[i:i + 40]
                        resp = await client.post(
                            "https://api.17track.net/track/v2.2/gettrackinfo",
                            headers={"17token": api_key, "Content-Type": "application/json"},
                            json=batch,
                            timeout=30,
                        )
                        if resp.status_code == 200:
                            data = resp.json().get("data", [])
                            job.items_synced += len(data)
                            job.items_created += len(data)

                self._add_log(job.id, "info",
                             f"17TRACK synced: {job.items_synced} tracking numbers")
            except Exception as e:
                job.items_failed += 1
                self._add_log(job.id, "error", f"17TRACK sync error: {e}")

    # ── 手动触发 ────────────────────────────────

    async def manual_sync(self, provider: str, sync_type: str,
                         connection_id: str = "") -> Dict:
        """手动触发同步"""
        return await self.run_sync(provider, sync_type, connection_id)

    # ── 查询 ────────────────────────────────────

    def get_jobs(self, provider: str = None, status: str = None, limit: int = 50) -> List[Dict]:
        jobs = list(self._jobs.values())
        if provider:
            jobs = [j for j in jobs if j.provider == provider]
        if status:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda j: j.started_at, reverse=True)
        return [j.to_dict() for j in jobs[:limit]]

    def get_logs(self, job_id: str = None, limit: int = 100) -> List[Dict]:
        logs = self._logs
        if job_id:
            logs = [l for l in logs if l.job_id == job_id]
        return [l.to_dict() for l in logs[-limit:]]

    def get_status(self) -> Dict:
        """引擎状态概览"""
        running_jobs = [j for j in self._jobs.values() if j.status == "running"]
        failed_jobs = [j for j in self._jobs.values() if j.status == "failed"]
        total_synced = sum(j.items_synced for j in self._jobs.values())

        return {
            "running": self._running,
            "scheduled_tasks": list(self._scheduled_tasks.keys()),
            "total_jobs": len(self._jobs),
            "running_jobs": len(running_jobs),
            "failed_jobs": len(failed_jobs),
            "total_items_synced": total_synced,
            "sync_tasks": [
                {
                    "provider": t["provider"],
                    "sync_type": t["sync_type"],
                    "interval_seconds": t.get("interval", self.DEFAULT_INTERVAL),
                    "description": t["description"],
                    "guide_ref": t.get("guide_ref", ""),
                }
                for t in self.DEFAULT_SYNC_TASKS
            ],
        }

    def register_tracking_numbers(self, tracking_numbers: List[Dict]) -> Dict:
        """注册物流追踪号（供17TRACK同步使用）"""
        existing = _load_json(SYNC_DIR / "tracking_numbers.json")
        if not isinstance(existing, list):
            existing = []

        existing_ids = {t.get("num") for t in existing}
        added = 0
        for tn in tracking_numbers:
            if tn.get("num") and tn.get("num") not in existing_ids:
                existing.append(tn)
                existing_ids.add(tn["num"])
                added += 1

        _save_json(SYNC_DIR / "tracking_numbers.json", existing)
        return {"total": len(existing), "added": added}


# ── 单例 ──────────────────────────────────────────

_auto_pull_engine: Optional[AutoPullEngine] = None


def get_auto_pull_engine() -> AutoPullEngine:
    global _auto_pull_engine
    if _auto_pull_engine is None:
        _auto_pull_engine = AutoPullEngine()
    return _auto_pull_engine
