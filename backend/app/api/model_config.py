"""
模型配置 API — 多模型路由管理

端点:
  GET    /api/v1/model-configs              — 所有模型路由配置
  GET    /api/v1/model-configs/active        — 获取当前激活的全部路由
  POST   /api/v1/model-configs               — 创建/更新单条路由
  PUT    /api/v1/model-configs/{role}        — 更新指定角色路由
  DELETE /api/v1/model-configs/{role}        — 删除指定角色路由
  POST   /api/v1/model-configs/{role}/activate — 激活指定路由（切换默认）
  GET    /api/v1/model-configs/usage          — Token使用统计
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.core.model_router import get_model_router
from app.models.schemas import ModelConfig

router = APIRouter(prefix="/api/v1/model-configs", tags=["model-config"])


class ModelConfigRequest(BaseModel):
    """创建/更新模型路由请求"""
    role: str
    provider: str
    model: str
    api_key_env: str = ""
    base_url: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9


class ModelConfigResponse(BaseModel):
    """模型路由响应（API Key环境变量名显示）"""
    role: str
    provider: str
    model: str
    api_key_env: str
    base_url: str = ""
    max_tokens: int
    temperature: float
    top_p: float = 0.9


@router.get("", summary="所有模型路由配置")
async def list_model_configs():
    """获取所有模型路由配置（API Key环境变量名显示，不含实际key）"""
    router = get_model_router()
    routes = router.get_all_routes()
    return {
        "configs": [
            ModelConfigResponse(
                role=role,
                provider=cfg.provider,
                model=cfg.model,
                api_key_env=cfg.api_key_env,
                base_url=cfg.base_url,
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
                top_p=cfg.top_p,
            )
            for role, cfg in routes.items()
        ]
    }


@router.post("", summary="创建/更新模型路由")
async def create_model_config(req: ModelConfigRequest):
    """创建或更新模型路由配置"""
    model_router = get_model_router()
    config = ModelConfig(
        role=req.role,
        provider=req.provider,
        model=req.model,
        api_key_env=req.api_key_env,
        base_url=req.base_url,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
    )
    await model_router.update_route(req.role, config)
    return {"ok": True, "role": req.role}


@router.put("/{role}", summary="更新指定角色路由")
async def update_model_config(role: str, req: ModelConfigRequest):
    """更新指定角色的模型路由"""
    model_router = get_model_router()
    config = ModelConfig(
        role=req.role,
        provider=req.provider,
        model=req.model,
        api_key_env=req.api_key_env,
        base_url=req.base_url,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
    )
    await model_router.update_route(role, config)
    return {"ok": True, "role": role}


@router.delete("/{role}", summary="删除指定角色路由")
async def delete_model_config(role: str):
    """删除指定角色的模型路由"""
    model_router = get_model_router()
    # 不允许删除最后一个路由
    routes = model_router.get_all_routes()
    if role not in routes:
        raise HTTPException(status_code=404, detail=f"路由 {role} 不存在")
    if len(routes) <= 1:
        raise HTTPException(status_code=400, detail="不能删除最后一个路由")
    await model_router.remove_route(role)
    return {"ok": True, "role": role}


@router.get("/usage", summary="Token使用统计")
async def get_usage_stats():
    """获取Token使用统计"""
    model_router = get_model_router()
    return model_router.get_usage_stats()
