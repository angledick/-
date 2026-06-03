# 订单履约事件定义

> 由QAAgent维护，覆盖订单从创建到签收/退货的完整生命周期
> 对应指南§3 阶段6-9：订单处理 → 出口报关 → 进口清关 → 交付售后

## 事件注册表

| 事件编码 | 事件名称 | 业务阶段 | 触发条件 | 关联Worker | 严重级别 | 通知策略 |
|----------|----------|----------|----------|------------|----------|----------|
| order:created | 订单创建 | 阶段6 | Shopify Webhook推送新订单 | order_worker | low | dashboard |
| order:confirmed | 订单确认 | 阶段6 | 订单支付确认，进入履约流程 | order_worker | low | dashboard |
| order:shipped | 订单发货 | 阶段6 | 供应商/仓库确认发货，生成追踪号 | order_worker | low | dashboard,websocket |
| order:customs_declared | 出口报关 | 阶段7 | 提交出口报关单据 | customs_worker | medium | dashboard |
| order:customs_cleared_export | 出口放行 | 阶段7 | 海关出口放行 | customs_worker | low | dashboard |
| order:in_transit | 跨境运输中 | 阶段7 | 货物在途中（17TRACK更新） | logistics_worker | low | dashboard |
| order:import_customs | 进口清关 | 阶段8 | 到达目的国，开始进口清关 | customs_worker | medium | dashboard |
| order:import_duty_paid | 关税缴纳 | 阶段8 | 目的国关税/VAT缴纳完成 | customs_worker | low | dashboard |
| order:delivered | 订单签收 | 阶段9 | 买家确认签收 | order_worker | low | dashboard |
| order:returned | 订单退货 | 阶段9 | 退货申请或退货完成 | order_worker | medium | dashboard,websocket |
| order:refund_issued | 退款发出 | 阶段9 | 退款处理完成 | order_worker | medium | dashboard |
| order:dispute | 订单争议 | 阶段9 | 买家发起争议/拒付 | order_worker | high | dashboard,websocket,email |

## 物流追踪集成（参考指南开源推荐：17TRACK API）

- 免费层支持500单/月追踪
- 支持3100+承运商
- Webhook回调更新订单状态
