#!/usr/bin/env python3
"""深度功能验证：检查各阶段实际输出内容"""
import urllib.request
import urllib.error
import json
import time

BASE = "http://127.0.0.1:8000"

def get(path):
    try:
        req = urllib.request.Request(f"{BASE}{path}", method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return -1, {"error": str(e)}

def post(path, data):
    try:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE}{path}", data=body, method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return -1, {"error": str(e)}

print("=" * 70)
print("深度功能验证：各阶段实际输出检查")
print("=" * 70)

# ── Phase 1: 基础设施 ──
print("\n[Phase 1] 基础设施")
code, data = get("/api/v1/health")
print(f"  Health: status={data.get('status')}, version={data.get('version')}")
assert data["status"] == "ok", "Health check failed"

code, data = get("/api/v1/events/registry")
total_events = data.get("total", 0)
print(f"  Events registry: {total_events} events registered")
assert total_events > 0, "No events registered"

code, data = get("/api/v1/agents")
agents = data if isinstance(data, list) else []
print(f"  Agents: {len(agents)} agent(s)")
for a in agents:
    print(f"    - {a['id']}: {a['name']} ({a['type']})")

# ── Phase 2: 核心组件 ──
print("\n[Phase 2] 核心组件")
code, data = get("/api/v1/scheduler/jobs")
jobs = data.get("jobs", [])
global_jobs = [j for j in jobs if j.get("scope") == "global"]
product_jobs = [j for j in jobs if j.get("scope") == "product"]
print(f"  Scheduler: {len(jobs)} total jobs ({len(global_jobs)} global, {len(product_jobs)} product)")
for j in global_jobs:
    print(f"    - {j['id']}: {j['trigger']['type']} next={j['next_run_time'][:19]}")

# ── Phase 3.7: 风险情报 ──
print("\n[Phase 3.7] 风险情报")
code, data = get("/api/v1/risk-intel/heatmap")
print(f"  Heatmap: domains={list(data.get('by_domain', {}).keys())}")
print(f"    top_markets={data.get('top_markets', [])[:3]}")
print(f"    trend_count={len(data.get('trend', []))}")

code, data = get("/api/v1/risk-intel/feed")
print(f"  Feed: total={data.get('total', 0)}, page={data.get('page')}, has_next={data.get('has_next')}")

code, data = get("/api/v1/risk-intel/analyze/status")
print(f"  Analyze status: {data}")

# ── Phase 3.8: 产品出海生命周期 ──
print("\n[Phase 3.8] 产品出海生命周期")
code, data = get("/api/v1/products")
products = data if isinstance(data, list) else []
print(f"  Products: {len(products)} products")
if products:
    p = products[0]
    print(f"    Sample: id={p.get('id')}, name={p.get('name')}, type={p.get('product_type')}")
    print(f"    target_markets={p.get('target_markets', [])}")

# ── 关税计算 ──
print("\n  Customs duty calculator:")
code, data = post("/api/v1/customs/duty-calculator", {
    "hs_code": "9405.42",
    "declared_value": 5000,
    "dest_country": "US",
    "origin_country": "CN",
})
print(f"    [{code}] duty_result: {json.dumps(data, ensure_ascii=False)[:300]}")

# ── 管制商品检查 ──
print("\n  Controlled goods check:")
code, data = post("/api/v1/customs/controlled-goods/check", {
    "product_name": "LED lamp",
    "hs_code": "9405.42",
    "dest_country": "US",
})
if code == 405:
    # Try GET instead
    code, data = get("/api/v1/customs/controlled-goods/check?product_name=LED&hs_code=9405.42&dest_country=US")
print(f"    [{code}] controlled_check: {json.dumps(data, ensure_ascii=False)[:300]}")

# ── 三单比对 ──
print("\n  Three-way check:")
code, data = post("/api/v1/customs/three-way-check", {
    "order_id": "test_order_1",
})
print(f"    [{code}] three_way: {json.dumps(data, ensure_ascii=False)[:300]}")

# ── 关税率查询 ──
print("\n  Tariff rates:")
code, data = get("/api/v1/customs/tariff-rates")
print(f"    [{code}] tariff_rates: {json.dumps(data, ensure_ascii=False)[:300]}")

# ── 物流承运商 ──
print("\n  Logistics carriers:")
code, data = get("/api/v1/logistics/carriers")
print(f"    [{code}] carriers: {json.dumps(data, ensure_ascii=False)[:300]}")

# ── LLM Dispatch ──
print("\n  LLM Dispatch status:")
code, data = get("/api/v1/llm-dispatch/status")
print(f"    [{code}] dispatch_status: {json.dumps(data, ensure_ascii=False)[:300]}")

# ── Phase 5: 外部监听器 ──
print("\n[Phase 5] 外部监听器")
code, data = get("/api/v1/feishu/status")
print(f"  Feishu: status={data.get('status')}, service={data.get('service')}")

code, data = get("/api/v1/shopify/shops")
shops = data if isinstance(data, list) else []
print(f"  Shopify shops: {len(shops)}")
for s in shops:
    print(f"    - shop={s.get('shop')}, api_version={s.get('api_version')}")

code, data = get("/api/v1/shopify/products/count")
print(f"  Shopify products: count={data.get('count', 0)}")

# ── 知识库 ──
print("\n[Knowledge] 知识库")
code, data = get("/api/v1/knowledge/sections")
sections = data.get("sections", [])
print(f"  Sections: {len(sections)} sections")
for s in sections[:3]:
    print(f"    - {s['id']}: markets={s.get('markets', [])}")

code, data = get("/api/v1/knowledge/search?q=CE")
results = data.get("results", [])
print(f"  Search 'CE': {len(results)} results")
if results:
    print(f"    Top: {results[0]['id']} - {results[0]['title']}")

# ── 事件系统 ──
print("\n[Events] 事件系统")
code, data = get("/api/v1/events/stats")
print(f"  Stats: {data}")

code, data = get("/api/v1/events/timeline")
timeline = data.get("timeline", [])
print(f"  Timeline: {len(timeline)} entries")

# ── 通知系统 ──
print("\n[Notifications] 通知")
code, data = get("/api/v1/notifications")
notifs = data.get("notifications", [])
print(f"  Notifications: {len(notifs)}")
for n in notifs[:2]:
    print(f"    - {n.get('id')}: {n.get('title', '')[:50]} type={n.get('type')}")

# ── 管理后台 ──
print("\n[Phase 4] 管理后台")
code, data = get("/api/v1/admin/rbac/roles")
print(f"  RBAC roles: [{code}] {json.dumps(data, ensure_ascii=False)[:200]}")

code, data = get("/api/v1/admin/approvals")
print(f"  Approvals: [{code}] {json.dumps(data, ensure_ascii=False)[:200]}")

print("\n" + "=" * 70)
print("ALL DEEP CHECKS COMPLETED")
print("=" * 70)
