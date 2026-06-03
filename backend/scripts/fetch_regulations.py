#!/usr/bin/env python3
"""fetch_regulations.py — 合规文档官方源下载器

EUR-Lex (EU) 使用 Playwright (headless Chromium) 绕过 AWS WAF JS 挑战。
gesetze-im-internet.de (DE) 和 eCFR (US) 使用 httpx 直接请求。

用法:
    cd backend
    python scripts/fetch_regulations.py              # 全部（增量）
    python scripts/fetch_regulations.py --market eu  # 仅 EU
    python scripts/fetch_regulations.py --force      # 覆盖已有文件
    python scripts/fetch_regulations.py --dry-run    # 预览
    python scripts/fetch_regulations.py --list       # 查看目录
"""

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from typing import Optional

import httpx
import html2text as _h2t

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetch_regs")

OUT_DIR = ROOT / "data" / "regulations"

# ── 法规目录 ──────────────────────────────────────────────────────────────────
CATALOG: list[dict] = [
    # EU (EUR-Lex, Playwright) ───────────────────────────────────────────────
    {
        "id": "gpsr_2023",
        "name": "General Product Safety Regulation (GPSR) 2023/988/EU",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32023R0988",
        "effective_date": "2024-12-13",
        "tags": "product_safety,CE,market_surveillance",
        "note": "Replaces GPSD; mandatory for all consumer products from Dec 2024",
        "fetch": "playwright",
    },
    {
        "id": "lvd_2014",
        "name": "Low Voltage Directive (LVD) 2014/35/EU",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32014L0035",
        "effective_date": "2014-04-05",
        "tags": "electrical,CE,LVD",
        "note": "Electrical equipment 50-1000V AC / 75-1500V DC",
        "fetch": "playwright",
    },
    {
        "id": "emc_2014",
        "name": "Electromagnetic Compatibility Directive (EMC) 2014/30/EU",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32014L0030",
        "effective_date": "2014-04-05",
        "tags": "electrical,CE,EMC",
        "note": "All electrical/electronic equipment; immunity and emission limits",
        "fetch": "playwright",
    },
    {
        "id": "rohs_2011",
        "name": "RoHS Directive 2011/65/EU",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32011L0065",
        "effective_date": "2011-07-01",
        "tags": "chemical,electronics,RoHS,hazardous_substances",
        "note": "Restricts 10 hazardous substances in EEE; 2015/863 adds 4 phthalates",
        "fetch": "playwright",
    },
    {
        "id": "weee_2012",
        "name": "WEEE Directive 2012/19/EU",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32012L0019",
        "effective_date": "2012-07-04",
        "tags": "waste,electronics,WEEE,EAR,recycling",
        "note": "Requires producer registration in each member state (EAR in Germany)",
        "fetch": "playwright",
    },
    {
        "id": "reach_2006",
        "name": "REACH Regulation (EC) 1907/2006",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32006R1907",
        "effective_date": "2007-06-01",
        "tags": "chemical,REACH,SVHC,registration",
        "note": "Chemical registration; SVHC candidate list updated by ECHA bi-annually",
        "fetch": "playwright",
        "max_chars": 80000,
    },
    {
        "id": "gdpr_2016",
        "name": "General Data Protection Regulation (GDPR) 2016/679",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679",
        "effective_date": "2018-05-25",
        "tags": "data_privacy,GDPR,digital",
        "note": "Applies to any business processing EU resident personal data",
        "fetch": "playwright",
    },
    {
        "id": "erp_2009",
        "name": "Ecodesign Directive (ErP) 2009/125/EC",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32009L0125",
        "effective_date": "2009-10-21",
        "tags": "energy,ERP,ecodesign",
        "note": "Framework for energy-related products; product-specific measures separate",
        "fetch": "playwright",
    },
    {
        "id": "red_2014",
        "name": "Radio Equipment Directive (RED) 2014/53/EU",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32014L0053",
        "effective_date": "2016-06-13",
        "tags": "radio,wireless,CE,RED,IoT",
        "note": "All radio transmitters/receivers; cybersecurity articles mandatory Aug 2025",
        "fetch": "playwright",
    },
    {
        "id": "toy_safety_2009",
        "name": "Toy Safety Directive 2009/48/EC",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32009L0048",
        "effective_date": "2011-07-20",
        "tags": "toys,children,CE,EN_71",
        "note": "EN 71 standards; strict chemical + physical safety for age 0-14",
        "fetch": "playwright",
    },
    {
        "id": "battery_2023",
        "name": "Battery Regulation (EU) 2023/1542",
        "market": "eu",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32023R1542",
        "effective_date": "2023-08-17",
        "tags": "battery,sustainability,digital_passport",
        "note": "Replaces 2006/66/EC; QR code + digital battery passport from 2025",
        "fetch": "playwright",
    },
    # DE (gesetze-im-internet.de, httpx) ─────────────────────────────────────
    {
        "id": "verpackg_de",
        "name": "VerpackG — Verpackungsgesetz (Deutschland)",
        "market": "de",
        "url": "https://www.gesetze-im-internet.de/verpackg/",
        "effective_date": "2019-01-01",
        "tags": "packaging,LUCID,Germany,recycling,VerpackG",
        "note": "Mandatory LUCID registration + dual-system contract (Grüner Punkt etc.)",
        "fetch": "httpx",
    },
    # US (eCFR, httpx) ────────────────────────────────────────────────────────
    {
        "id": "fcc_part15",
        "name": "FCC Part 15 — Radio Frequency Devices (47 CFR Part 15)",
        "market": "us",
        "url": "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15",
        "effective_date": "2024-01-01",
        "tags": "FCC,radio,wireless,electronics,SDoC",
        "note": "Most consumer electronics need SDoC or FCC certification before US import",
        "fetch": "httpx",
    },
    {
        "id": "cpsc_16cfr_ch2",
        "name": "CPSC — Consumer Product Safety (16 CFR Chapter II)",
        "market": "us",
        "url": "https://www.ecfr.gov/current/title-16/chapter-II",
        "effective_date": "2024-01-01",
        "tags": "CPSC,product_safety,consumer,testing",
        "note": "Third-party testing for children's products; GCC for general consumer goods",
        "fetch": "httpx",
        "max_chars": 60000,
    },
]

# ── HTML → Markdown ───────────────────────────────────────────────────────────
_converter = _h2t.HTML2Text()
_converter.ignore_links  = True
_converter.ignore_images = True
_converter.body_width    = 0
_converter.unicode_snob  = True


def _extract_body(html: str, url: str) -> str:
    """尽量提取主体内容，去除导航/页眉/页脚。"""
    if "eur-lex.europa.eu" in url:
        m = re.search(r'<div[^>]+id=["\']text["\'][^>]*>(.*)', html, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1)
    if "gesetze-im-internet.de" in url:
        m = re.search(r'<div[^>]+id=["\']paddingLR12["\'][^>]*>(.*?)</div>\s*</div>',
                      html, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1)
        # 备用：提取 body 内容
        m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1)
    if "ecfr.gov" in url:
        m = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1)
    return html


def _html_to_md(html: str, url: str, max_chars: int = 120_000) -> str:
    body = _extract_body(html, url)
    md = _converter.handle(body)
    md = re.sub(r'\n{3,}', '\n\n', md).strip()
    if len(md) > max_chars:
        md = md[:max_chars] + f"\n\n---\n*[文档已截断，保留前 {max_chars:,} 字符]*\n"
    return md


def _frontmatter(reg: dict) -> str:
    lines = [
        "---",
        f'regulation_id: "{reg["id"]}"',
        f'name: "{reg["name"]}"',
        f'market: "{reg["market"]}"',
        f'source_url: "{reg["url"]}"',
        f'effective_date: "{reg["effective_date"]}"',
        f'tags: "{reg["tags"]}"',
        f'note: "{reg.get("note", "")}"',
        "---",
        "",
        f"# {reg['name']}",
        "",
        f"> **官方来源**: {reg['url']}",
        f"> **生效日期**: {reg['effective_date']}",
        f"> **标签**: {reg['tags']}",
        f"> {reg.get('note', '')}",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


# ── httpx 下载（DE / US）─────────────────────────────────────────────────────

def _fetch_httpx(url: str, client: httpx.Client) -> Optional[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    for attempt in range(3):
        try:
            r = client.get(url, headers=headers, timeout=45.0, follow_redirects=True)
            r.raise_for_status()
            return r.text
        except Exception as e:
            log.warning("  attempt %d/3 failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


# ── Playwright 下载（EUR-Lex AWS WAF）────────────────────────────────────────

_pw_browser = None    # 复用 browser 实例，避免每次重新启动


def _get_playwright_browser():
    """懒加载 Playwright Chromium browser（在第一次 EU 下载时启动）。"""
    global _pw_browser
    if _pw_browser is None:
        from playwright.sync_api import sync_playwright
        log.info("启动 Playwright Chromium (headless)...")
        _pw = sync_playwright().start()
        _pw_browser = _pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
    return _pw_browser


def _fetch_playwright(url: str) -> Optional[str]:
    """使用 Playwright 渲染页面，自动通过 AWS WAF JS 挑战。"""
    try:
        browser = _get_playwright_browser()
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page.goto(url, wait_until="networkidle", timeout=60_000)
        # 等待 WAF 挑战完成（通常 <5s）
        page.wait_for_timeout(3000)
        content = page.content()
        page.close()
        return content
    except Exception as e:
        log.warning("  Playwright 失败: %s", e)
        return None


def _close_playwright():
    global _pw_browser
    if _pw_browser is not None:
        try:
            _pw_browser.close()
        except Exception:
            pass
        _pw_browser = None


# ── 主下载函数 ────────────────────────────────────────────────────────────────

def download_one(reg: dict, force: bool, client: httpx.Client) -> str:
    """下载单份法规。返回 'saved' | 'skipped' | 'failed'"""
    dest = OUT_DIR / reg["market"] / f"{reg['id']}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        log.info("  ⏭  %-28s 已存在，跳过", reg["id"])
        return "skipped"

    log.info("  ↓  %-28s %s", reg["id"], reg["url"])

    method = reg.get("fetch", "httpx")
    if method == "playwright":
        html = _fetch_playwright(reg["url"])
    else:
        html = _fetch_httpx(reg["url"], client)

    if not html:
        log.error("  ✗  %-28s 下载失败", reg["id"])
        return "failed"

    # 检测是否仍然是 WAF 挑战页面
    if "challenge" in html.lower() and len(html) < 5000:
        log.error("  ✗  %-28s 仍被 WAF 拦截（%d chars）", reg["id"], len(html))
        return "failed"

    max_chars = reg.get("max_chars", 120_000)
    content = _frontmatter(reg) + _html_to_md(html, reg["url"], max_chars)
    dest.write_text(content, encoding="utf-8")
    size_kb = len(content) / 1024
    log.info("  ✓  %-28s → %s (%.1f KB)", reg["id"], dest.relative_to(ROOT), size_kb)
    return "saved"


def run(markets: list[str] = None, force: bool = False, dry_run: bool = False):
    """下载全部（或过滤后）的法规文档。"""
    catalog = [r for r in CATALOG if not markets or r["market"] in markets]
    if not catalog:
        log.warning("无匹配条目 (markets=%s)", markets)
        return

    log.info("=" * 64)
    log.info("避风港 合规文档下载器  |  共 %d 份法规  force=%s", len(catalog), force)
    log.info("输出: %s", OUT_DIR)
    log.info("=" * 64)

    if dry_run:
        for r in catalog:
            dest = OUT_DIR / r["market"] / f"{r['id']}.md"
            status = "✓ 已有" if dest.exists() else "✗ 待下"
            method = r.get("fetch", "httpx")
            print(f"  [{status}] {r['market']:4} [{method:9}]  {r['id']:28}  {r['name'][:48]}")
        return

    counts = {"saved": 0, "skipped": 0, "failed": 0}
    with httpx.Client(limits=httpx.Limits(max_connections=3)) as client:
        for i, reg in enumerate(catalog):
            result = download_one(reg, force, client)
            if result in counts:
                counts[result] += 1
            if i < len(catalog) - 1:
                time.sleep(1.0)

    _close_playwright()

    log.info("=" * 64)
    log.info("完成: 新增 %d | 跳过 %d | 失败 %d", counts["saved"], counts["skipped"], counts["failed"])

    _write_index()


def _write_index():
    lines = [
        "# 合规法规文档索引", "",
        "| 状态 | 市场 | 获取方式 | ID | 法规 | 生效日期 |",
        "|------|------|----------|----|------|----------|",
    ]
    for r in CATALOG:
        dest = OUT_DIR / r["market"] / f"{r['id']}.md"
        s = "✓" if dest.exists() else "✗"
        method = r.get("fetch", "httpx")
        lines.append(
            f"| {s} | {r['market'].upper()} | {method} | `{r['id']}` "
            f"| {r['name'][:48]} | {r['effective_date']} |"
        )
    (OUT_DIR / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="避风港 合规文档下载器")
    p.add_argument("--market", nargs="+", metavar="CODE", help="eu de us jp kr（可多选）")
    p.add_argument("--force",   action="store_true", help="覆盖已有文件")
    p.add_argument("--dry-run", action="store_true", help="预览计划")
    p.add_argument("--list",    action="store_true", help="列出目录")
    args = p.parse_args()

    if args.list:
        print(f"\n{'市场':6} {'获取':10} {'ID':28} 法规名称")
        print("-" * 90)
        for r in CATALOG:
            print(f"{r['market']:6} {r.get('fetch','httpx'):10} {r['id']:28} {r['name']}")
        print(f"\n合计 {len(CATALOG)} 份\n")
        return

    run(markets=args.market, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
