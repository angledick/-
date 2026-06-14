"""测试 Shopify 商品同步 — 直接拉取真实商品并同步到本地存储"""
import asyncio
import sys
import os

# Ensure backend dir is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.shopify_api import sync_to_local, get_products, count_products
from app.core.product_storage import ProductStorage


async def main():
    print("=" * 60)
    print("Shopify 商品同步测试")
    print("=" * 60)

    # Step 1: Check current local products
    storage = ProductStorage()
    local_products = storage.list_products(limit=100)
    print(f"\n[1] 当前本地产品数量: {len(local_products)}")

    # Step 2: Try to get Shopify product count
    print("\n[2] 尝试获取 Shopify 商品总数...")
    try:
        count_result = await count_products()
        total_count = count_result.get("count", 0)
        print(f"    Shopify 商品总数: {total_count}")
    except Exception as e:
        print(f"    获取总数失败: {e}")
        total_count = -1

    # Step 3: Try to fetch products from Shopify
    print("\n[3] 拉取 Shopify 商品列表...")
    try:
        data = await get_products(limit=50)
        products = data.get("products", [])
        print(f"    拉取到 {len(products)} 个商品")
        for p in products[:5]:
            print(f"      - ID: {p.get('id')}, 标题: {p.get('title')}, "
                  f"类型: {p.get('product_type', 'N/A')}, 供应商: {p.get('vendor', 'N/A')}")
    except Exception as e:
        print(f"    拉取失败: {e}")
        products = []

    # Step 4: Sync to local storage
    if products:
        print(f"\n[4] 同步 {len(products)} 个商品到本地存储...")
        try:
            result = await sync_to_local(limit=50)
            print(f"    同步完成!")
            print(f"    synced={result.get('synced', 0)}, total={result.get('total', 0)}")
        except Exception as e:
            print(f"    同步失败: {e}")
            import traceback
            traceback.print_exc()

    # Step 5: Verify local storage after sync
    print(f"\n[5] 验证本地存储...")
    storage2 = ProductStorage()
    local_after = storage2.list_products(limit=100)
    print(f"    同步后本地产品数量: {len(local_after)}")
    for p in local_after:
        print(f"      - {p.id}: {p.name} ({p.lifecycle_stage})")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
