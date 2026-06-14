#!/usr/bin/env python3
"""触发风险情报采集并检查实际结果"""
import urllib.request
import json
import time

BASE = "http://127.0.0.1:8000"

# 1. 触发搜索
print("=== 触发风险情报搜索 ===")
data = json.dumps({"keyword": "tariff LED 2026", "markets": ["us"]}).encode("utf-8")
req = urllib.request.Request(
    f"{BASE}/api/v1/risk-intel/search",
    data=data, method="POST",
    headers={"Content-Type": "application/json"}
)
try:
    start = time.time()
    with urllib.request.urlopen(req, timeout=200) as resp:
        elapsed = time.time() - start
        result = json.loads(resp.read().decode("utf-8"))
        print(f"搜索完成 ({elapsed:.1f}s): run_id={result.get('run_id')}")
        print(f"  items_found={result.get('items_found', 0)}")
        print(f"  items_new={result.get('items_new', 0)}")
        items = result.get("items", [])
        print(f"  items_returned={len(items)}")
        for item in items[:3]:
            print(f"    - [{item.get('source_name')}] {item.get('title', '')[:80]}")
            print(f"      domain={item.get('risk_domain')}, severity={item.get('severity')}")
except Exception as e:
    print(f"搜索失败: {e}")

# 2. 检查采集后 feed
print("\n=== 检查 Feed ===")
req = urllib.request.Request(f"{BASE}/api/v1/risk-intel/feed", method="GET")
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    print(f"Feed: total={data.get('total', 0)}")
    for item in data.get("items", [])[:3]:
        print(f"  - [{item.get('source_name')}] {item.get('title', '')[:80]}")

# 3. 检查 Heatmap
print("\n=== 检查 Heatmap ===")
req = urllib.request.Request(f"{BASE}/api/v1/risk-intel/heatmap", method="GET")
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    print(f"Domains: {data.get('by_domain', {})}")
    print(f"Top markets: {data.get('top_markets', [])[:5]}")
    print(f"Trend: {len(data.get('trend', []))} entries")

# 4. 检查 Runs
print("\n=== 检查 Runs ===")
req = urllib.request.Request(f"{BASE}/api/v1/risk-intel/runs", method="GET")
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    runs = data if isinstance(data, list) else [data]
    print(f"Runs: {len(runs)}")
    for r in runs[:3]:
        print(f"  - id={r.get('id', '')[:12]} keyword={r.get('keyword')} status={r.get('status')} found={r.get('items_found')}")

# 5. 管制商品检查（GET方式）
print("\n=== 管制商品检查 ===")
req = urllib.request.Request(
    f"{BASE}/api/v1/customs/controlled-goods/check?declared_name=LED%20lamp&hs_code=9405.42&dest_country=US",
    method="GET"
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Controlled check: {json.dumps(data, ensure_ascii=False)[:400]}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8")
    print(f"[{e.code}] {body[:400]}")

print("\n=== DONE ===")
