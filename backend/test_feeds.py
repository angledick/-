#!/usr/bin/env python3
"""测试采集器各信源可达性"""
import time
import sys
sys.path.insert(0, ".")

# 逐个测试各采集器
collectors_to_test = [
    ("USTRCollector", "app.api.risk_intel"),
]

# 直接测试网络可达性
import httpx
import feedparser

feeds = [
    ("ustr", "https://ustr.gov/rss.xml"),
    ("cbp", "https://www.cbp.gov/newsroom/rss"),
    ("eu_official", "https://eur-lex.europa.eu/RSSEP.xml"),
    ("wto", "https://www.wto.org/english/news_e/rss_e.xml"),
    ("ofac", "https://ofac.treasury.gov/recent-actions/rss.xml"),
    ("un_news", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
    ("imf", "https://www.imf.org/en/News/rss"),
    ("fed", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("ecb", "https://www.ecb.europa.eu/rss/news.html"),
    ("bis", "https://www.bis.org/rss/home.rss"),
    ("jin10", "https://www.jin10.com/flash_newest.js"),
    ("chinanews", "https://www.chinanews.com.cn/rss/finance.xml"),
]

print("=== 信源可达性测试 ===")
for name, url in feeds:
    try:
        start = time.time()
        r = httpx.get(url, timeout=8, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; RiskIntelBot/1.0)"})
        elapsed = time.time() - start
        status = r.status_code
        size = len(r.content)
        print(f"  [{status}] {name:15s} {elapsed:.1f}s  {size:>8d} bytes")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  [ERR] {name:15s} {elapsed:.1f}s  {str(e)[:60]}")
