# 避风港 · 物流报关深度优化 — 开发进度日志

> 基于《避风港_物流报关深度优化_开发文档.md》  
> 分支：feat/event-bus-ws-optimization

---

## 进度总览

| Phase | 内容 | 状态 | 完成 |
|-------|------|------|------|
| A | 数据基础层 | ✅ 完成 | 2026-06-14 |
| B | 三单一致性 + Webhook 加固 | ✅ 完成 | 2026-06-14 |
| C | 17TRACK 集成 + 订单 API | ✅ 完成 | 2026-06-14 |

---

## API 接口清单（本次新增/修改）

### 新增：销售订单 `/api/v1/orders`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/v1/orders` | 订单列表（product_id/platform/status 过滤） | ✅ |
| POST | `/api/v1/orders` | 创建订单（支持 Shopify/手动） | ✅ |
| GET | `/api/v1/orders/{id}` | 订单详情 | ✅ |
| PUT | `/api/v1/orders/{id}` | 更新订单 | ✅ |
| POST | `/api/v1/orders/{id}/payments` | 添加支付记录 | ✅ |
| GET | `/api/v1/orders/{id}/payments` | 支付记录列表 + 汇总 | ✅ |
| GET | `/api/v1/orders/{id}/consistency-check` | **三单一致性检查** | ✅ |

### 扩展：报关 `/api/v1/customs`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/v1/customs/declarations` | 报关单生成（新增 15 个字段） | ✅ 扩展 |
| POST | `/api/v1/customs/declarations/{id}/check` | 合规检查（+管制品+三单一致性） | ✅ 扩展 |
| GET | `/api/v1/customs/controlled-goods/check` | **管制品快速检查** | ✅ 新增 |
| POST | `/api/v1/customs/three-way-check` | **三单一致性独立接口** | ✅ 新增 |
| POST | `/api/v1/customs/duty-calculator` | 关税计算（扩展至 20 国） | ✅ 扩展 |
| GET | `/api/v1/customs/tariff-rates` | 税率表（20 国） | ✅ 扩展 |

### 加固：物流 `/api/v1/logistics`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/v1/logistics/webhook/17track` | 17TRACK Webhook（HMAC+幂等+日志） | ✅ 加固 |
| POST | `/api/v1/logistics/webhook/aftership` | AfterShip Webhook（HMAC+幂等+日志） | ✅ 加固 |

---

## Phase A 详情

### 新建文件

| 文件 | 作用 |
|------|------|
| `app/storage/order_store.py` | 销售订单 + 支付记录 + Webhook 幂等日志 |
| `app/core/controlled_goods_checker.py` | 管制品规则引擎（制裁国+HS高危+新疆棉+稀土） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `app/storage/customs_store.py` | `_migrate_columns()` 新增 15 字段；`lookup_duty_rate()` 支持 `_ref`；`create_declaration()` 动态 INSERT |
| `data/customs/tariff_rates.json` | 从 7 国扩展至 20 国（新增 SG/MY/TH/VN/IN/BR/MX/AE/SA/ZA/TR/PL + 22 个 EU 成员国 _ref） |

### 三张新表

```sql
sales_orders       -- 销售订单主表
payment_records    -- 支付记录
webhook_event_log  -- Webhook 幂等去重
```

---

## Phase B 详情

### 新建文件

| 文件 | 作用 |
|------|------|
| `app/core/three_way_checker.py` | 三单一致性检查（6 维度真实对比） |

### 三单一致性检查维度

| 维度 | 规则 |
|------|------|
| 支付完整性 | 是否有 completed 状态的支付记录 |
| 订单 vs 支付金额 | 差异 ≤ 10%（汇率容忍） |
| **申报价值 vs 订单金额** | 申报 ≥ 订单 70%（低申报检测） |
| **收货人一致性** | buyer_name ≈ consignee_name |
| 数量一致性 | 订单总数 = 申报数量 |
| 目的国一致性 | 买家地址国 = 报关目的国 = 物流目的国 |

### Webhook 安全加固

- HMAC-SHA256 签名验证（可选，配置 `TRACK17_WEBHOOK_SECRET` 后强制验证）
- 幂等去重（`webhook_event_log` 表记录已处理事件 ID）
- 异步后台处理（快速返回 200，防 Webhook 超时重试）
- 结构化日志（不再静默吞掉异常）
- WS 实时推送 `logistics_updated` 事件

---

## Phase C 详情

### 新建文件

| 文件 | 作用 |
|------|------|
| `app/api/orders.py` | 销售订单 + 支付记录 + 三单一致性检查 API |

### 报关单字段扩充（DeclarationCreate）

新增 15 个字段：
```
brand / model_spec / unit_price / fx_rate_date          商品详情
shipper_name / shipper_address / shipper_eori           发货人
consignee_name / consignee_address                      收货人
order_id / contract_no / invoice_no                     关联单据
export_license_no / co_cert_no / ecommerce_record_no    许可证/备案
```

---

## 环境变量（新增，需配置）

```bash
TRACK17_API_KEY=          # 17TRACK 追踪 API Key
TRACK17_WEBHOOK_SECRET=   # 17TRACK Webhook 签名密钥
AFTERSHIP_HMAC_SECRET=    # AfterShip Webhook 签名密钥
```

---

## 变更记录

| 时间 | 内容 |
|------|------|
| 2026-06-14 | 开始开发，Phase A 完成 |
| 2026-06-14 | Phase B 完成（三单一致性 + Webhook 加固） |
| 2026-06-14 | Phase C 完成（订单 API + 报关字段扩充） |
| 2026-06-14 | 前端集成完成（API 客户端 + 页面对接，详见下方） |

---

## 前端集成状态

### API 客户端覆盖度（`frontend/src/api/config.ts`）

| API 模块 | 后端端点数 | 前端方法数 | 状态 |
|----------|-----------|-----------|------|
| ordersApi | 7 | 7 (list/create/get/update/getPayments/addPayment/consistencyCheck) | ✅ 完整 |
| customsApi | 11 | 11 (create/list/get/submit/check/clear/markException/calculateDuty/getTariffRates/checkControlledGoods/threeWayCheck) | ✅ 完整 |
| logisticsApi | 6 (+2 webhook) | 6 (listCarriers/createShipment/listShipments/getShipment/getTracking/refreshTracking) | ✅ 完整 |

> Webhook 端点（`/webhook/17track`、`/webhook/aftership`）为服务端接收，无需前端调用。

### 页面级功能对接

| 功能 | 页面文件 | 使用的 API | 状态 |
|------|---------|-----------|------|
| 销售订单管理 | `pages/OrdersPage.tsx` | ordersApi.list/create/getPayments/addPayment/consistencyCheck | ✅ |
| 物流轨迹追踪 | `pages/LogisticsTrackingPage.tsx` | logisticsApi.listShipments/createShipment/getTracking/refreshTracking + WS | ✅ |
| 三单一致性检查 | `pages/OrdersPage.tsx` | ordersApi.consistencyCheck | ✅ |
| 关税计算器（20 国） | `pages/ProductLifecyclePage.tsx` | customsApi.calculateDuty | ✅ |
| 报关单 CRUD | `pages/ProductLifecyclePage.tsx` | customsApi.create/list/submit/check | ✅ |
| 报关扩展字段（15个） | `api/config.ts` 类型定义 | customsApi.create() 含全部字段 | ✅ |
| 支付记录管理 | `pages/OrdersPage.tsx` | ordersApi.getPayments/addPayment | ✅ |
| WS 实时物流推送 | `pages/LogisticsTrackingPage.tsx` | WebSocketContext logistics_updated | ✅ |

### 路由与导航

| 路由 | 侧边栏入口 | 状态 |
|------|-----------|------|
| `/app/orders` | 「销售订单」(ShoppingCart) | ✅ |
| `/app/logistics` | 「物流追踪」(Truck) | ✅ |

### TypeScript 类型完整性

- `SalesOrder` / `PaymentRecord` / `ConsistencyCheckResult` — ✅
- `CustomsDeclaration` + 15 扩展字段 — ✅
- `LogisticsOrder` / `DutyCalcResult` — ✅
- `customsApi.create()` 参数含 15 扩展字段 — ✅
