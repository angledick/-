"""
使用Client Secret通过OAuth获取Access Token
"""
import os
import hashlib
import hmac
import requests
import json
from pathlib import Path
from datetime import datetime
import uuid

# Shopify配置
SHOPIFY_DOMAIN = "99hg9z-1k.myshopify.com"
SHOPIFY_CLIENT_ID = "63a92d222d6ef96d2e99e15229a73888"
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "REDACTED_PLACEHOLDER")  # 通过环境变量设置
SHOPIFY_REDIRECT_URI = "http://localhost:8000/api/v1/shopify/callback"
SHOPIFY_SCOPES = "read_products"

def generate_state():
    """生成state参数用于CSRF保护"""
    return uuid.uuid4().hex[:16]

def build_authorization_url():
    """构建OAuth授权URL"""
    params = {
        'client_id': SHOPIFY_CLIENT_ID,
        'scope': SHOPIFY_SCOPES,
        'redirect_uri': SHOPIFY_REDIRECT_URI,
        'state': generate_state(),
        'response_type': 'code'
    }

    from urllib.parse import urlencode
    base_url = f"https://{SHOPIFY_DOMAIN}/admin/oauth/authorize"
    url = f"{base_url}?{urlencode(params)}"

    return url

def exchange_code_for_token(code):
    """用授权码交换access token"""
    url = f"https://{SHOPIFY_DOMAIN}/admin/oauth/access_token"

    payload = {
        'client_id': SHOPIFY_CLIENT_ID,
        'client_secret': SHOPIFY_CLIENT_SECRET,
        'code': code
    }

    try:
        print("正在交换access token...")
        response = requests.post(url, data=payload)
        response.raise_for_status()

        data = response.json()
        access_token = data.get('access_token')

        if access_token:
            print(f"成功获取Access Token!")
            return access_token
        else:
            print("响应中没有找到access_token")
            print("响应内容:", data)
            return None

    except Exception as e:
        print(f"交换token失败: {e}")
        return None

def verify_webhook_hmac(hmac_header, raw_body):
    """验证Webhook HMAC签名（备用）"""
    digest = hmac.new(
        SHOPIFY_CLIENT_SECRET.encode('utf-8'),
        raw_body,
        hashlib.sha256
    ).digest()
    calculated_hmac = digest.hex()
    return hmac.compare_digest(calculated_hmac, hmac_header)

def save_access_token(token):
    """保存access token"""
    tokens_dir = Path("./data/shopify/tokens")
    tokens_dir.mkdir(parents=True, exist_ok=True)

    token_file = tokens_dir / f"{SHOPIFY_DOMAIN}.json"

    token_data = {
        "shop": SHOPIFY_DOMAIN,
        "access_token": token,
        "scope": SHOPIFY_SCOPES,
        "created_at": datetime.now().isoformat(),
        "client_id": SHOPIFY_CLIENT_ID
    }

    with open(token_file, 'w', encoding='utf-8') as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)

    print(f"Access token已保存到: {token_file}")
    return token_file

def test_api_access(token):
    """测试API访问"""
    graphql_url = f"https://{SHOPIFY_DOMAIN}/admin/api/2024-10/graphql.json"

    test_query = """
    query {
      shop {
        name
      }
    }
    """

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }

    try:
        print("测试API访问...")
        response = requests.post(
            graphql_url,
            json={"query": test_query},
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            shop_name = data["data"]["shop"]["name"]
            print(f"API访问成功! 店铺名称: {shop_name}")
            return True
        else:
            print(f"API访问失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"API测试异常: {e}")
        return False

def manual_oauth_flow():
    """手动OAuth流程"""
    print("=== Shopify OAuth 授权流程 ===")
    print()
    print("步骤1: 生成授权URL")
    print()

    auth_url = build_authorization_url()
    print("授权URL:")
    print(auth_url)
    print()

    print("步骤2: 访问授权URL")
    print("请复制上面的URL到浏览器中打开，完成Shopify授权")
    print()

    import webbrowser
    try:
        webbrowser.open(auth_url)
        print("已自动打开浏览器...")
    except:
        print("请手动复制URL到浏览器")

    print()
    print("步骤3: 获取授权码")
    print("授权后，你会被重定向到回调URL，URL中包含授权码(code参数)")
    print("回调URL格式: http://localhost:8000/api/v1/shopify/callback?code=xxx&state=xxx")
    print()

    code = input("请从回调URL中复制授权码(code): ").strip()

    if not code:
        print("未提供授权码，流程取消")
        return None

    print()
    print("步骤4: 交换Access Token")

    token = exchange_code_for_token(code)

    if token:
        print()
        print("=== 授权成功! ===")
        print(f"Access Token: {token[:20]}...")
        print()

        # 保存token
        save_access_token(token)

        # 测试API访问
        if test_api_access(token):
            print()
            print("现在可以使用这个token来:")
            print("1. 查询Shopify商品数据")
            print("2. 同步订单和客户信息")
            print("3. 管理商品库存")
            print("4. 进行合规检查")

        return token
    else:
        print("授权失败")
        return None

def check_existing_tokens():
    """检查现有token"""
    tokens_dir = Path("./data/shopify/tokens")

    if tokens_dir.exists():
        token_files = list(tokens_dir.glob("*.json"))
        if token_files:
            print("=== 现有Token文件 ===")
            for token_file in token_files:
                print(f"- {token_file.name}")

                try:
                    with open(token_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    token = data.get('access_token', '')
                    created = data.get('created_at', 'unknown')

                    print(f"  Token: {token[:20]}...")
                    print(f"  创建时间: {created}")
                    print(f"  权限: {data.get('scope', 'unknown')}")

                    # 测试这个token是否有效
                    if test_api_access(token):
                        print("  状态: 有效 ✓")
                        return token
                    else:
                        print("  状态: 无效 ✗")

                except:
                    print("  无法读取文件")

                print()
        else:
            print("没有找到现有token文件")
    else:
        print("tokens目录不存在")

    return None

def main():
    """主函数"""
    print("=== Shopify OAuth 认证助手 ===")
    print()

    print("当前配置:")
    print(f"店铺域名: {SHOPIFY_DOMAIN}")
    print(f"Client ID: {SHOPIFY_CLIENT_ID[:10]}...")
    print(f"Client Secret: {SHOPIFY_CLIENT_SECRET[:10]}...")
    print(f"权限范围: {SHOPIFY_SCOPES}")
    print()

    # 检查现有token
    print("检查现有token...")
    existing_token = check_existing_tokens()

    if existing_token:
        print()
        print("发现有效的现有token，可以直接使用!")
        return existing_token

    print()
    print("需要通过OAuth流程获取新的Access Token")
    print()

    # 执行OAuth流程
    token = manual_oauth_flow()

    if token:
        print()
        print("完成! 你现在可以使用Shopify API了")
        print(f"Access Token: {token}")
        print()
        print("设置环境变量:")
        print(f"export SHOPIFY_ACCESS_TOKEN='{token}'")
        print("(Windows PowerShell: $env:SHOPIFY_ACCESS_TOKEN='{token}')")

    return token

if __name__ == "__main__":
    main()