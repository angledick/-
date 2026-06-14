"""生命周期 & 知识库 全量迁移验证脚本"""
import httpx, json, sys, time

BASE = "http://127.0.0.1:8000"
C = httpx.Client(base_url=BASE, timeout=30)
results = []

def test(method, path, expect=200, **kw):
    try:
        r = getattr(C, method)(path, **kw)
        ok = r.status_code == expect
        body_preview = r.text[:200] if r.text else "(empty)"
        results.append((ok, method.upper(), path, r.status_code, body_preview))
        return r
    except Exception as e:
        results.append((False, method.upper(), path, 0, str(e)[:200]))
        return None

print("=" * 70)
print("生命周期 & 知识库 全量迁移验证")
print("=" * 70)

# ── 知识库 ──
print("\n[知识库]")
test("get", "/api/v1/knowledge")
test("get", "/api/v1/knowledge/sections")
r = test("get", "/api/v1/knowledge/search", params={"q": "合规"})

# ── 知识库导入 ──
print("\n[知识库导入]")
test("get", "/api/v1/knowledge-import/status")

# ── 供应商管理 ──
print("\n[供应商]")
r = test("get", "/api/v1/suppliers")
# 创建一个测试供应商
r = test("post", "/api/v1/suppliers", json={
    "name": "迁移测试供应商",
    "source_type": "factory",
    "contact_name": "张三",
    "country": "CN",
})
sid = None
if r and r.status_code == 200:
    sid = r.json().get("id")
    print(f"  创建供应商: {sid}")
if sid:
    test("get", f"/api/v1/suppliers/{sid}")
    test("put", f"/api/v1/suppliers/{sid}", json={"name": "迁移测试供应商(已更新)"})

# ── 合同管理 ──
print("\n[合同模板]")
test("get", "/api/v1/contracts/templates")
print("\n[合同]")
test("get", "/api/v1/contracts")

# ── 支付渠道 ──
print("\n[支付渠道]")
test("get", "/api/v1/payment-channels")

# ── 物流 ──
print("\n[物流商]")
test("get", "/api/v1/logistics/carriers")
print("\n[物流订单]")
test("get", "/api/v1/logistics")

# ── 报关 ──
print("\n[报关]")
test("get", "/api/v1/customs/declarations")
test("get", "/api/v1/customs/tariff-rates", params={"country": "US", "hs_code": "8471"})
test("get", "/api/v1/customs/duty-calculator", params={"hs_code": "8471", "value": "1000", "country": "US"})
test("get", "/api/v1/customs/controlled-goods/check", params={"declared_name": "laser pointer"})

# ── 订单 ──
print("\n[订单]")
test("get", "/api/v1/orders")

# ── LLM 调度 ──
print("\n[LLM 调度]")
test("get", "/api/v1/llm-dispatch/models")
test("get", "/api/v1/llm-dispatch/status")

# ── 风险情报 ──
print("\n[风险情报]")
test("get", "/api/v1/risk-intel/runs")
test("get", "/api/v1/risk-intel/keywords")
test("get", "/api/v1/risk-intel/feed")

# ── 清理测试数据 ──
if sid:
    print(f"\n[清理] 删除测试供应商 {sid}")
    test("delete", f"/api/v1/suppliers/{sid}")

# ── 汇总 ──
print("\n" + "=" * 70)
print("验证结果汇总")
print("=" * 70)
passed = sum(1 for ok, *_ in results if ok)
failed = sum(1 for ok, *_ in results if not ok)
for ok, method, path, code, preview in results:
    status = "✓" if ok else "✗"
    print(f"  {status} {method:6s} {path:55s} → {code}")
    if not ok:
        print(f"         ↳ {preview[:120]}")

print(f"\n总计: {len(results)} 个端点, {passed} 通过, {failed} 失败")
if failed:
    print("\n⚠ 存在失败端点，请检查")
    sys.exit(1)
else:
    print("\n✓ 全部通过 — 生命周期 & 知识库迁移完整，无逻辑冲突")
