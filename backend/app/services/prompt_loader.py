"""Prompt 模板加载器 — 所有 prompt 从 YAML 文件读取。

设计目标：
- 所有 Agent 任务指令和 SDK 调用 prompt 均从 YAML 文件读取，不硬编码
- 支持热加载（reload_all），prompt 微调后无需重启
- 支持简单变量渲染（后续可升级为 Jinja2）
- 全局缓存避免重复 I/O
"""

import yaml
from pathlib import Path
from typing import Any
from app.config import settings

_CACHE: dict[str, dict] = {}


def _get_prompt_dir() -> Path:
    """获取 prompt 模板目录绝对路径。"""
    return Path(settings.data_dir).resolve() / "prompts"


def load_prompt(name: str) -> dict[str, Any]:
    """加载 prompt 模板文件（带缓存）。

    Args:
        name: 模板名（不含 .yaml 后缀）

    Returns:
        dict: YAML 解析后的模板内容

    Raises:
        FileNotFoundError: 模板文件不存在
    """
    if name in _CACHE:
        return _CACHE[name]
    path = _get_prompt_dir() / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {path} "
            f"(data_dir={settings.data_dir})"
        )
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    _CACHE[name] = data
    return data


def reload_all():
    """热加载所有 prompt（用于微调后刷新缓存）。"""
    _CACHE.clear()


def render_prompt(name: str, **kwargs) -> str:
    """加载并渲染 prompt 模板。

    当前用简单 {{var}} 替换，后续可升级为 Jinja2。

    Args:
        name: 模板名
        **kwargs: 模板变量（{{var}} 会被替换）

    Returns:
        str: 渲染后的 system_prompt 字符串
    """
    template = load_prompt(name)
    prompt = template.get("system_prompt", "")
    for key, val in kwargs.items():
        prompt = prompt.replace("{{" + key + "}}", str(val))
    return prompt


def list_prompts() -> list[str]:
    """列出所有可用 prompt 模板名。"""
    prompt_dir = _get_prompt_dir()
    if not prompt_dir.exists():
        return []
    return [p.stem for p in prompt_dir.glob("*.yaml")]
