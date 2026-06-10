#!/usr/bin/env python3
"""OpenCLI 浏览器控制 — 独立可执行工具脚本。

Agent 可通过 Python 命令传参运行:
  python data/tools/impl/opencli_browser.py --action status
  python data/tools/impl/opencli_browser.py --action site --site hackernews --command top
  python data/tools/impl/opencli_browser.py --action navigate --params '{"url": "https://..."}'
  python data/tools/impl/opencli_browser.py --action snapshot

也可通过 JSON stdin 传参:
  echo '{"action": "site", "site": "github", "command": "trending"}' | python opencli_browser.py --stdin

两种调用路径：
  1. subprocess  — 调用 `opencli <site> <command>` 获取结构化数据（不需要浏览器）
  2. daemon HTTP — 向 localhost:19825 发送浏览器自动化命令（需要 Chrome + 扩展）

输出: JSON 格式结果到 stdout
"""

import argparse
import asyncio
import json
import subprocess
import sys
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

DAEMON_URL = "http://localhost:19825"
DAEMON_HEADERS = {"X-OpenCLI": "true", "Content-Type": "application/json"}
OPENCLI_BIN = "opencli"


# ── 守护进程健康 ──────────────────────────────────────────────────────

async def daemon_alive() -> bool:
    if httpx is None:
        return False
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            r = await c.get(f"{DAEMON_URL}/ping")
            return r.status_code == 200
    except Exception:
        return False


# ── subprocess: 站点命令（无浏览器） ──────────────────────────────────

def run_site_command(site: str, command: str, args: list[str] | None = None, timeout: int = 20) -> dict:
    """执行 opencli <site> <command> [args] -f json，返回解析后的数据。"""
    cmd = [OPENCLI_BIN, site, command] + (args or []) + ["-f", "json"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8",
        )
        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            if "not found" in stderr.lower() or "不是内部" in stderr:
                return {"ok": False, "error": f"opencli 未安装或不在 PATH 中"}
            return {"ok": False, "error": stderr or f"exit code {proc.returncode}"}

        stdout = proc.stdout.strip()
        if not stdout:
            return {"ok": True, "data": []}

        try:
            data = json.loads(stdout)
            return {"ok": True, "data": data}
        except json.JSONDecodeError:
            lines = [l.strip() for l in stdout.split("\n") if l.strip()]
            return {"ok": True, "data": lines}

    except FileNotFoundError:
        return {"ok": False, "error": "opencli 命令未找到，请安装: npm i -g @anthropic/opencli"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"命令超时 ({timeout}s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_available_sites() -> list[str]:
    """获取可用站点列表。"""
    try:
        proc = subprocess.run(
            [OPENCLI_BIN, "list"], capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            return [l.strip() for l in proc.stdout.strip().split("\n") if l.strip()]
    except Exception:
        pass
    return [
        "hackernews", "github", "reddit", "bilibili", "zhihu",
        "weibo", "twitter", "youtube", "producthunt", "linkedin",
    ]


# ── daemon HTTP: 浏览器自动化命令 ──────────────────────────────────

async def _send_daemon_command(action: str, params: dict | None = None) -> dict:
    """向 OpenCLI 守护进程发送命令。"""
    if httpx is None:
        return {"ok": False, "error": "httpx 未安装"}
    try:
        payload = {"action": action, **(params or {})}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{DAEMON_URL}/command", json=payload, headers=DAEMON_HEADERS)
            if r.status_code == 200:
                data = r.json()
                return {"ok": True, **data}
            return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "守护进程响应超时"}
    except httpx.ConnectError:
        return {"ok": False, "error": "无法连接守护进程，请执行 opencli daemon start"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def browser_action(action: str, params: dict | None = None, session: str = "default") -> dict:
    """执行浏览器自动化命令。"""
    if not await daemon_alive():
        return {"ok": False, "error": "OpenCLI 守护进程未运行，请执行 opencli daemon start"}
    full_params = {**(params or {})}
    if session and session != "default" and "contextId" not in full_params:
        full_params["contextId"] = session
    return await _send_daemon_command(action, full_params)


async def browser_navigate(url: str, session: str = "default") -> dict:
    """导航到指定 URL。"""
    result = await browser_action("navigate", {"url": url}, session)
    if result.get("ok"):
        title_r = await browser_action("exec", {"expression": "document.title"}, session)
        url_r = await browser_action("exec", {"expression": "location.href"}, session)
        return {
            "ok": True,
            "url": url_r.get("value", url),
            "title": title_r.get("value", ""),
        }
    return result


async def browser_snapshot(session: str = "default") -> dict:
    """获取当前页面的可访问性快照。"""
    return await browser_action("exec", {
        "expression": "document.documentElement.innerText.slice(0, 3000)",
    }, session)


# ── 主入口 ────────────────────────────────────────────────────────────

async def _dispatch(action: str, params: dict) -> dict:
    """根据 action 分发到对应处理器。"""
    if action == "status":
        alive = await daemon_alive()
        sites = list_available_sites()
        return {"ok": True, "daemon_running": alive, "daemon_url": DAEMON_URL, "sites": sites[:60]}

    elif action == "site":
        site = params.get("site", "")
        command = params.get("command", "")
        args = params.get("args", [])
        if not site or not command:
            return {"ok": False, "error": "site 和 command 参数必填"}
        return run_site_command(site, command, args)

    elif action == "navigate":
        url = params.get("url", "")
        if not url:
            return {"ok": False, "error": "url 参数必填"}
        session = params.get("session", "default")
        return await browser_navigate(url, session)

    elif action == "snapshot":
        session = params.get("session", "default")
        return await browser_snapshot(session)

    elif action == "action":
        browser_act = params.get("browser_action", "")
        browser_params = params.get("browser_params", {})
        session = params.get("session", "default")
        if not browser_act:
            return {"ok": False, "error": "browser_action 参数必填"}
        return await browser_action(browser_act, browser_params, session)

    else:
        return {"ok": False, "error": f"未知 action: {action}，可选: status|site|navigate|snapshot|action"}


def main():
    parser = argparse.ArgumentParser(
        description="OpenCLI 浏览器控制 — 站点数据获取 + 浏览器自动化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python opencli_browser.py --action status
  python opencli_browser.py --action site --site hackernews --command top
  python opencli_browser.py --action navigate --params '{"url": "https://github.com"}'
  python opencli_browser.py --action snapshot
  echo '{"action": "site", "site": "github", "command": "trending"}' | python opencli_browser.py --stdin
        """,
    )
    parser.add_argument("--action", "-a", type=str, help="操作: status|site|navigate|snapshot|action")
    parser.add_argument("--site", type=str, default="", help="站点名称（site action 用）")
    parser.add_argument("--command", type=str, default="", help="站点命令（site action 用）")
    parser.add_argument("--params", "-p", type=str, default="{}", help="JSON 格式参数")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON 参数")
    parser.add_argument("--pretty", action="store_true", help="美化 JSON 输出")

    args = parser.parse_args()

    if args.stdin:
        try:
            stdin_data = json.loads(sys.stdin.read())
            action = stdin_data.get("action", "status")
            params = {k: v for k, v in stdin_data.items() if k != "action"}
        except json.JSONDecodeError as e:
            print(json.dumps({"ok": False, "error": f"stdin JSON 解析失败: {e}"}, ensure_ascii=False))
            sys.exit(1)
    elif args.action:
        action = args.action
        params = {}
        if args.site:
            params["site"] = args.site
        if args.command:
            params["command"] = args.command
        try:
            extra = json.loads(args.params) if args.params != "{}" else {}
            params.update(extra)
        except json.JSONDecodeError:
            pass
    else:
        parser.print_help()
        sys.exit(1)

    result = asyncio.run(_dispatch(action, params))

    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))

    if not result.get("ok", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
