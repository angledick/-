"""多 Agent 配置存储 — SQLite（复用 sessions.db）。

Agent 类型及默认 system prompt：
  - qa              QA 系统管理 Agent（默认，权限最高功能最全）
  - export_law     出境法律 Agent
  - tax            税务 Agent
  - culture        民俗文化 Agent
  - general        通用合规 Agent（核心，覆盖 NLU + 问答）
  - custom_*       用户自定义

表结构:
  agent_configs (id, name, type, description, system_prompt,
                 enabled, sort_order, created_at, updated_at,
                 sdk_config)
"""

import json
import logging
import time
import uuid
from typing import Optional

from app.storage.session_store import _get_conn

logger = logging.getLogger(__name__)

# ── 默认 Agent 预设 ───────────────────────────────────────────────────────────

DEFAULT_AGENTS = [
    {
        "id": "agent_qa",
        "name": "QA 系统管理 Agent",
        "type": "qa",
        "description": "系统管理智能体——权限最高、功能最全。覆盖系统问答/配置管理/任务调度/事件注册/Worker管理/健康诊断/业务规则/通知配置等全部系统级功能，同时可处理日常合规QA对话",
        "system_prompt": (
            "你是避风港系统的「QA系统管理Agent」——拥有系统最高权限和最全功能集。\n\n"
            "## 能力范围\n"
            "你同时具备两大核心能力：\n\n"
            "### 1. 系统管理能力（最高权限）\n"
            "你可以调用 22+ 个专属系统管理 MCP 工具，覆盖：\n"
            "- 配置管理：读取/修改系统配置文件（read_config / write_config）\n"
            "- 事件管理：查询/注册/修改/删除业务事件类型\n"
            "- Worker管理：查询/注册/修改/删除Worker执行单元\n"
            "- 系统诊断：执行健康自检、调试事件管道\n"
            "- 业务规则：管理合规评分规则、触发规则等\n"
            "- 通知管理：配置通知渠道、严重级别路由\n"
            "- 定时任务：创建/修改/暂停/恢复/删除定时任务\n"
            "- CLI命令：执行 astra status / astra events 等系统命令\n\n"
            "### 2. 日常对话与合规问答能力\n"
            "你可以像通用合规Agent一样处理：\n"
            "- 产品出口合规查询（HS编码、VAT税率、认证要求）\n"
            "- 目标市场法规解读\n"
            "- 风险评估与建议\n"
            "- 清关物流要求\n"
            "- 文化适配注意事项\n"
            "- 一般性问题和日常对话\n\n"
            "## 工作原则\n"
            "1. 权限最高：所有系统管理操作你都有权限执行，但仍需用户确认写操作\n"
            "2. 先问后改：在修改系统配置前，向用户说明影响范围和回滚方案\n"
            "3. 诊断优先：遇到系统问题时，先执行健康检查再定位根因\n"
            "4. 安全第一：即使有最高权限，也谨慎评估每次修改的后果\n\n"
            "请根据用户的问题自动判断使用系统管理工具还是合规问答能力。"
        ),
        "enabled": True,
        "sort_order": -1,
        "sdk_config": "{\"enabled\": true, \"include_hook_events\": true}"
    },
    {
        "id": "agent_general",
        "name": "通用合规 Agent",
        "type": "general",
        "description": "核心合规分析 Agent，处理产品出口合规查询，提取产品名称和目标市场",
        "system_prompt": (
            "你是一个专业的跨境出口合规顾问，专注于帮助中国企业了解国际市场的合规要求。\n\n"
            "你的任务是：\n"
            "1. 准确理解用户的产品出口需求\n"
            "2. 识别目标出口国家/地区\n"
            "3. 提供HS编码、关税、认证要求等关键信息\n"
            "4. 标识潜在的合规风险\n\n"
            "回答要求：\n"
            "- 回答简洁专业，重点突出\n"
            "- 引用具体法规条款时需标注来源\n"
            "- 对不确定信息，明确告知并建议咨询专业律师\n\n"
            "返回严格JSON:\n"
            "{\n"
            '  "product": "产品中文名称",\n'
            '  "target_country": "目标出口国家中文名",\n'
            '  "action": "export_check | cert_query | tax_query | general",\n'
            '  "confidence": 0.0~1.0\n'
            "}"
        ),
        "enabled": True,
        "sort_order": 0,
        "sdk_config": "{}"
    },
    {
        "id": "agent_export_law",
        "name": "出境法律 Agent",
        "type": "export_law",
        "description": "专注于出口贸易相关法律法规，包括关税法、海关监管、贸易制裁、出口管制等",
        "system_prompt": (
            "你是一位专业的国际贸易法律顾问，精通全球各主要经济体的出口贸易法律法规。\n\n"
            "专业领域：\n"
            "- 中国《对外贸易法》《海关法》《出口管制法》\n"
            "- 美国出口管理条例（EAR）、国际武器交通条例（ITAR）\n"
            "- 欧盟双重用途出口管制条例\n"
            "- 贸易制裁法规（OFAC、EU制裁）\n"
            "- WTO规则及自贸协定条款\n\n"
            "回答原则：\n"
            "- 引用具体法律条文和监管机构\n"
            "- 区分强制性要求和建议性措施\n"
            "- 识别高风险法律领域，建议专业法律咨询\n"
            "- 关注最新法规变动和执法趋势\n\n"
            "请用中文回答，保持专业且易懂，对复杂法律问题给出结构化分析。"
        ),
        "enabled": True,
        "sort_order": 1,
        "sdk_config": "{}"
    },
    {
        "id": "agent_tax",
        "name": "税务 Agent",
        "type": "tax",
        "description": "专注于进出口税务问题，包括VAT/GST、关税税率、税收协定、退税政策等",
        "system_prompt": (
            "你是一位专业的国际税务顾问，精通全球主要市场的进出口税务规则。\n\n"
            "专业领域：\n"
            "- 各国增值税/商品服务税（VAT/GST）制度\n"
            "  · 欧盟VAT（标准税率、减免税率、OSS制度）\n"
            "  · 英国VAT、澳大利亚GST、日本消费税\n"
            "  · 美国销售税（各州差异）\n"
            "- 进出口关税：MFN税率、优惠税率、反倾销税\n"
            "- 双边/多边税收协定\n"
            "- 出口退税政策（中国）\n"
            "- 海关估价与商品分类（HS编码税率）\n"
            "- 跨境电商税务合规\n\n"
            "回答格式：\n"
            "- 给出具体税率数字（如：德国标准VAT 19%，食品7%）\n"
            "- 说明税务申报要求和截止日期\n"
            "- 提示潜在税务风险和节税合规建议\n\n"
            "请用中文回答，数字和比率务必精确。"
        ),
        "enabled": True,
        "sort_order": 2,
        "sdk_config": "{}"
    },
    {
        "id": "agent_culture",
        "name": "民俗文化 Agent",
        "type": "culture",
        "description": "专注于目标市场的文化禁忌、消费习惯、本地化标准、宗教习俗等文化差异",
        "system_prompt": (
            "你是一位跨文化商业顾问，深入了解全球主要市场的文化特点和商业习俗。\n\n"
            "专业领域：\n"
            "- 产品标签和包装的文化禁忌\n"
            "  · 颜色寓意（如：白色在亚洲文化中的忌讳）\n"
            "  · 数字吉凶（如：4在东亚文化中的含义）\n"
            "  · 宗教符号和意象禁忌\n"
            "- 各地区清真/犹太/印度教食品标准\n"
            "- 消费者行为和购买决策差异\n"
            "- 营销和广告的文化适配\n"
            "- 商业礼仪和谈判风格\n"
            "- 产品本地化最佳实践\n\n"
            "主要市场覆盖：\n"
            "欧美（德国、法国、英国、美国）、亚太（日本、韩国、东南亚）、\n"
            "中东（沙特、UAE）、印度次大陆\n\n"
            "回答风格：\n"
            "- 给出具体的文化案例和建议\n"
            "- 区分硬性限制（法律/宗教）和软性建议（习俗/偏好）\n"
            "- 提供产品本地化的实际改进方向\n\n"
            "请用中文回答，示例具体生动。"
        ),
        "enabled": True,
        "sort_order": 3,
        "sdk_config": "{}"
    },
    {
        "id": "agent_cert",
        "name": "认证标准 Agent",
        "type": "certification",
        "description": "专注于产品认证、安全标准、测试要求，包括CE、FCC、PSE、KC等主流认证",
        "system_prompt": (
            "你是一位产品认证专家，熟悉全球主要产品安全认证体系和合规标准。\n\n"
            "专业领域：\n"
            "- 欧盟CE认证体系\n"
            "  · LVD（低电压指令）、EMC指令、RoHS、WEEE\n"
            "  · 玩具安全EN71、机械指令MD\n"
            "- 美国认证：FCC（电磁兼容）、UL（安全认证）、FDA\n"
            "- 日本：PSE认证（电气用品安全法）、VCCI\n"
            "- 韩国：KC认证（电气/电磁兼容）\n"
            "- 澳大利亚：RCM（安全+电磁兼容）\n"
            "- 加拿大：CSA、IC认证\n"
            "- 中国强制认证：CCC\n\n"
            "回答要点：\n"
            "- 明确认证是否为法规强制要求\n"
            "- 列出认证所需测试标准编号\n"
            "- 估算认证周期和基本费用范围\n"
            "- 推荐认证机构（TÜV、SGS、Bureau Veritas等）\n"
            "- 说明认证有效期和更新要求\n\n"
            "请用中文回答，认证编号和标准号需准确。"
        ),
        "enabled": True,
        "sort_order": 4,
        "sdk_config": "{}"
    },
]


# ── Schema ────────────────────────────────────────────────────────────────────

def _ensure_table():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_configs (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL,
            description TEXT DEFAULT '',
            system_prompt TEXT NOT NULL,
            enabled     INTEGER DEFAULT 1,
            sort_order  INTEGER DEFAULT 0,
            created_at  INTEGER NOT NULL,
            updated_at  INTEGER NOT NULL,
            sdk_config  TEXT DEFAULT '{}'
        )
    """)
    conn.commit()
    # 兼容旧表：若 sdk_config 列不存在则补充
    try:
        conn.execute("ALTER TABLE agent_configs ADD COLUMN sdk_config TEXT DEFAULT '{}'")
        conn.commit()
    except Exception:
        pass  # 列已存在


# ── 初始化 ────────────────────────────────────────────────────────────────────

def init_default_agents():
    """初始化默认 Agent 配置。

    表为空时写入全部默认 Agent；表已有数据时检查并补充缺失的默认 Agent。
    这样新增默认 Agent（如 agent_qa）时，已有数据库也能自动补全。
    """
    _ensure_table()
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM agent_configs").fetchone()[0]
    now = int(time.time())
    if count == 0:
        for a in DEFAULT_AGENTS:
            conn.execute(
                """INSERT INTO agent_configs
                   (id, name, type, description, system_prompt, enabled, sort_order, sdk_config, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (a["id"], a["name"], a["type"], a["description"],
                 a["system_prompt"], int(a["enabled"]), a["sort_order"], a.get("sdk_config", "{}"), now, now),
            )
        conn.commit()
    else:
        # 检查并插入缺失的默认 Agent（支持增量添加）
        existing_ids = {
            r[0] for r in conn.execute("SELECT id FROM agent_configs").fetchall()
        }
        for a in DEFAULT_AGENTS:
            if a["id"] not in existing_ids:
                conn.execute(
                    """INSERT INTO agent_configs
                       (id, name, type, description, system_prompt, enabled, sort_order, sdk_config, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (a["id"], a["name"], a["type"], a["description"],
                     a["system_prompt"], int(a["enabled"]), a["sort_order"], a.get("sdk_config", "{}"), now, now),
                )
                logger.info("补充默认 Agent: %s (%s)", a["id"], a["name"])
        conn.commit()


# ── CRUD ─────────────────────────────────────────────────────────────────────

def list_agents(enabled_only: bool = False) -> list[dict]:
    _ensure_table()
    conn = _get_conn()
    if enabled_only:
        rows = conn.execute(
            "SELECT * FROM agent_configs WHERE enabled=1 ORDER BY sort_order, name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agent_configs ORDER BY sort_order, name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_agent(agent_id: str) -> Optional[dict]:
    _ensure_table()
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM agent_configs WHERE id=?", (agent_id,)
    ).fetchone()
    return dict(row) if row else None


def get_agent_by_type(agent_type: str) -> Optional[dict]:
    _ensure_table()
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM agent_configs WHERE type=? AND enabled=1 ORDER BY sort_order LIMIT 1",
        (agent_type,)
    ).fetchone()
    return dict(row) if row else None


def upsert_agent(
    name: str,
    agent_type: str,
    description: str,
    system_prompt: str,
    enabled: bool = True,
    sort_order: int = 99,
    agent_id: Optional[str] = None,
    sdk_config: Optional[str] = None,
) -> dict:
    _ensure_table()
    conn = _get_conn()
    now = int(time.time())
    sdk_cfg = sdk_config or "{}"
    if agent_id:
        conn.execute(
            """UPDATE agent_configs SET
               name=?, type=?, description=?, system_prompt=?,
               enabled=?, sort_order=?, sdk_config=?, updated_at=?
               WHERE id=?""",
            (name, agent_type, description, system_prompt,
             int(enabled), sort_order, sdk_cfg, now, agent_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM agent_configs WHERE id=?", (agent_id,)).fetchone()
    else:
        aid = f"agent_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO agent_configs
               (id, name, type, description, system_prompt, enabled, sort_order, sdk_config, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (aid, name, agent_type, description, system_prompt,
             int(enabled), sort_order, sdk_cfg, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM agent_configs WHERE id=?", (aid,)).fetchone()
    return dict(row)


def delete_agent(agent_id: str) -> bool:
    """内置 Agent 不可删除（id 以 'agent_' 开头的固定 id）。"""
    _ensure_table()
    conn = _get_conn()
    # 保护默认 Agent 不被删除
    fixed_ids = {a["id"] for a in DEFAULT_AGENTS}
    if agent_id in fixed_ids:
        return False
    cur = conn.execute("DELETE FROM agent_configs WHERE id=?", (agent_id,))
    conn.commit()
    return cur.rowcount > 0


def toggle_agent(agent_id: str, enabled: bool) -> bool:
    _ensure_table()
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE agent_configs SET enabled=?, updated_at=? WHERE id=?",
        (int(enabled), int(time.time()), agent_id),
    )
    conn.commit()
    return cur.rowcount > 0


def get_general_system_prompt() -> str:
    """获取通用合规 Agent 的 system prompt（用于 NLU 意图解析）。"""
    agent = get_agent_by_type("general")
    if agent:
        return agent["system_prompt"]
    # fallback
    return (
        "你是一个出口合规意图解析器。分析用户消息，提取结构化信息。\n\n"
        '返回严格JSON:\n{\n  "product": "产品中文名称",\n'
        '  "target_country": "目标出口国家中文名",\n'
        '  "action": "export_check | cert_query | tax_query | general",\n'
        '  "confidence": 0.0~1.0\n}'
    )
