# 认证管理事件定义

> 由QAAgent维护，管理产品所需的各类合规认证（CE/WEEE/RoHS/FCC等）
> 对应指南§3 阶段3：供应商审核与采购中的认证合规

## 事件注册表

| 事件编码 | 事件名称 | 业务阶段 | 触发条件 | 关联Worker | 严重级别 | 通知策略 |
|----------|----------|----------|----------|------------|----------|----------|
| certification:uploaded | 认证上传 | 阶段3 | 上传认证文件（PDF/图片）到产品记录 | cert_worker | low | dashboard |
| certification:verified | 认证验证通过 | 阶段3 | 认证文件经RAG比对验证有效 | cert_worker | low | dashboard |
| certification:rejected | 认证验证失败 | 阶段3 | 认证文件无效或信息不匹配 | cert_worker | high | dashboard,websocket |
| certification:expiring | 认证即将到期 | 全阶段 | 认证在30天内到期（可配置阈值） | cert_worker | high | dashboard,websocket,email |
| certification:expired | 认证已过期 | 全阶段 | 认证超过有效期，产品合规状态变为failed | cert_worker | critical | dashboard,websocket,email |
| certification:renewed | 认证已续期 | 全阶段 | 认证续期完成，更新有效期 | cert_worker | low | dashboard |
| certification:required | 认证需求识别 | 阶段3 | 根据产品类目和目标市场识别所需认证 | cert_worker | medium | dashboard |
| certification:missing | 认证缺失 | 阶段3 | 产品缺少必要认证，阻止上架 | cert_worker | high | dashboard,websocket |

## 认证类型参考

| 认证名称 | 适用市场 | 适用品类 | 有效期 |
|----------|----------|----------|--------|
| CE | 欧盟 | 电子/玩具/机械 | 无固定（需定期复查） |
| WEEE | 德国/欧盟 | 电子电气 | 1年 |
| RoHS | 欧盟 | 电子电气 | 无固定 |
| FCC | 美国 | 电子产品 | 无固定 |
| UKCA | 英国 | 同CE | 无固定 |
| PSE | 日本 | 电子产品 | 3-7年 |
