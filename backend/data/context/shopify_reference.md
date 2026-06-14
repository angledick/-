# Shopify 能力参考（Agent / Worker 运行时上下文）

> 当你收到 source 为 "shopify" 的事件时，请参考以下信息理解事件数据并执行任务。
> **所有 Shopify 操作必须通过 shopify-ai-toolkit 技能执行，禁止直连 Shopify REST/GraphQL API。**

## 核心原则

Shopify 操作链路：
```
事件 → Manager → Worker → Claude Agent SDK → shopify-ai-toolkit 技能 → Shopify API
```

你拥有以下 Shopify AI Toolkit 技能，请根据事件类型选择调用：

| 技能 | 适用场景 |
|---|---|
| `shopify-use-shopify-cli` | **授权认证**：`shopify store auth` 登录店铺、执行 GraphQL、库存/产品变更 |
| `shopify-onboarding-merchant` | **店铺连接**：引导商家连接店铺、安装应用 |
| `shopify-admin` | **Admin API**：产品 CRUD、订单管理、报关单证（设计/生成 GraphQL 查询） |
| `shopify-custom-data` | **Metafields**：HS编码、税务属性、合规元数据绑定 |
| `shopify-customer` | **客户账户**：客户通知、DSAR 数据请求 |
| `shopify-dev` | **知识库查询**：搜索 Shopify 开发文档 |
| `shopify-functions` | **后端逻辑**：配送自定义、税费计算、风控 Function |
| `shopify-storefront-graphql` | **前端查询**：产品详情、物流追踪展示 |

## 事件数据格式

### OAuth 授权事件

#### shopify:oauth_start（发起授权）

```json
{
  "event_code": "shopify:oauth_start",
  "source": "shopify",
  "shop": "my-store.myshopify.com",
  "message_id": "shopify_oauth_start_my-store_a1b2c3d4"
}
```

**处理指引：**
1. 使用 `shopify-use-shopify-cli` 技能的 `shopify store auth` 构建授权流程
2. 或使用 `shopify-onboarding-merchant` 技能引导连接店铺
3. 返回授权 URL 供用户跳转

#### shopify:oauth_callback（授权回调）

```json
{
  "event_code": "shopify:oauth_callback",
  "source": "shopify",
  "shop": "my-store.myshopify.com",
  "code": "授权码",
  "callback_params": {
    "code": "...",
    "shop": "...",
    "state": "...",
    "timestamp": "...",
    "hmac": "..."
  }
}
```

**处理指引：**
1. 使用 `shopify-use-shopify-cli` 技能用授权码交换访问令牌
2. 返回 `access_token` 和 `scope`（后端会通过 `save_token_from_sdk()` 持久化）
3. 输出格式：
```json
{
  "status": "authorized",
  "shop": "my-store.myshopify.com",
  "access_token": "shpat_xxx",
  "scope": "read_products,write_products,..."
}
```

### 产品事件

```json
{
  "event_code": "product:created",
  "source": "shopify",
  "shop": "99hg9z-1k.myshopify.com",
  "shopify_topic": "products/create",
  "product_id": "88123",
  "product_title": "Wireless Bluetooth Earbuds",
  "product_type": "Electronics",
  "vendor": "TechCo",
  "tags": "bluetooth, wireless, audio",
  "handle": "wireless-bluetooth-earbuds",
  "compliance_query": "Wireless Bluetooth Earbuds Electronics TechCo bluetooth, wireless, audio",
  "message_id": "shopify_products/create_88123_a1b2c3d4",
  "data": {}
}
```

### 同步事件

```json
{
  "event_code": "shopify:sync_products",
  "source": "shopify",
  "shop": "99hg9z-1k.myshopify.com",
  "access_token": "shpat_xxx",
  "since": "2025-06-13T10:00:00Z",
  "max_count": 50,
  "poll_triggered": true,
  "message_id": "shopify_poll_products_99hg9z_a1b2c3d4"
}
```

类似的同步事件还有 `shopify:sync_orders`、`shopify:sync_inventory`。

## 关键字段说明

| 字段 | 含义 | 用途 |
|---|---|---|
| `product_title` | 产品标题 | 合规审查核心内容 |
| `product_type` | 产品类型 | HS编码查询、法规匹配 |
| `vendor` | 供应商/品牌 | 品牌合规检查 |
| `tags` | 产品标签 | 关键词合规匹配 |
| `compliance_query` | 合规查询文本 | 已拼接好的检索关键词，直接用于合规知识库查询 |
| `shop` | 店铺域名 | 区分不同店铺来源 |
| `access_token` | API 访问令牌 | 在同步事件中提供，供 shopify-ai-toolkit 技能使用 |
| `data` | 原始 Webhook body | 完整的 Shopify 原始数据 |

## 事件类型与处理指引

### shopify:oauth_start（发起授权）

使用 `shopify-use-shopify-cli` 或 `shopify-onboarding-merchant` 技能：
1. 根据店铺域名和配置构建 OAuth 授权 URL
2. 返回授权 URL 供用户在浏览器中跳转

### shopify:oauth_callback（授权回调）

使用 `shopify-use-shopify-cli` 技能：
1. 用回调中的授权码交换访问令牌
2. 返回 access_token（后端会自动持久化）

### shopify:sync_products（产品同步）

使用 `shopify-admin` 或 `shopify-use-shopify-cli` 技能：
1. 用 `access_token` 调用 Admin API 拉取产品列表
2. `since` 字段提供增量同步起始时间（为空表示全量拉取）
3. 将产品导入本地产品管理体系
4. 对新产品触发合规初始化
5. 返回同步结果摘要

### shopify:sync_orders（订单同步）

使用 `shopify-admin` 技能拉取订单列表，检查目标市场合规要求。

### shopify:sync_inventory（库存同步）

使用 `shopify-admin` 技能查询库存水平。

### product:created（产品创建）

1. 提取 `product_title`、`product_type`、`vendor`、`tags` 字段
2. 用 `compliance_query` 字段查询合规知识库
3. 检查产品标题/描述是否包含禁用词、虚假宣传、违规声明
4. 检查产品类型对应的 HS 编码是否需要特殊认证（CE/FCC/REACH等）
5. 生成合规报告

### order:created（订单创建）

1. 从 `data` 中提取目标国家、商品清单、金额
2. 检查目标国家是否有特殊合规限制（如欧盟 VAT、CE 认证）
3. 检查商品清单是否都已通过合规审查
4. 标记需要人工审核的异常订单

### order:fulfilled（订单履约完成）

1. 提取物流追踪号和承运商
2. 触发出口报关准备
3. 记录发货信息

## 输出格式

请以 JSON 格式返回处理结果：

```json
{
  "status": "completed",
  "summary": "处理摘要",
  "details": "详细处理过程",
  "recommendations": ["建议1", "建议2"]
}
```
