# src/server_new/mediagent/controller/test_tm_router.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/_test_tm", tags=["_test_tm"])

def _get_tm_from_request(request: Request):
    tm = getattr(request.app.state.services, "tm", None)
    if tm is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="TaskManager not ready")
    return tm

@router.get("/health")
async def health(request: Request):
    """
    验证：能否从 Request 拿到 tm，并调用 list_tools()
    """
    tm = _get_tm_from_request(request)
    try:
        tools = await tm.list_tools()
        return {"ok": True, "tool_count": len(tools)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"list_tools failed: {e!r}")

@router.get("/tools")
async def tools(request: Request, limit: int = 10):
    """
    返回部分工具名，验证 MCP 会话是否工作正常
    """
    tm = _get_tm_from_request(request)
    tools = await tm.list_tools()
    names = [t.get("name") for t in tools][:max(0, limit)]
    return {"count": len(tools), "preview": names}

class CreateTaskIn(BaseModel):
    user_uid: str = Field(..., min_length=1)
    steps: List[Dict[str, Any]] = Field(..., description="TaskManager 所需 steps，含 step_number 等字段")
    check_tools: bool = True

@router.post("/create")
async def create_task(payload: CreateTaskIn, request: Request):
    """
    直接通过 tm.create_task 创建任务，返回 task_uid
    """
    tm = _get_tm_from_request(request)
    try:
        created = await tm.create_task(
            user_uid=payload.user_uid,
            steps=payload.steps,
            check_tools=payload.check_tools,
        )
        return created
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"create_task failed: {e!r}")

@router.get("/status/{task_uid}")
async def task_status(task_uid: str, request: Request):
    """
    查询任务状态（只查状态，不拉日志）
    """
    tm = _get_tm_from_request(request)
    try:
        return await tm.get_task_status(task_uid)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"get_task_status failed: {e!r}")
