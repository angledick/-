---
category: order
events:
  - event_code: "order:created"
    event_name: "订单创建"
    business_stage: "阶段6"
    severity: low
    worker: order_worker
    skills: ["order_track", "logistics_query"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "Shopify Webhook推送新订单"
    agent_action: "从Webhook负载中提取订单详情（商品、数量、金额、地址）。检查产品清单中各商品的合规状态。标记订单合规检查状态为pending，传递给compliance_worker。"
  - event_code: "order:confirmed"
    event_name: "订单确认"
    business_stage: "阶段6"
    severity: low
    worker: order_worker
    skills: ["order_track"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "订单支付确认，进入履约流程"
    agent_action: "确认支付状态，更新订单状态为待发货。触发合规检查：验证产品VAT税率和认证是否齐全。通知仓库备货。"
  - event_code: "order:shipped"
    event_name: "订单发货"
    business_stage: "阶段6"
    severity: low
    worker: order_worker
    skills: ["order_track", "logistics_query"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "供应商/仓库确认发货，生成追踪号"
    agent_action: "记录追踪号和物流商。更新订单状态为shipped。通知买家发货信息。自动发起物流追踪订阅（17TRACK API）。"
  - event_code: "order:customs_declared"
    event_name: "出口报关"
    business_stage: "阶段7"
    severity: medium
    worker: customs_worker
    skills: ["customs_declare", "duty_calc"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "提交出口报关单据"
    agent_action: "验证报关单据完整性。提交出口报关到目的国海关系统。记录报关单号，更新订单状态为出口报关中。触发合规检查确保HS编码准确。"
  - event_code: "order:customs_cleared_export"
    event_name: "出口放行"
    business_stage: "阶段7"
    severity: low
    worker: customs_worker
    skills: ["customs_declare"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "海关出口放行"
    agent_action: "确认出口放行状态。更新物流状态为offshore。记录放行时间，计算已清关时间的时效指标。"
  - event_code: "order:in_transit"
    event_name: "跨境运输中"
    business_stage: "阶段7"
    severity: low
    worker: logistics_worker
    skills: ["tracking_query", "eta_calc"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "货物在途中（17TRACK更新）"
    agent_action: "更新运输轨迹和预计到达时间。监控运输时效是否偏离预期。如延迟超阈值，触发异常预警。"
  - event_code: "order:import_customs"
    event_name: "进口清关"
    business_stage: "阶段8"
    severity: medium
    worker: customs_worker
    skills: ["customs_declare", "duty_calc"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "到达目的国，开始进口清关"
    agent_action: "准备进口清关文件（发票/箱单/原产地证）。检查目的国认证和标签要求。提交进口清关申请。核实关税预付状态。"
  - event_code: "order:import_duty_paid"
    event_name: "关税缴纳"
    business_stage: "阶段8"
    severity: low
    worker: customs_worker
    skills: ["duty_calc"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "目的国关税/VAT缴纳完成"
    agent_action: "记录关税缴纳金额和凭证。更新支付状态。更新物流状态进入本地派送阶段。"
  - event_code: "order:delivered"
    event_name: "订单签收"
    business_stage: "阶段9"
    severity: low
    worker: order_worker
    skills: ["order_track"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "买家确认签收"
    agent_action: "确认签收状态。更新订单生命周期为aftersale。触发售后合规流程：退货政策复核、客户评价邀请、质量反馈记录。"
  - event_code: "order:returned"
    event_name: "订单退货"
    business_stage: "阶段9"
    severity: medium
    worker: order_worker
    skills: ["order_track"]
    tools: []
    notify_strategy: ["dashboard", "websocket"]
    trigger_condition: "退货申请或退货完成"
    agent_action: "确认退货原因和退货商品状态。启动退货物流。检查退货产品是否合规再销售或报废。更新库存和财务记录。"
  - event_code: "order:refund_issued"
    event_name: "退款发出"
    business_stage: "阶段9"
    severity: medium
    worker: order_worker
    skills: ["order_track"]
    tools: []
    notify_strategy: ["dashboard"]
    trigger_condition: "退款处理完成"
    agent_action: "确认退款金额和退款方式。更新订单财务状态。关闭退货工单。记录退款原因到合规分析。"
  - event_code: "order:dispute"
    event_name: "订单争议"
    business_stage: "阶段9"
    severity: high
    worker: order_worker
    skills: ["order_track"]
    tools: []
    notify_strategy: ["dashboard", "websocket", "email"]
    trigger_condition: "买家发起争议/拒付"
    agent_action: "立即标记订单状态为disputed。收集交易证据（聊天记录、物流追踪、签收证明）。通知客服团队启动争议处理流程。评估拒付风险等级。"
---
# 订单履约事件定义

> 由 QAAgent 维护，覆盖订单从创建到签收/退货的完整生命周期
> 对应指南 §3 阶段6-9：订单处理 → 出口报关 → 进口清关 → 交付售后

## 物流追踪集成（参考指南开源推荐：17TRACK API）

- 免费层支持500单/月追踪
- 支持3100+承运商
- Webhook回调更新订单状态
