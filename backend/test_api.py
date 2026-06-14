#!/usr/bin/env python3
"""Quick API test for existing + new modules"""
import urllib.request
import urllib.error
import json

BASE = "http://127.0.0.1:8000"

def test_get(path):
    try:
        req = urllib.request.Request(f"{BASE}{path}", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")[:150]
            print(f"  [200] GET {path}  => {body[:100]}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")[:150]
        print(f"  [{e.code}] GET {path}  => {body[:100]}")
        return False
    except Exception as e:
        print(f"  [ERR] GET {path}  => {e}")
        return False

def test_post(path, data):
    try:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE}{path}", data=body, method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_body = resp.read().decode("utf-8")[:150]
            print(f"  [200] POST {path}  => {resp_body[:100]}")
            return True
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8")[:150]
        print(f"  [{e.code}] POST {path}  => {resp_body[:100]}")
        return False
    except Exception as e:
        print(f"  [ERR] POST {path}  => {e}")
        return False

print("=" * 70)
print("TEST REPORT: Astra v4.0.0 后端完整性测试")
print("=" * 70)

# ── 原有功能 ──
print("\n[1] 原有核心功能")
get_tests = [
    "/api/v1/health",
    "/api/v1/agents",
    "/api/v1/chains/actions",
    "/api/v1/events/registry",
    "/api/v1/events/stats",
    "/api/v1/events/timeline",
    "/api/v1/knowledge/sections",
    "/api/v1/knowledge/search?q=CE",
    "/api/v1/scheduler/jobs",
    "/api/v1/notifications",
    "/api/v1/metrics",
    "/api/v1/products",
]
pass_count = 0
for p in get_tests:
    if test_get(p):
        pass_count += 1
print(f"  --> {pass_count}/{len(get_tests)} passed")

print("\n[2] 飞书/Shopify 监听器（原有）")
listener_tests = [
    "/api/v1/feishu/status",
    "/api/v1/shopify/shops",
    "/api/v1/shopify/products/count",
]
pass_count = 0
for p in listener_tests:
    if test_get(p):
        pass_count += 1
print(f"  --> {pass_count}/{len(listener_tests)} passed")

# ── 新增功能 ──
print("\n[3] 风险情报 API (Phase 3.7)")
risk_get = [
    "/api/v1/risk-intel/feed",
    "/api/v1/risk-intel/heatmap",
    "/api/v1/risk-intel/keywords",
    "/api/v1/risk-intel/runs",
    "/api/v1/risk-intel/analyze/status",
]
pass_count = 0
for p in risk_get:
    if test_get(p):
        pass_count += 1
print(f"  --> GET: {pass_count}/{len(risk_get)} passed")

risk_post = [
    ("/api/v1/risk-intel/search", {"keyword": "LED regulation", "markets": ["us"]}),
    ("/api/v1/risk-intel/keywords/suggest", {"product_category": "electronics", "markets": ["us"]}),
    ("/api/v1/risk-intel/keywords", {"keyword": "tariff LED 2026", "domain": "tariff", "markets": ["us"]}),
]
pass_count = 0
for path, data in risk_post:
    if test_post(path, data):
        pass_count += 1
print(f"  --> POST: {pass_count}/{len(risk_post)} passed")

print("\n[4] 产品出海生命周期管理 (Phase 3.8)")
lifecycle_get = [
    "/api/v1/suppliers",
    "/api/v1/contracts",
    "/api/v1/contracts/templates",
    "/api/v1/payment-channels",
    "/api/v1/orders",
    "/api/v1/logistics/shipments",
    "/api/v1/logistics/carriers",
    "/api/v1/customs/declarations",
    "/api/v1/customs/tariff-rates",
    "/api/v1/llm-dispatch/status",
]
pass_count = 0
for p in lifecycle_get:
    if test_get(p):
        pass_count += 1
print(f"  --> GET: {pass_count}/{len(lifecycle_get)} passed")

lifecycle_post = [
    ("/api/v1/customs/duty-calculator", {
        "hs_code": "9405.42",
        "declared_value": 5000,
        "dest_country": "US",
        "origin_country": "CN",
    }),
    ("/api/v1/customs/controlled-goods/check", {
        "product_name": "LED lamp",
        "hs_code": "9405.42",
        "dest_country": "US",
    }),
]
pass_count = 0
for path, data in lifecycle_post:
    if test_post(path, data):
        pass_count += 1
print(f"  --> POST: {pass_count}/{len(lifecycle_post)} passed")

print("\n[5] 管理后台 (Phase 4)")
admin_tests = [
    "/api/v1/admin/rbac/roles",
    "/api/v1/admin/approvals",
    "/api/v1/admin/reports/compliance",
]
pass_count = 0
for p in admin_tests:
    if test_get(p):
        pass_count += 1
print(f"  --> {pass_count}/{len(admin_tests)} passed")

# ── 汇总 ──
print("\n" + "=" * 70)
print("SUMMARY: 全部路由注册在 /openapi.json 可见")
print("=" * 70)

# Count all routes
try:
    req = urllib.request.Request(f"{BASE}/openapi.json", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        spec = json.loads(resp.read())
        paths = spec.get("paths", {})
        total = sum(len(v) for v in paths.values())
        print(f"Total OpenAPI paths: {len(paths)}, operations: {total}")
except Exception:
    pass

print("\nDONE")
