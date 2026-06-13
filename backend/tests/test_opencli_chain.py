"""
测试 OpenCLI browser-control 全链路:
  1. SkillExecutor → browser-control (脚本执行)
  2. ManagerAgent → Worker → Skill (全链路)
"""
import asyncio
import json
import sys
import os

# 确保可以 import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows event loop
if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


async def test_skill_executor():
    """测试 SkillExecutor → browser-control 脚本执行"""
    print("=" * 60)
    print("[TEST 1] SkillExecutor → browser-control (脚本执行)")
    print("=" * 60)

    from app.core.skill_registry import get_skill_registry, SkillExecutor

    reg = get_skill_registry()
    executor = SkillExecutor(reg)

    # 检查 skill 是否已注册
    skill_info = reg.get_skill_by_name("browser-control")
    if skill_info:
        print(f"  Skill 已注册: source={skill_info.get('source')}, script={skill_info.get('script')}")
    else:
        print("  ⚠️  Skill 未注册，尝试直接执行...")

    result = await executor.execute("browser-control", {"action": "status"})
    print(f"  执行结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    return result


async def test_manager_agent_chain():
    """测试 ManagerAgent → submit_task → Worker → Skill"""
    print("\n" + "=" * 60)
    print("[TEST 2] ManagerAgent → Worker → Skill (全链路)")
    print("=" * 60)

    from app.core.manager_agent import get_manager_agent

    manager = get_manager_agent()

    # 检查 browser_worker 是否可用
    workers = manager.workers.get_all_workers()
    browser_w = [w for w in workers if w.worker_code == "browser_worker"]
    if browser_w:
        w = browser_w[0]
        print(f"  Worker 已注册: {w.worker_name}, skills={w.available_skills}, sdk={w.sdk_enabled}")
    else:
        print("  ⚠️  browser_worker 未找到!")
        print(f"  可用 Workers: {[w.worker_code for w in workers]}")
        return None

    # 提交任务
    print("\n  → 提交任务: '检查浏览器状态'")
    group = await manager.submit_task(
        task="检查浏览器状态",
        context={"action": "status"},
        created_by="test",
    )
    print(f"  任务组: {group.group_id}")
    print(f"  子任务数: {len(group.subtasks)}")
    for st in group.subtasks:
        print(f"    [{st.task_id}] {st.task_type}: {st.description}")
        print(f"      worker={st.assigned_worker}, skills={st.required_skills}")

    # 执行
    print("\n  → 执行任务组...")
    try:
        result = await manager.execute_group(group.group_id)
        print(f"  执行结果: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
        return result
    except Exception as e:
        print(f"  ❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_event_driven():
    """测试事件驱动链路: publish browser:status_check → ManagerAgent.on_event"""
    print("\n" + "=" * 60)
    print("[TEST 3] 事件驱动: EventBus → ManagerAgent → Worker")
    print("=" * 60)

    from app.core.event_bus import get_event_bus
    from app.core.manager_agent import get_manager_agent

    bus = get_event_bus()
    manager = get_manager_agent()

    # 检查事件是否已加载
    evt = bus._event_registry.get_event("browser:status_check") if bus._event_registry else None
    if evt:
        print(f"  事件已加载: {evt.event_name}, worker={evt.related_worker}, skills={evt.skills}")
    else:
        print("  ⚠️  事件 browser:status_check 未加载")

    # 确保 on_all 绑定
    bus.on_all(manager.on_event)
    print("  已绑定 bus.on_all(manager.on_event)")

    # 发布事件
    print("\n  → 发布事件 browser:status_check")
    await bus.publish_raw({
        "type": "browser:status_check",
        "source": "test",
        "data": {"user_id": "default", "action": "status"},
    })
    print("  ✅ 事件已发布（异步处理，检查结果日志）")


async def main():
    print("🔍 OpenCLI browser-control 全链路测试\n")

    # Test 1: SkillExecutor
    r1 = await test_skill_executor()

    # Test 2: ManagerAgent full chain
    r2 = await test_manager_agent_chain()

    # Test 3: Event driven
    await test_event_driven()

    print("\n" + "=" * 60)
    print("📋 测试总结")
    print("=" * 60)
    print(f"  Test 1 (SkillExecutor): {'✅' if r1 and r1.get('status') == 'success' else '❌'}")
    print(f"  Test 2 (ManagerAgent):  {'✅' if r2 else '❌'}")
    print(f"  Test 3 (EventDriven):   ⏳ 异步执行，检查日志")


if __name__ == "__main__":
    asyncio.run(main())
