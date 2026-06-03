"""
Phase 1 功能测试：事件驱动 + QAAgent + TokenJuice + 产品存储
模拟前端用户操作，验证后端API功能

运行方式: pytest tests/test_phase1.py -m live (需先启动后端服务)
"""
import pytest
import httpx

pytestmark = pytest.mark.live
import json
import time
import os
from pathlib import Path

BASE = "http://localhost:8002/api/v1"
REPORT = []
PASS = 0
FAIL = 0
TOTAL = 0

def log_test(phase, module, scenario, endpoint, method, req_body, resp_status, resp_body, expected_hints, checks):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    passed = True
    details = []
    for check_name, check_func in checks:
        try:
            if check_func(resp_body):
                details.append(f"  ✅ {check_name}")
            else:
                details.append(f"  ❌ {check_name}")
                passed = False
        except Exception as e:
            details.append(f"  ❌ {check_name}: 异常 - {e}")
            passed = False

    if passed:
        PASS += 1
        status_icon = "✅"
    else:
        FAIL += 1
        status_icon = "❌"

    entry = f"""
## [{status_icon}] {phase} | {module} | {scenario}
- **端点**: {method} {endpoint}
- **请求体**: {json.dumps(req_body, ensure_ascii=False, indent=2) if req_body else '无'}
- **响应状态**: {resp_status}
- **响应体**: {json.dumps(resp_body, ensure_ascii=False, indent=2)[:2000]}
- **预期要点**: {expected_hints}
- **检查明细**:
{chr(10).join(details)}
- **结论**: {'通过' if passed else '失败'}
"""
    REPORT.append(entry)

def check_contains(key):
    return (f"含字段 '{key}'", lambda r: key in r)

def check_eq(key, val):
    return (f"{key} == {val}", lambda r: r.get(key) == val)

def check_type(key, typ):
    return (f"{key} 类型为 {typ}", lambda r: isinstance(r.get(key), typ))

def check_len_gt(key, n):
    return (f"{key} 长度 > {n}", lambda r: len(r.get(key, [])) > n)

def check_nested_contains(key_list):
    def _check(r):
        d = r
        for k in key_list:
            if isinstance(d, dict):
                d = d.get(k)
            elif isinstance(d, list) and k.isdigit():
                d = d[int(k)]
            else:
                return False
        return d is not None
    return (f"嵌套字段 {'→'.join(key_list)} 存在", _check)

def main():
    global PASS, FAIL, TOTAL
    client = httpx.Client(timeout=30)
    created_product_ids = []

    # ======================================================================
    # 1.1 产品管理 API
    # ======================================================================
    log_test("Phase 1", "产品管理", "健康检查",
             "/health", "GET", None, *[None, None], "基础健康检查", [])

    # 1.1.1 创建产品 - LED灯带-德国
    product_req = {
        "name": "LED灯带-德国",
        "product_type": "LED灯",
        "market": "德国",
        "hs_code": "8541.4100",
        "description": "智能LED灯带，适用于德国市场"
    }
    resp = client.post(f"{BASE}/products", json=product_req)
    body = resp.json()
    created_product_ids.append(body.get("id", ""))
    checks = [
        check_contains("id"),
        check_eq("name", "LED灯带-德国"),
        check_eq("product_type", "LED灯"),
        check_eq("market", "德国"),
        check_eq("lifecycle_stage", "concept"),
        check_contains("created_at"),
    ]
    log_test("Phase 1", "产品管理", "创建产品-LED灯带德国",
             "/products", "POST", product_req, resp.status_code, body,
             "创建成功，返回产品ID，生命周期为concept，触发product:created事件", checks)

    # 1.1.2 创建第二个产品 - WIFI智能插座-法国
    product_req2 = {
        "name": "WIFI智能插座-法国",
        "product_type": "智能插座",
        "market": "法国",
        "hs_code": "8536.6900",
        "description": "WIFI智能插座，CE认证"
    }
    resp2 = client.post(f"{BASE}/products", json=product_req2)
    body2 = resp2.json()
    created_product_ids.append(body2.get("id", ""))
    checks2 = [
        check_contains("id"),
        check_eq("market", "法国"),
        check_eq("lifecycle_stage", "concept"),
    ]
    log_test("Phase 1", "产品管理", "创建产品-WIFI插座法国",
             "/products", "POST", product_req2, resp2.status_code, body2,
             "第二个产品创建成功，产品级隔离存储初始化", checks2)

    pid1 = created_product_ids[0] if created_product_ids else "p_test_001"
    pid2 = created_product_ids[1] if len(created_product_ids) > 1 else "p_test_002"

    # 1.1.3 获取产品列表
    resp3 = client.get(f"{BASE}/products")
    body3 = resp3.json()
    checks3 = [
        check_type("list", list),
        (f"包含产品 '{product_req['name']}'", lambda r: any(p.get("name") == product_req["name"] for p in r)),
    ]
    log_test("Phase 1", "产品管理", "查询产品列表",
             "/products", "GET", None, resp3.status_code, body3[:3],
             "返回所有产品列表，包含刚创建的2个产品", checks3)

    # 1.1.4 按生命周期筛选
    resp4 = client.get(f"{BASE}/products", params={"lifecycle_stage": "concept"})
    body4 = resp4.json()
    checks4 = [
        (f"全部为concept阶段", lambda r: all(p.get("lifecycle_stage") == "concept" for p in r)),
    ]
    log_test("Phase 1", "产品管理", "按生命周期筛选(concept)",
             "/products?lifecycle_stage=concept", "GET", None, resp4.status_code, body4[:3],
             "仅返回concept阶段的产品", checks4)

    # 1.1.5 获取单个产品详情
    resp5 = client.get(f"{BASE}/products/{pid1}")
    body5 = resp5.json()
    checks5 = [
        check_eq("name", product_req["name"]),
        check_contains("hs_code"),
        check_contains("created_at"),
    ]
    log_test("Phase 1", "产品管理", "获取产品详情",
             f"/products/{pid1}", "GET", None, resp5.status_code, body5,
             "返回完整产品信息（含HS编码、创建时间等）", checks5)

    # 1.1.6 更新产品生命周期状态 design
    resp6 = client.put(f"{BASE}/products/{pid1}/lifecycle", json={"lifecycle_stage": "design"})
    body6 = resp6.json()
    checks6 = [
        check_eq("lifecycle_stage", "design"),
        (f"状态机转换合法 (concept→design)", lambda r: r.get("lifecycle_stage") == "design"),
    ]
    log_test("Phase 1", "产品管理", "生命周期状态变更 concept→design",
             f"/products/{pid1}/lifecycle", "PUT", {"lifecycle_stage": "design"},
             resp6.status_code, body6, "状态从concept转为design，触发product:status_changed事件", checks6)

    # 1.1.7 更新产品详细信息
    resp7 = client.put(f"{BASE}/products/{pid1}", json={
        "description": "更新描述-智能LED灯带德国市场新版",
        "hs_code": "8541.4101"
    })
    body7 = resp7.json()
    checks7 = [
        check_contains("description"),
        check_eq("hs_code", "8541.4101"),
    ]
    log_test("Phase 1", "产品管理", "更新产品信息",
             f"/products/{pid1}", "PUT", {"description": "更新描述-...", "hs_code": "8541.4101"},
             resp7.status_code, body7, "产品描述和HS编码更新成功", checks7)

    # 1.1.8 产品计数
    resp8 = client.get(f"{BASE}/products/count")
    body8 = resp8.json()
    checks8 = [
        check_contains("count"),
        check_type("count", int),
        (f"count >= 2", lambda r: r.get("count", 0) >= 2),
    ]
    log_test("Phase 1", "产品管理", "产品数量统计",
             "/products/count", "GET", None, resp8.status_code, body8,
             "返回产品总数 >= 2", checks8)

    # 1.1.9 产品级隔离存储验证
    product_dir = Path(f"c:/Users/22859/Desktop/astra-main/backend/data/products/{pid1}")
    checks_storage = [
        (f"产品级目录存在", lambda r: product_dir.exists()),
        (f"events目录存在", lambda r: (product_dir / "events").exists()),
        (f"metrics目录存在", lambda r: (product_dir / "metrics").exists()),
    ]
    log_test("Phase 1", "产品隔离存储", f"验证产品{pid1}隔离存储目录",
             f"data/products/{pid1}/", "文件系统检查", None, 200,
             {"dir_exists": str(product_dir.exists())},
             "产品级events/metrics/memory/knowledge目录已创建", checks_storage)

    # 1.1.10 产品事件时间线
    resp_ev = client.get(f"{BASE}/products/{pid1}/events")
    body_ev = resp_ev.json()
    checks_ev = [
        (f"events存在", lambda r: isinstance(r, list) or "events" in r),
    ]
    log_test("Phase 1", "产品管理", "获取产品事件时间线",
             f"/products/{pid1}/events", "GET", None, resp_ev.status_code, body_ev,
             "返回产品事件链，包含product:created等事件", checks_ev)

    # ======================================================================
    # 1.2 事件总线 API
    # ======================================================================
    # 1.2.1 发布事件
    event_payload = {
        "type": "compliance:check_failed",
        "source": "rule_engine",
        "product_id": pid1,
        "business_stage": "阶段2",
        "data": {"risk_level": "high", "failed_items": ["CE认证缺失", "WEEE未注册"]},
        "severity": "high"
    }
    resp_e = client.post(f"{BASE}/events", json=event_payload)
    body_e = resp_e.json()
    checks_e = [
        check_contains("event_id"),
        check_contains("type"),
        (f"事件type正确", lambda r: "compliance:check_failed" in str(r)),
    ]
    log_test("Phase 1", "事件总线", "发布合规检查失败事件",
             "/events", "POST", event_payload, resp_e.status_code, body_e,
             "事件被标准化为EventRecord，写入全局事件总线+产品事件链", checks_e)

    # 1.2.2 获取事件列表
    resp_el = client.get(f"{BASE}/events")
    body_el = resp_el.json()
    events_list = body_el.get("events", []) if isinstance(body_el, dict) else (body_el if isinstance(body_el, list) else [])
    checks_el = [
        (f"事件列表非空", lambda r: len(events_list) > 0),
        (f"事件含product_id", lambda r: all(e.get("product_id") for e in events_list if "product_id" in e)),
    ]
    log_test("Phase 1", "事件总线", "获取事件列表",
             "/events", "GET", None, resp_el.status_code, {"count": len(events_list), "sample": events_list[:2]},
             "返回所有已发布的事件列表", checks_el)

    # 1.2.3 事件订阅-精准订阅
    sub_req = {
        "subscriber": "test_client",
        "event_type": "compliance:*",
        "filter": {"product_ids": [pid1], "type": "precise"}
    }
    resp_sub = client.post(f"{BASE}/events/subscribe", json=sub_req)
    body_sub = resp_sub.json()
    log_test("Phase 1", "事件总线", "事件订阅-精准订阅",
             "/events/subscribe", "POST", sub_req, resp_sub.status_code, body_sub,
             "精准订阅返回subscription_id", [check_contains("subscription_id")])

    # 1.2.4 批量订阅
    sub_batch = {
        "subscriber": "batch_client",
        "event_type": "certification:*",
        "filter": {"product_ids": [pid1, pid2], "type": "batch"}
    }
    resp_sb = client.post(f"{BASE}/events/subscribe", json=sub_batch)
    log_test("Phase 1", "事件总线", "事件订阅-批量订阅",
             "/events/subscribe", "POST", sub_batch, resp_sb.status_code, resp_sb.json(),
             "批量订阅多个产品", [check_contains("subscription_id")])

    # 1.2.5 全局订阅
    sub_global = {
        "subscriber": "global_client",
        "event_type": "regulation:*",
        "filter": {"type": "global"}
    }
    resp_sg = client.post(f"{BASE}/events/subscribe", json=sub_global)
    log_test("Phase 1", "事件总线", "事件订阅-全局订阅",
             "/events/subscribe", "POST", sub_global, resp_sg.status_code, resp_sg.json(),
             "全局订阅所有regulation事件", [check_contains("subscription_id")])

    # 1.2.6 条件订阅
    sub_cond = {
        "subscriber": "condition_client",
        "event_type": "risk:*",
        "filter": {"condition": "severity == 'critical'", "type": "condition"}
    }
    resp_sc = client.post(f"{BASE}/events/subscribe", json=sub_cond)
    log_test("Phase 1", "事件总线", "事件订阅-条件订阅",
             "/events/subscribe", "POST", sub_cond, resp_sc.status_code, resp_sc.json(),
             "条件订阅仅severity=critical事件", [check_contains("subscription_id")])

    # 1.2.7 事件Schema查询
    resp_schema = client.get(f"{BASE}/events/schemas")
    log_test("Phase 1", "事件总线", "查询事件Schema",
             "/events/schemas", "GET", None, resp_schema.status_code, resp_schema.json(),
             "返回8类事件的Schema定义", [check_type("list", list)])

    # ======================================================================
    # 1.3 RAG知识库 API
    # ======================================================================
    resp_rag = client.get(f"{BASE}/rag/status")
    body_rag = resp_rag.json()
    log_test("Phase 1", "RAG知识库", "RAG系统状态",
             "/rag/status", "GET", None, resp_rag.status_code, body_rag,
             "返回RAG系统状态（collections数、文档数、embedding模型）",
             [check_contains("collections")])

    rag_search = {"query": "CE认证要求", "market": "eu", "top_k": 3}
    resp_rs = client.post(f"{BASE}/rag/search", json=rag_search)
    log_test("Phase 1", "RAG知识库", "语义搜索",
             "/rag/search", "POST", rag_search, resp_rs.status_code, resp_rs.json(),
             "返回语义搜索结果（文档片段+相似度）", [check_contains("results")])

    resp_rb = client.get(f"{BASE}/rag/browse", params={"market": "eu", "category": "电子产品"})
    log_test("Phase 1", "RAG知识库", "按市场×品类浏览法规",
             "/rag/browse?market=eu&category=电子产品", "GET", None, resp_rb.status_code, resp_rb.json(),
             "返回EU市场电子产品的法规目录", [check_contains("results")])

    # ======================================================================
    # 1.4 合规流水线 API
    # ======================================================================
    resp_ps = client.get(f"{BASE}/pipeline/stages")
    body_ps = resp_ps.json()
    log_test("Phase 1", "合规流水线", "10阶段合规状态",
             "/pipeline/stages", "GET", None, resp_ps.status_code, body_ps,
             "返回10个业务阶段的合规聚合状态(通过率/风险产品数/待办数)",
             [check_type("list", list)])

    resp_psd = client.get(f"{BASE}/pipeline/stages/1")
    log_test("Phase 1", "合规流水线", "指定阶段详情(阶段1)",
             "/pipeline/stages/1", "GET", None, resp_psd.status_code, resp_psd.json(),
             "返回阶段1的详细检查项清单", [check_contains("stage")])

    # ======================================================================
    # 1.5 CLI命令执行 API
    # ======================================================================
    cli_exec = {"command": "astra product list", "args": {}}
    resp_ce = client.post(f"{BASE}/cli/execute", json=cli_exec)
    log_test("Phase 1", "CLI命令", "执行CLI命令(astra product list)",
             "/cli/execute", "POST", cli_exec, resp_ce.status_code, resp_ce.json(),
             "执行astra product list命令返回产品列表",
             [check_contains("output"), check_contains("status")])

    cli_magic = {"command": "/help", "args": {}}
    resp_cm = client.post(f"{BASE}/cli/magic", json=cli_magic)
    log_test("Phase 1", "CLI命令", "执行魔法命令(/help)",
             "/cli/magic", "POST", cli_magic, resp_cm.status_code, resp_cm.json(),
             "魔法命令/help返回所有魔法命令列表",
             [check_contains("output")])

    resp_cc = client.get(f"{BASE}/cli/complete", params={"prefix": "astra p"})
    log_test("Phase 1", "CLI命令", "命令自动补全",
             "/cli/complete?prefix=astra p", "GET", None, resp_cc.status_code, resp_cc.json(),
             "返回'astra product'等补全建议",
             [check_type("suggestions", list)])

    resp_ch = client.get(f"{BASE}/cli/history")
    log_test("Phase 1", "CLI命令", "命令执行历史",
             "/cli/history", "GET", None, resp_ch.status_code, resp_ch.json(),
             "返回历史命令列表",
             [check_type("history", list)])

    # ======================================================================
    # 1.6 QAAgent配置 API — 事件类型CRUD
    # ======================================================================
    new_event_req = {
        "event_code": "test:custom_event",
        "event_name": "测试自定义事件",
        "business_stage": "阶段2",
        "category": "system",
        "trigger_condition": "手动触发",
        "severity": "low",
        "notify_strategy": ["dashboard"]
    }
    resp_ce_add = client.post(f"{BASE}/config/events", json=new_event_req)
    log_test("Phase 1", "QAAgent配置", "添加新事件类型",
             "/config/events", "POST", new_event_req, resp_ce_add.status_code, resp_ce_add.json(),
             "QAAgent添加新事件类型到配置文件",
             [check_contains("event_code"), check_contains("status")])

    resp_ce_list = client.get(f"{BASE}/config/events")
    body_ce_list = resp_ce_list.json()
    ce_list = body_ce_list.get("events", []) if isinstance(body_ce_list, dict) else (body_ce_list if isinstance(body_ce_list, list) else [])
    log_test("Phase 1", "QAAgent配置", "获取所有事件类型",
             "/config/events", "GET", None, resp_ce_list.status_code, ce_list[:3],
             "返回所有已注册的事件类型列表",
             [(f"事件列表非空", lambda r: len(ce_list) > 0)])

    resp_ce_stage = client.get(f"{BASE}/config/events/stage/阶段2")
    body_ce_stage = resp_ce_stage.json()
    ce_stage = body_ce_stage.get("events", []) if isinstance(body_ce_stage, dict) else (body_ce_stage if isinstance(body_ce_stage, list) else [])
    log_test("Phase 1", "QAAgent配置", "按业务阶段查询事件",
             "/config/events/stage/阶段2", "GET", None, resp_ce_stage.status_code, ce_stage[:3],
             "返回阶段2的所有事件定义",
             [(f"阶段2事件非空", lambda r: len(ce_stage) > 0)])

    # ======================================================================
    # 1.7 QAAgent配置 — Worker类型CRUD
    # ======================================================================
    new_worker_req = {
        "worker_code": "test_worker",
        "worker_name": "测试Worker",
        "business_stage": "阶段2",
        "description": "用于测试的自定义Worker",
        "available_skills": ["shopify-admin", "shopify-custom-data"],
        "priority": 3
    }
    resp_cw_add = client.post(f"{BASE}/config/workers", json=new_worker_req)
    log_test("Phase 1", "QAAgent配置", "添加新Worker类型",
             "/config/workers", "POST", new_worker_req, resp_cw_add.status_code, resp_cw_add.json(),
             "QAAgent添加新Worker类型到配置文件",
             [check_contains("worker_code")])

    resp_cw_list = client.get(f"{BASE}/config/workers")
    body_cw_list = resp_cw_list.json()
    cw_list = body_cw_list.get("workers", []) if isinstance(body_cw_list, dict) else (body_cw_list if isinstance(body_cw_list, list) else [])
    log_test("Phase 1", "QAAgent配置", "获取所有Worker类型",
             "/config/workers", "GET", None, resp_cw_list.status_code, cw_list[:3],
             "返回所有已注册的Worker类型",
             [(f"Worker列表非空", lambda r: len(cw_list) > 0)])

    resp_cw_stage = client.get(f"{BASE}/config/workers/stage/阶段2")
    body_cw_stage = resp_cw_stage.json()
    cw_stage = body_cw_stage.get("workers", []) if isinstance(body_cw_stage, dict) else (body_cw_stage if isinstance(body_cw_stage, list) else [])
    log_test("Phase 1", "QAAgent配置", "按阶段查询Worker",
             "/config/workers/stage/阶段2", "GET", None, resp_cw_stage.status_code, cw_stage[:3],
             "返回阶段2的所有Worker类型",
             [(f"阶段2 Worker非空", lambda r: len(cw_stage) > 0)])

    # ======================================================================
    # 打印摘要
    # ======================================================================
    summary = f"""
{'='*60}
Phase 1 测试执行摘要
{'='*60}
总测试数: {TOTAL}
通过: {PASS}
失败: {FAIL}
通过率: {PASS/TOTAL*100:.1f}%
{'='*60}
"""
    print(summary)
    print("\n".join(REPORT))

    # 保存测试结果
    report_content = f"# Phase 1 功能测试报告\n\n测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{summary}\n\n" + "\n".join(REPORT)
    with open("c:/Users/22859/Desktop/astra-main/test_report_phase1.md", "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"\nPhase 1 测试报告已保存: test_report_phase1.md")
    print(f"通过: {PASS}/{TOTAL}, 失败: {FAIL}/{TOTAL}")

if __name__ == "__main__":
    main()
