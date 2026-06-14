"""
Shopify OAuth 认证助手

帮助用户通过OAuth流程获取Shopify访问令牌
"""
import hashlib
import base64
import requests
import os
from urllib.parse import urlencode, urlparse, parse_qs
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import webbrowser

# Shopify配置
SHOPIFY_DOMAIN = os.environ.get("SHOPIFY_DOMAIN", "99hg9z-1k.myshopify.com")
SHOPIFY_CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "63a92d222d6ef96d2e99e15229a73888")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "REDACTED_PLACEHOLDER")
SHOPIFY_REDIRECT_URI = "http://localhost:8000/api/v1/shopify/callback"
SHOPIFY_SCOPES = "read_products"

def generate_nonce():
    """生成随机nonce"""
    import uuid
    return uuid.uuid4().hex[:16]

def calculate_hmac(secret, data):
    """计算HMAC签名"""
    digest = hashlib.sha256(secret.encode('utf-8'))
    digest.update(data.encode('utf-8'))
    return digest.hexdigest()

def build_authorization_url():
    """构建OAuth授权URL"""
    params = {
        'client_id': SHOPIFY_CLIENT_ID,
        'scope': SHOPIFY_SCOPES,
        'redirect_uri': SHOPIFY_REDIRECT_URI,
        'state': generate_nonce(),
        'response_type': 'code'
    }

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
        response = requests.post(url, data=payload)
        response.raise_for_status()

        data = response.json()
        access_token = data.get('access_token')

        if access_token:
            print(f"成功获取Access Token: {access_token[:20]}...")
            return access_token
        else:
            print("响应中没有找到access_token")
            return None

    except Exception as e:
        print(f"交换token失败: {e}")
        return None

def save_access_token(token):
    """保存access token到文件"""
    tokens_dir = Path("./data/shopify/tokens")
    tokens_dir.mkdir(parents=True, exist_ok=True)

    token_file = tokens_dir / f"{SHOPIFY_DOMAIN}.json"

    import json
    token_data = {
        "shop": SHOPIFY_DOMAIN,
        "access_token": token,
        "scope": SHOPIFY_SCOPES,
        "created_at": str(datetime.now())
    }

    with open(token_file, 'w', encoding='utf-8') as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)

    print(f"Access token已保存到: {token_file}")
    return token_file

def manual_oauth_flow():
    """手动OAuth流程"""
    print("=== Shopify OAuth 授权流程 ===")
    print()
    print("步骤1: 访问授权URL")
    print()

    auth_url = build_authorization_url()
    print(f"授权URL: {auth_url}")
    print()

    print("步骤2: 点击上面的URL，在浏览器中完成授权")
    print("授权后，你会被重定向到回调URL，URL中包含授权码(code)")
    print()

    # 自动打开浏览器
    try:
        webbrowser.open(auth_url)
        print("已自动打开浏览器，请完成授权...")
    except:
        print("请手动复制上面的URL到浏览器中打开")

    print()
    print("步骤3: 从回调URL中复制授权码")
    print("回调URL格式类似: http://localhost:8000/api/v1/shopify/callback?code=xxx&state=xxx")
    print()
    code = input("请输入授权码(code): ").strip()

    if code:
        print()
        print("步骤4: 交换access token...")
        token = exchange_code_for_token(code)

        if token:
            print()
            print("=== 授权成功！===")
            print(f"Access Token: {token}")
            print()
            print("你现在可以使用这个token来访问Shopify API了")
            print()

            save_access_token(token)

            print()
            print("设置环境变量:")
            print(f"export SHOPIFY_ACCESS_TOKEN='{token}'")
            print("(Windows PowerShell: $env:SHOPIFY_ACCESS_TOKEN='{token}')")

            return token
    else:
        print("未提供授权码，流程取消")
        return None

def direct_api_access():
    """直接API访问方法（使用现有token）"""
    print("=== 直接使用Access Token ===")
    print()
    print("如果你已经有了Access Token，可以直接输入:")
    print()

    token = input("请输入你的Shopify Access Token: ").strip()

    if token:
        # 简单验证token格式
        if token.startswith('shpat_') and len(token) > 50:
            print()
            print("Token格式看起来正确！")
            save_access_token(token)

            print()
            print("设置环境变量:")
            print(f"export SHOPIFY_ACCESS_TOKEN='{token}'")
            print("(Windows PowerShell: $env:SHOPIFY_ACCESS_TOKEN='{token}')")

            return token
        else:
            print()
            print("警告: Token格式可能不正确")
            print("Shopify Access Token通常以'shpat_'开头，长度约64字符")
            print("你提供的token:", token[:20] + "..." if len(token) > 20 else token)

            confirm = input("仍然要保存这个token吗？(y/n): ").lower()
            if confirm == 'y':
                save_access_token(token)
                return token
    else:
        print("未输入token")
        return None

def check_existing_tokens():
    """检查现有的token文件"""
    tokens_dir = Path("./data/shopify/tokens")

    if tokens_dir.exists():
        token_files = list(tokens_dir.glob("*.json"))
        if token_files:
            print("=== 现有的Shopify Token文件 ===")
            for token_file in token_files:
                print(f"- {token_file.name}")

                # 读取并显示token信息
                try:
                    import json
                    with open(token_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    print(f"  店铺: {data.get('shop', 'unknown')}")
                    print(f"  Token: {data.get('access_token', '')[:20]}...")
                    print(f"  权限: {data.get('scope', 'unknown')}")
                    print(f"  创建时间: {data.get('created_at', 'unknown')}")
                    print()
                except:
                    print(f"  (无法读取文件)")
                    print()

            return True
        else:
            print("没有找到现有的token文件")
            return False
    else:
        print("tokens目录不存在")
        return False

def main():
    """主函数"""
    print("=== Shopify OAuth 认证助手 ===")
    print("=" * 50)
    print()

    print("当前配置:")
    print(f"店铺域名: {SHOPIFY_DOMAIN}")
    print(f"Client ID: {SHOPIFY_CLIENT_ID[:10]}...")
    print(f"Client Secret: {SHOPIFY_CLIENT_SECRET[:10]}...")
    print(f"权限范围: {SHOPIFY_SCOPES}")
    print()

    # 检查现有token
    check_existing_tokens()

    print("请选择认证方式:")
    print("1. OAuth 授权流程（推荐用于生产环境）")
    print("2. 直接输入Access Token（如果你已经有了token）")
    print("3. 退出")
    print()

    choice = input("请输入选择 (1/2/3): ").strip()

    if choice == '1':
        manual_oauth_flow()
    elif choice == '2':
        direct_api_access()
    else:
        print("退出")

if __name__ == "__main__":
    from datetime import datetime
    main()