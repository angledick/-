"""
操作链 / 事件链 / 自然语言本地存储 API 路由。

提供 RESTful 接口供前端（或 UI 设计师）使用。
"""

from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import (
    ActionChainSchema,
    ActionChainSummary,
    EventChainSchema,
    EventCreateRequest,
    EventChainSummary,
    NLRecordSchema,
    NLRecordCreateRequest,
    NLRecordUpdateRequest,
    NLSearchResult,
    NLSummaryItem,
)
from app.core.action_chain import ActionChain
from app.core.event_chain import EventChain
from app.core.local_store import get_store

router = APIRouter(prefix="/api/v1", tags=["chains"])


# ════════════════════════════════════════════════════════════════
# 操作链 (ActionChain) API
# ════════════════════════════════════════════════════════════════

@router.get(
    "/chains/actions",
    response_model=list[ActionChainSummary],
    summary="操作链列表",
    description="列出最近的操作链摘要，按最后更新时间倒序。",
)
async def list_action_chains(max_count: int = Query(20, description="最大返回数")):
    """列出最近的操作链摘要。"""
    return ActionChain.list_chains(max_count=max_count)


@router.get(
    "/chains/actions/{chain_id}",
    response_model=ActionChainSchema,
    summary="获取操作链",
    description="获取指定操作链的完整内容，包含所有操作节点的详细数据。",
)
async def get_action_chain(chain_id: str):
    """获取指定操作链的完整内容。"""
    chain = ActionChain.load(chain_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"操作链 {chain_id} 不存在")
    return chain.to_dict()


@router.get(
    "/chains/actions/{chain_id}/trail",
    response_model=list[str],
    summary="操作链路",
    description="获取指定操作链的自然语言描述链（emoji前缀格式化），可直接用于前端展示。",
)
async def get_action_trail(chain_id: str):
    """获取指定操作链的自然语言描述链（用于直接展示）。"""
    chain = ActionChain.load(chain_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"操作链 {chain_id} 不存在")
    return chain.get_trail()


# ════════════════════════════════════════════════════════════════
# 事件链 (EventChain) API
# ════════════════════════════════════════════════════════════════

@router.get(
    "/chains/events",
    response_model=list[EventChainSummary],
    summary="事件链列表",
    description="列出最近的事件链摘要，按最后更新时间倒序。",
)
async def list_event_chains(max_count: int = Query(20, description="最大返回数")):
    """列出最近的事件链摘要。"""
    return EventChain.list_chains(max_count=max_count)


@router.get(
    "/chains/events/{chain_id}",
    response_model=EventChainSchema,
    summary="获取事件链",
    description="获取指定事件链的完整内容，包含所有事件节点的详细数据。",
)
async def get_event_chain(chain_id: str):
    """获取指定事件链的完整内容。"""
    chain = EventChain.load(chain_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"事件链 {chain_id} 不存在")
    return chain.to_dict()


@router.get(
    "/chains/events/{chain_id}/timeline",
    response_model=list[str],
    summary="事件时间线",
    description="获取指定事件链的自然语言时间线（emoji+严重度前缀），可直接用于前端展示。",
)
async def get_event_timeline(chain_id: str):
    """获取指定事件链的自然语言时间线（用于直接展示）。"""
    chain = EventChain.load(chain_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"事件链 {chain_id} 不存在")
    return chain.get_timeline()


@router.get(
    "/chains/events/{chain_id}/filter",
    summary="筛选事件",
    description="按条件筛选事件链中的事件，支持按来源、类型、严重度、标签过滤。",
)
async def filter_events(
    chain_id: str,
    source: str = Query(None, description="事件来源"),
    event_type: str = Query(None, description="事件类型"),
    severity: str = Query(None, description="严重度: low/medium/high/critical"),
    tags: str = Query(None, description="标签，逗号分隔"),
    max_count: int = Query(100, description="最大返回数"),
):
    """按条件筛选事件链中的事件。"""
    chain = EventChain.load(chain_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"事件链 {chain_id} 不存在")
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    return chain.filter(
        source=source,
        event_type=event_type,
        severity=severity,
        tags=tag_list,
        max_count=max_count,
    )


@router.post(
    "/chains/events",
    response_model=dict,
    summary="创建事件",
    description="向指定事件链追加一个新事件。如果事件链不存在则自动创建。",
)
async def create_event(req: EventCreateRequest):
    """向事件链追加一个新事件。"""
    chain = EventChain.load(req.chain_id)
    if not chain:
        chain = EventChain(chain_id=req.chain_id)
    event = chain.add_event(
        source=req.source,
        event_type=req.type,
        description_nl=req.description_nl,
        severity=req.severity,
        payload=req.payload,
        tags=req.tags,
    )
    chain.save()
    return event.to_dict()


# ════════════════════════════════════════════════════════════════
# 自然语言本地存储 (NLStore) API
# ════════════════════════════════════════════════════════════════

# 注意：/nl-store/search 必须定义在 /nl-store/{namespace} 之前
# 否则 "search" 会被 {namespace} 路径参数捕获

@router.get(
    "/nl-store/search",
    response_model=list[NLSearchResult],
    summary="全文搜索",
    description="全文搜索自然语言存储内容，匹配 title + content_nl + tags，按匹配分数倒序。",
)
async def search_nl(
    q: str = Query(..., description="搜索关键词"),
    namespace: str = Query(None, description="限定 namespace"),
    max_results: int = Query(20, description="最大结果数"),
):
    """全文搜索自然语言存储内容。"""
    store = get_store()
    return store.search(query=q, namespace=namespace, max_results=max_results)


@router.get(
    "/nl-store/{namespace}",
    response_model=list[NLSummaryItem],
    summary="列出Namespace",
    description="列出某个 namespace 下的所有记录摘要（key/title/tags/updated_at）。",
)
async def list_namespace(namespace: str):
    """列出某个 namespace 下的所有记录摘要。"""
    store = get_store()
    return store.list_namespace(namespace)


@router.get(
    "/nl-store/{namespace}/{key}",
    response_model=NLRecordSchema,
    summary="获取记录",
    description="获取指定 namespace/key 的记录完整内容。",
    responses={404: {"description": "记录不存在"}},
)
async def get_record(namespace: str, key: str):
    """获取指定记录。"""
    store = get_store()
    record = store.get(namespace, key)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"记录 {namespace}/{key} 不存在",
        )
    return record.to_dict()


@router.post(
    "/nl-store/{namespace}",
    response_model=NLRecordSchema,
    summary="创建记录",
    description="在指定 namespace 下创建或更新一条自然语言记录（key 已存在则更新）。",
)
async def create_record(namespace: str, req: NLRecordCreateRequest):
    """创建或更新一条自然语言记录。"""
    store = get_store()
    record = store.put(
        namespace=namespace,
        key=req.key,
        title=req.title,
        content_nl=req.content_nl,
        metadata=req.metadata,
        tags=req.tags,
    )
    return record.to_dict()


@router.put(
    "/nl-store/{namespace}/{key}",
    response_model=NLRecordSchema,
    summary="更新记录",
    description="更新指定记录的部分字段（仅传入的字段被更新）。",
    responses={404: {"description": "记录不存在"}},
)
async def update_record(namespace: str, key: str, req: NLRecordUpdateRequest):
    """更新指定记录的部分字段。"""
    store = get_store()
    record = store.get(namespace, key)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"记录 {namespace}/{key} 不存在",
        )
    updates = {}
    for field in ("title", "content_nl", "metadata", "tags"):
        value = getattr(req, field, None)
        if value is not None:
            updates[field] = value
    record.update(**updates)
    store._save_namespace(namespace)
    return record.to_dict()


@router.delete(
    "/nl-store/{namespace}/{key}",
    summary="删除记录",
    description="删除指定记录。",
    responses={
        200: {"description": "删除成功"},
        404: {"description": "记录不存在"},
    },
)
async def delete_record(namespace: str, key: str):
    """删除指定记录。"""
    store = get_store()
    success = store.delete(namespace, key)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"记录 {namespace}/{key} 不存在",
        )
    return {"status": "deleted", "namespace": namespace, "key": key}
