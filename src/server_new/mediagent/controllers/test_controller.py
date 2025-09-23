# src/server_new/mediagent/controller/test_tm_router.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/_test_tm", tags=["_test_tm"])

def _get_tm_from_request(request: Request):
    tm = getattr(request.app.state.services, "tm", None)
    if tm is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="TaskManager not ready")
    return tm

def _get_settings_from_request(request: Request):
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Settings not attached to app.state")
    return settings

def _path_info(p: Any) -> Dict[str, Any]:
    try:
        path = Path(p)
        return {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
        }
    except Exception:
        return {"path": str(p), "exists": False, "is_file": False, "is_dir": False}

def _mask_secret(s: Optional[str], keep_start: int = 4, keep_end: int = 2) -> Optional[str]:
    if not s:
        return s
    if len(s) <= keep_start + keep_end:
        return "*" * len(s)
    return f"{s[:keep_start]}...{s[-keep_end:]}"

@router.get("/health")
async def health(request: Request):
    """
    验证：能否从 Request 拿到 tm，并调用 list_tools()；
    同时返回 settings 中关键参数与路径的健康状况（不暴露敏感明文）。
    """
    tm = _get_tm_from_request(request)
    settings = _get_settings_from_request(request)

    # 工具数（MCP 会话连通性）
    tool_count: Optional[int] = None
    tool_names_preview: List[str] = []
    try:
        tools = await tm.list_tools()
        tool_count = len(tools)
        tool_names_preview = [t.get("name") for t in tools][:10]
    except Exception as e:
        # 不因工具列表失败而让健康检查 500，标注错误信息即可
        tool_count = None
        tool_names_preview = []
        tools_error = repr(e)
    else:
        tools_error = None

    # 组织 settings 健康信息
    resp = {
        "ok": tools_error is None,
        "task_manager": {
            "available": True,
            "tool_count": tool_count,
            "tools_error": tools_error,
            "tools_preview": tool_names_preview,
        },
        "settings": {
            # 环境/模型相关（API Key 打码）
            "MODEL_URL": getattr(settings, "MODEL_URL", None),
            "MODEL": getattr(settings, "MODEL", None),
            "MODEL_API_KEY_masked": _mask_secret(getattr(settings, "MODEL_API_KEY", None)),
            # 路径相关（检测存在性）
            "paths": {
                "data_dir": _path_info(getattr(settings, "data_dir", None)),
                "PUBLIC_DATASETS_ROOT": _path_info(getattr(settings, "PUBLIC_DATASETS_ROOT", None)),
                "WORKSPACE_ROOT": _path_info(getattr(settings, "WORKSPACE_ROOT", None)),
                "DATABASE_FILE": _path_info(getattr(settings, "DATABASE_FILE", None)),
                "MCPSERVER_FILE": _path_info(getattr(settings, "MCPSERVER_FILE", None)),
            },
        },
    }
    return resp

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
