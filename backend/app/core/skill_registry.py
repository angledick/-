"""
SkillRegistry + SkillExecutor + SkillRecommender（Phase 3.3）

参考开源选型：
- skill-vetter（指南 §4.3 跨阶段通用Skills）安全审查
- Open WebUI（指南 §3.5.11）插件系统架构
- 各阶段Skills映射矩阵（指南 §4.2）

功能:
- SkillRegistry: 技能注册表（注册/安装/卸载/查询/配置）
- SkillExecutor: 技能执行器（调用Skill、结果处理、超时控制）
- SkillRecommender: 技能推荐器（根据事件类型/业务阶段推荐Skills）

Skills×阶段映射矩阵对齐指南 §4.2
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings


# ── 数据结构 ────────────────────────────────────────


class SkillStatus(str, Enum):
    available = "available"
    installed = "installed"
    active = "active"
    disabled = "disabled"
    error = "error"


@dataclass
class SkillInfo:
    """技能信息"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    display_name: str = ""
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    source: str = ""                # github / local / builtin
    source_url: str = ""
    file_path: str = ""             # SKILL.md 文件路径
    status: SkillStatus = SkillStatus.available
    business_stages: List[int] = field(default_factory=list)  # 适用业务阶段（1-10）
    event_types: List[str] = field(default_factory=list)       # 适用事件类型
    required_permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    install_count: int = 0
    success_rate: float = 1.0       # 执行成功率
    avg_execution_ms: int = 0
    last_used_at: str = ""
    security_scan: Dict[str, Any] = field(default_factory=dict)  # 安全扫描结果
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SkillInfo":
        status_val = data.pop("status", "available")
        skill = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        skill.status = SkillStatus(status_val) if isinstance(status_val, str) else status_val
        return skill


@dataclass
class SkillExecution:
    """技能执行记录"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    skill_id: str = ""
    skill_name: str = ""
    status: str = "pending"     # pending / running / success / failed / timeout
    args: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


import yaml

SKILLS_DATA_DIR = Path(settings.data_dir) / "skills"


def _load_yaml_config(filename: str) -> Any:
    """从 data/skills/ 加载 YAML 配置。"""
    path = SKILLS_DATA_DIR / filename
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception:
            pass
    return {}


# ── Skills×阶段映射矩阵（指南 §4.2）— 从 YAML 文件加载 ─────────────────

_skills_data = _load_yaml_config("_stage_matrix.yaml")
SKILLS_STAGE_MATRIX: Dict[int, List[Dict]] = _skills_data.get("stage_matrix", {})
CROSS_STAGE_SKILLS: List[Dict] = _skills_data.get("cross_stage_skills", [])

# 事件动作推荐清单（指南 §5 三层动作推荐）— 从 YAML 文件加载
_actions_data = _load_yaml_config("_event_actions.yaml")
EVENT_ACTION_MAP: Dict[str, List[Dict]] = _actions_data.get("event_actions", {})


# ── 持久化 ────────────────────────────────────────

SKILLS_DIR = Path(settings.data_dir) / "skills"
SKILLS_FILE = SKILLS_DIR / "registry.json"
EXECUTIONS_FILE = SKILLS_DIR / "executions.json"


def _load_json(path: Path) -> Any:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── SkillRegistry ─────────────────────────────────


class SkillRegistry:
    """技能注册表"""

    # 内置Skills列表（从 data/skills/_registry.yaml 加载）
    BUILTIN_SKILLS = _load_yaml_config("_registry.yaml").get("skills", [])

    def __init__(self):
        self._skills: Dict[str, SkillInfo] = {}
        self._load_all()
        self._ensure_builtins()

    def _load_all(self):
        raw = _load_json(SKILLS_FILE)
        for sd in raw:
            skill = SkillInfo.from_dict(sd)
            self._skills[skill.id] = skill

    def _ensure_builtins(self):
        """确保内置Skills已注册（支持 builtin / prompt 两种来源）

        如果技能在YAML中声明了 path，则尝试加载其 SKILL.md 文件夹:
          - 读取 YAML frontmatter 丰富技能元数据
          - 设置 file_path 指向 SKILL.md

        对已存在的技能也会更新 file_path（处理缓存脏数据场景）。
        """
        existing = {s.name: s for s in self._skills.values()}
        for builtin in self.BUILTIN_SKILLS:
            file_path = ""
            loaded_yaml = {}
            skill_path = builtin.get("path", "")
            if skill_path:
                md_path, loaded_yaml = self._load_skill_md(skill_path)
                if md_path:
                    file_path = md_path

            name = builtin["name"]
            if name not in existing:
                # 新技能: 创建并注册
                skill = SkillInfo(
                    name=name,
                    display_name=loaded_yaml.get("display_name", builtin["display_name"]),
                    description=loaded_yaml.get("description", builtin["description"]),
                    source=builtin.get("source", "builtin"),
                    status=SkillStatus.installed,
                    business_stages=builtin["stages"],
                    file_path=file_path,
                    config={"prompt": builtin["prompt"]} if builtin.get("prompt") else {},
                )
                self._skills[skill.id] = skill
            elif file_path and not existing[name].file_path:
                # 已存在但 file_path 为空: 更新之
                existing[name].file_path = file_path
        self._persist()

    @staticmethod
    def _load_skill_md(skill_path: str) -> tuple:
        """从技能文件夹加载 SKILL.md 文件。

        Args:
            skill_path: 技能文件夹名（相对于 data/skills/）

        Returns:
            (file_path, frontmatter_dict) — SKILL.md 的路径和 YAML frontmatter
            如果找不到文件则返回 ("", {})
        """
        md_file = SKILLS_DATA_DIR / skill_path / "SKILL.md"
        if not md_file.exists():
            return "", {}

        content = md_file.read_text(encoding="utf-8")
        import re
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if match:
            try:
                front_matter = yaml.safe_load(match.group(1))
                if isinstance(front_matter, dict):
                    return str(md_file), front_matter
            except Exception:
                pass

        return str(md_file), {}

    def _persist(self):
        _save_json(SKILLS_FILE, [s.to_dict() for s in self._skills.values()])

    # ── CRUD ────────────────────────────────────

    def list_skills(self, status: str = None, stage: int = None) -> List[Dict]:
        skills = list(self._skills.values())
        if status:
            skills = [s for s in skills if s.status.value == status]
        if stage:
            skills = [s for s in skills if stage in s.business_stages]
        return [s.to_dict() for s in skills]

    def get_skill(self, skill_id: str) -> Optional[Dict]:
        skill = self._skills.get(skill_id)
        return skill.to_dict() if skill else None

    def get_skill_by_name(self, name: str) -> Optional[Dict]:
        for s in self._skills.values():
            if s.name == name:
                return s.to_dict()
        return None

    def install_skill(self, name: str, source: str = "builtin",
                     source_url: str = "", config: Dict = None) -> Dict:
        """安装Skill。

        对于自定义技能（source != 'builtin'），自动在 data/skills/custom/ 下生成
        SKILL.md 模板文件，供用户编辑实现逻辑。
        """
        # 检查是否已安装
        for s in self._skills.values():
            if s.name == name and s.status == SkillStatus.installed:
                return s.to_dict()

        # 检查安全扫描
        if source_url:
            try:
                from app.core.security_sandbox import get_security_sandbox
                sandbox = get_security_sandbox()
                # 对远程来源执行安全扫描
                scan_result = sandbox.scan_skill(f"Source: {source_url}", name)
                if scan_result.blocked:
                    raise RuntimeError(f"Security scan failed: {scan_result.description}")
            except ImportError:
                pass

        # 查找内置定义
        builtin = next((b for b in self.BUILTIN_SKILLS if b["name"] == name), None)

        skill = SkillInfo(
            name=name,
            display_name=builtin["display_name"] if builtin else name,
            description=builtin["description"] if builtin else f"Custom skill: {name}",
            source=source,
            source_url=source_url,
            status=SkillStatus.installed,
            business_stages=builtin["stages"] if builtin else [],
            config=config or {},
            install_count=1,
        )

        # 自定义技能: 生成 SKILL.md 实现文件到 data/skills/custom/
        if source != "builtin":
            skill.file_path = self._generate_skill_md(skill)

        self._skills[skill.id] = skill
        self._persist()

        # 触发安装事件
        try:
            from app.core.event_bus import get_event_bus
            import asyncio
            asyncio.create_task(get_event_bus().publish_raw({
                "type": "system:skill_installed",
                "source": "skill_registry",
                "data": {"skill_name": name, "source": source},
            }))
        except Exception:
            pass

        return skill.to_dict()

    def _generate_skill_md(self, skill: SkillInfo) -> str:
        """为自定义技能生成 SKILL.md 模板到 data/skills/custom/。

        返回生成的文件相对路径。
        """
        custom_dir = SKILLS_DIR / "custom"
        custom_dir.mkdir(parents=True, exist_ok=True)

        safe_name = skill.name.lower().replace(" ", "-").replace("_", "-")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "-")
        file_path = custom_dir / f"{safe_name}" / "SKILL.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 不覆盖已有文件
        if file_path.exists():
            return str(file_path.relative_to(SKILLS_DIR))

        content = f"""---
name: {skill.name}
display_name: {skill.display_name}
description: {skill.description}
version: "1.0.0"
author: custom
source: {skill.source}
source_url: "{skill.source_url}"
business_stages: {json.dumps(skill.business_stages)}
---

# {skill.display_name}

{skill.description}

## 使用方法

Agent 在接收到匹配的事件或用户指令时，将调用此 Skill。

## 执行逻辑

```python
# TODO: 实现技能核心逻辑
def execute(args: dict) -> dict:
    \"\"\"技能入口函数。

    Args:
        args: 输入参数字典

    Returns:
        dict: 执行结果
    \"\"\"
    return {{
        "status": "success",
        "result": "技能执行完成",
    }}
```

## 配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| timeout | int | 30 | 超时时间（秒） |
"""
        file_path.write_text(content, encoding="utf-8")
        return str(file_path.relative_to(SKILLS_DIR))

    def uninstall_skill(self, skill_id: str) -> bool:
        skill = self._skills.get(skill_id)
        if not skill:
            return False
        if skill.source == "builtin":
            skill.status = SkillStatus.disabled
        else:
            del self._skills[skill_id]
        self._persist()
        return True

    def update_config(self, skill_id: str, config: Dict[str, Any]) -> Optional[Dict]:
        skill = self._skills.get(skill_id)
        if not skill:
            return None
        skill.config.update(config)
        skill.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._persist()
        return skill.to_dict()

    def enable_skill(self, skill_id: str) -> Optional[Dict]:
        skill = self._skills.get(skill_id)
        if not skill:
            return None
        skill.status = SkillStatus.active
        self._persist()
        return skill.to_dict()

    def disable_skill(self, skill_id: str) -> Optional[Dict]:
        skill = self._skills.get(skill_id)
        if not skill:
            return None
        skill.status = SkillStatus.disabled
        self._persist()
        return skill.to_dict()

    def get_stage_matrix(self) -> Dict:
        """获取Skills×阶段映射矩阵"""
        return {str(k): v for k, v in SKILLS_STAGE_MATRIX.items()}

    def get_cross_stage_skills(self) -> List[Dict]:
        """获取跨阶段通用Skills"""
        return CROSS_STAGE_SKILLS


# ── SkillExecutor ─────────────────────────────────


class SkillExecutor:
    """技能执行器"""

    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self._executions: List[SkillExecution] = []

    async def execute(self, skill_name: str, args: Dict[str, Any] = None,
                     timeout: int = None) -> Dict:
        """执行Skill"""
        skill_info = self.registry.get_skill_by_name(skill_name)
        if not skill_info:
            return {"status": "error", "error": f"Skill '{skill_name}' not found"}

        if skill_info.get("status") in ("disabled", "available"):
            return {"status": "error", "error": f"Skill '{skill_name}' is {skill_info['status']}"}

        # 安全检查
        try:
            from app.core.security_sandbox import get_security_sandbox
            sandbox = get_security_sandbox()
            check = sandbox.check_tool_call(skill_name, args=args or {})
            if check.blocked:
                return {"status": "blocked", "error": check.description}
        except ImportError:
            pass

        execution = SkillExecution(
            skill_id=skill_info["id"],
            skill_name=skill_name,
            status="running",
            args=args or {},
            started_at=time.time(),
        )
        self._executions.append(execution)

        try:
            result = await self._run_skill(skill_name, args or {}, timeout or self.DEFAULT_TIMEOUT)
            execution.status = "success"
            execution.result = result
            execution.finished_at = time.time()
            execution.duration_ms = int((execution.finished_at - execution.started_at) * 1000)

            # 更新Skill统计
            self._update_skill_stats(skill_info["id"], True, execution.duration_ms)

            return {
                "status": "success",
                "skill": skill_name,
                "result": result,
                "duration_ms": execution.duration_ms,
            }
        except asyncio.TimeoutError:
            execution.status = "timeout"
            execution.error = f"Execution timed out after {timeout or self.DEFAULT_TIMEOUT}s"
            execution.finished_at = time.time()
            self._update_skill_stats(skill_info["id"], False, 0)
            return {"status": "timeout", "error": execution.error}
        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            execution.finished_at = time.time()
            self._update_skill_stats(skill_info["id"], False, 0)
            return {"status": "failed", "error": str(e)}

    async def _run_skill(self, skill_name: str, args: Dict[str, Any], timeout: int) -> Any:
        """实际执行Skill

        根据 skill_name 路由到对应的真实执行逻辑。
        支持:
          - shopify系列: 通过 Shopify GraphQL API
          - web-search / summarize / brandkit / skill-vetter: 内置逻辑
          - prompt 类型: 通过 AstraAssistant.run_task() 执行 prompt 模板
        """
        import asyncio

        # 先查注册表，判断 skill 类型
        skill_info = self.registry.get_skill_by_name(skill_name)
        if isinstance(skill_info, dict):
            source = skill_info.get("source", "")
            prompt_name = ((skill_info.get("config", {}) or {})).get("prompt", "")
            script = skill_info.get("script", "")
            script_args = skill_info.get("script_args", [])
        else:
            source = prompt_name = script = ""
            script_args = []

        # prompt 类型: 委托给 AstraAssistant 执行 prompt 模板
        if source == "prompt" and prompt_name:
            return await self._execute_prompt_skill(prompt_name, skill_name, args)

        # script 类型: 通过 subprocess 执行独立脚本
        if source == "script" and script:
            return await self._execute_script_skill(script, script_args, skill_name, args, timeout)

        async def _inner():
            if skill_name.startswith("shopify-"):
                return await self._execute_shopify_skill(skill_name, args)
            elif skill_name == "web-search":
                return await self._execute_web_search(args)
            elif skill_name == "summarize":
                return await self._execute_summarize(args)
            elif skill_name == "brandkit":
                return await self._execute_brandkit(args)
            elif skill_name == "skill-vetter":
                return await self._execute_vetter(args)
            else:
                return {"message": f"Skill '{skill_name}' executed", "args": args}

        return await asyncio.wait_for(_inner(), timeout=timeout)

    async def _execute_script_skill(
        self,
        script: str,
        script_args: List[str],
        skill_name: str,
        args: Dict[str, Any],
        timeout: int,
    ) -> Dict:
        """通过 subprocess 执行脚本 Skill。

        将 skill_info 中的 script_args 模板与调用参数绑定后，
        使用 subprocess.run([sys.executable, script_path, ...]) 执行。
        """
        script_path = SKILLS_DATA_DIR / script
        if not script_path.exists():
            return {
                "skill": skill_name,
                "status": "error",
                "error": f"脚本文件不存在: {script_path}",
            }

        # 绑定模板参数: {key} → args["key"]
        cmd = [sys.executable, str(script_path)]
        for arg_tpl in script_args:
            bound = arg_tpl
            for key, val in (args or {}).items():
                placeholder = "{" + key + "}"
                if placeholder in bound:
                    bound = bound.replace(placeholder, str(val))
            if "{" in bound or "}" in bound:
                # 有未绑定的占位符，跳过该参数
                continue
            cmd.append(bound)

        try:
            loop = asyncio.get_event_loop()
            proc = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=timeout // 1000 if timeout > 1000 else timeout,
                        encoding="utf-8",
                    ),
                ),
                timeout=timeout if timeout < 300 else 300,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                try:
                    result_data = json.loads(proc.stdout.strip())
                except json.JSONDecodeError:
                    result_data = {"raw": proc.stdout.strip()}
            else:
                result_data = {
                    "returncode": proc.returncode,
                    "stderr": proc.stderr[:500] if proc.stderr else "",
                }
            return {
                "skill": skill_name,
                "script": str(script_path),
                "status": "success" if proc.returncode == 0 else "error",
                "result": result_data,
            }
        except subprocess.TimeoutExpired:
            return {
                "skill": skill_name,
                "status": "timeout",
                "error": f"脚本执行超时 ({timeout}s)",
            }
        except Exception as e:
            return {
                "skill": skill_name,
                "status": "error",
                "error": str(e),
            }

    async def _execute_prompt_skill(self, prompt_name: str, skill_name: str, args: Dict[str, Any]) -> Dict:
        """通过 Prompt 模板执行合规技能。

        使用 AstraAssistant.run_task() 调用 prompts/{prompt_name}.yaml 模板。
        """
        try:
            from app.services.astra_assistant import AstraAssistant
            assistant = AstraAssistant()
            result = await assistant.run_task(
                prompt_name=prompt_name,
                context=args,
            )
            return {
                "skill": skill_name,
                "prompt": prompt_name,
                "status": "success",
                "result": result,
            }
        except Exception as e:
            return {
                "skill": skill_name,
                "prompt": prompt_name,
                "status": "error",
                "error": str(e),
            }

    async def _execute_web_search(self, args: Dict[str, Any]) -> Dict:
        """真实 Web 搜索

        优先使用配置的搜索 API（如 Tavily/SearXNG），
        回退到 DuckDuckGo 零点击 API。
        """
        query = args.get("query", args.get("q", ""))
        if not query:
            return {"error": "未提供搜索关键词", "query": query, "results": []}

        # 尝试使用配置的搜索引擎
        import os
        tavily_key = os.environ.get("TAVILY_API_KEY", "")
        if tavily_key:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://api.tavily.com/search",
                        json={"api_key": tavily_key, "query": query, "search_depth": "basic"},
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return {"query": query, "results": data.get("results", []), "source": "tavily"}
            except Exception:
                pass

        # 回退到 DuckDuckGo
        try:
            import httpx
            from urllib.parse import quote
            # DuckDuckGo 即时回答 API
            ddg_url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1&skip_disambig=1"
            async with httpx.AsyncClient() as client:
                resp = await client.get(ddg_url, timeout=10, follow_redirects=True)
                data = resp.json()
                results = []
                # 解析 AbstractText
                abstract = data.get("AbstractText", "")
                if abstract:
                    results.append({
                        "title": data.get("Heading", "摘要"),
                        "content": abstract,
                        "url": data.get("AbstractURL", ""),
                    })
                # 解析 RelatedTopics
                for topic in data.get("RelatedTopics", [])[:5]:
                    if "Text" in topic:
                        results.append({
                            "title": topic.get("Text", "")[:80],
                            "content": topic.get("Text", ""),
                            "url": topic.get("FirstURL", ""),
                        })
                    elif "Topics" in topic:
                        for sub in topic["Topics"][:3]:
                            results.append({
                                "title": sub.get("Text", "")[:80],
                                "content": sub.get("Text", ""),
                                "url": sub.get("FirstURL", ""),
                            })
                return {"query": query, "results": results, "source": "duckduckgo"}
        except Exception as e:
            return {"query": query, "results": [], "error": str(e), "source": "fallback"}

    async def _execute_shopify_skill(self, skill_name: str, args: Dict[str, Any]) -> Dict:
        """执行 Shopify 系列 Skill

        从 OAuth 管理器获取已配置的 Shopify 凭证，
        调用真实的 Admin GraphQL API。
        """
        from app.core.oauth_manager import get_oauth_manager
        oauth = get_oauth_manager()
        shopify_conns = oauth.list_connections(provider="shopify")
        shopify_config = shopify_conns[0] if shopify_conns else None

        if not shopify_config:
            return {
                "skill": skill_name,
                "status": "config_required",
                "message": "Shopify OAuth 凭证未配置。请在 配置中心 -> OAuth 页面配置 Shopify 集成后重试。",
            }

        shop_domain = shopify_config.get("shop_domain", "")
        access_token = shopify_config.get("access_token", "")
        if not shop_domain or not access_token:
            return {
                "skill": skill_name,
                "status": "config_required",
                "message": "Shopify 凭证不完整，需要 shop_domain 和 access_token。",
            }

        return await self._call_shopify_graphql(skill_name, args, shop_domain, access_token)

    async def _call_shopify_graphql(self, skill_name: str, args: Dict, domain: str, token: str) -> Dict:
        """调用 Shopify Admin GraphQL API"""
        import httpx

        # 按 Skill 类型构建 GraphQL 查询
        query_map = {
            "shopify-admin": """{
  products(first: 10) {
    edges { node { id title handle status } }
  }
}""",
            "shopify-customer": """{
  customers(first: 10) {
    edges { node { id email displayName } }
  }
}""",
            "shopify-custom-data": """{
  metaobjects(first: 10) { edges { node { id type } } }
}""",
            "shopify-payments-apps": """{
  shop { name email } paymentsApps { name }
}""",
            "shopify-functions": """{
  shop { name }
}""",
            "shopify-storefront-graphql": """{
  shop { name } products(first: 5) { edges { node { id title } } }
}""",
        }
        query = query_map.get(skill_name, "{ shop { name } }")[:2000]

        api_version = args.get("api_version", "2024-10")
        endpoint = f"https://{domain}/admin/api/{api_version}/graphql.json"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    endpoint,
                    headers={
                        "X-Shopify-Access-Token": token,
                        "Content-Type": "application/json",
                    },
                    json={"query": query},
                    timeout=15,
                )
                data = resp.json()

                if "errors" in data:
                    return {
                        "skill": skill_name,
                        "status": "api_error",
                        "error": data["errors"][0].get("message", str(data["errors"])),
                    }

                return {
                    "skill": skill_name,
                    "status": "success",
                    "shop": domain,
                    "data": data.get("data", {}),
                }
        except httpx.TimeoutException:
            return {"skill": skill_name, "status": "timeout", "error": f"Shopify API 请求超时 ({endpoint})"}
        except Exception as e:
            return {"skill": skill_name, "status": "error", "error": str(e)}

    async def _execute_summarize(self, args: Dict[str, Any]) -> Dict:
        """URL 内容摘要"""
        url = args.get("url", "")
        text = args.get("text", "")

        if not url and not text:
            return {"error": "请提供 url 或 text 参数"}

        if url:
            try:
                import httpx
                from urllib.parse import urlparse
                parsed = urlparse(url)
                if not parsed.scheme:
                    url = "https://" + url

                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=15, follow_redirects=True)
                    content_type = resp.headers.get("content-type", "")
                    body = resp.text

                    # HTML 提取纯文本
                    if "text/html" in content_type:
                        import re
                        body = re.sub(r"<[^>]+>", " ", body)
                        body = re.sub(r"\s+", " ", body).strip()

                    summary = body[:2000] if len(body) > 2000 else body
                    return {
                        "url": url,
                        "status": "success",
                        "content_length": len(body),
                        "summary": summary[:500] + "..." if len(summary) > 500 else summary,
                    }
            except Exception as e:
                return {"url": url, "status": "error", "error": str(e)}

        return {"status": "success", "summary": text[:500]}

    async def _execute_brandkit(self, args: Dict[str, Any]) -> Dict:
        """品牌工具包 — 基于品牌名称哈希生成定制化品牌指南"""
        brand_type = args.get("type", "report")
        name = args.get("name", args.get("brand", "未命名"))

        # 从品牌名称哈希生成确定性色板
        import hashlib
        seed = int(hashlib.md5(name.encode("utf-8")).hexdigest()[:8], 16)

        def _hue_offset(idx: int) -> str:
            # 生成6位HSL色值
            h = (seed + idx * 47) % 360
            s = 50 + (seed + idx) % 30  # 50-79%
            l = 35 + (seed * 3 + idx * 11) % 25  # 35-59%
            return f"hsl({h},{s}%,{l}%)"

        palette = {
            "primary": _hue_offset(0),
            "secondary": _hue_offset(1),
            "accent": _hue_offset(2),
            "neutral": _hue_offset(3),
            "background": f"hsl({(seed + 180) % 360},10%,96%)",
        }

        # 根据品牌类型推荐字体
        type_fonts = {
            "tech":      ["Inter", "SF Pro Display", "JetBrains Mono"],
            "retail":    ["Noto Sans SC", "Playfair Display", "DM Sans"],
            "logistics": ["IBM Plex Sans", "Space Grotesk", "Roboto Mono"],
            "finance":   ["Source Sans 3", "Merriweather", "Fira Code"],
            "report":    ["Noto Sans SC", "Noto Serif SC", "JetBrains Mono"],
        }
        typography = type_fonts.get(brand_type, type_fonts["report"])

        suggestions = [
            f"基于{_hue_offset(0)}主色构建品牌色板系统",
            "输出品牌Logo在不同背景下的适配方案",
            "准备品牌图标库（24px/32px/48px三档）",
            f"输出{name}的字体排版规范（标题/正文/代码）",
            "制作品牌展示板（Brand Guidelines Board）",
        ]
        if brand_type in ("tech", "finance"):
            suggestions.append("输出暗色模式品牌适配指南")

        return {
            "type": brand_type,
            "brand": name,
            "status": "generated",
            "palette": palette,
            "typography": typography,
            "suggestions": suggestions,
            "seed_hash": hex(seed)[:10],
        }

    async def _execute_vetter(self, args: Dict[str, Any]) -> Dict:
        """Skill 安全审查 — 检查 SKILL.md 源码中是否存在高危模式"""
        target = args.get("skill_name", "")
        source = args.get("source_url", args.get("source", ""))

        checks = []
        content_found = True
        raw_content = ""

        # 尝试读取 SKILL.md 文件
        skill_path = Path(".agents/skills") / target if target else None
        if skill_path and skill_path.exists():
            raw_content = skill_path.read_text(encoding="utf-8", errors="replace")
        elif skill_path and (skill_path / "SKILL.md").exists():
            raw_content = (skill_path / "SKILL.md").read_text(encoding="utf-8", errors="replace")
        else:
            # 尝试在项目根目录搜索
            candidates = list(Path(".").rglob(f"**/{target}/SKILL.md")) if target else []
            if candidates:
                raw_content = candidates[0].read_text(encoding="utf-8", errors="replace")
            else:
                content_found = False

        DANGEROUS_PATTERNS = [
            ("eval/exec", r"\b(eval|exec)\s*\(", "危险代码执行"),
            ("subprocess", r"\b(subprocess\.(call|Popen|run)|os\.system|os\.popen)\b", "系统命令执行"),
            ("file_write", r"\bopen\s*\(.*['\"][rwab]\+?['\"]\)", "文件写入操作"),
            ("network_req", r"\b(requests\.(get|post|put|delete)|httpx\.|urllib\.request|aiohttp\.ClientSession)\b", "外部网络请求"),
            ("env_read", r"\bos\.environ\b|\bgetenv\b", "环境变量读取"),
            ("tempfile", r"\btempfile\.|\bmkdtemp\b", "临时文件创建"),
            ("base64_decode", r"\bbase64\.(b64decode|urlsafe_b64decode)\b", "Base64解码"),
            ("pickle_load", r"\bpickle\.(load|loads|Unpickler)\b", "不安全反序列化"),
            ("sql_inject", r"\bexecute\(?\s*['\"]\s*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)", "SQL语句执行"),
            ("shell_escape", r"\bshlex\.quote\b", "Shell转义处理"),
        ]

        if content_found and raw_content:
            import re
            found_issues = []
            for check_id, pattern, description in DANGEROUS_PATTERNS:
                matches = re.findall(pattern, raw_content, re.IGNORECASE)
                if matches:
                    status = "warn" if check_id in ("eval/exec", "subprocess", "pickle_load") else "info"
                    found_issues.append({
                        "check": description,
                        "status": status,
                        "detail": f"发现 {len(matches)} 处匹配",
                    })
                else:
                    found_issues.append({
                        "check": description,
                        "status": "pass",
                    })
            checks = found_issues
        else:
            # 未找到实际内容时，基于参数做静态推断
            checks = [
                {"check": "权限声明", "status": "warn" if not target else "pass"},
                {"check": "外部网络请求", "status": "warn" if source else "info", "detail": f"来源: {source}" if source else ""},
                {"check": "文件系统访问", "status": "info"},
                {"check": "环境变量读取", "status": "info"},
                {"check": "危险代码模式", "status": "info"},
            ]

        if source:
            checks.append({"check": "来源可信度", "status": "info", "detail": source})

        # 计算综合风险
        warn_count = sum(1 for c in checks if c["status"] == "warn")
        if warn_count >= 2:
            risk_level = "high"
            approved = False
            summary = f"技能 '{target}' 发现 {warn_count} 个高危模式，建议暂停安装并人工审查"
        elif warn_count == 1:
            risk_level = "medium"
            approved = False
            summary = f"技能 '{target}' 存在 {warn_count} 个潜在风险，建议人工确认后再安装"
        elif "unknown" in source.lower() or "unverified" in source.lower():
            risk_level = "medium"
            approved = False
            summary = f"技能 '{target}' 来源未经验证，建议人工审核后再安装"
        else:
            risk_level = "low"
            approved = True
            summary = f"技能 '{target}' 安全审查通过，风险等级：低"

        return {
            "skill": target or "unknown",
            "status": "reviewed",
            "approved": approved,
            "risk_level": risk_level,
            "checks": checks,
            "summary": summary,
            "content_scanned": content_found and bool(raw_content),
        }

    def _update_skill_stats(self, skill_id: str, success: bool, duration_ms: int):
        """更新Skill执行统计"""
        skill = self.registry._skills.get(skill_id)
        if not skill:
            return
        skill.install_count += 1
        total = skill.install_count
        if success:
            skill.success_rate = ((skill.success_rate * (total - 1)) + 1) / total
        else:
            skill.success_rate = (skill.success_rate * (total - 1)) / total
        skill.avg_execution_ms = int((skill.avg_execution_ms * (total - 1) + duration_ms) / total)
        skill.last_used_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.registry._persist()

    def get_executions(self, skill_name: str = None, limit: int = 50) -> List[Dict]:
        execs = self._executions
        if skill_name:
            execs = [e for e in execs if e.skill_name == skill_name]
        return [e.to_dict() for e in execs[-limit:]]


# ── SkillRecommender ──────────────────────────────


class SkillRecommender:
    """技能推荐器 — 根据事件类型/业务阶段推荐Skills"""

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def recommend_by_event(self, event_category: str) -> List[Dict]:
        """根据事件类别推荐Skills（三层动作：Skill/CLI/API）"""
        actions = EVENT_ACTION_MAP.get(event_category, [])
        return actions

    def recommend_by_stage(self, stage: int, event_type: str = "") -> List[Dict]:
        """根据业务阶段推荐Skills"""
        stage_skills = SKILLS_STAGE_MATRIX.get(stage, [])

        if event_type:
            # 精确匹配
            matched = [s for s in stage_skills if event_type in s.get("events", [])]
            if matched:
                return matched

        # 阶段默认 + 跨阶段通用
        result = list(stage_skills)
        result.extend(CROSS_STAGE_SKILLS[:2])  # 附加 skill-vetter 和 web-search
        return result

    def recommend_by_context(self, context: Dict[str, Any]) -> List[Dict]:
        """根据上下文综合推荐"""
        recommendations = []

        stage = context.get("business_stage")
        event_category = context.get("event_category", "")
        product_type = context.get("product_type", "")

        if stage:
            stage_recs = self.recommend_by_stage(int(stage))
            recommendations.extend([{"skill": s.get("skill", ""), "reason": s.get("purpose", ""),
                                    "source": "stage_match"} for s in stage_recs])

        if event_category:
            event_recs = self.recommend_by_event(event_category)
            recommendations.extend([{"skill": r.get("name", ""), "reason": r.get("action", ""),
                                    "source": "event_match", "type": r.get("type", "")} for r in event_recs])

        # 去重
        seen = set()
        unique = []
        for r in recommendations:
            key = r.get("skill", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(r)

        return unique[:10]  # 最多返回10个推荐

    def get_action_recommendations(self, event_category: str) -> Dict:
        """获取完整的事件动作推荐清单（Skill/CLI/API三层）"""
        return {
            "event_category": event_category,
            "actions": EVENT_ACTION_MAP.get(event_category, []),
            "guide_ref": f"§5 事件动作推荐清单",
        }


# ── 整合单例 ──────────────────────────────────────

_skill_registry: Optional[SkillRegistry] = None
_skill_executor: Optional[SkillExecutor] = None
_skill_recommender: Optional[SkillRecommender] = None


def get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry


def get_skill_executor() -> SkillExecutor:
    global _skill_executor
    if _skill_executor is None:
        _skill_executor = SkillExecutor(get_skill_registry())
    return _skill_executor


def get_skill_recommender() -> SkillRecommender:
    global _skill_recommender
    if _skill_recommender is None:
        _skill_recommender = SkillRecommender(get_skill_registry())
    return _skill_recommender
