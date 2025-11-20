# task_manager.py —— 常驻会话版本（仅支持新风格 steps：step_number + tool_name + args）
from __future__ import annotations
import sys
import sqlite3
import asyncio
import json
import time
import threading
import uuid
import traceback
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Dict, List, Optional, Tuple, Set, Union

from src.server_new.mediagent.paths import in_data

# ===================== 日志配置（可修改） =====================
LOG_ENABLED: bool = True  # 是否开启日志输出到文件
LOG_DIR: Path = in_data("TM_logs")  # 日志文件存放目录

# 需要：pip install "mcp>=1.13.0"
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ===== MCP 交互的统一超时/重试策略 =====
MCP_DEFAULT_TIMEOUT_SEC: float = 10.0   # 单次调用超时
MCP_DEFAULT_RETRIES: int = 5           # 最大重试次数（含最后一次）
MCP_BACKOFF_BASE_SEC: float = 0.5      # 退避起始秒数，指数退避：base * (2 ** (attempt-1))


# ============================ 轻量日志工具 ============================
_log_lock = threading.RLock()
_log_file_path: Optional[Path] = None


def _init_log_file_once() -> None:
    global _log_file_path
    if not LOG_ENABLED:
        return
    with _log_lock:
        if _log_file_path is not None:
            return
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        try:
            import os as _os
            pid = str(_os.getpid())
        except Exception:
            pid = "na"
        fname = f"task_manager_{ts}_pid{pid}.log"
        _log_file_path = (LOG_DIR / fname).resolve()
        try:
            with open(_log_file_path, "a", encoding="utf-8") as f:
                f.write(f"{_now()} | main | INFO  | LOG | log file created: {_log_file_path}\n")
        except Exception:
            pass


def _now() -> str:
    t = time.time()
    lt = time.localtime(t)
    ms = int((t - int(t)) * 1000)
    return time.strftime("%Y-%m-%d %H:%M:%S", lt) + f".{ms:03d}"


def _w(level: str, tag: str, msg: str) -> None:
    if not LOG_ENABLED:
        return
    _init_log_file_once()
    try:
        name = threading.current_thread().name
        line = f"{_now()} | {name} | {level:<5} | {tag} | {msg}\n"
        with _log_lock:
            if _log_file_path is not None:
                with open(_log_file_path, "a", encoding="utf-8") as f:
                    f.write(line)
    except Exception:
        pass


def log_info(tag: str, msg: str) -> None:
    _w("INFO", tag, msg)


def log_warn(tag: str, msg: str) -> None:
    _w("WARN", tag, msg)


def log_error(tag: str, msg: str) -> None:
    _w("ERROR", tag, msg)


def log_debug(tag: str, msg: str) -> None:
    _w("DEBUG", tag, msg)


def log_exception(tag: str, prefix: str, exc: BaseException) -> None:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    _w("ERROR", tag, f"{prefix}; EXC={exc!r}\n{tb}".rstrip())


def _schema_to_json(schema_obj: Any) -> Optional[Dict[str, Any]]:
    if schema_obj is None:
        return None
    if isinstance(schema_obj, dict):
        return schema_obj
    if hasattr(schema_obj, "model_dump"):
        try:
            return schema_obj.model_dump(mode="json")
        except TypeError:
            return schema_obj.model_dump()
    try:
        return dict(schema_obj)  # type: ignore[arg-type]
    except Exception:
        return None


# ========================= 常驻执行器 =========================
class MCPExecutor:
    """
    在独立线程中维护一个事件循环和 MCP stdio 会话（常驻）。
    为所有对 MCP 的直接调用提供“超时 + 重试”的同步方法包装：
      - list_tools(timeout=None, retries=None)
      - list_job_tools_meta(timeout=None, retries=None)
      - call_tool(name, args, timeout=None, retries=None)
    以上参数缺省时使用全局默认（见常量）。
    """

    def __init__(self, server_path: Path) -> None:
        self._server_path = Path(server_path).expanduser().resolve()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready_evt = threading.Event()
        self._stop_evt: Optional[asyncio.Event] = None
        self._session: Optional[ClientSession] = None
        self._client_cm = None
        self._error: Optional[BaseException] = None
        log_info("MCP", f"Executor init with server={self._server_path}")

    # ---------- 对外生命周期 ----------
    def start(self, timeout: float = 15.0) -> None:
        log_info("MCP", "Executor start() called")
        if not self._server_path.exists():
            log_error("MCP", f"server file not found: {self._server_path}")
            raise FileNotFoundError(f"MCP 服务器文件不存在：{self._server_path}")
        self._thread = threading.Thread(target=self._thread_main, name="mcp-executor", daemon=True)
        self._thread.start()
        ok = self._ready_evt.wait(timeout=timeout)
        if not ok:
            log_error("MCP", "Executor start timeout waiting for ready_evt")
            raise TimeoutError("MCP 执行线程启动超时")
        if self._error:
            err = self._error
            self._error = None
            log_exception("MCP", "Executor startup encountered error (bubble up)", err)
            raise err
        log_info("MCP", "Executor started and ready")

    def close(self, timeout: float = 10.0) -> None:
        log_info("MCP", "Executor close() called")
        loop = self._loop
        if loop is None:
            log_info("MCP", "Executor close(): loop is None, return")
            return

        def _signal_stop():
            if self._stop_evt is not None:
                self._stop_evt.set()

        loop.call_soon_threadsafe(_signal_stop)
        loop.call_soon_threadsafe(loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        self._loop = None
        log_info("MCP", "Executor closed")

    # ---------- 线程安全同步方法（带超时+重试） ----------
    def list_tools(self, *, timeout: Optional[float] = None, retries: Optional[int] = None) -> List[Dict[str, Any]]:
        timeout = timeout or MCP_DEFAULT_TIMEOUT_SEC
        retries = retries if retries is not None else MCP_DEFAULT_RETRIES
        loop = self._loop
        if loop is None or self._session is None:
            log_error("MCP", "list_tools(): loop/session not ready")
            raise RuntimeError("MCP 执行器未就绪")

        attempt = 0
        while True:
            attempt += 1
            fut = asyncio.run_coroutine_threadsafe(self._coro_list_tools(), loop)
            try:
                tools = fut.result(timeout=timeout)
                log_info("MCP", f"list_tools(): got {len(tools)} tools")
                return tools
            except Exception as e:
                fut.cancel()
                log_warn("MCP", f"list_tools(): attempt#{attempt} failed ({type(e).__name__}: {e})")
                if attempt >= retries:
                    log_exception("MCP", "list_tools(): exhausted retries", e)
                    raise
                time.sleep(MCP_BACKOFF_BASE_SEC * (2 ** (attempt - 1)))

    def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> Any:
        timeout = timeout or MCP_DEFAULT_TIMEOUT_SEC
        retries = retries if retries is not None else MCP_DEFAULT_RETRIES
        loop = self._loop
        if loop is None or self._session is None:
            log_error("MCP", f"call_tool({tool_name}): loop/session not ready")
            raise RuntimeError("MCP 执行器未就绪")

        log_info("MCP", f"call_tool(): name={tool_name}, args_keys={list(arguments.keys())}")
        attempt = 0
        last_err: Optional[BaseException] = None

        while True:
            attempt += 1
            fut = asyncio.run_coroutine_threadsafe(self._coro_call_tool(tool_name, arguments), loop)
            try:
                res = fut.result(timeout=timeout)
                rid = None
                if isinstance(res, dict):
                    rid = res.get("run_id") or (
                        res.get("data", {}) if isinstance(res.get("data"), dict) else {}
                    ).get("run_id")
                preview = (
                    f"dict keys={list(res.keys())}"
                    if isinstance(res, dict)
                    else (str(res)[:200] + "..." if isinstance(res, str) and len(res) > 200 else str(res))
                )
                log_info("MCP", f"call_tool() result: run_id={rid}, preview={preview}")
                return res
            except Exception as e:
                last_err = e
                fut.cancel()
                log_warn("MCP", f"call_tool({tool_name}): attempt#{attempt} failed ({type(e).__name__}: {e})")
                if attempt >= retries:
                    log_exception("MCP", f"call_tool({tool_name}): exhausted retries", e)
                    raise
                time.sleep(MCP_BACKOFF_BASE_SEC * (2 ** (attempt - 1)))

    def list_job_tools_meta(self, *, timeout: Optional[float] = None, retries: Optional[int] = None) -> list[dict]:
        """
        线程安全同步方法（通过自定义工具 list_job_tools 获取 name/description 列表）
        """
        timeout = timeout or MCP_DEFAULT_TIMEOUT_SEC
        retries = retries if retries is not None else MCP_DEFAULT_RETRIES
        loop = self._loop
        if loop is None or self._session is None:
            log_error("MCP", "list_job_tools_meta(): loop/session not ready")
            raise RuntimeError("MCP 执行器未就绪")

        attempt = 0
        while True:
            attempt += 1
            fut = asyncio.run_coroutine_threadsafe(self._coro_list_job_tools(), loop)
            try:
                tools = fut.result(timeout=timeout)
                log_info("MCP", f"list_job_tools_meta(): got {len(tools)} tools (via MCP tool)")
                return tools
            except Exception as e:
                fut.cancel()
                log_warn(
                    "MCP",
                    f"list_job_tools_meta(): attempt#{attempt} failed ({type(e).__name__}: {e})"
                )
                if attempt >= retries:
                    log_exception("MCP", "list_job_tools_meta(): exhausted retries", e)
                    raise
                time.sleep(MCP_BACKOFF_BASE_SEC * (2 ** (attempt - 1)))

    # ---------- 仅在执行线程事件循环中运行的协程 ----------
    async def _coro_list_tools(self) -> List[Dict[str, Any]]:
        assert self._session is not None
        res = await self._session.list_tools()
        tools: List[Dict[str, Any]] = []
        for t in res.tools:
            tools.append({
                "name": t.name,
                "description": t.description or "",
                "inputSchema": _schema_to_json(getattr(t, "inputSchema", None)),
            })
        return tools

    async def _coro_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        assert self._session is not None
        res = await self._session.call_tool(tool_name, arguments)
        try:
            for seg in res.content:
                if getattr(seg, "type", None) == "json":
                    return seg.data
            texts = [seg.text for seg in res.content if getattr(seg, "text", None)]
            if texts:
                return "\n".join(texts)
        except Exception:
            pass
        out: List[Any] = []
        for seg in res.content:
            if getattr(seg, "type", None) == "json":
                out.append(("json", getattr(seg, "data", None)))
            elif getattr(seg, "type", None) == "text":
                out.append(("text", getattr(seg, "text", None)))
            else:
                out.append(("unknown", str(seg)))
        return out

    async def _coro_list_job_tools(self) -> list[dict]:
        assert self._session is not None
        res = await self._session.call_tool("list_job_tools", {})
        # 1) 优先 JSON 段
        try:
            for seg in res.content:
                if getattr(seg, "type", None) == "json":
                    data = seg.data or {}
                    items = data.get("tools", [])
                    out = []
                    for x in items:
                        if isinstance(x, dict) and x.get("name"):
                            out.append({
                                "name": str(x["name"]).strip(),
                                "description": str(x.get("description", "")).strip()
                            })
                        elif isinstance(x, str):
                            out.append({"name": x.strip(), "description": ""})
                    if out:
                        return out
        except Exception:
            pass
        # 2) 兼容 text 段里包 JSON
        try:
            texts = [
                seg.text for seg in res.content
                if getattr(seg, "type", None) == "text"
                and getattr(seg, "text", None)
            ]
            blob = "\n".join(texts).strip()
            if blob.startswith("{") or blob.startswith("["):
                data = json.loads(blob)
                items = data.get("tools", []) if isinstance(data, dict) else data
                out = []
                for x in items:
                    if isinstance(x, dict) and x.get("name"):
                        out.append({
                            "name": str(x["name"]).strip(),
                            "description": str(x.get("description", "")).strip()
                        })
                    elif isinstance(x, str):
                        out.append({"name": x.strip(), "description": ""})
                if out:
                    return out
        except Exception as e:
            log_warn("MCP", f"_coro_list_job_tools(): text->json parse failed: {e!r}")
        # 3) 调试预览
        try:
            preview = []
            for seg in res.content:
                t = getattr(seg, "type", None)
                if t == "json":
                    preview.append(("json", list((seg.data or {}).keys())))
                elif t == "text":
                    txt = (seg.text or "")[:200]
                    preview.append(("text", txt))
                else:
                    preview.append((t, ""))
            log_warn("MCP", f"_coro_list_job_tools(): no parse, preview={preview}")
        except Exception:
            pass
        return []

    async def _runner(self) -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=[self._server_path.as_posix()],
            cwd=self._server_path.parent.as_posix(),
        )
        self._stop_evt = asyncio.Event()
        log_info("MCP", f"Starting stdio client: cmd={params.command} args={params.args} cwd={params.cwd}")
        try:
            self._client_cm = stdio_client(params)
            read, write = await self._client_cm.__aenter__()
            async with ClientSession(read, write) as session:
                self._session = session
                await session.initialize()
                log_info("MCP", "ClientSession initialized")
                self._ready_evt.set()
                await self._stop_evt.wait()
                log_info("MCP", "Stop event received, shutting down session")
        except BaseException as e:
            self._error = e
            self._ready_evt.set()
            log_exception("MCP", "Runner encountered error", e)
        finally:
            try:
                if self._client_cm is not None:
                    await self._client_cm.__aexit__(None, None, None)
                    log_info("MCP", "stdio client __aexit__ done")
            finally:
                self._client_cm = None
                self._session = None

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        runner_task = loop.create_task(self._runner())
        try:
            log_info("MCP", "Event loop run_forever()")
            loop.run_forever()
        finally:
            runner_task.cancel()
            try:
                loop.run_until_complete(asyncio.gather(runner_task, return_exceptions=True))
            except Exception as e:
                log_exception("MCP", "Gather runner_task error", e)
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            log_info("MCP", "Event loop closed")


# =============== 通用 $ref 解析（新架构核心） ===============
JSONValue = Union[None, bool, int, float, str, Dict[str, Any], List[Any]]


class ResolveContext:
    """
    用于 $ref 解析的上下文，封装对 TaskManager 的访问。
    """

    def __init__(self, tm: "TaskManager", task_uid: str) -> None:
        self._tm = tm
        self._task_uid = task_uid

    # ---------- dataset 根目录 ----------
    def dataset_root_for(self, ds_id: Any) -> Path:
        """
        通过 dataset_catalog.id 获取数据集根目录，并做权限校验。
        """
        return self._tm._lookup_dataset_path_for_task(self._task_uid, ds_id)

    # ---------- 前置 step 输出根目录 ----------
    def job_output_root_for(self, step_number: int) -> Path:
        """
        通过某个“已成功步骤号”获取该步骤的输出目录。
        """
        try:
            step_k = int(step_number)
        except Exception:
            raise RuntimeError(f"job_output 引用的 step 必须是整数：{step_number!r}")

        row = self._tm.db.execute(
            "SELECT step_uid FROM steps "
            "WHERE task_uid = ? AND step_number = ? AND status = 'succeeded' "
            "ORDER BY rowid DESC LIMIT 1",
            (self._task_uid, step_k),
        ).fetchone()

        if not row:
            raise RuntimeError(
                f"未找到已成功的前置步骤：task={self._task_uid} step_number={step_k}"
            )

        prev_step_uid = row["step_uid"]
        user_uid = self._tm._get_user_uid_by_task(self._task_uid)
        base = (
            self._tm.workspace_root
            / user_uid
            / "workspace"
            / self._task_uid
            / prev_step_uid
        ).resolve()

        if not base.exists() or not base.is_dir():
            raise RuntimeError(
                f"job_output 根目录不存在或不是目录：task={self._task_uid}, "
                f"step={step_k}, dir={base}"
            )
        return base

    def config_value_for(self, key: str) -> Any:
        """
        预留：从全局配置中拿值。现在先占位，根据需要自己实现。
        """
        raise KeyError(f"config 引用功能尚未实现：key={key!r}")


def _safe_join_under(base: Path, relative: str) -> Path:
    """
    在 base 下安全拼接 relative，禁止 .. 逃逸。
    """
    rel = Path(relative)
    if rel.is_absolute():
        raise RuntimeError("relative 不应为绝对路径")
    final = (base / rel).resolve()
    try:
        final.relative_to(base)
    except Exception:
        raise RuntimeError(f"relative 导致路径逃逸：base={base}, final={final}")
    return final


def resolve_ref(ref: Dict[str, Any], ctx: ResolveContext) -> Any:
    """
    解析一个 {"kind": ..., ...} 引用，返回具体值（通常是路径字符串）。
    支持的 kind：
      - dataset:   {"kind": "dataset", "id": <dataset_id>, "relative": "C2.nii.gz"}
      - job_output:{"kind": "job_output", "step": 1, "relative": "pred"}
      - filesystem:{"kind": "filesystem", "path": "/base", "relative": "subdir"}
      - config:    {"kind": "config", "key": "xxx"}   # 预留
      - literal:   {"kind": "literal", "value": any}
    """
    kind = ref.get("kind")

    if kind == "dataset":
        ds_id = ref.get("id")
        if ds_id is None:
            raise ValueError(f"dataset 引用缺少 id 字段：{ref}")
        root = ctx.dataset_root_for(ds_id)
        p = root
        rel = ref.get("relative")
        if rel:
            p = _safe_join_under(root, rel)
        return str(p)

    if kind == "job_output":
        step = ref.get("step")
        if step is None:
            raise ValueError(f"job_output 引用缺少 step 字段：{ref}")
        root = ctx.job_output_root_for(step)
        p = root
        rel = ref.get("relative")
        if rel:
            p = _safe_join_under(root, rel)
        return str(p)

    if kind == "filesystem":
        base = Path(ref.get("path", ".")).expanduser().resolve()
        rel = ref.get("relative")
        if rel:
            base = _safe_join_under(base, rel)
        return str(base)

    if kind == "config":
        key = ref.get("key")
        if not key:
            raise ValueError(f"config 引用缺少 key 字段：{ref}")
        return ctx.config_value_for(str(key))

    if kind == "literal":
        # 显式声明 literal 时，直接返回 value
        return ref.get("value")

    raise ValueError(f"未知的 ref.kind: {kind!r}, ref={ref}")


def resolve_any(value: JSONValue, ctx: ResolveContext) -> JSONValue:
    """
    递归解析任意 JSON 结构中的 $ref：
    - 如果是 {"$ref": {...}}，调用 resolve_ref
    - dict：对每个 value 递归
    - list：对每个元素递归
    - 其他类型：原样返回
    """
    # 1) 引用包装：{"$ref": {...}}
    if isinstance(value, dict) and "$ref" in value:
        inner = value["$ref"]
        if not isinstance(inner, dict):
            raise ValueError(f"$ref 必须对应一个对象，收到：{type(inner).__name__}")
        return resolve_ref(inner, ctx)

    # 2) 普通 dict：递归 value
    if isinstance(value, dict):
        return {k: resolve_any(v, ctx) for k, v in value.items()}

    # 3) 列表：递归每个元素
    if isinstance(value, list):
        return [resolve_any(v, ctx) for v in value]

    # 4) 原子类型：直接返回
    return value


# ========================= TaskManager =========================
class TaskManager:
    """
    新版 TaskManager（彻底抛弃旧的 source_kind/source/relative 逻辑）：

    - 每个 step 仅支持新风格：
        {
          "step_number": 1,
          "tool_name": "start_n4",
          "args": {
            "image_path": {"$ref": {"kind": "dataset", "id": 123, "relative": "C2.nii.gz"}},
            "mask_path": {"$ref": {"kind": "dataset", "id": 123, "relative": "C2_mask.nii.gz"}},
            "n4_kernel_radius": 3
          }
        }

    - args 是任意 JSON 结构，可以在任何位置嵌入 {"$ref": {...}} 表示引用。
      支持：
        * kind="dataset"   （通过 dataset_catalog.id + relative 拼出路径）
        * kind="job_output"（通过前置步骤输出 + relative 拼出路径）
        * kind="filesystem"（任意文件系统路径）
        * kind="literal"   （显式字面量）
        * kind="config"    （预留）

    - 调用工具前，TaskManager 会对 args 做 resolve_any(args, ResolveContext)，
      得到全是字面量值的最终参数，然后调用 MCP 工具。
    """

    def __init__(
        self,
        public_datasets_source_root: str | Path,
        workspace_root: str | Path,
        database_file: str | Path,
        mcpserver_file: str | Path,
    ) -> None:
        log_info("INIT", "TaskManager __init__ enter")

        # 1) 规范化路径
        self.public_root = Path(public_datasets_source_root).expanduser().resolve()
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.db_path = Path(database_file).expanduser().resolve()
        self.mcpserver_path = Path(mcpserver_file).expanduser().resolve()
        log_info(
            "INIT",
            "paths resolved: public_root=%s, workspace_root=%s, db_path=%s, mcpserver_path=%s"
            % (self.public_root, self.workspace_root, self.db_path, self.mcpserver_path)
        )

        # 2) 必要资源存在性
        if not self.db_path.exists():
            log_error("INIT", f"db not found: {self.db_path}")
            raise FileNotFoundError(f"数据库文件不存在：{self.db_path}")
        if not self.mcpserver_path.exists():
            log_error("INIT", f"mcp server not found: {self.mcpserver_path}")
            raise FileNotFoundError(f"MCP 服务器文件不存在：{self.mcpserver_path}")

        # 3) 连接数据库
        try:
            self.db = sqlite3.connect(self.db_path.as_posix(), check_same_thread=False)
            self.db.row_factory = sqlite3.Row
            self.db.execute("SELECT 1;").fetchone()
            log_info("DB", "SQLite connected and test SELECT 1 passed")
        except Exception as e:
            log_exception("DB", "connect failed", e)
            raise RuntimeError(f"连接数据库失败：{e}") from e

        # 4) 任务队列
        self.task_queue: Queue[str] = Queue()
        log_info("INIT", "task_queue created")

        # 5) 启动常驻 MCP 执行器
        self._mcp = MCPExecutor(self.mcpserver_path)
        self._mcp.start()  # 阻塞等待就绪

        # 5.1 优先尝试自定义工具 list_job_tools_meta()
        tools_meta = self._mcp.list_job_tools_meta()
        if tools_meta:
            # 白名单名称
            self.allowed_tool_names = {
                t["name"] for t in tools_meta
                if isinstance(t, dict) and t.get("name")
            }
            log_info("MCP", f"allowed tools (from meta): {sorted(self.allowed_tool_names)}")

            # 只给外部展示 name/description
            self.tools_index = {
                t["name"]: {
                    "name": t["name"],
                    "description": t.get("description", "")
                }
                for t in tools_meta
                if isinstance(t, dict) and t.get("name")
            }

            # all_tools_index 仍保留调试信息
            all_tools = self._mcp.list_tools()
            self.all_tools_index = {
                t["name"]: t for t in all_tools
                if isinstance(t, dict) and t.get("name")
            }
        else:
            # 回退逻辑：老版本
            all_tools = self._mcp.list_tools()
            self.all_tools_index = {
                t["name"]: t for t in all_tools
                if isinstance(t, dict) and t.get("name")
            }
            self.allowed_tool_names = self._fetch_allowed_tool_names()
            self.tools_index = {
                name: {
                    "name": name,
                    "description": (self.all_tools_index.get(name, {}).get("description") or "")
                }
                for name in self.allowed_tool_names
            }
            log_info("MCP", f"allowed tools (fallback): {sorted(self.tools_index.keys())}")

        # 6) 初始化运行状态
        self.task_running: Optional[str] = None

        # 7) 运行线程控制
        self._runner_thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        log_info("INIT", "TaskManager __init__ done")

    # —— 白名单拉取 / 回退策略 ——
    def _fetch_allowed_tool_names(self) -> Set[str]:
        """
        通过 MCP 的 list_job_tools 获取白名单。
        若无该工具（兼容旧版），退化为以 'start_' 开头的工具名。
        """
        allowed: Set[str] = set()
        try:
            res = self._mcp.call_tool("list_job_tools", {})
            if isinstance(res, dict) and isinstance(res.get("tools"), list):
                items = res["tools"]
                names: set[str] = set()
                for x in items:
                    if isinstance(x, str):
                        names.add(x)
                    elif isinstance(x, dict) and x.get("name"):
                        names.add(str(x["name"]))
                allowed = names
                log_info("MCP", f"list_job_tools -> {sorted(allowed)}")
        except Exception as e:
            log_warn("MCP", f"list_job_tools not available or failed: {e!r}")

        if not allowed:
            # 回退策略：名称以 start_ 开头
            allowed = {
                name for name in self.all_tools_index.keys()
                if str(name).startswith("start_")
            }
            log_info("MCP", f"fallback allowed tools by prefix start_: {sorted(allowed)}")
        return allowed

    # —— 对外工具调用 ——（允许内部用到非白名单工具，如 get_status）
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        return self._mcp.call_tool(tool_name, arguments)

    # —— 对外展示（只展示白名单工具）——
    def list_tools(self) -> List[Dict[str, Any]]:
        return list(self.tools_index.values())

    # —— 调试/诊断：展示全部工具（含内部）——
    def list_all_tools(self) -> List[Dict[str, Any]]:
        return list(self.all_tools_index.values())

    # ==================== 创建任务 ====================
    def _validate_steps(
        self,
        steps: List[Dict[str, Any]],
        check_tools: bool = True
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        新版 steps 校验与标准化（彻底放弃旧的 source_kind/source/relative 逻辑）：

        约定：
        - 每个 step 必须包含：
            * step_number: int，从 1 开始连续
            * tool_name: str
            * args: object，可选，若缺省则视为空 dict
        - args 是任意 JSON 结构：
            * 可以是普通字面量、嵌套 dict/list
            * 任意位置可以出现 {"$ref": {...}}，由 TaskManager 调用前统一解析
        - 不再使用 source_kind/source/relative/additional_params 等旧字段
          （但为了兼容 DB schema，会把 args 原样写入 steps.additional_params 列做记录）
        """
        log_info(
            "CREATE",
            f"_validate_steps(): steps_count={len(steps) if isinstance(steps, list) else 'N/A'} check_tools={check_tools}"
        )
        if not steps or not isinstance(steps, list):
            raise ValueError("steps 不能为空")

        normalized: List[Dict[str, Any]] = []
        nums: List[int] = []
        for s in steps:
            if not isinstance(s, dict):
                raise ValueError("每个 step 必须是对象")

            n = s.get("step_number", s.get("stepNumber"))
            try:
                n = int(n)
            except Exception:
                raise ValueError(f"step_number 非法：{n}")

            tool = s.get("tool_name", s.get("toolName"))
            if not tool or not isinstance(tool, str):
                raise ValueError(f"step {n}: tool_name 不能为空")

            args = s.get("args")
            if args is None:
                args = {}
            if not isinstance(args, dict):
                raise ValueError(f"step {n}: args 必须是对象（dict），收到 {type(args).__name__}")

            normalized.append({
                "step_number": n,
                "tool_name": tool,
                "args": args,
            })
            nums.append(n)

        nums_sorted = sorted(nums)
        if nums_sorted != list(range(1, len(nums_sorted) + 1)):
            raise ValueError("step_number 必须从 1 开始连续且无重复")

        if check_tools:
            for s in normalized:
                if s["tool_name"] not in self.tools_index:
                    raise ValueError(f"未知或不允许的工具：{s['tool_name']}")

        total_steps = len(nums_sorted)
        normalized.sort(key=lambda x: x["step_number"])
        log_info(
            "CREATE",
            f"_validate_steps(): ok, total_steps={total_steps}, step_numbers={nums_sorted}"
        )
        return total_steps, normalized

    def create_task(
        self,
        user_uid: str,
        steps: List[Dict[str, Any]],
        *,
        check_tools: bool = True,
    ) -> Dict[str, Any]:
        """
        创建新任务（仅支持新风格 steps）：
        - 校验 steps
        - 入库 tasks/steps（queued）
        - 入内存队列等待主循环调度
        """
        log_info(
            "CREATE",
            f"create_task(): user_uid={user_uid!r}, check_tools={check_tools}"
        )
        if not user_uid:
            raise ValueError("user_uid 不能为空")

        total_steps, normalized_steps = self._validate_steps(
            steps, check_tools=check_tools
        )
        task_uid = uuid.uuid4().hex
        request_obj = {"steps": normalized_steps}
        request_json = json.dumps(request_obj, ensure_ascii=False)
        log_info(
            "CREATE",
            f"create_task(): task_uid={task_uid}, total_steps={total_steps}"
        )

        if total_steps == 0:
            self.db.execute(
                "INSERT INTO tasks (task_uid, user_uid, total_steps, status, "
                "current_step_number, current_step_uid, last_completed_step, "
                "failed_step_number, failed_step_uid, request_json) "
                "VALUES (?, ?, 0, 'succeeded', NULL, NULL, 0, NULL, NULL, ?)",
                (task_uid, user_uid, request_json),
            )
            self.db.commit()
            log_info(
                "CREATE",
                f"create_task(): zero-step -> succeeded task_uid={task_uid}"
            )
            return {
                "task_uid": task_uid,
                "status": "succeeded",
                "total_steps": 0
            }

        self.db.execute(
            "INSERT INTO tasks (task_uid, user_uid, total_steps, status, "
            "current_step_number, current_step_uid, last_completed_step, "
            "failed_step_number, failed_step_uid, request_json) "
            "VALUES (?, ?, ?, 'queued', NULL, NULL, 0, NULL, NULL, ?)",
            (task_uid, user_uid, total_steps, request_json),
        )
        self.db.commit()
        log_info(
            "CREATE",
            f"create_task(): inserted queued task task_uid={task_uid}"
        )

        self.task_queue.put(task_uid)
        log_info("QUEUE", f"task enqueued: {task_uid}")

        return {
            "task_uid": task_uid,
            "status": "queued",
            "total_steps": total_steps
        }

    # ==================== 任务/用户/数据集辅助 ====================
    def _get_user_uid_by_task(self, task_uid: str) -> str:
        row = self.db.execute(
            "SELECT user_uid FROM tasks WHERE task_uid = ?", (task_uid,)
        ).fetchone()
        if not row or not row["user_uid"]:
            log_error(
                "TASK",
                f"_get_user_uid_by_task(): not found for task={task_uid}"
            )
            raise RuntimeError(
                f"user_uid 未找到：task_uid={task_uid}"
            )
        return str(row["user_uid"])

    def _lookup_dataset_path_for_task(
        self,
        task_uid: str,
        dataset_id_raw: Union[str, int],
    ) -> Path:
        """
        根据任务ID和数据集主键(dataset_catalog.id)解析该任务对数据集的可访问目录。

        校验规则：
        - dataset_catalog.id == dataset_id
        - has_data == 1
        - data_path 非空
        - 权限：该行 user_id == -1 (公共) 或 user_id == 当前任务所属 user_uid
        - 返回的目录 = self.public_root / data_path
        """
        # 1. 解析 dataset_id
        try:
            dataset_id = int(dataset_id_raw)
        except Exception:
            raise RuntimeError(
                f"dataset 模式下 id 必须是数据集主键(整数)，收到 {dataset_id_raw!r}"
            )

        # 2. 查询任务所属用户
        user_uid = self._get_user_uid_by_task(task_uid)

        # 3. 查询该数据集元信息
        row = self.db.execute(
            "SELECT id, user_id, has_data, data_path "
            "FROM dataset_catalog WHERE id = ? LIMIT 1",
            (dataset_id,)
        ).fetchone()

        if not row:
            raise RuntimeError(
                f"未找到数据集 id={dataset_id} 对应的记录"
            )

        ds_user_id = row["user_id"]
        has_data = row["has_data"]
        data_path = row["data_path"]

        # 4. 权限校验
        if ds_user_id is None:
            raise RuntimeError(
                f"数据集 {dataset_id} 缺少 user_id 字段，拒绝访问"
            )

        allowed = False
        if int(ds_user_id) == -1:
            allowed = True
        else:
            try:
                if int(ds_user_id) == int(user_uid):
                    allowed = True
            except Exception:
                if str(ds_user_id) == str(user_uid):
                    allowed = True

        if not allowed:
            raise RuntimeError(
                f"任务用户 {user_uid} 无权访问数据集 {dataset_id}"
            )

        # 5. 有无数据
        if (has_data is None) or (int(has_data) != 1):
            raise RuntimeError(
                f"数据集 {dataset_id} 标记 has_data!=1，尚未上传/不可用"
            )

        if not data_path or not str(data_path).strip():
            raise RuntimeError(
                f"数据集 {dataset_id} 的 data_path 为空，无法定位文件目录"
            )

        # 6. 组装最终物理路径
        candidate = (self.public_root / str(data_path)).expanduser().resolve()

        if not candidate.exists() or not candidate.is_dir():
            raise RuntimeError(
                f"数据集 {dataset_id} 的目录不存在或不是目录：{candidate}"
            )

        log_info(
            "IO",
            f"_lookup_dataset_path_for_task(): task={task_uid}, dataset_id={dataset_id}, dir={candidate}"
        )
        return candidate

    def _alloc_step_uid_and_output_dir(self, task_uid: str) -> Tuple[str, Path]:
        user_uid = self._get_user_uid_by_task(task_uid)
        step_uid = uuid.uuid4().hex
        out_dir = (
            self.workspace_root / user_uid / "workspace" / task_uid / step_uid
        ).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        log_info(
            "IO",
            f"_alloc_step_uid_and_output_dir(): task={task_uid}, step_uid={step_uid}, out_dir={out_dir}"
        )
        return step_uid, out_dir

    # ---------- 产物导出 ----------
    def _export_results(self, task_uid: str, step_uid: str) -> None:
        import shutil
        try:
            user_uid = self._get_user_uid_by_task(task_uid)
        except Exception as e:
            log_exception(
                "RESULT",
                f"_export_results(): get user_uid failed task={task_uid}",
                e
            )
            return

        src_dir = (
            self.workspace_root / user_uid / "workspace" / task_uid / step_uid
        ).resolve()
        dst_dir = (
            self.workspace_root / user_uid / "workspace" / task_uid / "results"
        ).resolve()
        try:
            if not src_dir.exists() or not src_dir.is_dir():
                log_warn(
                    "RESULT",
                    f"_export_results(): src_dir invalid: {src_dir}"
                )
                return
            dst_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log_exception(
                "RESULT",
                f"_export_results(): prepare dst failed dst={dst_dir}",
                e
            )
            return

        log_info(
            "RESULT",
            f"export begin: task={task_uid}, step_uid={step_uid}, "
            f"src={src_dir}, dst={dst_dir}"
        )

        try:
            for item in src_dir.iterdir():
                s = item
                d = dst_dir / item.name
                try:
                    if s.is_dir():
                        shutil.copytree(s, d, dirs_exist_ok=True)
                        log_debug("RESULT", f"copytree OK: {s} -> {d}")
                    elif s.is_file():
                        d.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(s, d)
                        log_debug("RESULT", f"copy2 OK: {s} -> {d}")
                    else:
                        log_warn("RESULT", f"skip non-file/dir: {s}")
                except Exception as ie:
                    log_exception(
                        "RESULT",
                        f"copy item failed: {s} -> {d}",
                        ie
                    )
                    continue
        except Exception as e:
            log_exception(
                "RESULT",
                "iterate src_dir failed",
                e
            )
            return

        try:
            manifest = {
                "task_uid": task_uid,
                "from_step_uid": step_uid,
                "export_time": _now(),
                "src_dir": str(src_dir),
                "dst_dir": str(dst_dir),
            }
            (dst_dir / "_export_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            log_info("RESULT", f"export done: dst={dst_dir}")
        except Exception as e:
            log_exception(
                "RESULT",
                "write export manifest failed",
                e
            )

    def _export_latest_results_for_task(self, task_uid: str) -> None:
        try:
            row = self.db.execute(
                "SELECT step_uid FROM steps WHERE task_uid=? AND status='succeeded' "
                "AND step_number=("
                "   SELECT MAX(step_number) FROM steps "
                "   WHERE task_uid=? AND status='succeeded'"
                ") "
                "ORDER BY rowid DESC LIMIT 1",
                (task_uid, task_uid),
            ).fetchone()
            if not row:
                log_warn(
                    "RESULT",
                    f"_export_latest_results_for_task(): "
                    f"no succeeded step found for task={task_uid}"
                )
                return
            step_uid = str(row["step_uid"])
            self._export_results(task_uid, step_uid)
        except Exception as e:
            log_exception(
                "RESULT",
                f"_export_latest_results_for_task(): query failed task={task_uid}",
                e
            )

    # ==================== 启动/恢复 + 主循环 ====================
    def start(self) -> None:
        log_info("RUN", "start(): entering")
        self.task_queue = Queue()
        self._stop_evt.clear()
        self._recover_on_startup()
        self._load_queued_tasks_into_queue()
        self._runner_thread = threading.Thread(
            target=self._main_loop, name="task-runner", daemon=True
        )
        self._runner_thread.start()
        log_info("RUN", "start(): runner thread started")

    def stop(self, timeout: float = 5.0) -> None:
        log_info("RUN", "stop(): stop_evt set, waiting thread")
        self._stop_evt.set()
        if self._runner_thread and self._runner_thread.is_alive():
            self._runner_thread.join(timeout=timeout)
        self._runner_thread = None
        log_info("RUN", "stop(): runner thread joined")

    def close(self) -> None:
        log_info("RUN", "close(): enter")
        try:
            self.stop()
        except Exception as e:
            log_exception("RUN", "stop() failed", e)
        try:
            if hasattr(self, "_mcp") and self._mcp:
                self._mcp.close()
        except Exception as e:
            log_exception("RUN", "mcp.close() failed", e)
        try:
            if hasattr(self, "db") and self.db:
                self.db.close()
        except Exception as e:
            log_exception("RUN", "db.close() failed", e)
        log_info("RUN", "close(): done")

    # ---------- 启动恢复 ----------
    def _recover_on_startup(self) -> None:
        log_info("RECOVER", "recover_on_startup(): begin")
        cur = self.db.cursor()

        cur.execute(
            "SELECT step_uid, task_uid, step_number "
            "FROM steps WHERE status = 'running'"
        )
        rows = cur.fetchall()
        log_info(
            "RECOVER",
            f"steps.running count={len(rows)} -> mark failed"
        )
        for r in rows:
            step_uid = r["step_uid"]
            task_uid = r["task_uid"]
            step_number = r["step_number"]
            self.db.execute(
                "UPDATE steps SET status='failed' WHERE step_uid = ?",
                (step_uid,)
            )
            self.db.execute(
                "UPDATE tasks SET failed_step_number=?, failed_step_uid=? "
                "WHERE task_uid=?",
                (step_number, step_uid, task_uid),
            )

        self.db.execute(
            "UPDATE tasks SET status='queued', current_step_number=NULL, "
            "current_step_uid=NULL WHERE status='running'"
        )
        log_info("RECOVER", "tasks.running -> queued")

        self.db.execute(
            "UPDATE tasks SET last_completed_step = COALESCE(("
            "   SELECT MAX(step_number) FROM steps "
            "   WHERE steps.task_uid = tasks.task_uid "
            "     AND steps.status = 'succeeded'"
            "), 0)"
        )
        log_info("RECOVER", "recalc last_completed_step done")

        self.db.commit()
        log_info("RECOVER", "recover_on_startup(): committed")

    def _load_queued_tasks_into_queue(self) -> None:
        seen: set[str] = set()
        cur = self.db.execute(
            "SELECT task_uid FROM tasks WHERE status='queued' ORDER BY rowid ASC"
        )
        rows = cur.fetchall()
        log_info("QUEUE", f"load queued tasks: count={len(rows)}")
        for r in rows:
            uid = str(r["task_uid"])
            if uid not in seen:
                self.task_queue.put(uid)
                seen.add(uid)
                log_info("QUEUE", f"queued -> enqueued: task_uid={uid}")

    # ---------- 主循环 ----------
    def _main_loop(self) -> None:
        log_info("LOOP", "main_loop: enter")
        while not self._stop_evt.is_set():
            try:
                # A) 当前没有任务在跑：尝试取下一个
                if self.task_running is None:
                    try:
                        task_uid = self.task_queue.get_nowait()
                        log_info("LOOP", f"A-POP: got task_uid={task_uid}")
                    except Empty:
                        log_debug("LOOP", "A-IDLE: queue empty, sleep 5s")
                        time.sleep(5.0)
                        continue

                    task = self._get_task(task_uid)
                    if task is None:
                        log_warn(
                            "LOOP",
                            f"A-DROP: task not found in DB, task_uid={task_uid}"
                        )
                        continue

                    if task["status"] != "queued":
                        log_info(
                            "LOOP",
                            f"A-DROP: status={task['status']} != queued"
                        )
                        continue

                    last_done = int(task["last_completed_step"] or 0)
                    total = int(task["total_steps"] or 0)
                    log_info(
                        "LOOP",
                        f"A-CHECK: last_done={last_done}, total={total}"
                    )

                    if last_done >= total:
                        self._export_latest_results_for_task(task_uid)
                        self.db.execute(
                            "UPDATE tasks "
                            "SET status='succeeded', current_step_number=NULL, "
                            "current_step_uid=NULL "
                            "WHERE task_uid=?",
                            (task_uid,),
                        )
                        self.db.commit()
                        log_info(
                            "LOOP",
                            f"A-MARK: already complete -> succeeded, task={task_uid}"
                        )
                        continue

                    self.db.execute(
                        "UPDATE tasks SET status='running' WHERE task_uid=?",
                        (task_uid,),
                    )
                    self.db.commit()
                    self.task_running = task_uid
                    log_info(
                        "LOOP",
                        f"A-SET: task_running={task_uid}, status=running"
                    )
                    continue

                # B) 有任务在跑：轮询该任务
                task_uid = self.task_running
                task = self._get_task(task_uid)
                if task is None:
                    log_error(
                        "LOOP",
                        f"B-ERR: current task missing in DB, task_running={task_uid}"
                    )
                    self.task_running = None
                    continue

                last_done = int(task["last_completed_step"] or 0)
                total = int(task["total_steps"] or 0)
                log_info(
                    "LOOP",
                    f"B-STATE: task={task_uid}, last_done={last_done}, total={total}"
                )

                if last_done >= total:
                    self._export_latest_results_for_task(task_uid)
                    self.db.execute(
                        "UPDATE tasks SET status='succeeded', "
                        "current_step_number=NULL, current_step_uid=NULL "
                        "WHERE task_uid=?",
                        (task_uid,),
                    )
                    self.db.commit()
                    log_info(
                        "LOOP",
                        f"B-MARK: task complete -> succeeded, task={task_uid}"
                    )
                    self.task_running = None
                    continue

                # 查是否有运行中的 step
                step_row = self.db.execute(
                    "SELECT * FROM steps "
                    "WHERE task_uid=? AND status='running' "
                    "ORDER BY rowid DESC LIMIT 1",
                    (task_uid,),
                ).fetchone()
                log_info(
                    "LOOP",
                    f"B-CHECK-RUNNING: has_running={bool(step_row)}"
                )

                if step_row:
                    run_id = step_row["run_id"]
                    st = self._safe_get_status(run_id)
                    done = bool(st.get("done")) if isinstance(st, dict) else False
                    exit_code = st.get("exit_code") if isinstance(st, dict) else None

                    log_info(
                        "LOOP",
                        f"B-POLL: run_id={run_id}, done={done}, exit_code={exit_code}"
                    )

                    def _is_zero(x):
                        try:
                            return int(x) == 0
                        except Exception:
                            return False

                    if done and _is_zero(exit_code):
                        # 成功
                        self.db.execute(
                            "UPDATE steps SET status='succeeded' WHERE step_uid=?",
                            (step_row["step_uid"],),
                        )
                        self.db.execute(
                            "UPDATE tasks SET last_completed_step=?, "
                            "current_step_number=NULL, current_step_uid=NULL "
                            "WHERE task_uid=?",
                            (step_row["step_number"], task_uid),
                        )
                        self.db.commit()
                        log_info(
                            "LOOP",
                            "B-DONE-OK: step_number=%s succeeded"
                            % (step_row["step_number"],)
                        )

                        if int(step_row["step_number"]) >= total:
                            # 最终步完成
                            self._export_results(
                                task_uid,
                                step_row["step_uid"]
                            )
                            self.db.execute(
                                "UPDATE tasks SET status='succeeded' "
                                "WHERE task_uid=?",
                                (task_uid,),
                            )
                            self.db.commit()
                            log_info(
                                "RESULT",
                                "final step succeeded -> exported + task succeeded, "
                                f"task={task_uid}"
                            )
                            self.task_running = None
                            time.sleep(0.05)
                            continue

                        time.sleep(0.05)
                        continue

                    elif done and exit_code is not None and not _is_zero(exit_code):
                        # 失败
                        self.db.execute(
                            "UPDATE steps SET status='failed' WHERE step_uid=?",
                            (step_row["step_uid"],),
                        )
                        self.db.execute(
                            "UPDATE tasks SET status='failed', "
                            "failed_step_number=?, failed_step_uid=?, "
                            "current_step_number=NULL, current_step_uid=NULL "
                            "WHERE task_uid=?",
                            (
                                step_row["step_number"],
                                step_row["step_uid"],
                                task_uid,
                            ),
                        )
                        self.db.commit()
                        log_error(
                            "LOOP",
                            "B-DONE-FAIL: step_number=%s exit_code=%s"
                            % (step_row["step_number"], exit_code)
                        )
                        self.task_running = None
                        time.sleep(0.05)
                        continue

                    elif done and exit_code is None:
                        # 模糊态：done=True 但没给 exit_code
                        log_debug(
                            "LOOP",
                            "B-POLL: done=True but exit_code=None, short sleep for confirm"
                        )
                        time.sleep(0.05)
                        st2 = self._safe_get_status(run_id)
                        ec2 = st2.get("exit_code") if isinstance(st2, dict) else None
                        if _is_zero(ec2):
                            self.db.execute(
                                "UPDATE steps SET status='succeeded' WHERE step_uid=?",
                                (step_row["step_uid"],),
                            )
                            self.db.execute(
                                "UPDATE tasks SET last_completed_step=?, "
                                "current_step_number=NULL, current_step_uid=NULL "
                                "WHERE task_uid=?",
                                (step_row["step_number"], task_uid),
                            )
                            self.db.commit()
                            log_info(
                                "LOOP",
                                "B-DONE-OK2: confirm success step_number=%s"
                                % (step_row["step_number"],)
                            )

                            if int(step_row["step_number"]) >= total:
                                self._export_results(
                                    task_uid,
                                    step_row["step_uid"]
                                )
                                self.db.execute(
                                    "UPDATE tasks SET status='succeeded' "
                                    "WHERE task_uid=?",
                                    (task_uid,),
                                )
                                self.db.commit()
                                log_info(
                                    "RESULT",
                                    "final step succeeded (confirm) -> exported + task succeeded, "
                                    f"task={task_uid}"
                                )
                                self.task_running = None
                                time.sleep(0.05)
                                continue
                            time.sleep(0.05)
                            continue

                        elif ec2 is not None and not _is_zero(ec2):
                            self.db.execute(
                                "UPDATE steps SET status='failed' WHERE step_uid=?",
                                (step_row["step_uid"],),
                            )
                            self.db.execute(
                                "UPDATE tasks SET status='failed', "
                                "failed_step_number=?, failed_step_uid=?, "
                                "current_step_number=NULL, current_step_uid=NULL "
                                "WHERE task_uid=?",
                                (
                                    step_row["step_number"],
                                    step_row["step_uid"],
                                    task_uid,
                                ),
                            )
                            self.db.commit()
                            log_error(
                                "LOOP",
                                "B-DONE-FAIL2: confirm fail step_number=%s ec2=%s"
                                % (step_row["step_number"], ec2)
                            )
                            self.task_running = None
                            time.sleep(0.05)
                            continue
                        else:
                            log_debug(
                                "LOOP",
                                "B-POLL: still unclear, sleep 0.1s and continue"
                            )
                            time.sleep(0.1)
                            continue
                    else:
                        time.sleep(0.2)
                        continue

                # 没有运行中的步骤：启动下一步
                next_k = (int(task["last_completed_step"] or 0)) + 1
                if next_k > total:
                    self._export_latest_results_for_task(task_uid)
                    self.db.execute(
                        "UPDATE tasks SET status='succeeded', "
                        "current_step_number=NULL, current_step_uid=NULL "
                        "WHERE task_uid=?",
                        (task_uid,),
                    )
                    self.db.commit()
                    log_info(
                        "LOOP",
                        "B-MARK-AGAIN: completed on recheck -> exported + succeeded, "
                        f"task={task_uid}"
                    )
                    self.task_running = None
                    continue

                step_def = self._get_step_def_from_request(task, next_k)
                log_info(
                    "LOOP",
                    f"B-NEXT: next_k={next_k}, step_def_exists={bool(step_def)}"
                )
                if step_def is None:
                    self._fail_task_with_step(
                        task_uid=task_uid,
                        step_number=next_k,
                        step_uid=None
                    )
                    self.task_running = None
                    log_error(
                        "LOOP",
                        f"B-ERR: step_def missing, mark task failed, "
                        f"task={task_uid}, next_k={next_k}"
                    )
                    continue

                # 为本步骤分配输出目录
                step_uid, out_dir = self._alloc_step_uid_and_output_dir(task_uid)

                tool_name = str(
                    step_def.get("tool_name") or step_def.get("toolName")
                )
                if not tool_name:
                    self._fail_task_with_step(
                        task_uid=task_uid,
                        step_number=next_k,
                        step_uid=step_uid
                    )
                    self.task_running = None
                    log_error(
                        "LOOP",
                        f"B-ERR: empty tool_name, task={task_uid}, next_k={next_k}"
                    )
                    continue

                raw_args = step_def.get("args") or {}
                if not isinstance(raw_args, dict):
                    self._fail_task_with_step(
                        task_uid=task_uid,
                        step_number=next_k,
                        step_uid=step_uid
                    )
                    self.task_running = None
                    log_error(
                        "LOOP",
                        f"B-ERR: args 必须是对象(dict)，收到 {type(raw_args).__name__}, "
                        f"task={task_uid}, step={next_k}"
                    )
                    continue

                # 使用统一的 $ref 解析器，把任意嵌套结构中的 {"$ref": {...}} 展开
                ctx = ResolveContext(self, task_uid)
                try:
                    args_any = resolve_any(raw_args, ctx)
                    if not isinstance(args_any, dict):
                        raise RuntimeError(
                            f"解析后的 args 不是对象：step={next_k}, type={type(args_any).__name__}"
                        )
                    args = args_any
                except Exception as e:
                    self._fail_task_with_step(
                        task_uid=task_uid,
                        step_number=next_k,
                        step_uid=step_uid
                    )
                    self.task_running = None
                    log_exception(
                        "LOOP",
                        f"B-ERR: resolve_any(args) failed for step={next_k}",
                        e
                    )
                    continue

                # 为工具确保提供 out_dir 参数（如果调用方没写，就补一个字面量）
                args.setdefault("out_dir", str(out_dir))

                log_info(
                    "LOOP",
                    "B-CALL: tool=%s, next_k=%s, out_dir=%s, args_keys=%s"
                    % (
                        tool_name,
                        next_k,
                        out_dir,
                        list(args.keys()),
                    )
                )

                # 调 MCP 工具，拿 run_id
                run_id = None
                retries = 0
                while run_id is None and not self._stop_evt.is_set():
                    try:
                        res = self.call_tool(tool_name, args)
                        if isinstance(res, dict) and "run_id" in res:
                            run_id = res["run_id"]
                        elif (
                            isinstance(res, dict)
                            and "data" in res
                            and isinstance(res["data"], dict)
                            and "run_id" in res["data"]
                        ):
                            run_id = res["data"]["run_id"]
                        else:
                            # 兜底：有些 MCP 工具可能返回字符串形式的 json
                            try:
                                txt = res if isinstance(res, str) else ""
                                parsed = json.loads(txt) if txt else {}
                                if "run_id" in parsed:
                                    run_id = parsed["run_id"]
                            except Exception:
                                pass
                    except Exception as e:
                        log_exception(
                            "LOOP",
                            f"B-CALL: call_tool exception (will retry) tool={tool_name}",
                            e
                        )

                    retries += 1
                    if run_id is None:
                        log_warn(
                            "LOOP",
                            f"B-CALL: run_id missing (retry #{retries})"
                        )
                        time.sleep(0.5)

                    if retries >= 10 and run_id is None:
                        log_error(
                            "LOOP",
                            f"B-CALL: run_id still None after {retries} retries, "
                            "will fail step"
                        )
                        break

                if run_id is None:
                    self._fail_task_with_step(
                        task_uid=task_uid,
                        step_number=next_k,
                        step_uid=step_uid
                    )
                    self.task_running = None
                    log_error(
                        "LOOP",
                        "B-FAIL: cannot obtain run_id, task failed, "
                        f"task={task_uid}, step={next_k}"
                    )
                    continue

                # 记录 running 的步骤
                self.db.execute(
                    "INSERT INTO steps (step_uid, task_uid, step_number, "
                    "tool_name, source_kind, source, relative, run_id, "
                    "additional_params, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running')",
                    (
                        step_uid,
                        task_uid,
                        next_k,
                        tool_name,
                        None,   # 不再使用 source_kind
                        None,   # 不再使用 source
                        None,   # 不再使用 relative
                        str(run_id),
                        json.dumps(
                            step_def.get("args") or {},
                            ensure_ascii=False
                        ),
                    ),
                )
                self.db.execute(
                    "UPDATE tasks SET current_step_number=?, current_step_uid=?, "
                    "status='running' WHERE task_uid=?",
                    (next_k, step_uid, task_uid),
                )
                self.db.commit()
                log_info(
                    "LOOP",
                    "B-STARTED: step running, task=%s, step=%s, step_uid=%s, run_id=%s"
                    % (task_uid, next_k, step_uid, run_id)
                )

                time.sleep(0.1)
                continue

            except Exception as e:
                log_exception(
                    "LOOP",
                    "UNCAUGHT in main_loop iteration (sleep 0.3s)",
                    e
                )
                time.sleep(0.3)
                continue

    # ---------- 工具方法 ----------
    def _get_task(self, task_uid: str) -> Optional[sqlite3.Row]:
        row = self.db.execute(
            "SELECT * FROM tasks WHERE task_uid=?",
            (task_uid,)
        ).fetchone()
        log_debug(
            "TASK",
            f"_get_task(): task_uid={task_uid}, exists={bool(row)}"
        )
        return row

    def _fail_task_with_step(
        self,
        task_uid: str,
        step_number: int,
        step_uid: Optional[str],
    ) -> None:
        if step_uid:
            self.db.execute(
                "UPDATE steps SET status='failed' WHERE step_uid=?",
                (step_uid,),
            )
        self.db.execute(
            "UPDATE tasks SET status='failed', failed_step_number=?, "
            "failed_step_uid=?, current_step_number=NULL, "
            "current_step_uid=NULL WHERE task_uid=?",
            (step_number, step_uid, task_uid),
        )
        self.db.commit()
        log_error(
            "TASK",
            f"_fail_task_with_step(): task={task_uid}, "
            f"step_number={step_number}, step_uid={step_uid}"
        )

    def _safe_get_status(self, run_id: str) -> Dict[str, Any]:
        try:
            res = self.call_tool("get_status", {"run_id": run_id})

            if isinstance(res, dict):
                log_debug(
                    "MCP",
                    f"_safe_get_status(): run_id={run_id}, "
                    f"done={res.get('done')}, exit_code={res.get('exit_code')}"
                )
                return res

            if isinstance(res, (str, bytes)):
                txt = (
                    res.decode("utf-8", errors="ignore")
                    if isinstance(res, bytes)
                    else res
                )
                txt_stripped = txt.strip()
                if txt_stripped.startswith("{") or txt_stripped.startswith("["):
                    try:
                        obj = json.loads(txt_stripped)
                        if isinstance(obj, dict):
                            log_debug(
                                "MCP",
                                f"_safe_get_status(): parsed JSON for run_id={run_id}"
                            )
                            return obj
                        else:
                            log_warn(
                                "MCP",
                                "_safe_get_status(): parsed JSON is not a dict "
                                f"(type={type(obj).__name__})"
                            )
                    except Exception as je:
                        log_warn(
                            "MCP",
                            "_safe_get_status(): json parse failed: %r; "
                            "preview=%s"
                            % (je, txt_stripped[:200])
                        )

            log_warn(
                "MCP",
                f"_safe_get_status(): unsupported type={type(res).__name__}; "
                "return empty dict"
            )
            return {}
        except Exception as e:
            log_exception(
                "MCP",
                f"_safe_get_status(): exception for run_id={run_id}",
                e
            )
            return {}

    def _get_step_def_from_request(
        self,
        task_row: sqlite3.Row,
        step_number: int
    ) -> Optional[Dict[str, Any]]:
        req = task_row["request_json"]
        if not req:
            log_warn(
                "TASK",
                "_get_step_def_from_request(): 'steps' missing due to empty request_json"
            )
            return None
        try:
            obj = json.loads(req) if isinstance(req, (str, bytes)) else req
        except Exception as e:
            log_exception(
                "TASK",
                "_get_step_def_from_request(): json loads failed",
                e
            )
            return None

        steps = obj.get("steps") if isinstance(obj, dict) else None
        if steps is None:
            log_warn(
                "TASK",
                "_get_step_def_from_request(): 'steps' missing"
            )
            return None

        if isinstance(steps, list):
            for s in steps:
                try:
                    if int(
                        s.get("step_number")
                        or s.get("stepNumber")
                    ) == int(step_number):
                        log_debug(
                            "TASK",
                            "_get_step_def_from_request(): list found step_number=%s"
                            % step_number
                        )
                        return s
                except Exception:
                    continue

        if isinstance(steps, dict):
            s = steps.get(str(step_number)) or steps.get(step_number)
            if isinstance(s, dict):
                s.setdefault("step_number", step_number)
                log_debug(
                    "TASK",
                    "_get_step_def_from_request(): dict found step_number=%s"
                    % step_number
                )
                return s

        log_warn(
            "TASK",
            f"_get_step_def_from_request(): step_number={step_number} not found"
        )
        return None

    # =============== 按任务ID查询任务运行情况（仅查状态，不查日志） ===============
    def get_task_status(self, task_uid: str) -> Dict[str, Any]:
        log_info("QUERY", f"get_task_status(NO-LOGS): task_uid={task_uid}")
        task = self._get_task(task_uid)
        if task is None:
            log_warn(
                "QUERY",
                f"get_task_status(): task not found task_uid={task_uid}"
            )
            return {
                "ok": False,
                "error": "task_not_found",
                "task_uid": task_uid
            }

        base: Dict[str, Any] = {
            "ok": True,
            "task_uid": task_uid,
            "status": task["status"],
            "user_uid": task["user_uid"],
            "total_steps": int(task["total_steps"] or 0),
            "last_completed_step": int(task["last_completed_step"] or 0),
            "current_step_number": (
                int(task["current_step_number"])
                if task["current_step_number"] is not None
                else None
            ),
            "current_step_uid": task["current_step_uid"],
            "failed_step_number": (
                int(task["failed_step_number"])
                if task["failed_step_number"] is not None
                else None
            ),
            "failed_step_uid": task["failed_step_uid"],
        }

        if str(task["status"]) == "running":
            step_row = None
            if task["current_step_uid"]:
                step_row = self.db.execute(
                    "SELECT step_uid, step_number, tool_name, status, run_id "
                    "FROM steps WHERE step_uid=? LIMIT 1",
                    (task["current_step_uid"],),
                ).fetchone()

            if step_row is None:
                step_row = self.db.execute(
                    "SELECT step_uid, step_number, tool_name, status, run_id "
                    "FROM steps WHERE task_uid=? AND status='running' "
                    "ORDER BY rowid DESC LIMIT 1",
                    (task_uid,),
                ).fetchone()

            if step_row:
                base["running_step"] = {
                    "step_uid": step_row["step_uid"],
                    "step_number": int(step_row["step_number"]),
                    "tool_name": step_row["tool_name"],
                    "status": step_row["status"],
                    "run_id": step_row["run_id"],
                }
            else:
                base["running_step"] = None

        try:
            total = base["total_steps"] or 0
            done = base["last_completed_step"] or 0
            base["progress"] = (done / total) if total > 0 else None
        except Exception:
            base["progress"] = None

        return base


# ========================= Async 外观：包装同步实现 =========================
class AsyncTaskManager:
    def __init__(
        self,
        public_datasets_source_root: str | Path,
        workspace_root: str | Path,
        database_file: str | Path,
        mcpserver_file: str | Path,
    ) -> None:
        """
        对外签名保持不变：
        - public_datasets_source_root 仍然是第一个参数名
        """
        self._cfg = (
            Path(public_datasets_source_root),
            Path(workspace_root),
            Path(database_file),
            Path(mcpserver_file),
        )
        self._tm: Optional[TaskManager] = None
        self._started = False

    async def astart(self) -> None:
        if self._started:
            return

        def _init_and_start() -> TaskManager:
            tm = TaskManager(
                public_datasets_source_root=self._cfg[0],
                workspace_root=self._cfg[1],
                database_file=self._cfg[2],
                mcpserver_file=self._cfg[3],
            )
            tm.start()
            return tm

        self._tm = await asyncio.to_thread(_init_and_start)
        self._started = True
        log_info("ASYNC", "AsyncTaskManager started")

    async def aclose(self) -> None:
        if not self._started or self._tm is None:
            return

        def _close():
            try:
                self._tm.close()
            except Exception as e:
                log_exception("ASYNC", "close() failed", e)

        await asyncio.to_thread(_close)
        self._tm = None
        self._started = False
        log_info("ASYNC", "AsyncTaskManager closed")

    def _require_tm(self) -> TaskManager:
        if not self._started or self._tm is None:
            raise RuntimeError("AsyncTaskManager 未启动：请先调用 astart()")
        return self._tm

    async def list_tools(self) -> List[Dict[str, Any]]:
        tm = self._require_tm()
        return await asyncio.to_thread(tm.list_tools)

    async def list_all_tools(self) -> List[Dict[str, Any]]:
        tm = self._require_tm()
        return await asyncio.to_thread(tm.list_all_tools)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        tm = self._require_tm()
        return await asyncio.to_thread(tm.call_tool, tool_name, arguments)

    async def create_task(
        self,
        user_uid: str,
        steps: List[Dict[str, Any]],
        *,
        check_tools: bool = True,
    ) -> Dict[str, Any]:
        tm = self._require_tm()
        return await asyncio.to_thread(
            tm.create_task,
            user_uid,
            steps,
            check_tools=check_tools
        )

    async def get_task_status(self, task_uid: str) -> Dict[str, Any]:
        tm = self._require_tm()
        return await asyncio.to_thread(tm.get_task_status, task_uid)

    @property
    def sync(self) -> TaskManager:
        return self._require_tm()


# 兼容：确保 os 已导入（日志初始化曾引用）
import os  # noqa: E402
