"""修正验证 - 使用正确的路径"""
import httpx

C = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)
results = []

def t(method, path, expect=200, **kw):
    try:
        r = getattr(C, method)(path, **kw)
        ok = r.status_code == expect
        results.append((ok, method.upper(), path, r.status_code))
        info = ""
        if "json" in r.headers.get("content-type",""):
            d = r.json()
            if isinstance(d, list):
                info = f"  [{len(d)} items]"
            elif isinstance(d, dict):
                keys = list(d.keys())[:5]
                info = f"  {{{','.join(keys)}}}"
        print(f"  {'OK' if ok else 'FAIL'} {method.upper():6s} {path:55s} -> {r.status_code}{info}")
        return r
    except Exception as e:
        results.append((False, method.upper(), path, 0))
        print(f"  ERR  {method.upper():6s} {path:55s} -> {str(e)[:80]}")

print("[知识库 - 修正路径]")
t("get", "/knowledge/stats")
t("get", "/knowledge/docs")
t("get", "/api/v1/knowledge/sections")
t("get", "/api/v1/knowledge/search", params={"q": "合规"})

print("\n[知识库导入 - 修正路径]")
t("get", "/knowledge/stats")

print("\n[供应商 CRUD]")
t("get", "/api/v1/suppliers")
r = t("post", "/api/v1/suppliers", expect=201, json={"name":"test_v2","source_type":"factory","contact_name":"T","country":"CN"})
sid = r.json().get("id") if r and r.status_code == 201 else None
if sid:
    t("get", f"/api/v1/suppliers/{sid}")
    t("put", f"/api/v1/suppliers/{sid}", json={"name":"test_v2_updated"})
    t("delete", f"/api/v1/suppliers/{sid}")

print("\n[物流 - 修正路径]")
t("get", "/api/v1/logistics/shipments")
t("get", "/api/v1/logistics/carriers")

print("\n[报关 - 修正路径]")
t("get", "/api/v1/customs/controlled-goods/check", params={"declared_name":"laser","hs_code":"9001"})

print("\n[LLM调度 - 修正路径]")
t("get", "/api/v1/llm-dispatch/status")
t("post", "/api/v1/llm-dispatch/lifecycle/scan", expect=422)  # missing body

print("\n" + "=" * 60)
ok = sum(1 for x in results if x[0])
fail = sum(1 for x in results if not x[0])
print(f"总计: {len(results)}, 通过: {ok}, 失败: {fail}")
if fail == 0:
    print("ALL PASSED")
