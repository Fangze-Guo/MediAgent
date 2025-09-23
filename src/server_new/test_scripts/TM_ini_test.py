# TM_tools_descriptions_test.py
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from textwrap import indent

from mediagent.paths import in_data, in_mediagent

# ======== 需要你自己填写/确认的变量（建议保持与你现有脚本一致）========
PUBLIC_DATASETS_ROOT = in_data("files", "public")
WORKSPACE_ROOT       = in_data("files", "private")
DATABASE_FILE        = in_data("db", "app.sqlite3")   # 必须已存在
MCPSERVER_FILE       = in_mediagent("mcp_server_tools", "mcp_server.py")  # 必须已存在

# ======== 导入 AsyncTaskManager（按你的工程结构修改）========
try:
    from mediagent.modules.task_manager import AsyncTaskManager
except Exception as e:
    print("[FATAL] 无法导入 AsyncTaskManager，请检查模块路径。")
    print("示例：from mediagent.task_manager import AsyncTaskManager")
    print("错误信息：", e)
    sys.exit(1)


def _check_path(label: str, p: str | Path) -> Path:
    path = Path(p).expanduser().resolve()
    print(f"[check] {label}: {path}")
    return path


def _has_schema_fields(tools: list[dict]) -> bool:
    """是否包含我们不想给 LLM 的 schema 字段。"""
    if not isinstance(tools, list):
        return False
    keys = {"inputSchema", "planningInputSchema", "runtimeInputSchema"}
    return any(isinstance(t, dict) and any(k in t for k in keys) for t in tools)


def _missing_descriptions(tools: list[dict]) -> bool:
    """是否存在缺少 description 的项。"""
    if not isinstance(tools, list):
        return True
    return any(isinstance(t, dict) and not (t.get("description") or "").strip() for t in tools)


def _brief(text: str, max_lines: int = 12) -> str:
    """把长描述做行数限制的预览（完整描述仍然会在下方提供展开提示）。"""
    if not text:
        return ""
    lines = text.strip().splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    preview = "\n".join(lines[:max_lines])
    more = len(lines) - max_lines
    return f"{preview}\n…（以下省略 {more} 行，可在 mcp_server.py 中查看完整描述）"


async def _fetch_tools_via_tm(tm: AsyncTaskManager) -> list[dict]:
    """使用 TaskManager 的 list_tools（理想路径：透传 list_job_tools 的结果）"""
    try:
        tools = await tm.list_tools()
        if isinstance(tools, dict) and "tools" in tools:
            tools = tools["tools"]
        if not isinstance(tools, list):
            raise TypeError("tm.list_tools() 返回的不是 list/可迭代工具项")
        return tools
    except Exception as e:
        print("[warn] tm.list_tools() 调用失败：", repr(e))
        return []


async def _fetch_tools_via_mcp(tm: AsyncTaskManager) -> list[dict]:
    """直接调用 MCP 的 list_job_tools（兜底路径）"""
    try:
        # 优先使用 tm.mcp.call_tool
        if hasattr(tm, "mcp") and hasattr(tm.mcp, "call_tool"):
            resp = await tm.mcp.call_tool("list_job_tools", args={})
        # 次选：某些封装可能提供 call_mcp_tool
        elif hasattr(tm, "call_mcp_tool"):
            resp = await tm.call_mcp_tool("list_job_tools", args={})
        else:
            print("[warn] 未找到 tm.mcp.call_tool 或 tm.call_mcp_tool，无法直接调用 MCP。")
            return []
        tools = resp.get("tools", [])
        if not isinstance(tools, list):
            print("[warn] MCP list_job_tools 返回格式异常：", resp)
            return []
        return tools
    except Exception as e:
        print("[warn] 直接调用 MCP list_job_tools 失败：", repr(e))
        return []


def _normalize_tools(tools: list[dict]) -> list[dict]:
    """只保留 {name, description}，并确保为字符串。"""
    out: list[dict] = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        name = str(t.get("name", "")).strip()
        desc = str(t.get("description", "")).strip()
        if not name:
            continue
        out.append({"name": name, "description": desc})
    return out


def _print_tools(tools: list[dict], preview_lines: int = 12) -> None:
    print(f"\n[tools] 共 {len(tools)} 个工具（仅展示 name/description）：")
    for i, t in enumerate(tools, 1):
        print(f"\n  --- Tool #{i} ---")
        print(f"  name: {t['name']}")
        desc = t.get("description", "")
        if not desc:
            print("  description: （缺失）")
            continue
        brief = _brief(desc, max_lines=preview_lines)
        print("  description:")
        print(indent(brief, "    "))


async def main():
    # —— 基础路径校验 ——
    if not DATABASE_FILE or not Path(DATABASE_FILE).exists():
        print("[FATAL] 请正确填写 DATABASE_FILE（必须已存在的 sqlite 文件）。")
        return
    if not MCPSERVER_FILE or not Path(MCPSERVER_FILE).exists():
        print("[FATAL] 请正确填写 MCPSERVER_FILE（必须已存在的 mcp 服务器脚本）。")
        return

    pub_root = _check_path("public_datasets_source_root", PUBLIC_DATASETS_ROOT) if PUBLIC_DATASETS_ROOT else None
    ws_root  = _check_path("workspace_root", WORKSPACE_ROOT) if WORKSPACE_ROOT else None
    db_path  = _check_path("database_file", DATABASE_FILE)
    mcp_path = _check_path("mcpserver_file", MCPSERVER_FILE)

    print("\n[step] 初始化 AsyncTaskManager …\n")

    tm: AsyncTaskManager | None = None
    try:
        tm = AsyncTaskManager(
            public_datasets_source_root=pub_root or ".",
            workspace_root=ws_root or ".",
            database_file=db_path,
            mcpserver_file=mcp_path,
        )
        await tm.astart()
        print("[ok] AsyncTaskManager 启动成功。")

        # 1) 先用 TM 的 list_tools()
        tools_tm = await _fetch_tools_via_tm(tm)

        # 2) 判定是否需要兜底（若含 schema 或描述缺失，则尝试直接从 MCP 获取）
        need_fallback = _has_schema_fields(tools_tm) or _missing_descriptions(tools_tm)
        if need_fallback:
            print("\n[info] 检测到 list_tools() 返回包含 schema 或描述缺失，尝试直接调用 MCP 的 list_job_tools…")
            tools_mcp = await _fetch_tools_via_mcp(tm)
            if tools_mcp:
                tools = tools_mcp
                print("[info] 已改用 MCP list_job_tools 的结果。")
            else:
                tools = tools_tm
                print("[warn] MCP list_job_tools 兜底失败，仍沿用 tm.list_tools() 的结果。")
        else:
            tools = tools_tm

        # 3) 规范化并打印
        tools_norm = _normalize_tools(tools)
        if not tools_norm:
            print("\n[warn] 未获取到任何工具（name/description）。请确认：")
            print("  - mcp_server.py 中是否定义了 @server.tool() 的 list_job_tools 并返回 {'tools': [...]}；")
            print("  - AsyncTaskManager.list_tools() 是否直接透传了该结果；")
        else:
            _print_tools(tools_norm, preview_lines=14)

        # 4) 额外健康检查（可选）
        try:
            # 简单 DB 探测
            def _peek_tables():
                cur = tm.sync.db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 10;")
                return [r[0] for r in cur.fetchall()]
            tables = await asyncio.to_thread(_peek_tables)
            print(f"\n[check] 数据库连接正常，示例表：{tables or '（未发现表，可忽略）'}")
        except Exception as e:
            print("\n[warn] 数据库简单查询失败，但连接已建立。错误：", repr(e))

        # 任务队列状态
        try:
            def _peek_runtime():
                return tm.sync.task_queue.empty(), tm.sync.task_running
            is_empty, running = await asyncio.to_thread(_peek_runtime)
            print(f"[check] task_queue 为空：{is_empty}")
            print(f"[check] task_running = {running}")
        except Exception as e:
            print("\n[warn] 读取运行状态失败：", repr(e))

        print("\n[RESULT] 工具描述拉取与展示完成（无 schema，面向 LLM 的完整说明）。")

    except Exception as e:
        print("\n[ERROR] 初始化失败：", repr(e))
    finally:
        if tm is not None:
            try:
                await tm.aclose()
                print("[cleanup] 资源释放完成。")
            except Exception as e:
                print("[cleanup-warn] 释放资源时出错：", repr(e))


if __name__ == "__main__":
    asyncio.run(main())
