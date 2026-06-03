"""
SecuritySandbox — 安全沙箱（Phase 3.2）

参考开源选型：
- PyOD（指南 §3.5.6）异常检测算法统一接口，用于工具调用异常模式检测
- n8n（指南 §3.5.8）工作流安全策略参考

三层防护：
1. ToolGuard   — 工具防护（拦截危险命令、参数校验、调用频率限制）
2. FileGuard   — 文件防护（敏感文件访问需确认、路径穿越检测、文件大小限制）
3. SkillScanner — 技能安全扫描（Prompt注入检测、权限声明审查、依赖树分析）
"""

from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.config import settings


# ── 数据结构 ────────────────────────────────────────


class ThreatLevel(str, Enum):
    safe = "safe"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ActionType(str, Enum):
    allow = "allow"
    warn = "warn"
    block = "block"
    require_approval = "require_approval"


@dataclass
class SecurityEvent:
    """安全事件记录"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    guard_type: str = ""        # tool / file / skill
    threat_level: ThreatLevel = ThreatLevel.safe
    action: ActionType = ActionType.allow
    source: str = ""            # 调用来源（tool_name / file_path / skill_name）
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    blocked: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["threat_level"] = self.threat_level.value
        d["action"] = self.action.value
        return d


@dataclass
class GuardRule:
    """防护规则"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    description: str = ""
    guard_type: str = ""        # tool / file / skill
    pattern: str = ""           # 正则或关键词
    threat_level: ThreatLevel = ThreatLevel.medium
    action: ActionType = ActionType.block
    enabled: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["threat_level"] = self.threat_level.value
        d["action"] = self.action.value
        return d


# ── ToolGuard — 工具防护 ─────────────────────────


class ToolGuard:
    """
    工具防护 — 拦截危险命令、参数校验、调用频率限制

    参考 PyOD（指南 §3.5.6）异常模式检测
    """

    # 危险命令模式
    DANGEROUS_PATTERNS = [
        # 系统级危险命令
        (r"\b(rm\s+-rf|del\s+/[sq]|format\s+[a-z]:|mkfs\.|dd\s+if=)\b", ThreatLevel.critical, "Destructive system command"),
        (r"\b(shutdown|reboot|init\s+[06]|halt|poweroff)\b", ThreatLevel.high, "System power command"),
        (r"\b(curl|wget)\b.*\|\s*(bash|sh|python|node)\b", ThreatLevel.high, "Pipe to shell execution"),
        (r"\b(chmod\s+[0-7]*7|chown\s+root)\b", ThreatLevel.medium, "Permission escalation"),

        # 数据危险操作
        (r"\b(DROP\s+TABLE|TRUNCATE|DELETE\s+FROM\s+\w+\s*;)\b", ThreatLevel.high, "Destructive SQL"),
        (r"\bGRANT\s+ALL\b", ThreatLevel.medium, "SQL privilege escalation"),

        # 网络危险操作
        (r"\b(nc\s+-l|ncat\s+-l|socat)\b", ThreatLevel.high, "Network listener (potential backdoor)"),
        (r"\b(ssh\s+-R|ssh\s+-D)\b", ThreatLevel.medium, "SSH tunnel/port forwarding"),

        # 敏感信息泄露
        (r"(password|secret|api_key|token|credential)\s*[:=]\s*['\"][^'\"]+['\"]", ThreatLevel.high, "Hardcoded credential"),
        (r"\.env\b.*\b(cat|type|less|head)\b", ThreatLevel.medium, "Environment file access"),
    ]

    # 调用频率限制
    RATE_LIMITS: Dict[str, int] = {
        "default": 100,        # 每分钟默认100次
        "shopify_api": 30,     # Shopify API限制
        "email_send": 10,      # 邮件发送限制
        "file_write": 50,      # 文件写入限制
    }

    def __init__(self):
        self._call_counts: Dict[str, List[float]] = defaultdict(list)
        self._compiled_patterns = []
        for pattern, level, desc in self.DANGEROUS_PATTERNS:
            try:
                self._compiled_patterns.append((re.compile(pattern, re.IGNORECASE), level, desc))
            except re.error:
                continue

    def check_command(self, command: str, tool_name: str = "") -> SecurityEvent:
        """检查命令是否安全"""
        event = SecurityEvent(
            guard_type="tool",
            source=tool_name,
            details={"command": command[:500]},
        )

        # 1. 检查危险命令模式
        for pattern, level, desc in self._compiled_patterns:
            if pattern.search(command):
                event.threat_level = level
                event.description = f"Blocked: {desc}"
                event.action = ActionType.block
                event.blocked = True
                return event

        # 2. 检查调用频率
        if not self._check_rate_limit(tool_name):
            event.threat_level = ThreatLevel.medium
            event.description = f"Rate limit exceeded for {tool_name}"
            event.action = ActionType.warn
            return event

        event.threat_level = ThreatLevel.safe
        event.action = ActionType.allow
        return event

    def check_tool_args(self, tool_name: str, args: Dict[str, Any]) -> SecurityEvent:
        """检查工具参数安全性"""
        event = SecurityEvent(
            guard_type="tool",
            source=tool_name,
            details={"args_keys": list(args.keys())},
        )

        # 检查参数中的危险内容
        args_str = str(args)
        for pattern, level, desc in self._compiled_patterns:
            if pattern.search(args_str):
                event.threat_level = level
                event.description = f"Dangerous content in args: {desc}"
                event.action = ActionType.block
                event.blocked = True
                return event

        event.threat_level = ThreatLevel.safe
        event.action = ActionType.allow
        return event

    def _check_rate_limit(self, key: str) -> bool:
        """检查调用频率"""
        now = time.time()
        window = 60  # 1 minute window

        # 清理过期计数
        self._call_counts[key] = [t for t in self._call_counts[key] if now - t < window]

        limit = self.RATE_LIMITS.get(key, self.RATE_LIMITS["default"])
        if len(self._call_counts[key]) >= limit:
            return False

        self._call_counts[key].append(now)
        return True

    def get_rate_limit_status(self) -> Dict:
        """获取频率限制状态"""
        now = time.time()
        status = {}
        for key in set(list(self._call_counts.keys()) + list(self.RATE_LIMITS.keys())):
            limit = self.RATE_LIMITS.get(key, self.RATE_LIMITS["default"])
            recent = len([t for t in self._call_counts.get(key, []) if now - t < 60])
            status[key] = {"current": recent, "limit": limit, "remaining": max(0, limit - recent)}
        return status


# ── FileGuard — 文件防护 ─────────────────────────


class FileGuard:
    """文件防护 — 敏感文件访问、路径穿越、大小限制"""

    # 敏感路径模式
    SENSITIVE_PATHS = [
        r"\.env\b",
        r"\.git[/\\]",
        r"[/\\]\.ssh[/\\]",
        r"credentials?\.json",
        r"secrets?\.ya?ml",
        r"private[_-]?key",
        r"\.pem$",
        r"\.p12$",
        r"\.keystore$",
        r"shadow$",
        r"passwd$",
    ]

    # 危险文件扩展名
    DANGEROUS_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".sh", ".vbs", ".js", ".py", ".dll", ".so"}

    # 受保护目录
    PROTECTED_DIRS = {"config/", "config\\", ".git/", ".git\\"}

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    def __init__(self):
        self._sensitive_patterns = [re.compile(p, re.IGNORECASE) for p in self.SENSITIVE_PATHS]

    def check_access(self, file_path: str, operation: str = "read") -> SecurityEvent:
        """检查文件访问安全性"""
        event = SecurityEvent(
            guard_type="file",
            source=file_path,
            details={"operation": operation, "path": file_path},
        )

        # 1. 路径穿越检测
        if self._is_path_traversal(file_path):
            event.threat_level = ThreatLevel.critical
            event.description = "Path traversal detected"
            event.action = ActionType.block
            event.blocked = True
            return event

        # 2. 敏感文件检测
        for pattern in self._sensitive_patterns:
            if pattern.search(file_path):
                event.threat_level = ThreatLevel.high
                event.description = f"Sensitive file access: {file_path}"
                event.action = ActionType.require_approval
                return event

        # 3. 受保护目录检测
        normalized = file_path.replace("\\", "/")
        for protected in self.PROTECTED_DIRS:
            if protected.replace("\\", "/") in normalized:
                event.threat_level = ThreatLevel.medium
                event.description = f"Protected directory access: {file_path}"
                event.action = ActionType.warn
                return event

        # 4. 危险扩展名检测（写入时）
        if operation == "write":
            ext = Path(file_path).suffix.lower()
            if ext in self.DANGEROUS_EXTENSIONS:
                event.threat_level = ThreatLevel.medium
                event.description = f"Dangerous file type write: {ext}"
                event.action = ActionType.warn
                return event

        event.threat_level = ThreatLevel.safe
        event.action = ActionType.allow
        return event

    def check_file_size(self, file_path: str) -> SecurityEvent:
        """检查文件大小"""
        event = SecurityEvent(guard_type="file", source=file_path)
        try:
            size = Path(file_path).stat().st_size
            event.details["size_bytes"] = size
            if size > self.MAX_FILE_SIZE:
                event.threat_level = ThreatLevel.medium
                event.description = f"File exceeds size limit: {size} > {self.MAX_FILE_SIZE}"
                event.action = ActionType.warn
            else:
                event.threat_level = ThreatLevel.safe
                event.action = ActionType.allow
        except FileNotFoundError:
            event.threat_level = ThreatLevel.safe
            event.action = ActionType.allow
        return event

    def _is_path_traversal(self, file_path: str) -> bool:
        """检测路径穿越"""
        # 检查 .. 组件
        parts = Path(file_path).parts
        if ".." in parts:
            return True
        # 检查绝对路径访问系统目录
        if Path(file_path).is_absolute():
            normalized = file_path.replace("\\", "/").lower()
            system_dirs = ["/etc/", "/usr/", "/var/", "/sys/", "/proc/",
                          "c:/windows/", "c:/program files/"]
            for sys_dir in system_dirs:
                if normalized.startswith(sys_dir):
                    return True
        return False


# ── SkillScanner — 技能安全扫描 ──────────────────


class SkillScanner:
    """
    技能安全扫描 — Prompt注入检测、权限声明审查、依赖树分析

    参考 skill-vetter（指南 §4.3 跨阶段通用Skills）安全审查模式
    """

    # Prompt注入模式
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"you\s+are\s+now\s+a",
        r"disregard\s+(all\s+)?prior",
        r"forget\s+(all\s+)?previous",
        r"new\s+instructions?\s*:",
        r"system\s*prompt\s*:",
        r"override\s+(your\s+)?instructions?",
        r"act\s+as\s+(if\s+)?a",
        r"pretend\s+(to\s+be|you\s+are)",
        r"jailbreak",
        r"DAN\s+mode",
    ]

    # 高风险权限
    HIGH_RISK_PERMISSIONS = [
        "file_system_write",
        "network_access",
        "shell_execution",
        "credential_access",
        "database_write",
        "system_config_modify",
    ]

    # 需要声明的网络域名白名单
    ALLOWED_DOMAINS = [
        "shopify.com", "myshopify.com",
        "open.feishu.cn", "api.dingtalk.com",
        "api.openai.com", "api.anthropic.com",
        "github.com", "raw.githubusercontent.com",
    ]

    def __init__(self):
        self._injection_patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]

    def scan_skill(self, skill_content: str, skill_name: str = "") -> SecurityEvent:
        """扫描Skill内容安全性"""
        event = SecurityEvent(
            guard_type="skill",
            source=skill_name,
            details={"content_length": len(skill_content)},
        )

        findings = []

        # 1. Prompt注入检测
        injection_results = self._check_injection(skill_content)
        if injection_results:
            findings.append({
                "type": "prompt_injection",
                "severity": "critical",
                "matches": injection_results,
            })

        # 2. 权限声明审查
        permission_issues = self._check_permissions(skill_content)
        if permission_issues:
            findings.append({
                "type": "permission_violation",
                "severity": "high",
                "issues": permission_issues,
            })

        # 3. 敏感信息检测
        sensitive_info = self._check_sensitive_info(skill_content)
        if sensitive_info:
            findings.append({
                "type": "sensitive_info",
                "severity": "medium",
                "findings": sensitive_info,
            })

        # 4. 网络访问检查
        network_access = self._check_network_access(skill_content)
        if network_access:
            findings.append({
                "type": "network_access",
                "severity": "low",
                "urls": network_access,
            })

        event.details["findings"] = findings

        if any(f.get("severity") == "critical" for f in findings):
            event.threat_level = ThreatLevel.critical
            event.action = ActionType.block
            event.blocked = True
            event.description = "Critical security issues found in skill"
        elif any(f.get("severity") == "high" for f in findings):
            event.threat_level = ThreatLevel.high
            event.action = ActionType.require_approval
            event.description = "High-risk issues require approval"
        elif findings:
            event.threat_level = ThreatLevel.medium
            event.action = ActionType.warn
            event.description = f"Found {len(findings)} potential issues"
        else:
            event.threat_level = ThreatLevel.safe
            event.action = ActionType.allow
            event.description = "Skill passed security scan"

        return event

    def _check_injection(self, content: str) -> List[str]:
        """检测Prompt注入"""
        matches = []
        for pattern in self._injection_patterns:
            found = pattern.findall(content)
            if found:
                matches.extend(found[:5])  # Limit to 5 per pattern
        return matches

    def _check_permissions(self, content: str) -> List[str]:
        """检查权限声明"""
        issues = []
        content_lower = content.lower()
        for perm in self.HIGH_RISK_PERMISSIONS:
            if perm in content_lower:
                issues.append(f"High-risk permission referenced: {perm}")
        return issues

    def _check_sensitive_info(self, content: str) -> List[str]:
        """检测敏感信息"""
        findings = []
        # API keys patterns
        key_patterns = [
            r"sk-[a-zA-Z0-9]{20,}",           # OpenAI keys
            r"sk-ant-[a-zA-Z0-9-]{20,}",      # Anthropic keys
            r"ghp_[a-zA-Z0-9]{36}",            # GitHub PAT
            r"xoxb-[0-9]+-[a-zA-Z0-9]+",       # Slack bot token
        ]
        for pattern in key_patterns:
            if re.search(pattern, content):
                findings.append(f"Possible API key found: {pattern[:20]}...")
        return findings

    def _check_network_access(self, content: str) -> List[str]:
        """检查网络访问URL"""
        url_pattern = re.compile(r"https?://[^\s'\"]+", re.IGNORECASE)
        urls = url_pattern.findall(content)
        unknown_urls = []
        for url in urls:
            is_allowed = any(domain in url for domain in self.ALLOWED_DOMAINS)
            if not is_allowed:
                unknown_urls.append(url[:100])
        return unknown_urls[:20]


# ── SecuritySandbox — 统一安全沙箱 ───────────────


class SecuritySandbox:
    """安全沙箱 — 整合三层防护"""

    def __init__(self):
        self.tool_guard = ToolGuard()
        self.file_guard = FileGuard()
        self.skill_scanner = SkillScanner()
        self._events: List[SecurityEvent] = []
        self._custom_rules: List[GuardRule] = []
        self._load_rules()

    def _load_rules(self):
        rules_file = Path(settings.data_dir) / "config" / "security_rules.json"
        if rules_file.exists():
            try:
                import json
                with open(rules_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for rd in data:
                    self._custom_rules.append(GuardRule(**{k: v for k, v in rd.items() if k in GuardRule.__dataclass_fields__}))
            except Exception:
                pass

    def _save_rules(self):
        import json
        rules_file = Path(settings.data_dir) / "config" / "security_rules.json"
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        with open(rules_file, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in self._custom_rules], f, ensure_ascii=False, indent=2)

    def _log_event(self, event: SecurityEvent):
        self._events.append(event)
        if len(self._events) > 1000:
            self._events = self._events[-500:]

    # ── 统一检查接口 ─────────────────────────────

    def check_tool_call(self, tool_name: str, command: str = "",
                       args: Dict[str, Any] = None) -> SecurityEvent:
        """检查工具调用安全性"""
        # 1. 命令检查
        if command:
            event = self.tool_guard.check_command(command, tool_name)
            if event.blocked:
                self._log_event(event)
                return event

        # 2. 参数检查
        if args:
            event = self.tool_guard.check_tool_args(tool_name, args)
            if event.blocked:
                self._log_event(event)
                return event

        # 3. 自定义规则
        for rule in self._custom_rules:
            if rule.enabled and rule.guard_type == "tool":
                if rule.pattern and re.search(rule.pattern, command or ""):
                    event = SecurityEvent(
                        guard_type="tool",
                        source=tool_name,
                        threat_level=rule.threat_level,
                        action=rule.action,
                        description=f"Custom rule '{rule.name}' triggered",
                        blocked=rule.action == ActionType.block,
                    )
                    self._log_event(event)
                    return event

        event = SecurityEvent(guard_type="tool", source=tool_name,
                            threat_level=ThreatLevel.safe, action=ActionType.allow)
        self._log_event(event)
        return event

    def check_file_access(self, file_path: str, operation: str = "read") -> SecurityEvent:
        """检查文件访问安全性"""
        event = self.file_guard.check_access(file_path, operation)
        self._log_event(event)
        return event

    def scan_skill(self, skill_content: str, skill_name: str = "") -> SecurityEvent:
        """扫描Skill安全性"""
        event = self.skill_scanner.scan_skill(skill_content, skill_name)
        self._log_event(event)
        return event

    # ── 规则管理 ────────────────────────────────

    def add_rule(self, rule: Dict[str, Any]) -> Dict:
        """添加自定义防护规则"""
        gr = GuardRule(**{k: v for k, v in rule.items() if k in GuardRule.__dataclass_fields__})
        self._custom_rules.append(gr)
        self._save_rules()
        return gr.to_dict()

    def remove_rule(self, rule_id: str) -> bool:
        """删除防护规则"""
        before = len(self._custom_rules)
        self._custom_rules = [r for r in self._custom_rules if r.id != rule_id]
        if len(self._custom_rules) < before:
            self._save_rules()
            return True
        return False

    def list_rules(self) -> List[Dict]:
        """列出所有防护规则"""
        return [r.to_dict() for r in self._custom_rules]

    # ── 统计 ────────────────────────────────────

    def get_events(self, guard_type: str = None, threat_level: str = None,
                   limit: int = 100) -> List[Dict]:
        events = self._events
        if guard_type:
            events = [e for e in events if e.guard_type == guard_type]
        if threat_level:
            events = [e for e in events if e.threat_level.value == threat_level]
        return [e.to_dict() for e in events[-limit:]]

    def get_stats(self) -> Dict:
        """安全统计"""
        total = len(self._events)
        blocked = sum(1 for e in self._events if e.blocked)
        by_type = defaultdict(int)
        by_level = defaultdict(int)
        for e in self._events:
            by_type[e.guard_type] += 1
            by_level[e.threat_level.value] += 1
        return {
            "total_events": total,
            "blocked": blocked,
            "by_guard_type": dict(by_type),
            "by_threat_level": dict(by_level),
            "custom_rules": len(self._custom_rules),
            "rate_limits": self.tool_guard.get_rate_limit_status(),
        }


# ── 单例 ──────────────────────────────────────────

_security_sandbox: Optional[SecuritySandbox] = None


def get_security_sandbox() -> SecuritySandbox:
    global _security_sandbox
    if _security_sandbox is None:
        _security_sandbox = SecuritySandbox()
    return _security_sandbox
