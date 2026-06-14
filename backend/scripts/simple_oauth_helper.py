"""
简化的Shopify OAuth助手 - 解决编码问题
"""
import os
import hashlib
import hmac
import requests
import json
from pathlib import Path
from datetime import datetime
import uuid
from urllib.parse import urlencode

# Shopify配置
SHOPIFY_DOMAIN = "99hg9z-1k.myshopify.com"
SHOPIFY_CLIENT_ID = "63a92d222d6ef96d2e99e15229a73888"
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "REDACTED_PLACEHOLDER")
SHOPIFY_REDIRECT_URI = "http://localhost:8000/api/v1/shopify/callback"
SHOPIFY_SCOPES = "read_products"

def generate_authorization_url():
    """生成授权URL"""
    state = uuid.uuid4().hex[:16]

    params = {
        'client_id': SHOPIFY_CLIENT_ID,
        'scope': SHOPIFY_SCOPES,
        'redirect_uri': SHOPIFY_REDIRECT_URI,
        'state': state,
        'response_type': 'code'
    }

    base_url = f"https://{SHOPIFY_DOMAIN}/admin/oauth/authorize"
    url = f"{base_url}?{urlencode(params)}"

    return url, state

def exchange_code_for_token(code):
    """用授权码交换access token"""
    url = f"https://{SHOPIFY_DOMAIN}/admin/oauth/access_token"

    payload = {
        'client_id': SHOPIFY_CLIENT_ID,
        'client_secret': SHOPIFY_CLIENT_SECRET,
        'code': code
    }

    try:
        response = requests.post(url, data=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('access_token')
    except Exception as e:
        print(f"Error exchanging code: {e}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response.text}")
        return None

def save_and_display_token(token):
    """保存并显示token"""
    # 保存到文件
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

    # 显示token信息
    print()
    print("=== Access Token获取成功! ===")
    print()
    print("Token信息:")
    print(f"Access Token: {token}")
    print(f"店铺域名: {SHOPIFY_DOMAIN}")
    print(f"权限范围: {SHOPIFY_SCOPES}")
    print(f"创建时间: {token_data['created_at']}")
    print()

    print("使用方法:")
    print("设置环境变量:")
    print(f'export SHOPIFY_ACCESS_TOKEN="{token}"')
    print(f'(Windows PowerShell: $env:SHOPIFY_ACCESS_TOKEN="{token}")')
    print()

    print("测试API访问:")
    print('python scripts/execute_shopify_query.py')
    print()

    print("文件已保存到:")
    print(f"{token_file.absolute()}")
    print()

    return token

def main():
    """主函数"""
    print("=== Shopify OAuth Helper ===")
    print()

    # 步骤1: 生成授权URL
    print("Step 1: Generate Authorization URL")
    print()

    auth_url, state = generate_authorization_url()

    print("Authorization URL:")
    print("-" * 50)
    print(auth_url)
    print("-" * 50)
    print()
    print(f"State: {state}")
    print()

    # 步骤2: 指导用户完成授权
    print("Step 2: Complete Authorization")
    print()
    print("Please follow these steps:")
    print("1. Copy the URL above")
    print("2. Open it in your browser")
    print("3. Login to Shopify if required")
    print("4. Authorize the app")
    print("5. You will be redirected to the callback URL")
    print()

    import webbrowser
    try:
        webbrowser.open(auth_url)
        print("Browser opened automatically...")
    except:
        print("Please manually copy the URL to your browser")

    print()

    # 步骤3: 获取授权码
    print("Step 3: Get Authorization Code")
    print()
    print("After authorization, you'll be redirected to:")
    print("http://localhost:8000/api/v1/shopify/callback?code=XXXXX&state=XXXXX")
    print()
    print("Please copy the 'code' parameter value from the URL")
    print()

    code = input("Enter authorization code: ").strip()

    if not code:
        print("No authorization code provided. Exiting...")
        return None

    print()
    print("Step 4: Exchange Code for Access Token")
    print()

    # 步骤4: 交换token
    token = exchange_code_for_token(code)

    if token:
        save_and_display_token(token)
        return token
    else:
        print()
        print("Failed to get access token")
        print("Please check:")
        print("1. Authorization code is correct")
        print("2. Client ID and Secret are correct")
        print("3. Redirect URI matches exactly")
        print("4. Shopify app has proper permissions")
        return None

if __name__ == "__main__":
    main()