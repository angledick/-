"""危险事件闭环模拟测试。

模拟完整流程:
  1. 发布 danger 事件 (severity=critical) → ManagerAgent 自动暂停 → 飞书通知
  2. 模拟用户在飞书回复 "执行" → resume_pending_group → Worker 执行
  3. Worker 执行完成 → 飞书通知结果

用法:
    cd backend
    python -m scripts.test_danger_event                  # 默认使用 risk:fraud_detected
    python -m scripts.test_danger_event --event regulation:import_restriction
    python -m scripts.test_danger_event --chat-id oc_xxx --step 1   # 只执行第1步
    python -m scripts.test_danger_event --step 2 --group-id group_xxx  # 只执行第2步
"""

import argparse
import asyncio
import json
import sys
import os

# 确保 backend 目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# 默认飞书会话 ID
DEFAULT_CHAT_ID = "oc_c0a0a056f96abaf03cc6605b9fc26e4b"


async def step1_trigger_danger_event(event_code: str, chat_id: str):
    """第1步: 触发危险事件 → 自动暂停 → 飞书通知

    发布事件到 EventBus，ManagerAgent.on_event 捕获后:
      - submit_event_task → severity=critical → pending_approval
      - 飞书收到 "⚠️ 危险事件需要人工审批" 通知
    """
    print(f"\n{'='*60}")
    print(f"  第1步: 触发危险事件 [{event_code}]")
    print(f"  飞书会话: {chat_id}")
    print(f"{'='*60}")

    from app.core.event_bus import get_event_bus

    bus = get_event_bus()

    # 发布危险事件
    raw_event = {
        "type": event_code,
        "source": "test_script",
        "severity": "critical",
        "data": {
            "chat_id": chat_id,
            "product_id": "test_product_001",
            "description": f"[模拟测试] 危险事件 {event_code} 触发",
            "risk_score": 95,
            "affected_markets": ["德国", "欧盟"],
        },
    }

    print(f"\n发布事件: {json.dumps(raw_event, ensure_ascii=False, indent=2)}")

    event = await bus.publish_raw(raw_event)
    print(f"\n事件已发布: id={event.id} type={event.type} severity={event.severity}")

    # 等待 ManagerAgent.on_event 处理完成
    await asyncio.sleep(2)

    # 检查是否有 pending_approval 任务组
    from app.core.manager_agent import get_manager_agent
    manager = get_manager_agent()
    pending = manager.get_pending_groups()

    if pending:
        print(f"\n✅ 检测到 {len(pending)} 个待审批任务组:")
        for g in pending:
            print(f"   - group_id: {g['group_id']}")
            print(f"   - status: {g['status']}")
            print(f"   - task: {g['task_description']}")
            print(f"   - pause_reason: {g.get('context', {}).get('pause_reason', 'N/A')}")
        print(f"\n飞书应收到 '⚠️ 危险事件需要人工审批' 通知")
        print(f"\n第1步完成。请检查飞书是否收到通知。")
        print(f"然后用以下命令恢复执行:")
        print(f"  python -m scripts.test_danger_event --step 2 --group-id {pending[0]['group_id']} --chat-id {chat_id}")
        return pending[0]["group_id"]
    else:
        print("\n⚠️ 未检测到待审批任务组！检查事件定义是否正确。")
        # 打印所有活跃任务组
        active = manager.get_active_groups()
        if active:
            print(f"\n当前活跃任务组 ({len(active)}):")
            for g in active:
                print(f"   - {g['group_id']} status={g['status']} task={g['task_description']}")
        return None


async def step2_resume_and_execute(group_id: str, chat_id: str, instructions: str):
    """第2步: 模拟用户回复处理意见 → 恢复执行 → Worker 执行

    这一步模拟用户在飞书回复 "执行" 后的流程:
      - resume_pending_group → status=running
      - execute_group → Worker SDK 执行
      - 完成后飞书收到 "✅ 任务执行完成" 通知
    """
    print(f"\n{'='*60}")
    print(f"  第2步: 恢复任务组并执行")
    print(f"  group_id: {group_id}")
    print(f"  处理意见: {instructions}")
    print(f"  飞书会话: {chat_id}")
    print(f"{'='*60}")

    from app.core.manager_agent import get_manager_agent

    manager = get_manager_agent()

    # 检查任务组是否存在
    group = manager._task_groups.get(group_id)
    if not group:
        print(f"\n❌ 任务组 {group_id} 不存在！")
        return

    print(f"\n当前状态: status={group.status}")
    print(f"任务描述: {group.task_description}")
    print(f"子任务数: {len(group.subtasks)}")

    # 恢复执行
    print(f"\n恢复任务组 (模拟用户飞书回复: '{instructions}')...")
    ok = await manager.resume_pending_group(group_id, instructions)
    if not ok:
        print(f"❌ 恢复失败！")
        return

    print(f"✅ 任务组已恢复，等待 Worker 执行...")

    # 等待执行完成（后台 asyncio.create_task）
    await asyncio.sleep(5)

    # 检查最终状态
    group = manager._task_groups.get(group_id)
    if group:
        progress = group._calc_progress()
        print(f"\n最终状态: status={group.status}")
        print(f"进度: {progress}")
        print(f"\n飞书应收到 '✅ 任务执行完成' 通知")


async def step3_full_flow(event_code: str, chat_id: str):
    """完整流程: 触发 → 等待 → 恢复 → 执行 (自动)"""
    group_id = await step1_trigger_danger_event(event_code, chat_id)
    if group_id:
        print(f"\n等待 3 秒后自动恢复...")
        await asyncio.sleep(3)
        await step2_resume_and_execute(group_id, chat_id, "执行")


async def main():
    parser = argparse.ArgumentParser(description="危险事件闭环模拟测试")
    parser.add_argument(
        "--event", default="risk:fraud_detected",
        help="事件编码 (默认: risk:fraud_detected)"
    )
    parser.add_argument(
        "--chat-id", default=DEFAULT_CHAT_ID,
        help=f"飞书会话ID (默认: {DEFAULT_CHAT_ID})"
    )
    parser.add_argument(
        "--step", type=int, default=3,
        choices=[1, 2, 3],
        help="执行步骤: 1=触发事件, 2=恢复执行, 3=完整流程 (默认: 3)"
    )
    parser.add_argument(
        "--group-id", default="",
        help="任务组ID (step=2 时必须)"
    )
    parser.add_argument(
        "--instructions", default="执行",
        help="处理意见 (默认: 执行)"
    )
    args = parser.parse_args()

    if args.step == 1:
        await step1_trigger_danger_event(args.event, args.chat_id)
    elif args.step == 2:
        if not args.group_id:
            print("❌ step=2 需要 --group-id 参数")
            sys.exit(1)
        await step2_resume_and_execute(args.group_id, args.chat_id, args.instructions)
    else:
        await step3_full_flow(args.event, args.chat_id)


if __name__ == "__main__":
    asyncio.run(main())
