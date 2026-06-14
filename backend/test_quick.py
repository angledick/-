"""快速联调验证（直连后端8000）"""
import requests
B = "http://127.0.0.1:8000/api/v1"
ok = 0
fail = 0

def t(name, method, path, **kw):
    global ok, fail
    try:
        r = getattr(requests, method)(f"{B}/{path}", timeout=15, **kw)
        if r.status_code < 400:
            print(f"  OK  {name}: {r.status_code}")
            ok += 1
            return r.json() if r.headers.get("content-type","").startswith("application/json") else None
        else:
            print(f"  FAIL {name}: {r.status_code} {r.text[:100]}")
            fail += 1
    except Exception as e:
        print(f"  FAIL {name}: {e}")
        fail += 1
    return None

print("=== 快速联调验证 ===")
# Auth
d = t("login", "post", "auth/login", json={"username":"admin","password":"admin123"})
token = d["access_token"] if d else ""
h = {"Authorization": f"Bearer {token}"}
t("auth/me", "get", "auth/me", headers=h)
t("system/health", "get", "system/health", headers=h)
t("products", "get", "products", headers=h)
t("knowledge/stats", "get", "knowledge/stats", headers=h)
t("knowledge/docs", "get", "knowledge/docs", headers=h)
t("risk-intel/heatmap", "get", "risk-intel/heatmap", headers=h)
t("risk-intel/keywords", "get", "risk-intel/keywords", headers=h)
t("model-configs", "get", "model-configs", headers=h)
t("llm-dispatch/status", "get", "llm-dispatch/status", headers=h)
t("suppliers", "get", "suppliers", headers=h)
t("contracts", "get", "contracts", headers=h)
t("orders", "get", "orders", headers=h)
t("scheduler/jobs/grouped", "get", "scheduler/jobs/grouped", headers=h)
t("integrations", "get", "integrations", headers=h)
t("channels", "get", "channels", headers=h)
t("rbac/roles", "get", "rbac/roles", headers=h)
t("shopify/products", "get", "shopify/products", headers=h)
t("risk/alerts", "get", "risk/alerts?size=3", headers=h)
t("customs/tariff-rates", "get", "customs/tariff-rates", headers=h)
t("logistics/carriers", "get", "logistics/carriers", headers=h)
t("proactive/brief", "get", "proactive/brief?limit=3", headers=h)
t("pipeline/health", "get", "pipeline/health", headers=h)
t("metrics/dashboard", "get", "metrics/dashboard", headers=h)

print(f"\n=== 结果: {ok} OK, {fail} FAIL ===")
