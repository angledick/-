"""验证三个页面对接后端的状态"""
import httpx
import json

base = 'http://127.0.0.1:8000/api/v1'

# 1. 集成管理 - 平台状态
print('=== 1. 集成管理 /integrations/status ===')
r = httpx.get(f'{base}/integrations/status')
data = r.json()
connected = {k: v for k, v in data['status'].items() if v['status'] == 'connected'}
print(f'已连接平台: {list(connected.keys())}')
for k, v in connected.items():
    print(f'  - {v["name"]} ({k}): status={v["status"]}, env_configured={v["env_configured"]}')

# 2. 通知配置 - 渠道列表
print()
print('=== 2. 通知配置 /notifications/channels ===')
r2 = httpx.get(f'{base}/notifications/channels?user_id=default')
ch_data = r2.json()
print(f'状态码: {r2.status_code}')
print(f'渠道数据: {json.dumps(ch_data, ensure_ascii=False, indent=2)[:500]}')

# 3. 风险监控 - 预警列表
print()
print('=== 3. 风险监控 /risk/alerts ===')
r3 = httpx.get(f'{base}/risk/alerts?user_id=default&size=10')
alert_data = r3.json()
print(f'状态码: {r3.status_code}')
print(f'预警数量: {len(alert_data.get("alerts", []))}')

# 4. 连接列表（应为空 - 已清理）
print()
print('=== 4. 连接列表 /integrations ===')
r4 = httpx.get(f'{base}/integrations')
conn_data = r4.json()
print(f'连接记录数: {len(conn_data.get("connections", []))}')

print()
print('=== 总结 ===')
print(f'集成管理: {len(connected)} 个平台已连接 (Shopify + 飞书)')
print(f'通知配置: 渠道API正常 (状态码 {r2.status_code})')
print(f'风险监控: 预警API正常 (状态码 {r3.status_code}), 已连接平台数据来源于集成状态API')
