"""
Tools CRUD API — 前端ToolPanel操作的后端支持。

端点:
  GET    /api/v1/tools              — Tools列表
  POST   /api/v1/tools              — 创建Tool
  GET    /api/v1/tools/{tool_id}    — Tool详情
  PUT    /api/v1/tools/{tool_id}    — 更新Tool
  DELETE /api/v1/tools/{tool_id}    — 删除Tool
  PUT    /api/v1/tools/{tool_id}/toggle — 启用/禁用Tool

参考: 路线图§6.9.2 Tools CRUD API
"""

import json
import uuid
import yaml
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.config import settings

DATA_DIR = Path(settings.data_dir)
TOOLS_FILE = DATA_DIR / "tools" / "tools.json"
TOOLS_YAML = Path(settings.data_dir) / "tools" / "_registry.yaml"
TOOLS_IMPL_DIR = DATA_DIR / "tools" / "impl"

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


# ── 请求模型 ──────────────────────────────────

class ToolCreate(BaseModel):
    name: str
    description: str = ""
    tool_type: str = "custom"       # builtin/custom/script/skill_wrapper
    category: str = "general"       # compliance/logistics/certification/general
    config: Dict[str, Any] = {}
    script_args: List[str] = []     # script 类型的命令行参数模板
    enabled: bool = True


class ToolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


# ── 辅助函数 ──────────────────────────────────

def _load_tools() -> List[Dict[str, Any]]:
    """加载Tools列表。配置文件必须存在且正确。"""
    if not TOOLS_FILE.exists():
        # 尝试从 _registry.yaml 初始化
        return _init_default_tools()
    data = json.loads(TOOLS_FILE.read_text(encoding="utf-8"))
    return data.get("tools", [])


def _save_tools(tools: List[Dict[str, Any]]):
    """保存Tools列表"""
    TOOLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOOLS_FILE.write_text(
        json.dumps({"tools": tools}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _init_default_tools() -> List[Dict[str, Any]]:
    """从 data/tools/_registry.yaml 初始化 Tools。配置文件必须存在。"""
    if not TOOLS_YAML.exists():
        raise FileNotFoundError(
            f"Tools注册配置不存在: {TOOLS_YAML}\n"
            "请确保 data/tools/_registry.yaml 已创建"
        )
    import yaml
    with open(TOOLS_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    defaults = data.get("tools", [])
    if not defaults:
        raise ValueError(f"Tools注册配置为空: {TOOLS_YAML}")

    _save_tools(defaults)
    return defaults


# ── 端点 ──────────────────────────────────

@router.get("", summary="Tools列表")
async def list_tools(
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
):
    """获取Tools列表"""
    tools = _load_tools()

    if category:
        tools = [t for t in tools if t.get("category") == category]
    if enabled is not None:
        tools = [t for t in tools if t.get("enabled") == enabled]

    return {"tools": tools, "total": len(tools)}


@router.post("", summary="创建Tool")
async def create_tool(req: ToolCreate):
    """创建新Tool。

    当 tool_type == 'script' 时，自动在 data/tools/impl/ 下生成脚手架脚本，
    并同步到 _registry.yaml。Agent 可通过 python 命令传参运行该脚本。
    """
    tools = _load_tools()

    tool_id = f"tool_{uuid.uuid4().hex[:8]}"
    tool = {
        "id": tool_id,
        "name": req.name,
        "description": req.description,
        "tool_type": req.tool_type,
        "category": req.category,
        "config": req.config,
        "enabled": req.enabled,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # script 类型: 生成实现脚本 + 同步 _registry.yaml
    if req.tool_type == "script":
        script_filename = _generate_impl_script(tool_id, req)
        tool["script"] = f"impl/{script_filename}"
        tool["script_args"] = req.script_args or ["--input", "{input}"]
        _sync_to_registry_yaml(tool)

    tools.append(tool)
    _save_tools(tools)

    return tool


@router.get("/{tool_id}", summary="Tool详情")
async def get_tool(tool_id: str):
    """获取Tool详情"""
    tools = _load_tools()
    for t in tools:
        if t["id"] == tool_id:
            return t
    raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")


@router.put("/{tool_id}", summary="更新Tool")
async def update_tool(tool_id: str, req: ToolUpdate):
    """更新Tool"""
    tools = _load_tools()

    for i, t in enumerate(tools):
        if t["id"] == tool_id:
            if req.name is not None:
                tools[i]["name"] = req.name
            if req.description is not None:
                tools[i]["description"] = req.description
            if req.category is not None:
                tools[i]["category"] = req.category
            if req.config is not None:
                tools[i]["config"] = {**tools[i].get("config", {}), **req.config}
            if req.enabled is not None:
                tools[i]["enabled"] = req.enabled
            tools[i]["updated_at"] = datetime.now(timezone.utc).isoformat()

            _save_tools(tools)
            return tools[i]

    raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")


@router.delete("/{tool_id}", summary="删除Tool")
async def delete_tool(tool_id: str):
    """删除Tool"""
    tools = _load_tools()
    original = len(tools)
    tools = [t for t in tools if t["id"] != tool_id]

    if len(tools) == original:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    _save_tools(tools)
    return {"deleted": tool_id}


@router.put("/{tool_id}/toggle", summary="启用/禁用Tool")
async def toggle_tool(tool_id: str):
    """切换Tool启用/禁用状态"""
    tools = _load_tools()

    for i, t in enumerate(tools):
        if t["id"] == tool_id:
            tools[i]["enabled"] = not tools[i].get("enabled", True)
            tools[i]["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_tools(tools)
            return {
                "id": tool_id,
                "enabled": tools[i]["enabled"],
                "name": tools[i]["name"],
            }

    raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")


# ── Script 工具实现生成 ──────────────────────────────────

def _generate_impl_script(tool_id: str, req: ToolCreate) -> str:
    """为 script 类型工具生成脚手架 Python 脚本到 data/tools/impl/。

    返回生成的脚本文件名。
    """
    TOOLS_IMPL_DIR.mkdir(parents=True, exist_ok=True)

    # 使用 tool name 生成安全文件名
    safe_name = req.name.lower().replace(" ", "_").replace("-", "_")
    safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
    script_filename = f"{safe_name}.py"
    script_path = TOOLS_IMPL_DIR / script_filename

    # 如果文件已存在不覆盖
    if script_path.exists():
        return script_filename

    # 生成脚手架脚本
    scaffold = f'''#!/usr/bin/env python3
"""{req.name} — 自定义工具脚本。

{req.description or "用户自定义工具实现。"}

Agent 可通过 Python 命令传参运行:
  python data/tools/impl/{script_filename} --input "参数内容"

也可通过 JSON stdin 传参:
  echo '{{\'input\': \'内容\'}}' | python data/tools/impl/{script_filename} --stdin

输出: JSON 格式结果到 stdout
"""

import argparse
import json
import sys


def run(input_data: str, **kwargs) -> dict:
    """工具主逻辑。

    Args:
        input_data: 输入数据
        **kwargs: 其他参数

    Returns:
        dict: 执行结果
    """
    # TODO: 实现工具逻辑
    return {{
        "status": "success",
        "tool_id": "{tool_id}",
        "result": f"处理完成: {{input_data}}",
    }}


def main():
    parser = argparse.ArgumentParser(description="{req.name}")
    parser.add_argument("--input", "-i", type=str, help="输入数据")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON 输入")
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")
    args = parser.parse_args()

    if args.stdin:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({{{"error": "stdin 为空"}}}))
            sys.exit(1)
        params = json.loads(raw)
        input_data = params.get("input", "")
    elif args.input:
        input_data = args.input
    else:
        print(json.dumps({{{"error": "请提供 --input 或 --stdin 参数"}}}))
        sys.exit(1)

    result = run(input_data)
    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()
'''
    script_path.write_text(scaffold, encoding="utf-8")
    return script_filename


def _sync_to_registry_yaml(tool: Dict[str, Any]):
    """将新创建的 script 工具同步到 data/tools/_registry.yaml。"""
    TOOLS_YAML.parent.mkdir(parents=True, exist_ok=True)

    data = {"tools": []}
    if TOOLS_YAML.exists():
        raw = yaml.safe_load(TOOLS_YAML.read_text(encoding="utf-8"))
        if raw and isinstance(raw, dict):
            data = raw

    # 检查是否已存在
    existing_ids = {t.get("id") for t in data.get("tools", [])}
    if tool["id"] in existing_ids:
        return

    entry = {
        "id": tool["id"],
        "name": tool["name"],
        "description": tool.get("description", ""),
        "tool_type": "script",
        "category": tool.get("category", "general"),
        "script": tool.get("script", ""),
        "script_args": tool.get("script_args", []),
        "config": tool.get("config", {}),
        "enabled": tool.get("enabled", True),
    }
    data["tools"].append(entry)

    TOOLS_YAML.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
