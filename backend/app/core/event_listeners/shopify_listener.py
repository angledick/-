"""ShopifyEventListener — 定时直连 Shopify API 同步商品。

与旧版的区别：
  旧版: 后台线程定期下发事件到 Claude Agent SDK → shopify-ai-toolkit
  新版: 后台线程定期直连 Shopify Admin REST API → 同步到 ProductStorage

不经过事件驱动架构，直接调用 shopify_api.sync_to_local()。
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Optional

from app.core.event_listeners.base import BaseEventListener

logger = logging.getLogger(__name__)

# 定时同步间隔（秒）— 默认 30 分钟
SYNC_INTERVAL = 1800


class ShopifyEventListener(BaseEventListener):
    """Shopify 定时同步监听器 — 直连 Admin REST API。"""

    @property
    def name(self) -> str:
        return "shopify"

    def __init__(self, sync_interval: int = SYNC_INTERVAL):
        super().__init__()
        self._sync_interval = sync_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    async def start(self):
        self._main_loop = asyncio.get_running_loop()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="ShopifyEventListener",
        )
        self._thread.start()
        logger.info(
            "ShopifyEventListener 已启动 (interval=%ds, 直连同步模式)",
            self._sync_interval,
        )

    async def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("ShopifyEventListener 已停止")

    # ── 后台线程：定时同步 ──────────────────────────

    def _sync_loop(self):
        """后台守护线程：定时直连 Shopify API 同步商品。"""
        # 启动时等待 30 秒，让其他服务初始化
        time.sleep(30)

        while not self._stop_event.is_set():
            try:
                # 在主事件循环中执行 async 同步
                future = asyncio.run_coroutine_threadsafe(
                    self._do_sync(), self._main_loop
                )
                result = future.result(timeout=120)
                logger.info(
                    "ShopifyEventListener: 定时同步完成 synced=%s total=%s",
                    result.get("synced", 0),
                    result.get("total", 0),
                )
            except Exception as e:
                logger.warning("ShopifyEventListener: 定时同步失败: %s", e)

            # 等待下次同步
            self._stop_event.wait(self._sync_interval)

    async def _do_sync(self) -> dict:
        """执行一次 Shopify 商品同步。"""
        from app.services.shopify_api import sync_to_local
        return await sync_to_local(limit=250)
