"""
执行Shopify GraphQL查询获取商品数据

这个脚本会：
1. 检查Shopify配置
2. 如果没有访问令牌，提供获取指引
3. 执行GraphQL查询获取商品数据
"""
import os
import json
import requests
from pathlib import Path
from datetime import datetime

# Shopify配置
SHOPIFY_DOMAIN = os.environ.get("SHOPIFY_DOMAIN", "99hg9z-1k.myshopify.com")
SHOPIFY_CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "63a92d222d6ef96d2e99e15229a73888")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "REDACTED_PLACEHOLDER")
SHOPIFY_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
SHOPIFY_API_VERSION = "2024-10"

def check_configuration():
    """检查Shopify配置"""
    print("=== 检查Shopify配置 ===")
    print(f"域名: {SHOPIFY_DOMAIN}")
    print(f"Client ID: {SHOPIFY_CLIENT_ID[:10]}... 已配置")
    print(f"Client Secret: {SHOPIFY_CLIENT_SECRET[:10]}... 已配置")
    print(f"Access Token: {'已配置' if SHOPIFY_ACCESS_TOKEN else '未配置'}")
    print()

    if not SHOPIFY_ACCESS_TOKEN:
        print("ERROR: 缺少Shopify Access Token")
        print()
        print("获取Access Token的方法:")
        print()
        print("方法1: 创建自定义App（推荐用于开发）")
        print(f"1. 访问: https://{SHOPIFY_DOMAIN}/admin/apps/development")
        print("2. 点击 'Create an app'")
        print("3. 输入App名称，如 'Astra Integration'")
        print("4. 在 'Admin API access' 部分:")
        print("   - 选择 'Custom access'")
        print("   - 勾选 'read_products' 权限")
        print("5. 点击 'Create app'")
        print("6. 在 'Admin API credentials' 部分:")
        print("   - 复制 'Access token'")
        print("7. 设置环境变量:")
        print("   export SHOPIFY_ACCESS_TOKEN='your_token_here'")
        print("   (Windows PowerShell: $env:SHOPIFY_ACCESS_TOKEN='your_token_here')")
        print()
        print("方法2: 通过OAuth授权（生产环境推荐）")
        print("1. 访问OAuth授权URL:")
        print(f"   https://{SHOPIFY_DOMAIN}/admin/oauth/authorize")
        print(f"   ?client_id={SHOPIFY_CLIENT_ID}")
        print(f"   &scope=read_products")
        print(f"   &redirect_uri=http://localhost:8000/api/v1/shopify/callback")
        print("2. 授权后会获得access_token")
        print()
        return False

    return True

def execute_graphql_query(query, variables=None):
    """执行GraphQL查询"""
    endpoint = f"https://{SHOPIFY_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"

    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "query": query,
        "variables": variables or {}
    }

    try:
        print(f"发送GraphQL查询到 {endpoint}...")
        response = requests.post(endpoint, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"查询失败: HTTP {response.status_code}")
            print(f"响应: {response.text}")
            return None

    except Exception as e:
        print(f"请求异常: {e}")
        return None

def get_products_query(limit=50):
    """获取商品的GraphQL查询"""
    return f"""
    query GetShopifyProducts {{
      products(first: {limit}) {{
        edges {{
          cursor
          node {{
            id
            title
            description
            handle
            vendor
            productType
            status
            createdAt
            updatedAt
            featuredImage {{
              url
              altText
            }}
            images(first: 5) {{
              edges {{
                node {{
                  url
                  altText
                }}
              }}
            }}
            variants(first: 10) {{
              edges {{
                node {{
                  id
                  title
                  sku
                  price
                  compareAtPrice
                  availableForSale
                  barcode
                  inventoryPolicy
                  createdAt
                  updatedAt
                }}
              }}
            }}
            tags
            priceRangeV2 {{
              minVariantPrice {{
                amount
                currencyCode
              }}
              maxVariantPrice {{
                amount
                currencyCode
              }}
            }}
            totalInventory
            tracksInventory
          }}
        }}
        pageInfo {{
          hasNextPage
          hasPreviousPage
        }}
      }}
    }}
    """

def save_products_data(products_data):
    """保存商品数据到文件"""
    output_dir = Path("./data/shopify/products")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"products_api_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(products_data, f, ensure_ascii=False, indent=2)

    print(f"商品数据已保存到: {output_file}")
    return output_file

def analyze_products_data(products_data):
    """分析商品数据"""
    if not products_data or "data" not in products_data:
        print("无效的商品数据")
        return

    products = products_data["data"]["products"]
    edges = products.get("edges", [])

    print()
    print("=== Shopify商品数据摘要 ===")
    print(f"获取商品数量: {len(edges)}")
    print(f"是否有下一页: {products['pageInfo']['hasNextPage']}")

    if edges:
        print()
        print("商品列表:")

        for i, edge in enumerate(edges[:20], 1):  # 只显示前20个
            product = edge["node"]
            title = product.get("title", "未知商品")
            product_type = product.get("productType", "未分类")
            vendor = product.get("vendor", "未知供应商")
            status = product.get("status", "unknown")
            total_inventory = product.get("totalInventory", 0)

            # 价格范围
            price_range = product.get("priceRangeV2", {})
            min_price = price_range.get("minVariantPrice", {})
            max_price = price_range.get("maxVariantPrice", {})

            print(f"{i}. {title}")
            print(f"   类型: {product_type} | 供应商: {vendor}")
            print(f"   状态: {status} | 库存: {total_inventory}")

            if min_price and max_price:
                print(f"   价格: {min_price['amount']}-{max_price['amount']} {min_price['currencyCode']}")

            # 变体信息
            variants = product.get("variants", {}).get("edges", [])
            if variants:
                print(f"   变体数: {len(variants)}")
                first_variant = variants[0]["node"]
                print(f"   第一个变体: {first_variant.get('title', 'N/A')} | SKU: {first_variant.get('sku', 'N/A')}")

            print()

def main():
    """主函数"""
    print("=== Shopify商品数据查询工具 ===")

    # 检查配置
    if not check_configuration():
        return

    # 执行GraphQL查询
    query = get_products_query(limit=50)

    print("正在执行GraphQL查询...")
    result = execute_graphql_query(query)

    if not result:
        print("查询执行失败")
        return

    # 检查是否有错误
    if "errors" in result:
        print("GraphQL查询返回错误:")
        for error in result["errors"]:
            print(f"   - {error.get('message', 'Unknown error')}")
        return

    # 保存数据
    save_products_data(result)

    # 分析数据
    analyze_products_data(result)

    print()
    print("查询完成！")

if __name__ == "__main__":
    main()