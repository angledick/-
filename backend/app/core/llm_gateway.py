"""统一 LLM 网关 — 所有模块的 LLM 调用统一经过此处。

设计原则：
  - 单一入口：risk_intel_analyzer / lifecycle_analyzer / dispatcher 均使用此网关
  - 配置统一：从 routes.yaml 读取 provider/model/key/url，不散落在各模块
  - 可观测：统计调用次数、token 消耗、成功率
  - 降级透明：无 Key 时立即返回 None，调用方显式处理降级

使用方式：
    from app.core.llm_gateway import get_llm_gateway
    gw = get_llm_gateway()
    result = await gw.chat_json(role="risk_analysis", system=SYSTEM, user=USER)
    # result 是解析后的 dict；失败返回 None，调用方自行降级
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_ROUTES_FILE = Path(__file__).resolve().parents[2] / "data" / "models" / "routes.yaml"


# ─────────────────────────────────────────────────────────────────────────────
# 配置读取
# ─────────────────────────────────────────────────────────────────────────────

def _env(key: str, default: str = "") -> str:
    v = os.environ.get(key, "")
    if v:
        return v
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, val = line.partition("=")
            if k.strip() == key:
                return val.strip().strip('"').strip("'")
    return default


def _load_route(role: str) -> dict:
    """从 routes.yaml 加载指定角色的配置。"""
    try:
        import yaml
        data = yaml.safe_load(_ROUTES_FILE.read_text(encoding="utf-8"))
        route = data.get("routes", {}).get(role)
        if not route:
            route = data.get("routes", {}).get("risk_analysis", {})
        return route or {}
    except Exception:
        return {}


def get_model_config(role: str = "risk_analysis") -> dict:
    """返回完整的模型配置（优先 routes.yaml，回退 ZHIPUAI 环境变量）。"""
    route = _load_route(role)
    api_key_env = route.get("api_key_env", "ZHIPUAI_API_KEY")
    api_key = _env(api_key_env) or _env("ZHIPUAI_API_KEY") or _env("ANTHROPIC_API_KEY") or _env("LLM_API_KEY")
    base_url = route.get("base_url") or _env("ZHIPUAI_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4")
    model = route.get("model") or _env("ZHIPUAI_MODEL", "glm-5.1")
    return {
        "provider":   route.get("provider", "zhipu"),
        "api_key":    api_key,
        "base_url":   base_url,
        "model":      model,
        "max_tokens": max(int(route.get("max_tokens", 2000)), 2000),
        "temperature":float(route.get("temperature", 0.1)),
        "available":  bool(api_key),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 统计
# ─────────────────────────────────────────────────────────────────────────────

class _Stats:
    def __init__(self):
        self._calls:   dict[str, int]   = {}  # role → count
        self._tokens:  dict[str, int]   = {}  # role → total tokens
        self._errors:  dict[str, int]   = {}  # role → error count
        self._latency: dict[str, float] = {}  # role → total seconds

    def record(self, role: str, tokens: int, elapsed: float, error: bool = False):
        self._calls[role]   = self._calls.get(role, 0) + 1
        self._tokens[role]  = self._tokens.get(role, 0) + tokens
        self._latency[role] = self._latency.get(role, 0.0) + elapsed
        if error:
            self._errors[role] = self._errors.get(role, 0) + 1

    def summary(self) -> dict:
        result = {}
        for role in self._calls:
            n = self._calls[role]
            result[role] = {
                "calls":       n,
                "tokens":      self._tokens.get(role, 0),
                "errors":      self._errors.get(role, 0),
                "success_rate": round((n - self._errors.get(role, 0)) / n * 100, 1) if n else 0,
                "avg_latency_s": round(self._latency.get(role, 0) / n, 2) if n else 0,
            }
        return result


_stats = _Stats()


# ─────────────────────────────────────────────────────────────────────────────
# 网关主类
# ─────────────────────────────────────────────────────────────────────────────

class LLMGateway:
    """统一 LLM 调用网关。"""

    def __init__(self):
        self._clients: dict[str, object] = {}   # role → AsyncOpenAI client
        self._sema = asyncio.Semaphore(6)        # 全局并发限制

    def _get_client(self, role: str):
        """惰性初始化 OpenAI 兼容客户端。"""
        if role in self._clients:
            return self._clients[role]
        cfg = get_model_config(role)
        if not cfg["available"]:
            return None
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"] or None)
            self._clients[role] = client
            logger.info("[LLMGateway] 初始化 role=%s model=%s", role, cfg["model"])
            return client
        except ImportError:
            logger.error("[LLMGateway] openai 包未安装")
            return None
        except Exception as e:
            logger.error("[LLMGateway] 客户端初始化失败 role=%s: %s", role, e)
            return None

    def available(self, role: str = "risk_analysis") -> bool:
        return get_model_config(role)["available"]

    async def chat_json(
        self,
        system: str,
        user: str,
        role: str = "risk_analysis",
        retry: int = 2,
    ) -> Optional[dict]:
        """调用 LLM，强制 JSON 输出，返回解析后的 dict。失败返回 None。"""
        client = self._get_client(role)
        if not client:
            return None

        cfg = get_model_config(role)
        start = time.time()

        for attempt in range(retry + 1):
            try:
                async with self._sema:
                    resp = await client.chat.completions.create(
                        model=cfg["model"],
                        max_tokens=cfg["max_tokens"],
                        temperature=cfg["temperature"],
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user",   "content": user},
                        ],
                    )

                raw = resp.choices[0].message.content or ""
                tokens = getattr(resp.usage, "total_tokens", 0)
                elapsed = time.time() - start
                _stats.record(role, tokens, elapsed)

                parsed = self._parse_json(raw)
                if parsed is not None:
                    parsed["_model"] = cfg["model"]
                    parsed["_role"]  = role
                    return parsed

                logger.warning("[LLMGateway] JSON 解析失败 role=%s attempt=%d", role, attempt)

            except Exception as e:
                elapsed = time.time() - start
                _stats.record(role, 0, elapsed, error=True)
                err = str(e)
                if "rate_limit" in err.lower() or "429" in err:
                    wait = 15 * (attempt + 1)
                    logger.warning("[LLMGateway] 限流 role=%s，等待 %ds", role, wait)
                    await asyncio.sleep(wait)
                elif attempt < retry:
                    await asyncio.sleep(2.0 * (attempt + 1))
                else:
                    logger.error("[LLMGateway] 调用失败 role=%s: %s", role, e)
                    return None

        return None

    async def chat_text(
        self,
        system: str,
        user: str,
        role: str = "risk_analysis",
    ) -> Optional[str]:
        """调用 LLM，返回纯文本（无 JSON 强制）。"""
        client = self._get_client(role)
        if not client:
            return None
        cfg = get_model_config(role)
        start = time.time()
        try:
            async with self._sema:
                resp = await client.chat.completions.create(
                    model=cfg["model"],
                    max_tokens=cfg["max_tokens"],
                    temperature=cfg["temperature"],
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                )
            raw = resp.choices[0].message.content or ""
            _stats.record(role, getattr(resp.usage, "total_tokens", 0), time.time() - start)
            return raw.strip()
        except Exception as e:
            _stats.record(role, 0, time.time() - start, error=True)
            logger.error("[LLMGateway] chat_text 失败 role=%s: %s", role, e)
            return None

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        if not raw:
            return None
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            if text.startswith("json"):
                text = text[4:].lstrip()
        try:
            return json.loads(text)
        except Exception:
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e > s:
                try: return json.loads(text[s:e+1])
                except: pass
        return None

    def get_stats(self) -> dict:
        return _stats.summary()


# ─────────────────────────────────────────────────────────────────────────────
# 单例
# ─────────────────────────────────────────────────────────────────────────────

_gateway: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
