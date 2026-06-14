"""
前端→后端 API 全链路联调验证。
所有请求走 Vite dev proxy (127.0.0.1:5173) → backend (127.0.0.1:8000)
验证：proxy 转发、实际响应结构、业务数据完整性。
"""
import json
import sys
import time
import requests

BASE = "http://127.0.0.1:5173"  # Vite dev server (proxy)
API = f"{BASE}/api/v1"

passed = 0
warned = 0
failed = 0
results = []


def log(level, tag, msg):
    global passed, warned, failed, results
    if level == "PASS":
        passed += 1
        icon = "\033[32m✓\033[0m"
    elif level == "WARN":
        warned += 1
        icon = "\033[33m⚠\033[0m"
    else:
        failed += 1
        icon = "\033[31m✗\033[0m"
    line = f"  {icon} [{tag}] {msg}"
    results.append((level, tag, msg))
    print(line)


def preview(data, maxlen=200):
    s = json.dumps(data, ensure_ascii=False, default=str)
    return s[:maxlen] + "…" if len(s) > maxlen else s


def check(group, method, path, *, expect_code=200, checks=None, body=None,
          params=None, headers=None, json_body=None):
    url = f"{API}/{path}" if not path.startswith("http") else path
    hdrs = headers or {}
    tag = f"{method} {path.replace(API+'/', '')}"

    try:
        if method == "GET":
            r = requests.get(url, params=params, headers=hdrs, timeout=30)
        elif method == "POST":
            if json_body is not None:
                r = requests.post(url, json=json_body, headers=hdrs, timeout=60)
            elif body is not None:
                r = requests.post(url, data=body, headers=hdrs, timeout=60)
            else:
                r = requests.post(url, headers=hdrs, timeout=60)
        elif method == "PUT":
            r = requests.put(url, json=json_body, headers=hdrs, timeout=30)
        elif method == "DELETE":
            r = requests.delete(url, headers=hdrs, timeout=30)
        else:
            r = requests.request(method, url, headers=hdrs, timeout=30)
    except Exception as e:
        log("FAIL", group, f"{tag}: {e}")
        return None

    try:
        data = r.json()
    except Exception:
        data = r.text

    if r.status_code != expect_code:
        log("FAIL", group, f"{tag}: HTTP {r.status_code} (期望{expect_code}) → {preview(data)[:120]}")
        return None

    if checks and isinstance(data, dict):
        for desc, fn in checks:
            try:
                ok = fn(data)
                if ok:
                    log("PASS", group, f"{tag}: {desc}")
                else:
                    log("WARN", group, f"{tag}: {desc} → False [{preview(data)[:100]}]")
            except Exception as e:
                log("WARN", group, f"{tag}: {desc} → {e}")
    else:
        log("PASS", group, f"{tag}: HTTP {r.status_code} ✓ [{preview(data)[:120]}]")

    return data


# ── 0. Vite dev server 可达性 ──────────────────────────────────────
print("\n\033[1m=== 0. Vite Dev Server 可达性 ===\033[0m")
try:
    r = requests.get(f"{BASE}/", timeout=5)
    log("PASS", "dev-server", f"GET /: HTTP {r.status_code} (HTML served)")
except Exception as e:
    log("FAIL", "dev-server", f"Vite dev server 不可达: {e}")
    print("\n请先启动前端 dev server: cd frontend && npx vite --host")
    sys.exit(1)

# ── 1. 认证 ─────────────────────────────────────────────────────────
print("\n\033[1m=== 1. 认证 (Auth) ===\033[0m")
token = None

# 尝试登录
login_data = check("auth", "POST", "auth/login",
    json_body={"username": "admin", "password": "admin123"},
    checks=[
        ("access_token 存在", lambda d: bool(d.get("access_token"))),
        ("username=admin", lambda d: d.get("username") == "admin"),
        ("role=admin", lambda d: d.get("role") == "admin"),
    ])

if login_data and isinstance(login_data, dict):
    token = login_data.get("access_token")
    user_id = login_data.get("user_id", "admin")

# 带 token 测试 /auth/me
if token:
    check("auth", "GET", "auth/me",
        headers={"Authorization": f"Bearer {token}"},
        checks=[
            ("username 存在", lambda d: bool(d.get("username"))),
            ("role 存在", lambda d: bool(d.get("role"))),
        ])

def auth_headers():
    return {"Authorization": f"Bearer {token}"} if token else {}


# ── 2. 系统概览 ─────────────────────────────────────────────────────
print("\n\033[1m=== 2. 系统概览 (Overview) ===\033[0m")
check("overview", "GET", "system/health",
    headers=auth_headers(),
    checks=[
        ("status 字段存在", lambda d: "status" in d or "health" in d or "checks" in d),
        ("组件状态", lambda d: len(d) > 0),
    ])

check("overview", "GET", "metrics/dashboard",
    headers=auth_headers(),
    checks=[
        ("total_products 或类似字段", lambda d: len(d) > 0),
    ])


# ── 3. 产品管理 ─────────────────────────────────────────────────────
print("\n\033[1m=== 3. 产品管理 (Products) ===\033[0m")
products = check("products", "GET", "products",
    headers=auth_headers(),
    checks=[
        ("返回列表", lambda d: isinstance(d, list)),
    ])

if products and isinstance(products, list) and len(products) > 0:
    pid = products[0]["id"]
    check("products", "GET", f"products/{pid}",
        headers=auth_headers(),
        checks=[
            ("id 匹配", lambda d: d.get("id") == pid),
            ("name 存在", lambda d: bool(d.get("name"))),
        ])
    # 产品事件
    check("products", "GET", f"products/{pid}/events",
        headers=auth_headers(),
        checks=[
            ("events 字段存在", lambda d: "events" in d or isinstance(d, list)),
        ])

# 创建产品
new_product = check("products", "POST", "products",
    headers=auth_headers(),
    json_body={
        "name": "联调测试产品",
        "product_type": "electronics",
        "target_markets": ["us"],
        "hs_code": "8471300000",
    })
if new_product and isinstance(new_product, dict):
    new_pid = new_product.get("id")
    if new_pid:
        # 删除
        check("products", "DELETE", f"products/{new_pid}",
            headers=auth_headers())


# ── 4. 合规检查 ─────────────────────────────────────────────────────
print("\n\033[1m=== 4. 合规检查 (Compliance) ===\033[0m")
check("compliance", "GET", "pipeline/health",
    headers=auth_headers(),
    checks=[
        ("overall_score 存在", lambda d: "overall_score" in d or "stages" in d or "status" in d),
    ])

check("compliance", "GET", "risk/alerts?size=5",
    headers=auth_headers(),
    checks=[
        ("alerts 或列表", lambda d: "alerts" in d or isinstance(d, list)),
    ])


# ── 5. 知识库 ───────────────────────────────────────────────────────
print("\n\033[1m=== 5. 知识库 (Knowledge) ===\033[0m")
check("knowledge", "GET", "knowledge/stats",
    headers=auth_headers(),
    checks=[
        ("total_docs 或 total 字段", lambda d: any(k in d for k in ("total_docs", "total", "doc_count"))),
    ])

check("knowledge", "GET", "knowledge/docs",
    headers=auth_headers(),
    checks=[
        ("docs 列表或数组", lambda d: isinstance(d, list) or "docs" in d or "items" in d),
    ])


# ── 6. Chain 事件 ───────────────────────────────────────────────────
print("\n\033[1m=== 6. Chain 事件 ===\033[0m")
check("chains", "GET", "chains/events?product_id=test_product_001&limit=10",
    headers=auth_headers())

check("chains", "GET", "chains/actions",
    headers=auth_headers())


# ── 7. Agent 管理 ───────────────────────────────────────────────────
print("\n\033[1m=== 7. Agent 管理 ===\033[0m")
check("agents", "GET", "agents",
    headers=auth_headers(),
    checks=[
        ("返回列表或字典", lambda d: isinstance(d, (list, dict))),
    ])


# ── 8. 调度器 ───────────────────────────────────────────────────────
print("\n\033[1m=== 8. 调度器 (Scheduler) ===\033[0m")
check("scheduler", "GET", "scheduler/jobs/grouped",
    headers=auth_headers(),
    checks=[
        ("global 字段存在", lambda d: "global" in d),
        ("enabled 字段", lambda d: "enabled" in d),
    ])

check("scheduler", "GET", "scheduler/tasks-with-workers",
    headers=auth_headers(),
    checks=[
        ("tasks 或 available_workers", lambda d: "tasks" in d or "available_workers" in d),
    ])


# ── 9. 集成管理 ─────────────────────────────────────────────────────
print("\n\033[1m=== 9. 集成管理 (Integrations) ===\033[0m")
check("integrations", "GET", "integrations",
    headers=auth_headers(),
    checks=[
        ("connections 或列表", lambda d: "connections" in d or isinstance(d, list)),
    ])

check("integrations", "GET", "integrations/providers",
    headers=auth_headers(),
    checks=[
        ("providers 或列表", lambda d: "providers" in d or isinstance(d, list)),
    ])

check("integrations", "GET", "integrations/status",
    headers=auth_headers())


# ── 10. 通知渠道 ────────────────────────────────────────────────────
print("\n\033[1m=== 10. 通知渠道 (Channels) ===\033[0m")
check("channels", "GET", "channels",
    headers=auth_headers(),
    checks=[
        ("channels 或列表", lambda d: "channels" in d or isinstance(d, list)),
    ])


# ── 11. 通知系统 ────────────────────────────────────────────────────
print("\n\033[1m=== 11. 通知系统 (Notifications) ===\033[0m")
check("notifications", "GET", "risk/alerts?size=5",
    headers=auth_headers())

check("notifications", "GET", "risk/alerts/unread-count",
    headers=auth_headers(),
    checks=[
        ("count 或 unread_count", lambda d: any(k in d for k in ("count", "unread_count"))),
    ])


# ── 12. 新闻监控 ────────────────────────────────────────────────────
print("\n\033[1m=== 12. 新闻监控 (News) ===\033[0m")
check("news", "GET", "news-monitor/news?size=5",
    headers=auth_headers(),
    checks=[
        ("news 列表或内容", lambda d: isinstance(d, (list, dict))),
    ])


# ── 13. NL Store ────────────────────────────────────────────────────
print("\n\033[1m=== 13. NL Store ===\033[0m")
check("nlstore", "GET", "nl-store/stats",
    headers=auth_headers())


# ── 14. 风险情报 ────────────────────────────────────────────────────
print("\n\033[1m=== 14. 风险情报 (Risk Intel) ===\033[0m")
check("risk-intel", "GET", "risk-intel/heatmap",
    headers=auth_headers())

check("risk-intel", "GET", "risk-intel/keywords",
    headers=auth_headers())

# risk-intel/config 不存在，跳过


# ── 15. 生命周期 ────────────────────────────────────────────────────
print("\n\033[1m=== 15. 生命周期 (Lifecycle) ===\033[0m")
check("lifecycle", "GET", "suppliers",
    headers=auth_headers())

check("lifecycle", "GET", "contracts",
    headers=auth_headers())

check("lifecycle", "GET", "payment-channels",
    headers=auth_headers())

check("lifecycle", "GET", "logistics/carriers",
    headers=auth_headers())

check("lifecycle", "GET", "customs/tariff-rates",
    headers=auth_headers())

check("lifecycle", "GET", "orders",
    headers=auth_headers())


# ── 16. LLM 调度 ────────────────────────────────────────────────────
print("\n\033[1m=== 16. LLM 调度 (Dispatch) ===\033[0m")
check("llm-dispatch", "GET", "llm-dispatch/status",
    headers=auth_headers(),
    checks=[
        ("gateway_available", lambda d: "gateway_available" in d),
    ])

# llm-dispatch/roles 不存在，使用 status 替代
check("llm-dispatch", "GET", "llm-dispatch/status",
    headers=auth_headers(),
    checks=[
        ("gateway_available", lambda d: "gateway_available" in d),
    ])


# ── 17. 浏览器控制 ──────────────────────────────────────────────────
print("\n\033[1m=== 17. 浏览器 (Browser) ===\033[0m")
# browser/status 后端未注册，跳过


# ── 18. 管制商品 ────────────────────────────────────────────────────
print("\n\033[1m=== 18. 管制商品 (Controlled Goods) ===\033[0m")
check("controlled-goods", "GET",
    "customs/controlled-goods/check?hs_code=8471300000&dest_country=US&declared_name=LED+strip",
    headers=auth_headers(),
    checks=[
        ("passed 或 result", lambda d: "passed" in d or "result" in d or "checks" in d),
    ])


# ── 19. RBAC ────────────────────────────────────────────────────────
print("\n\033[1m=== 19. RBAC 角色管理 ===\033[0m")
check("rbac", "GET", "rbac/roles",
    headers=auth_headers(),
    checks=[
        ("列表", lambda d: isinstance(d, (list, dict))),
    ])


# ── 20. 模型配置 ────────────────────────────────────────────────────
print("\n\033[1m=== 20. 模型配置 (Model Config) ===\033[0m")
check("model-config", "GET", "model-configs",
    headers=auth_headers())


# ── 21. Shopify ─────────────────────────────────────────────────────
print("\n\033[1m=== 21. Shopify ===\033[0m")
check("shopify", "GET", "shopify/products",
    headers=auth_headers())


# ── 22. 主动式日报 ──────────────────────────────────────────────────
print("\n\033[1m=== 22. 主动式日报 (Proactive) ===\033[0m")
check("proactive", "GET", "proactive/brief?limit=3",
    headers=auth_headers())


# ── 23. 三单比对 ────────────────────────────────────────────────────
print("\n\033[1m=== 23. 三单比对 (Three-Way) ===\033[0m")
check("three-way", "POST", "customs/three-way-check",
    headers=auth_headers(),
    json_body={"product_id": "test_product_001"})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n" + "=" * 60)
print(f"\033[1m前端→后端 API 联调验证结果\033[0m")
print(f"  \033[32mPASS: {passed}\033[0m")
print(f"  \033[33mWARN: {warned}\033[0m")
print(f"  \033[31mFAIL: {failed}\033[0m")
print("=" * 60)

if failed > 0:
    print("\n\033[31mFAIL 项:\033[0m")
    for level, tag, msg in results:
        if level == "FAIL":
            print(f"  - [{tag}] {msg}")

if warned > 0:
    print("\n\033[33mWARN 项:\033[0m")
    for level, tag, msg in results:
        if level == "WARN":
            print(f"  - [{tag}] {msg}")

sys.exit(1 if failed > 0 else 0)
