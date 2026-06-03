# 产品生命周期事件定义

> 由QAAgent维护，用户可通过前端管理界面或对话添加新事件
> 对应指南§3 阶段2-4：选品设计 → 供应商审核 → 商品上架

## 事件注册表

| 事件编码 | 事件名称 | 业务阶段 | 触发条件 | 关联Worker | 严重级别 | 通知策略 |
|----------|----------|----------|----------|------------|----------|----------|
| product:created | 产品创建 | 阶段2 | 新产品纳入管理（Shopify导入或手动添加） | product_worker | low | dashboard |
| product:design_started | 设计启动 | 阶段2 | 产品进入设计阶段，开始HS编码查询 | product_worker | low | dashboard |
| product:status_changed | 状态变更 | 全阶段 | 产品生命周期状态变更（8阶段状态机转换） | product_worker | medium | dashboard,websocket |
| product:listed | 产品上架 | 阶段4 | 产品状态变为active，Listing发布到Shopify | listing_worker | medium | dashboard,websocket |
| product:content_updated | 内容更新 | 阶段4 | 产品Listing内容变更（标题/描述/图片） | listing_worker | low | dashboard |
| product:ended | 产品下架 | 全阶段 | 产品状态变为end，从Shopify下架 | product_worker | low | dashboard |
| product:archived | 产品归档 | 全阶段 | 产品长期未活跃自动归档 | product_worker | low | dashboard |
| product:duplicate | 产品复制 | 阶段2 | 基于现有产品创建新产品 | product_worker | low | dashboard |

## 状态机转换规则

```
concept → design → sourcing → ready → active → fulfilling → aftersale → end
                  ↗                                         ↗
         (可直接跳过)                              (可并行多订单)
```

## 事件Schema定义

```yaml
event_schema:
  required:
    - event_code
    - event_name
    - business_stage
    - trigger_condition
  optional:
    - related_worker
    - severity
    - notify_strategy
    - description
    - data_schema
```
