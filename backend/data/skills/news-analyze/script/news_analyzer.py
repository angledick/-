#!/usr/bin/env python3
"""新闻 AI 分析器 — 独立可执行工具脚本。

Agent 可通过 Python 命令传参运行:
  python data/tools/impl/news_analyzer.py --limit 20
  python data/tools/impl/news_analyzer.py --summary --hours 24

也可通过 JSON stdin 传参:
  echo '{"limit": 20}' | python news_analyzer.py --stdin

使用已配置的 OpenAI 兼容 LLM（MiMo 等）分析新闻风险方向。

输出: JSON 格式分析结果到 stdout
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是一个专业的金融风险分析师，专注于跨境电商合规与市场风险。

任务：分析新闻对跨境电商卖家的潜在风险。

**输出要求（严格 JSON，无多余文字）：**
{
  "risk_direction": "利多" | "利空" | "中性",
  "risk_level": "high" | "medium" | "low",
  "affected_markets": ["欧盟", "美国", "日本", ...],
  "logic": "简要说明为什么对跨境电商有影响（50字以内）",
  "confidence": 0.0~1.0
}

**判断原则：**
- "利多"：有利于跨境贸易（如关税降低、市场开放、合规放松）
- "利空"：不利于跨境贸易（如贸易制裁、新合规要求、市场准入收紧）
- "中性"：影响不明确或与跨境电商关联度低
- risk_level 根据影响程度：high=直接重大影响，medium=间接影响，low=边际影响

**禁止：**
- 预测价格或汇率
- 给出投资买卖建议
"""


def _get_llm_config() -> tuple[str, str, str]:
    """获取 LLM 配置（API Key, Base URL, Model）。"""
    # 优先从环境变量读取
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "")
    model = os.environ.get("LLM_MODEL", "mimo-v2.5-pro")

    # 回退：从 app.config 读取 anthropic_api_key
    if not api_key:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
            from app.config import settings
            api_key = settings.anthropic_api_key
            base_url = base_url or "https://openrouter.ai/api/v1"
        except Exception:
            pass

    # 再回退：从 .env 文件读取
    if not api_key:
        env_file = Path(__file__).resolve().parents[4] / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key == "LLM_API_KEY" and not api_key:
                    api_key = value
                elif key == "LLM_BASE_URL" and not base_url:
                    base_url = value
                elif key == "LLM_MODEL" and value:
                    model = value

    return api_key, base_url or "https://openrouter.ai/api/v1", model


def analyze_single(news: dict) -> dict | None:
    """分析单条新闻，返回分析结果字典，失败返回 None。"""
    api_key, base_url, model = _get_llm_config()
    if not api_key:
        log.warning("LLM API Key 未配置，跳过分析")
        return None

    user_prompt = (
        f"来源：{news['source']}\n"
        f"时间：{news['time']}\n"
        f"标题：{news['title']}\n"
        f"内容：{news.get('content', '')[:400]}"
    )

    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_completion_tokens=200,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        result = json.loads(raw)
        return {
            "news_id": news["id"],
            "risk_direction": result.get("risk_direction", "中性"),
            "risk_level": result.get("risk_level", "low"),
            "affected_markets": result.get("affected_markets", []),
            "logic": result.get("logic", ""),
            "confidence": float(result.get("confidence", 0.5)),
        }
    except Exception as e:
        log.warning("分析失败 [%s]: %s", news.get("title", "")[:30], e)
        return None


def run_batch_analysis(limit: int = 20) -> dict:
    """分析未处理的新闻，返回统计。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from app.storage.news_store import get_unanalyzed_news, save_analysis
    except ImportError as e:
        return {"error": f"无法导入 news_store: {e}", "analyzed": 0}

    pending = get_unanalyzed_news(limit)
    if not pending:
        return {"analyzed": 0, "message": "没有待分析的新闻"}

    done = 0
    results = []
    for news in pending:
        result = analyze_single(news)
        if result:
            save_analysis(result)
            results.append(result)
            done += 1
        time.sleep(0.5)  # 限速

    return {"analyzed": done, "total_pending": len(pending), "results": results}


def get_market_summary(hours: int = 24) -> dict:
    """生成最近 N 小时的跨境市场风险摘要。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from app.storage.news_store import get_recent_news
    except ImportError as e:
        return {"error": f"无法导入 news_store: {e}"}

    news_list = get_recent_news(hours=hours, limit=50)
    high_risk = [
        n for n in news_list
        if n.get("risk_level") == "high" and n.get("risk_direction") in ("利多", "利空")
    ]
    bullish = [n for n in news_list if n.get("risk_direction") == "利多"]
    bearish = [n for n in news_list if n.get("risk_direction") == "利空"]

    overall = "中性"
    if len(bearish) > len(bullish) * 1.5:
        overall = "利空偏向"
    elif len(bullish) > len(bearish) * 1.5:
        overall = "利多偏向"

    return {
        "overall_direction": overall,
        "bullish_count": len(bullish),
        "bearish_count": len(bearish),
        "neutral_count": len(news_list) - len(bullish) - len(bearish),
        "high_risk_news": high_risk[:5],
        "period_hours": hours,
    }


# ── CLI 入口 ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="新闻 AI 分析器 — LLM 风险方向分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--limit", type=int, default=20, help="分析条数上限")
    parser.add_argument("--summary", action="store_true", help="输出市场风险摘要")
    parser.add_argument("--hours", type=int, default=24, help="摘要时间窗口（小时）")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON 参数")
    parser.add_argument("--pretty", action="store_true", help="美化 JSON 输出")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.stdin:
        try:
            stdin_data = json.loads(sys.stdin.read())
            if stdin_data.get("summary"):
                result = get_market_summary(stdin_data.get("hours", 24))
            else:
                result = run_batch_analysis(stdin_data.get("limit", 20))
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"stdin JSON 解析失败: {e}"}, ensure_ascii=False))
            sys.exit(1)
    elif args.summary:
        result = get_market_summary(args.hours)
    else:
        result = run_batch_analysis(args.limit)

    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))

    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
