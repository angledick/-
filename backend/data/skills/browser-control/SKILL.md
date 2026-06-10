---
name: browser-control
display_name: 浏览器控制
description: OpenCLI 浏览器自动化（导航/快照/站点数据抓取），支持守护进程和subprocess两种模式
source: script
script: script/opencli_browser.py
script_args: ["--action", "{action}", "--params", "{params}"]
business_stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
---

# 浏览器控制 Skill

## 概述

通过 OpenCLI 实现浏览器自动化控制，支持两种调用路径：
1. **subprocess** — 调用 `opencli <site> <command>` 获取结构化数据（无需浏览器）
2. **daemon HTTP** — 向 localhost:19825 发送浏览器自动化命令（需要 Chrome + 扩展）

## 执行方式

此 Skill 为 **脚本驱动**，通过 Python subprocess 执行独立脚本。

| 步骤 | 说明 |
|------|------|
| 触发 | Agent 调用或定时任务 |
| 路由 | `SkillExecutor._run_skill()` → `_execute_script_skill()` |
| 脚本 | `script/opencli_browser.py` |
| 前置 | `npm i -g @anthropic/opencli`（subprocess模式）/ `opencli daemon start`（浏览器模式）|

## 输入参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| action | str | 是 | — | status / site / navigate / snapshot / action |
| site | str | 否 | — | 站点名称（site action 用） |
| command | str | 否 | — | 站点命令（site action 用） |
| url | str | 否 | — | 导航 URL（navigate action 用） |
| session | str | 否 | default | 浏览器会话 ID |

## 输出

```json
{
  "ok": true,
  "data": { "...": "..." }
}
```

## script/

此目录包含独立可执行 Python 脚本 `opencli_browser.py`，支持 CLI 参数和 stdin JSON 调用。
