"""
Shopify API 测试脚本 - 支持多种认证方式
"""
import os
import requests
import json
from pathlib import Path
from datetime import datetime

# Shopify配置
SHOPIFY_DOMAIN = "99hg9z-1k.myshopify.com"
SHOPIFY_API_VERSION = "2024-10"

# 尝试不同的认证头格式
AUTH_TOKENS = [
    os.environ.get("SHOPIFY_TOKEN", "REDACTED_PLACEHOLDER"),  # 请通过环境变量设置
    os.environ.get("SHOPIFY_TOKEN_LEGACY", "REDACTED_PLACEHOLDER"),
    # 如果需要其他格式，可以在这里添加
]

def test_auth_methods():
    """测试不同的认证方法"""
    print("=== 测试Shopify API认证方法 ===")
    print()

    # 测试GraphQL端点
    graphql_url = f"https://{SHOPIFY_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"

    # 简单的测试查询
    test_query = """
    query {
      shop {
        name
      }
    }
    """

    auth_methods = [
        {"name": "X-Shopify-Access-Token", "header": "X-Shopify-Access-Token"},
        {"name": "Authorization", "header": "Authorization"},
        {"name": "Bearer", "header": "Authorization", "prefix": "Bearer "},
    ]

    for token in AUTH_TOKENS:
        print(f"测试token: {token[:20]}...")
        print()

        for method in auth_methods:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            if method["name"] == "Bearer":
                headers[method["header"]] = method["prefix"] + token
            else:
                headers[method["header"]] = token

            try:
                print(f"  尝试方法: {method['name']}")

                response = requests.post(
                    graphql_url,
                    json={"query": test_query},
                    headers=headers,
                    timeout=10
                )

                print(f"  状态码: {response.status_code}")

                if response.status_code == 200:
                    print(f"  ✅ 成功!")
                    data = response.json()
                    if "data" in data:
                        shop_name = data["data"]["shop"]["name"]
                        print(f"  店铺名称: {shop_name}")
                    return token, method["name"]
                else:
                    print(f"  响应: {response.text[:200]}")

            except Exception as e:
                print(f"  异常: {e}")

            print()

    print("所有认证方法都失败了")
    return None, None

def execute_products_query(token, auth_method):
    """执行商品查询"""
    print(f"=== 使用 {auth_method} 方法查询商品 ===")

    graphql_url = f"https://{SHOPIFY_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"

    query = """
    query GetShopifyProducts($num: Int!) {
      products(first: $num) {
        edges {
          node {
            id
            title
            description
            handle
            vendor
            productType
            status
            featuredImage {
              url
              altText
            }
            variants(first: 5) {
              edges {
                node {
                  id
                  title
                  sku
                  price
                  availableForSale
                }
              }
            }
            priceRangeV2 {
              minVariantPrice {
                amount
                currencyCode
              }
              maxVariantPrice {
                amount
                currencyCode
              }
            }
            totalInventory
            tags
          }
        }
        pageInfo {
          hasNextPage
        }
      }
    }
    """

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    if auth_method == "Bearer":
        headers["Authorization"] = "Bearer " + token
    else:
        headers[auth_method] = token

    try:
        print("发送GraphQL查询...")
        response = requests.post(
            graphql_url,
            json={"query": query, "variables": {"num": 50}},
            headers=headers,
            timeout=30
        )

        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            if "errors" in data:
                print("GraphQL查询错误:")
                for error in data["errors"]:
                    print(f"  - {error.get('message', 'Unknown error')}")
                return None

            # 保存结果
            products = data["data"]["products"]
            edges = products["edges"]

            print(f"✅ 成功获取 {len(edges)} 个商品")

            # 保存到文件
            output_dir = Path("./data/shopify/products")
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"products_api_{timestamp}.json"

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"数据已保存到: {output_file}")

            # 显示商品摘要
            print()
            print("=== 商品数据摘要 ===")
            for i, edge in enumerate(edges[:10], 1):
                product = edge["node"]
                print(f"{i}. {product['title']}")
                print(f"   类型: {product['productType']} | 状态: {product['status']}")
                print(f"   库存: {product['totalInventory']} | 变体数: {len(product['variants']['edges'])}")
                print()

            return data
        else:
            print(f"请求失败: {response.text[:300]}")
            return None

    except Exception as e:
        print(f"请求异常: {e}")
        return None

def main():
    """主函数"""
    print("=== Shopify API 认证和查询测试 ===")
    print()

    # 第一步：测试认证方法
    working_token, working_method = test_auth_methods()

    if working_token:
        print()
        print(f"找到有效的认证方法: {working_method}")
        print()

        # 第二步：执行商品查询
        result = execute_products_query(working_token, working_method)

        if result:
            print()
            print("✅ 查询成功完成!")
        else:
            print()
            print("❌ 查询失败")
    else:
        print()
        print("❌ 未找到有效的认证方法")
        print()
        print("可能的原因:")
        print("1. Access Token不正确或已过期")
        print("2. Token权限不足（需要read_products权限）")
        print("3. 店铺域名不匹配")
        print()
        print("建议:")
        print("1. 检查Shopify后台: https://99hg9z-1k.myshopify.com/admin/apps/development")
        print("2. 确认App有read_products权限")
        print("3. 重新生成Access Token")

if __name__ == "__main__":
    main()