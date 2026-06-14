"""
Shopify 功能验证脚本
测试 OAuth 配置、产品同步等核心功能
"""

import requests
import json

BASE_URL = "http://localhost:8000"
SHOP = "99hg9z-1k.myshopify.com"

def test_shopify_auth():
    """测试 1: Shopify OAuth 授权 URL 生成"""
    print("=" * 60)
    print("测试 1: Shopify OAuth 授权 URL 生成")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/api/v1/shopify/auth", params={"shop": SHOP})
    
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ OAuth URL 生成成功")
        print(f"   店铺: {data['shop']}")
        print(f"   State: {data['state']}")
        print(f"   授权URL: {data['authorization_url'][:80]}...")
        return True
    else:
        print(f"❌ OAuth URL 生成失败")
        return False

def test_list_shops():
    """测试 2: 列出已连接店铺"""
    print("\n" + "=" * 60)
    print("测试 2: 列出已连接店铺")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/api/v1/shopify/shops")
    
    print(f"状态码: {response.status_code}")
    data = response.json()
    print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    if response.status_code == 200:
        if len(data) == 0:
            print(f"ℹ️  暂无已授权店铺（需要先完成 OAuth 授权）")
        else:
            print(f"✅ 已连接 {len(data)} 个店铺")
            for shop in data:
                print(f"   - {shop['shop']}")
        return True
    else:
        print(f"❌ 获取店铺列表失败")
        return False

def test_get_products():
    """测试 3: 获取产品列表"""
    print("\n" + "=" * 60)
    print("测试 3: 获取产品列表")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/api/v1/shopify/{SHOP}/products")
    
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        products = response.json()
        print(f"✅ 成功获取 {len(products)} 个产品")
        if products:
            print(f"\n前 3 个产品:")
            for i, product in enumerate(products[:3], 1):
                print(f"  {i}. {product.get('title', 'N/A')}")
                print(f"     ID: {product.get('shopify_id', 'N/A')}")
                print(f"     类型: {product.get('product_type', 'N/A')}")
                print()
        return True
    elif response.status_code == 401:
        print(f"⚠️  店铺未授权，需要先完成 OAuth 授权")
        print(f"   请访问 OAuth 授权 URL 完成授权")
        return False
    else:
        print(f"❌ 获取产品列表失败: {response.text}")
        return False

def test_webhook_endpoint():
    """测试 4: Webhook 端点可用性"""
    print("=" * 60)
    print("测试 4: Webhook 端点可用性")
    print("=" * 60)
    
    webhook_data = {
        "id": 123456789,
        "title": "Test Product",
        "body_html": "<p>Test description</p>"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/shopify/webhook",
        json=webhook_data,
        params={
            "X-Shopify-Topic": "products/create",
            "X-Shopify-Shop": SHOP
        }
    )
    
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    if response.status_code == 200:
        print(f"✅ Webhook 端点正常工作")
        return True
    else:
        print(f"❌ Webhook 端点异常")
        return False

def main():
    print("\n" + "🚀 " * 20)
    print("避风港 - Shopify 功能验证")
    print("🚀 " * 20 + "\n")
    
    results = []
    
    # 测试 1: OAuth URL 生成
    results.append(("OAuth URL 生成", test_shopify_auth()))
    
    # 测试 2: 列出已连接店铺
    results.append(("列出已连接店铺", test_list_shops()))
    
    # 测试 3: 获取产品列表
    results.append(("获取产品列表", test_get_products()))
    
    # 测试 4: Webhook 端点
    results.append(("Webhook 端点", test_webhook_endpoint()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败/需授权"
        print(f"{status} - {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有功能正常!")
    else:
        print("\n💡 提示:")
        print("   - OAuth 功能正常，可以生成授权 URL")
        print("   - 需要先完成 OAuth 授权才能使用产品同步等功能")
        print(f"   - 授权 URL: http://localhost:8000/api/v1/shopify/auth?shop={SHOP}")
        print("\n   完成授权后，再次运行此脚本验证产品功能")

if __name__ == "__main__":
    main()
