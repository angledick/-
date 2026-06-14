"""BaseEventListener — 外部事件监听器抽象基类。

所有外部事件源（飞书、钉钉等）的监听器都需要继承此基类。
"""

from __future__ import annotations

import abc
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class BaseEventListener(abc.ABC):
    """外部事件监听器抽象基类。"""

    def __init__(self):
        self.on_event: Optional[Callable] = None
        self._main_loop: Optional[object] = None  # asyncio.AbstractEventLoop

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """监听器名称。"""
        ...

    @abc.abstractmethod
    async def start(self):
        """启动监听。"""
        ...

    @abc.abstractmethod
    async def stop(self):
        """停止监听。"""
        ...

    def _emit(self, event_data: dict):
        """将解析后的事件数据传递给事件回调。

        支持从主事件循环或后台线程调用：
        - 主循环中：直接 create_task
        - 后台线程中：通过 run_coroutine_threadsafe 调度到主循环
        """
        if not self.on_event:
            return
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.on_event(event_data))
        except RuntimeError:
            # 从后台线程调用 → 调度到主事件循环
            main_loop = getattr(self, '_main_loop', None)
            if main_loop and main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.on_event(event_data), main_loop,
                )
            else:
                # 无主循环引用 → 在新循环中同步执行（阻塞）
                asyncio.run(self.on_event(event_data))
