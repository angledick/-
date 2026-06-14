"""端到端验证：Shopify同步 → 产品合规 → 生命周期"""
import httpx
import asyncio

BASE = "http://127.0.0.1:8000"


async def test_e2e():
    async with httpx.AsyncClient(timeout=15) as client:
        # 1. List products
        print("=== 1. 产品列表 ===")
        r = await client.get(f"{BASE}/api/v1/products")
        products = r.json()
        print(f"Status: {r.status_code}, Products: {len(products)}")
        for p in products:
            pid = p["id"]
            name = p["name"]
            lc = p["lifecycle_stage"]
            cs = p["compliance_status"]
            print(f"  - {pid}: {name} | lifecycle={lc} | compliance={cs}")

        if not products:
            print("No products found!")
            return

        pid = products[0]["id"]

        # 2. Get product details
        print(f"\n=== 2. 产品详情 ({pid}) ===")
        r = await client.get(f"{BASE}/api/v1/products/{pid}")
        detail = r.json()
        print(f"Status: {r.status_code}")
        print(f"  Name: {detail['name']}")
        print(f"  Vendor: {detail.get('vendor', '')}")
        print(f"  Type: {detail.get('product_type', '')}")
        print(f"  Tags: {detail.get('tags', [])}")
        print(f"  Lifecycle: {detail['lifecycle_stage']}")
        print(f"  Compliance: {detail['compliance_status']}")
        print(f"  Health: {detail.get('health_score', 0)}")
        meta = detail.get("metadata", {})
        print(f"  Shopify ID: {meta.get('shopify_id', 'N/A')}")
        print(f"  Handle: {meta.get('handle', 'N/A')}")

        # 3. Get product events
        print(f"\n=== 3. 产品事件 ({pid}) ===")
        r = await client.get(f"{BASE}/api/v1/products/{pid}/events")
        data = r.json()
        total = data.get("total", 0)
        print(f"Status: {r.status_code}, Events: {total}")
        for e in data.get("events", [])[:5]:
            etype = e["type"]
            sev = e.get("severity", "?")
            ts = e.get("created_at", "?")
            print(f"  - {etype} | severity={sev} | {ts}")

        # 4. Update lifecycle (concept -> design)
        current = detail["lifecycle_stage"]
        print(f"\n=== 4. 更新生命周期 ({current} -> design) ===")
        r = await client.put(
            f"{BASE}/api/v1/products/{pid}/lifecycle",
            json={"lifecycle_stage": "design", "reason": "E2E测试: 推进到设计阶段"},
        )
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            updated = r.json()
            print(f"  New lifecycle: {updated['lifecycle_stage']}")
            print(f"  Business stage: {updated.get('business_stage', '')}")
        else:
            print(f"  Error: {r.text}")

        # 5. Verify events after lifecycle change
        print(f"\n=== 5. 验证事件 (生命周期变更后) ===")
        r = await client.get(f"{BASE}/api/v1/products/{pid}/events")
        data = r.json()
        total = data.get("total", 0)
        print(f"Events total: {total}")
        for e in data.get("events", [])[:5]:
            etype = e["type"]
            edata = e.get("data", {})
            ts = e.get("created_at", "?")
            print(f"  - {etype} | data={edata} | {ts}")

        # 6. Test compliance check trigger
        print(f"\n=== 6. 触发合规检查 ===")
        r = await client.post(
            f"{BASE}/api/v1/products/{pid}/compliance-check",
            params={"target_market": "欧盟"},
        )
        print(f"Status: {r.status_code}")
        print(f"  Response: {r.json()}")

        # 7. Advance to next stage (design -> sourcing)
        print(f"\n=== 7. 推进到下一阶段 (design -> sourcing) ===")
        r = await client.put(
            f"{BASE}/api/v1/products/{pid}/lifecycle",
            json={"lifecycle_stage": "sourcing", "reason": "E2E测试: 推进到采购阶段"},
        )
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            updated = r.json()
            print(f"  Lifecycle: {updated['lifecycle_stage']}")
            print(f"  Business stage: {updated.get('business_stage', '')}")
        else:
            print(f"  Error: {r.text}")

        # 8. Final state check
        print(f"\n=== 8. 最终状态 ===")
        r = await client.get(f"{BASE}/api/v1/products/{pid}")
        final = r.json()
        print(f"  Name: {final['name']}")
        print(f"  Lifecycle: {final['lifecycle_stage']}")
        print(f"  Compliance: {final['compliance_status']}")
        print(f"  Business stage: {final.get('business_stage', '')}")

        r = await client.get(f"{BASE}/api/v1/products/{pid}/events")
        data = r.json()
        print(f"  Total events: {data.get('total', 0)}")

        print("\n=== 端到端验证完成 ===")


if __name__ == "__main__":
    asyncio.run(test_e2e())
