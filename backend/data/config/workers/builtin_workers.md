# 内置Worker定义

> 由QAAgent维护，用户可通过前端管理界面调整Worker配置
> 每个Worker对应一类业务阶段的处理逻辑

## Worker注册表

| Worker编码 | Worker名称 | 业务阶段 | 职责描述 | 可用Skills | 优先级 | 超时(秒) |
|------------|------------|----------|----------|------------|--------|----------|
| product_worker | 产品管理Worker | 阶段2-4 | 产品CRUD、生命周期状态管理、内容同步 | product_crud,lifecycle_manager | 2 | 300 |
| compliance_worker | 合规检查Worker | 全阶段 | 执行六阶段合规流水线（感知→检查→推荐→告知→交互→处理） | compliance_check,hs_lookup,vat_query | 1 | 600 |
| cert_worker | 认证管理Worker | 阶段3 | 认证上传/验证/到期预警/续期管理 | cert_verify,cert_monitor | 2 | 300 |
| listing_worker | 商品上架Worker | 阶段4 | Listing内容合规检查、Shopify发布 | content_check,shopify_publish | 2 | 300 |
| order_worker | 订单处理Worker | 阶段6-9 | 订单生命周期管理、物流追踪 | order_track,logistics_query | 3 | 300 |
| customs_worker | 报关清关Worker | 阶段7-8 | 出口报关/进口清关单据管理 | customs_declare,duty_calc | 2 | 600 |
| logistics_worker | 物流Worker | 阶段7-8 | 跨境运输追踪（17TRACK集成） | tracking_query,eta_calc | 3 | 300 |
| regulation_worker | 法规监控Worker | 全阶段 | 法规变更扫描、影响分析、知识库更新 | regulation_scan,impact_analysis | 1 | 600 |
| risk_worker | 风险预警Worker | 全阶段 | 风险评分计算、阈值监控、异常检测（PyOD） | risk_score,anomaly_detect | 1 | 300 |
| system_worker | 系统运维Worker | 全阶段 | API健康检查、同步任务、备份 | health_check,sync_task,backup | 3 | 120 |
| qa_agent | QAAgent | 全阶段 | 系统自我管理、配置问答、事件定义、流程串联 | config_manage,event_define,diagnose | 1 | 600 |

## Worker调度策略

| 策略 | 说明 | 适用Worker |
|------|------|------------|
| 优先级队列 | 优先级数字越小越先执行 | 全部 |
| 最大并发 | 限制同时运行的Worker实例数 | compliance_worker(3), order_worker(5) |
| 超时熔断 | 执行超时自动终止并告警 | 全部 |
| 失败重试 | 失败后自动重试（最多3次） | order_worker, customs_worker |
