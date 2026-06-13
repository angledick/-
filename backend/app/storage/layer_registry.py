"""
分层存储注册表 (Layer Registry) — L0-L5 统一入口。

各层存储模块通过此注册表暴露，上层业务代码只需引用 `layer_registry` 即可访问所有层。
新增存储层时，在此注册即可。

数据流转规则（详见 data/数据流转.md）：
  L0 (Raw)      → ComplianceRules 读取，用于确定性合规检查
  L1 (Knowledge) → RAG 检索，用于开放问答和法规引用
  L2 (Project)  → 合规报告写入/读取，产品历史追溯
  L3 (User)     → AstraAssistant/NLU 读取用户偏好，个性化回复
  L4 (Session)  → NLU 读取会话上下文，多轮对话维持
  L5 (Event)    → 全组件写入操作记录，审计/回溯/事件监控
"""

from app.storage.raw_store import RawStore
from app.storage.project_memory import ProjectMemory
from app.storage.user_memory import UserMemory
from app.storage.session_memory import SessionMemory
from app.storage.event_store import EventStore


class LayerRegistry:
    """分层存储注册表 — 所有存储层的统一访问入口。"""

    def __init__(self):
        # L0: 原始数据层 — 读取 data/raw/ 下的静态数据文件
        self.raw = RawStore()

        # L2: 项目/产品记忆层 — 产品合规档案（按对应产品隔离）
        self.project = ProjectMemory()

        # L3: 用户记忆层 — 用户画像/偏好（按用户隔离）
        self.user = UserMemory()

        # L4: 会话记忆层 — 会话上下文（按用户/会话隔离，不做TTL）
        self.session = SessionMemory()

        # L5: 事件链层 — 系统事件 + 操作链（合并 event + action）
        self.event = EventStore()


# 全局单例
registry = LayerRegistry()
