#!/usr/bin/env python3
"""米塔AI搜索 — 独立可执行工具脚本。

Agent 可通过 Python 命令传参运行:
  python data/tools/impl/metaso_search.py --query "欧盟 2026年 电子产品 新法规" --count 5

也可通过 JSON stdin 传参:
  echo '{"q": "搜索内容", "count": 5}' | python data/tools/impl/metaso_search.py --stdin

环境变量:
  METASO_API_KEY  — API Key（必需）
  METASO_API_URL  — API 地址（可选，默认 https://metaso.cn/api/v1/search）

输出: JSON 格式搜索结果到 stdout
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ── 配置 ──────────────────────────────────────────

DEFAULT_API_URL = "https://metaso.cn/api/v1/search"


def _get_api_config():
    """从环境变量或 .env 文件获取 API 配置。"""
    api_key = os.environ.get("METASO_API_KEY", "")
    api_url = os.environ.get("METASO_API_URL", DEFAULT_API_URL)

    # 回退: 从 backend/.env 文件读取
    if not api_key:
        env_file = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key == "METASO_API_KEY":
                    api_key = value
                elif key == "METASO_API_URL" and value:
                    api_url = value

    return api_key, api_url


# ── 搜索逻辑 ──────────────────────────────────────

def search(query: str, count: int = 5) -> dict:
    """执行米塔搜索，返回结果字典。"""
    api_key, api_url = _get_api_config()

    if not api_key:
        return {"error": "METASO_API_KEY 未配置。请在 .env 或环境变量中设置。"}

    if not query:
        return {"error": "搜索查询不能为空"}

    count = min(max(count, 1), 10)

    try:
        import httpx
    except ImportError:
        # 回退: 使用 urllib
        return _search_urllib(query, count, api_key, api_url)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "scope": "all",
        "size": count,
        "searchFile": False,
        "includeSummary": False,
        "conciseSnippet": True,
        "format": "chat_completions",
    }

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(api_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return {"error": "米塔搜索请求超时"}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP 错误: {e.response.status_code}"}
    except Exception as e:
        return {"error": f"请求失败: {e}"}

    return _parse_response(data, query)


def _search_urllib(query: str, count: int, api_key: str, api_url: str) -> dict:
    """使用标准库 urllib 的搜索回退。"""
    import urllib.request
    import urllib.error

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({
        "q": query,
        "scope": "all",
        "size": count,
        "searchFile": False,
        "includeSummary": False,
        "conciseSnippet": True,
        "format": "chat_completions",
    }).encode("utf-8")

    req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {"error": f"请求失败: {e}"}
    except Exception as e:
        return {"error": f"请求失败: {e}"}

    return _parse_response(data, query)


def _parse_response(data: dict, query: str) -> dict:
    """解析 API 返回为统一格式。"""
    webpages = data.get("webpages", [])
    results = []
    for wp in webpages:
        results.append({
            "title": wp.get("title", ""),
            "link": wp.get("link", ""),
            "snippet": wp.get("snippet", ""),
            "score": wp.get("score", ""),
        })
    return {
        "query": query,
        "total": len(results),
        "credits_used": data.get("credits", 0),
        "results": results,
    }


# ── CLI 入口 ──────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="米塔AI搜索 — 联网搜索实时信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python metaso_search.py --query "欧盟 CE 认证 2026"
  python metaso_search.py --query "VAT税率 德国" --count 3
  echo '{"q": "搜索内容"}' | python metaso_search.py --stdin
        """,
    )
    parser.add_argument("--query", "-q", type=str, help="搜索查询语句")
    parser.add_argument("--count", "-c", type=int, default=5, help="返回结果数量 (1-10, 默认5)")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON 参数")
    parser.add_argument("--pretty", action="store_true", help="美化 JSON 输出")

    args = parser.parse_args()

    if args.stdin:
        try:
            stdin_data = json.loads(sys.stdin.read())
            query = stdin_data.get("q", stdin_data.get("query", ""))
            count = stdin_data.get("count", stdin_data.get("size", 5))
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"stdin JSON 解析失败: {e}"}, ensure_ascii=False))
            sys.exit(1)
    elif args.query:
        query = args.query
        count = args.count
    else:
        parser.print_help()
        sys.exit(1)

    result = search(query, count)

    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))

    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
