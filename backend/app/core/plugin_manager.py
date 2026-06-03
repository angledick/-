"""
PluginManager + CodeCapability（Phase 3.4）

PluginManager — 插件系统
参考开源选型：
- Open WebUI（指南 §3.5.11）插件系统架构
- n8n（指南 §3.5.8）400+集成节点扩展模式
支持安装/卸载/安全审查/启用/禁用

CodeCapability — 编码能力
参考: Claude Code兼容、LSP跳转、AST搜索
"""

from __future__ import annotations

import ast
import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings


# ═══════════════════════════════════════════════════════
# PluginManager
# ═══════════════════════════════════════════════════════


class PluginSource(str, Enum):
    pypi = "pypi"
    git = "git"
    local = "local"


class PluginStatus(str, Enum):
    installed = "installed"
    active = "active"
    disabled = "disabled"
    error = "error"


@dataclass
class PluginInfo:
    """插件信息"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    display_name: str = ""
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    source: PluginSource = PluginSource.pypi
    source_url: str = ""
    status: PluginStatus = PluginStatus.installed
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)  # 声明的权限
    config: Dict[str, Any] = field(default_factory=dict)
    audit_result: Dict[str, Any] = field(default_factory=dict)  # 安全审查结果
    installed_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "PluginInfo":
        source_val = data.pop("source", "pypi")
        status_val = data.pop("status", "installed")
        plugin = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        plugin.source = PluginSource(source_val) if isinstance(source_val, str) else source_val
        plugin.status = PluginStatus(status_val) if isinstance(status_val, str) else status_val
        return plugin


@dataclass
class AuditReport:
    """安全审查报告"""
    plugin_id: str = ""
    plugin_name: str = ""
    passed: bool = False
    risk_level: str = "unknown"     # low / medium / high / critical
    findings: List[Dict] = field(default_factory=list)
    dependency_count: int = 0
    permission_count: int = 0
    network_access: List[str] = field(default_factory=list)
    file_access: List[str] = field(default_factory=list)
    scanned_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict:
        return asdict(self)


# ── 持久化 ────────────────────────────────────────

PLUGINS_FILE = Path(settings.data_dir) / "config" / "plugins.json"


def _load_plugins() -> Dict[str, dict]:
    if PLUGINS_FILE.exists():
        try:
            with open(PLUGINS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_plugins(data: Dict[str, dict]) -> None:
    PLUGINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PLUGINS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class PluginManager:
    """插件管理器"""

    # 推荐插件清单（参考指南 §3.5）
    RECOMMENDED_PLUGINS = [
        {"name": "chatwoot-client", "display_name": "Chatwoot Client",
         "description": "Chatwoot全渠道客服Python SDK（指南 §3.5.1）",
         "source": "pypi", "source_url": "chatwoot-client",
         "guide_ref": "§3.5.1 Chatwoot"},
        {"name": "listmonk-client", "display_name": "Listmonk Client",
         "description": "Listmonk邮件营销API客户端（指南 §3.5.2）",
         "source": "pypi", "source_url": "",
         "guide_ref": "§3.5.2 Listmonk"},
        {"name": "erpnext-client", "display_name": "ERPNext Client",
         "description": "ERPNext REST API客户端（指南 §3.5.3）",
         "source": "pypi", "source_url": "frappe-client",
         "guide_ref": "§3.5.3 ERPNext"},
        {"name": "pyod", "display_name": "PyOD",
         "description": "异常检测算法库，订单欺诈检测（指南 §3.5.6）",
         "source": "pypi", "source_url": "pyod",
         "guide_ref": "§3.5.6 PyOD"},
        {"name": "qdrant-client", "display_name": "Qdrant Client",
         "description": "Qdrant向量数据库客户端，ChromaDB升级路径（指南 §3.5.10）",
         "source": "pypi", "source_url": "qdrant-client",
         "guide_ref": "§3.5.10 Qdrant"},
        {"name": "temporalio", "display_name": "Temporal SDK",
         "description": "Temporal确定性工作流SDK（指南 §3.5.8）",
         "source": "pypi", "source_url": "temporalio",
         "guide_ref": "§3.5.8 Temporal"},
    ]

    def __init__(self):
        self._plugins: Dict[str, PluginInfo] = {}
        self._load_all()

    def _load_all(self):
        raw = _load_plugins()
        for pid, pdata in raw.items():
            try:
                self._plugins[pid] = PluginInfo.from_dict(pdata)
            except Exception:
                continue

    def _persist(self):
        _save_plugins({pid: p.to_dict() for pid, p in self._plugins.items()})

    # ── CRUD ────────────────────────────────────

    def list_plugins(self) -> List[Dict]:
        return [p.to_dict() for p in self._plugins.values()]

    def get_plugin(self, plugin_id: str) -> Optional[Dict]:
        plugin = self._plugins.get(plugin_id)
        return plugin.to_dict() if plugin else None

    async def install(self, source: str, source_type: str = "pypi",
                     config: Dict = None) -> Dict:
        """安装插件"""
        plugin = PluginInfo(
            name=source,
            display_name=source.replace("-", " ").title(),
            source=PluginSource(source_type),
            source_url=source,
            status=PluginStatus.installed,
            config=config or {},
        )

        # 安全审查
        audit = await self.security_audit(plugin)
        plugin.audit_result = audit.to_dict()

        if not audit.passed and audit.risk_level in ("high", "critical"):
            plugin.status = PluginStatus.error
            self._plugins[plugin.id] = plugin
            self._persist()
            raise RuntimeError(f"Plugin security audit failed: {audit.risk_level} risk. Findings: {audit.findings}")

        self._plugins[plugin.id] = plugin
        self._persist()

        # 触发安装事件
        try:
            from app.core.event_bus import get_event_bus
            import asyncio
            asyncio.create_task(get_event_bus().publish_raw({
                "type": "system:plugin_installed",
                "source": "plugin_manager",
                "data": {"plugin_name": source, "source_type": source_type},
            }))
        except Exception:
            pass

        return plugin.to_dict()

    async def uninstall(self, plugin_id: str) -> bool:
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            self._persist()
            return True
        return False

    async def enable(self, plugin_id: str) -> Optional[Dict]:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return None
        plugin.status = PluginStatus.active
        self._persist()
        return plugin.to_dict()

    async def disable(self, plugin_id: str) -> Optional[Dict]:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return None
        plugin.status = PluginStatus.disabled
        self._persist()
        return plugin.to_dict()

    async def security_audit(self, plugin: PluginInfo = None, plugin_id: str = "") -> AuditReport:
        """安全审查"""
        if plugin_id and not plugin:
            plugin = self._plugins.get(plugin_id)
        if not plugin:
            return AuditReport(passed=False, risk_level="unknown",
                             findings=[{"type": "error", "message": "Plugin not found"}])

        report = AuditReport(
            plugin_id=plugin.id,
            plugin_name=plugin.name,
        )

        findings = []

        # 1. 检查已知推荐插件
        recommended = any(r["name"] == plugin.name for r in self.RECOMMENDED_PLUGINS)
        if recommended:
            report.risk_level = "low"
            report.passed = True
            findings.append({"type": "info", "message": "Plugin is in recommended list"})
        else:
            # 2. 权限声明检查
            high_risk_perms = {"shell_execution", "credential_access", "database_write", "network_access"}
            risky = set(plugin.permissions) & high_risk_perms
            if risky:
                findings.append({"type": "permission_risk", "permissions": list(risky)})
                report.risk_level = "high" if "credential_access" in risky else "medium"
            else:
                report.risk_level = "low"

            # 3. 来源检查
            if plugin.source == PluginSource.git:
                findings.append({"type": "git_source", "url": plugin.source_url})
                if not plugin.source_url.startswith("https://github.com/"):
                    report.risk_level = "medium"

            report.passed = report.risk_level not in ("high", "critical")

        # 4. 使用SecuritySandbox扫描（如有）
        try:
            from app.core.security_sandbox import get_security_sandbox
            sandbox = get_security_sandbox()
            scan = sandbox.scan_skill(f"Plugin: {plugin.name} Source: {plugin.source_url}", plugin.name)
            findings.append({"type": "sandbox_scan", "threat_level": scan.threat_level.value,
                           "description": scan.description})
        except ImportError:
            pass

        report.findings = findings
        report.dependency_count = len(plugin.dependencies)
        report.permission_count = len(plugin.permissions)

        plugin.audit_result = report.to_dict()
        if plugin.id in self._plugins:
            self._persist()

        return report

    def get_recommended(self) -> List[Dict]:
        """获取推荐插件清单"""
        return self.RECOMMENDED_PLUGINS


# ═══════════════════════════════════════════════════════
# CodeCapability
# ═══════════════════════════════════════════════════════


@dataclass
class Definition:
    """LSP跳转定义"""
    file: str = ""
    line: int = 0
    col: int = 0
    symbol: str = ""
    doc: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ASTNode:
    """AST节点"""
    type: str = ""           # FunctionDef / ClassDef / Import / etc
    name: str = ""
    file: str = ""
    line: int = 0
    end_line: int = 0
    children: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PatchResult:
    """代码变更结果"""
    success: bool = False
    files_modified: List[str] = field(default_factory=list)
    lines_changed: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class CodeCapability:
    """编码能力 — LSP/AST/Agent兼容"""

    def __init__(self, workspace_root: str = ""):
        self.workspace_root = workspace_root or str(Path(settings.data_dir).parent)

    async def lsp_jump(self, file: str, line: int, col: int) -> Definition:
        """LSP跳转到定义（基于AST分析）"""
        full_path = self._resolve_path(file)
        if not Path(full_path).exists():
            return Definition(file=file, line=line, col=col, doc="File not found")

        try:
            source = Path(full_path).read_text(encoding="utf-8")
            tree = ast.parse(source)

            # 获取目标行的符号
            target_symbol = self._get_symbol_at(source, line, col)

            # 在AST中搜索定义
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == target_symbol:
                        return Definition(
                            file=full_path, line=node.lineno, col=node.col_offset,
                            symbol=node.name,
                            doc=ast.get_docstring(node) or "",
                        )
                elif isinstance(node, ast.ClassDef):
                    if node.name == target_symbol:
                        return Definition(
                            file=full_path, line=node.lineno, col=node.col_offset,
                            symbol=node.name,
                            doc=ast.get_docstring(node) or "",
                        )
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        if alias.name == target_symbol or alias.asname == target_symbol:
                            return Definition(
                                file=full_path, line=node.lineno, col=node.col_offset,
                                symbol=alias.name, doc=f"Import: {alias.name}",
                            )

            return Definition(file=file, line=line, col=col, symbol=target_symbol,
                            doc="Definition not found in file")
        except Exception as e:
            return Definition(file=file, line=line, col=col, doc=f"Error: {e}")

    async def ast_search(self, pattern: str, file_pattern: str = "**/*.py") -> List[ASTNode]:
        """AST模式搜索"""
        results = []
        base_path = Path(self.workspace_root)

        for file_path in base_path.glob(file_pattern):
            try:
                source = file_path.read_text(encoding="utf-8")
                tree = ast.parse(source)
                nodes = self._match_ast_nodes(tree, pattern, str(file_path))
                results.extend(nodes)
            except Exception:
                continue

        return [n.to_dict() for n in results[:50]]  # Limit results

    async def apply_patch(self, patch: str) -> PatchResult:
        """应用代码变更（unified diff格式）"""
        result = PatchResult()
        try:
            # 解析unified diff
            lines = patch.strip().split("\n")
            current_file = None
            changes = {}

            for line in lines:
                if line.startswith("--- "):
                    continue
                elif line.startswith("+++ "):
                    current_file = line[4:].strip()
                    if current_file.startswith("b/"):
                        current_file = current_file[2:]
                    changes[current_file] = []
                elif line.startswith("@@ "):
                    # Parse hunk header
                    continue
                elif current_file:
                    changes.setdefault(current_file, []).append(line)

            # 应用变更
            for file_name, change_lines in changes.items():
                file_path = Path(self.workspace_root) / file_name
                if not file_path.exists():
                    continue

                content = file_path.read_text(encoding="utf-8")
                content_lines = content.split("\n")

                # Simple line-based patching
                for cl in change_lines:
                    if cl.startswith("+") and not cl.startswith("+++"):
                        content_lines.append(cl[1:])
                        result.lines_changed += 1
                    elif cl.startswith("-") and not cl.startswith("---"):
                        # Remove line
                        target = cl[1:]
                        for i, existing in enumerate(content_lines):
                            if existing.strip() == target.strip():
                                content_lines.pop(i)
                                result.lines_changed += 1
                                break

                file_path.write_text("\n".join(content_lines), encoding="utf-8")
                result.files_modified.append(file_name)

            result.success = True
        except Exception as e:
            result.error = str(e)

        return result.to_dict()

    def _resolve_path(self, file: str) -> str:
        """解析文件路径"""
        if Path(file).is_absolute():
            return file
        return str(Path(self.workspace_root) / file)

    def _get_symbol_at(self, source: str, line: int, col: int) -> str:
        """获取指定位置的符号名"""
        lines = source.split("\n")
        if line < 1 or line > len(lines):
            return ""
        target_line = lines[line - 1]
        # 简单提取: 从col位置向两边扩展找单词
        start = col - 1
        end = col - 1
        while start > 0 and (target_line[start - 1].isalnum() or target_line[start - 1] == "_"):
            start -= 1
        while end < len(target_line) and (target_line[end].isalnum() or target_line[end] == "_"):
            end += 1
        return target_line[start:end]

    def _match_ast_nodes(self, tree: ast.AST, pattern: str, file_path: str) -> List[ASTNode]:
        """匹配AST节点"""
        import re
        results = []
        pattern_re = re.compile(pattern, re.IGNORECASE)

        for node in ast.walk(tree):
            name = getattr(node, "name", "")
            node_type = type(node).__name__

            if pattern_re.search(name) or pattern_re.search(node_type):
                ast_node = ASTNode(
                    type=node_type,
                    name=name,
                    file=file_path,
                    line=getattr(node, "lineno", 0),
                    end_line=getattr(node, "end_lineno", 0),
                )

                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    ast_node.children = [
                        getattr(n, "name", "")
                        for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    ]

                results.append(ast_node)

        return results


# ── 单例 ──────────────────────────────────────────

_plugin_manager: Optional[PluginManager] = None
_code_capability: Optional[CodeCapability] = None


def get_plugin_manager() -> PluginManager:
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def get_code_capability() -> CodeCapability:
    global _code_capability
    if _code_capability is None:
        _code_capability = CodeCapability()
    return _code_capability
