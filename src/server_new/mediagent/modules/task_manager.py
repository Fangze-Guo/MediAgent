# task_manager.py —— 常驻会话版本（后台线程独占 stdio，会话复用）
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
from typing import Any, Dict, List, Optional, Tuple
from mediagent.paths import in_data

# ===================== 日志配置（可修改） =====================
LOG_ENABLED: bool = True  # 是否开启日志输出到文件
LOG_DIR: Path = in_data("TM_logs")  # 日志文件存放目录

# 需要：pip install "mcp>=1.13.0"
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ============================ 轻量日志工具 ============================
# 说明：
# - 线程安全写文件；每个进程一个日志文件，例如 task_manager_20250922_160405_pid12345.log
# - 用 log_info / log_warn / log_error / log_debug 写日志
# - 统一格式：TS | Thread | LEVEL | TAG | message
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
        pid = str(os.getpid()) if 'os' in globals() else "na"
        fname = f"task_manager_{ts}_pid{pid}.log"
        _log_file_path = (LOG_DIR / fname).resolve()
        # 写一行头
        try:
            with open(_log_file_path, "a", encoding="utf-8") as f:
                f.write(f"{_now()} | main | INFO  | LOG | log file created: {_log_file_path}\n")
        except Exception:
            pass

def _now() -> str:
    # 精确到毫秒
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
        # 避免日志写入问题影响主流程
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
    - start(): 启动线程并建立会话（只一次）
    - list_tools(): 线程安全，同步调用
    - call_tool(name, args): 线程安全，同步调用
    - close(): 优雅关闭会话与线程
    """
    def __init__(self, server_path: Path) -> None:
        self._server_path = Path(server_path).expanduser().resolve()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready_evt = threading.Event()
        self._stop_evt: Optional[asyncio.Event] = None
        self._session: Optional[ClientSession] = None
        self._client_cm = None   # stdio_client(...) async contextmanager
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
            raise err  # 将连接期错误冒泡
        log_info("MCP", "Executor started and ready")

    def close(self, timeout: float = 10.0) -> None:
        log_info("MCP", "Executor close() called")
        loop = self._loop
        if loop is None:
            log_info("MCP", "Executor close(): loop is None, return")
            return
        # 通知 runner 结束
        def _signal_stop():
            if self._stop_evt is not None:
                self._stop_evt.set()
        loop.call_soon_threadsafe(_signal_stop)
        # 停止事件循环
        loop.call_soon_threadsafe(loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        self._loop = None
        log_info("MCP", "Executor closed")

    # ---------- 线程安全同步方法 ----------
    def list_tools(self) -> List[Dict[str, Any]]:
        loop = self._loop
        if loop is None or self._session is None:
            log_error("MCP", "list_tools(): loop/session not ready")
            raise RuntimeError("MCP 执行器未就绪")
        fut = asyncio.run_coroutine_threadsafe(self._coro_list_tools(), loop)
        tools = fut.result()
        log_info("MCP", f"list_tools(): got {len(tools)} tools")
        return tools

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        loop = self._loop
        if loop is None or self._session is None:
            log_error("MCP", f"call_tool({tool_name}): loop/session not ready")
            raise RuntimeError("MCP 执行器未就绪")
        log_info("MCP", f"call_tool(): name={tool_name}, args_keys={list(arguments.keys())}")
        fut = asyncio.run_coroutine_threadsafe(self._coro_call_tool(tool_name, arguments), loop)
        try:
            res = fut.result()
            # 尽量打印 run_id/简要回显，避免大型 JSON 占满日志
            rid = None
            if isinstance(res, dict):
                rid = res.get("run_id") or (res.get("data", {}) if isinstance(res.get("data"), dict) else {}).get("run_id")
            preview = f"dict keys={list(res.keys())}" if isinstance(res, dict) else (str(res)[:200] + "..." if isinstance(res, str) and len(res) > 200 else str(res))
            log_info("MCP", f"call_tool() result: run_id={rid}, preview={preview}")
            return res
        except BaseException as e:
            log_exception("MCP", f"call_tool({tool_name}) fut.result() failed", e)
            raise

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
        # 友好解析：优先 JSON → 其次文本 → 否则返回片段信息列表
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

    async def _runner(self) -> None:
        """启动 stdio client + ClientSession 并保持常驻，直到收到 stop 事件。"""
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
                await session.initialize()  # MCP 1.13.x 无参
                log_info("MCP", "ClientSession initialized")
                self._ready_evt.set()      # 对外：已就绪
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


# ========================= TaskManager =========================
class TaskManager:
    """
    常驻版初始化 + 启动流程：
      1) 参数规范化 + 校验 DB/MCP 文件存在
      2) 连接 SQLite
      3) 创建任务队列
      4) 启动 MCPExecutor（常驻会话）
      5) 通过执行器 list_tools() 拉取工具并缓存
      6) 提供 call_tool() 复用常驻会话
      7) start(): 恢复数据库状态 + 启动运行线程（主循环）
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
        log_info("INIT", f"paths resolved: public_root={self.public_root}, workspace_root={self.workspace_root}, "
                         f"db_path={self.db_path}, mcpserver_path={self.mcpserver_path}")

        # 2) 必要资源存在性
        if not self.db_path.exists():
            log_error("INIT", f"db not found: {self.db_path}")
            raise FileNotFoundError(f"数据库文件不存在：{self.db_path}")
        if not self.mcpserver_path.exists():
            log_error("INIT", f"mcp server not found: {self.mcpserver_path}")
            raise FileNotFoundError(f"MCP 服务器文件不存在：{self.mcpserver_path}")

        # 3) 连接数据库（仅连通性验证）
        try:
            self.db = sqlite3.connect(self.db_path.as_posix(), check_same_thread=False)
            self.db.row_factory = sqlite3.Row
            self.db.execute("SELECT 1;").fetchone()
            log_info("DB", "SQLite connected and test SELECT 1 passed")
        except Exception as e:
            log_exception("DB", "connect failed", e)
            raise RuntimeError(f"连接数据库失败：{e}") from e

        # 4) 空任务队列
        self.task_queue: Queue[str] = Queue()
        log_info("INIT", "task_queue created")

        # 5) 启动常驻 MCP 执行器并就绪后拉取工具
        self._mcp = MCPExecutor(self.mcpserver_path)
        self._mcp.start()  # 阻塞等待就绪或抛错
        tools = self._mcp.list_tools()
        self.tools_index: Dict[str, Dict[str, Any]] = {t["name"]: t for t in tools}
        log_info("MCP", f"tools indexed: {list(self.tools_index.keys())}")

        # 6) 初始化运行状态
        self.task_running: Optional[str] = None

        # 7) 运行线程控制
        self._runner_thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        log_info("INIT", "TaskManager __init__ done")

    # —— 对外工具调用（复用常驻会话） ——
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        return self._mcp.call_tool(tool_name, arguments)

    def list_tools(self) -> List[Dict[str, Any]]:
        return list(self.tools_index.values())

    # ==================== 创建任务（新增） ====================
    def _validate_steps(self, steps: List[Dict[str, Any]], check_tools: bool = True) -> Tuple[int, List[Dict[str, Any]]]:
        """
        校验并标准化 steps：
        - step_number 必须从 1 连续、无重复
        - tool_name 非空，source_kind ∈ {dataset, step, direct}
        - 返回 (total_steps, normalized_steps)
        """
        log_info("CREATE", f"_validate_steps(): steps_count={len(steps) if isinstance(steps, list) else 'N/A'} check_tools={check_tools}")
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
            sk = s.get("source_kind", s.get("sourceKind"))
            if sk not in ("dataset", "step", "direct"):
                raise ValueError(f"step {n}: source_kind 必须是 dataset/step/direct")
            ap = s.get("additional_params", s.get("additionalParams", {}))
            if isinstance(ap, str):
                try:
                    json.loads(ap)
                except Exception:
                    pass
            elif ap is None:
                ap = {}
            normalized.append({
                "step_number": n,
                "tool_name": tool,
                "source_kind": sk,
                "source": s.get("source"),
                "relative": s.get("relative"),
                "additional_params": ap,
            })
            nums.append(n)

        nums_sorted = sorted(nums)
        if nums_sorted != list(range(1, len(nums_sorted) + 1)):
            raise ValueError("step_number 必须从 1 开始连续且无重复")

        if check_tools:
            for s in normalized:
                if s["tool_name"] not in self.tools_index:
                    raise ValueError(f"未知工具：{s['tool_name']}")

        total_steps = len(nums_sorted)
        normalized.sort(key=lambda x: x["step_number"])
        log_info("CREATE", f"_validate_steps(): ok, total_steps={total_steps}, step_numbers={nums_sorted}")
        return total_steps, normalized

    def create_task(
        self,
        user_uid: str,
        steps: List[Dict[str, Any]],
        *,
        check_tools: bool = True,
    ) -> Dict[str, Any]:
        """
        创建新任务：
        - 随机生成 task_uid
        - 校验 steps，计算 total_steps
        - 原样保存 request_json
        - queued 插入 tasks 表（zero-step 直接 succeeded）
        - 入队 task_queue（非 zero-step）
        返回: {"task_uid", "status", "total_steps"}
        """
        log_info("CREATE", f"create_task(): user_uid={user_uid!r}, check_tools={check_tools}")
        if not user_uid:
            raise ValueError("user_uid 不能为空")

        total_steps, normalized_steps = self._validate_steps(steps, check_tools=check_tools)
        task_uid = uuid.uuid4().hex
        request_obj = {"steps": normalized_steps}
        request_json = json.dumps(request_obj, ensure_ascii=False)
        log_info("CREATE", f"create_task(): task_uid={task_uid}, total_steps={total_steps}")

        if total_steps == 0:
            self.db.execute(
                "INSERT INTO tasks (task_uid, user_uid, total_steps, status, "
                "current_step_number, current_step_uid, last_completed_step, "
                "failed_step_number, failed_step_uid, request_json) "
                "VALUES (?, ?, 0, 'succeeded', NULL, NULL, 0, NULL, NULL, ?)",
                (task_uid, user_uid, request_json),
            )
            self.db.commit()
            log_info("CREATE", f"create_task(): zero-step -> succeeded task_uid={task_uid}")
            return {"task_uid": task_uid, "status": "succeeded", "total_steps": 0}

        self.db.execute(
            "INSERT INTO tasks (task_uid, user_uid, total_steps, status, "
            "current_step_number, current_step_uid, last_completed_step, "
            "failed_step_number, failed_step_uid, request_json) "
            "VALUES (?, ?, ?, 'queued', NULL, NULL, 0, NULL, NULL, ?)",
            (task_uid, user_uid, total_steps, request_json),
        )
        self.db.commit()
        log_info("CREATE", f"create_task(): inserted queued task task_uid={task_uid}")

        self.task_queue.put(task_uid)
        log_info("QUEUE", f"task enqueued: {task_uid}")

        return {"task_uid": task_uid, "status": "queued", "total_steps": total_steps}

    # ==================== 文件重定向：输入/输出 ====================
    def _get_user_uid_by_task(self, task_uid: str) -> str:
        row = self.db.execute(
            "SELECT user_uid FROM tasks WHERE task_uid = ?", (task_uid,)
        ).fetchone()
        if not row or not row["user_uid"]:
            log_error("TASK", f"_get_user_uid_by_task(): not found for task={task_uid}")
            raise RuntimeError(f"user_uid 未找到：task_uid={task_uid}")
        return str(row["user_uid"])

    def _resolve_input_dir(
        self,
        task_uid: str,
        source_kind: str,
        source: str,
        relative: Optional[str],
    ) -> Path:
        """
        输入目录解析：
          - dataset:  public_root/<source>
          - step:     workspace_root/<user_uid>/workspace/<task_uid>/<prev_step_uid>
          - direct:   Path(source)（允许绝对路径；相对路径按 CWD 解析）
          - relative: 追加到以上基路径上，禁止逃逸
        """
        log_info("IO", f"_resolve_input_dir(): task={task_uid}, kind={source_kind}, source={source}, relative={relative}")
        if source_kind not in ("dataset", "step", "direct"):
            raise RuntimeError(f"不支持的 source_kind: {source_kind}")

        if source_kind == "dataset":
            if Path(source).is_absolute():
                raise RuntimeError("dataset 模式下 source 不应为绝对路径")
            base = (self.public_root / source).resolve()

        elif source_kind == "step":
            try:
                prev_k = int(source)
            except Exception:
                raise RuntimeError(f"step 模式下 source 必须是步骤号(整数)：{source}")

            row = self.db.execute(
                "SELECT step_uid FROM steps "
                "WHERE task_uid = ? AND step_number = ? AND status = 'succeeded' "
                "ORDER BY rowid DESC LIMIT 1",
                (task_uid, prev_k),
            ).fetchone()
            log_info("IO", f"_resolve_input_dir(): query prev step succeeded row -> {bool(row)}")
            if not row:
                raise RuntimeError(f"未找到已成功的前置步骤：task={task_uid} step_number={prev_k}")
            prev_step_uid = row["step_uid"]
            user_uid = self._get_user_uid_by_task(task_uid)
            base = (self.workspace_root / user_uid / "workspace" / task_uid / prev_step_uid).resolve()

        else:  # direct
            base = Path(source).expanduser().resolve()

        final = base
        if relative:
            rel = Path(relative)
            if rel.is_absolute():
                raise RuntimeError("relative 不应为绝对路径")
            final = (base / rel).resolve()
            try:
                final.relative_to(base)
            except Exception:
                raise RuntimeError(f"relative 导致路径逃逸：base={base}, final={final}")

        if not final.exists() or not final.is_dir():
            raise RuntimeError(f"输入目录不存在或不是目录：{final}")
        log_info("IO", f"_resolve_input_dir(): final={final}")
        return final

    def _alloc_step_uid_and_output_dir(self, task_uid: str) -> Tuple[str, Path]:
        """
        为新步骤实例分配 step_uid，并计算输出目录：
            workspace_root/<user_uid>/workspace/<task_uid>/<step_uid>
        不主动清空目录，若不存在则创建。
        """
        user_uid = self._get_user_uid_by_task(task_uid)
        step_uid = uuid.uuid4().hex
        out_dir = (self.workspace_root / user_uid / "workspace" / task_uid / step_uid).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        log_info("IO", f"_alloc_step_uid_and_output_dir(): task={task_uid}, step_uid={step_uid}, out_dir={out_dir}")
        return step_uid, out_dir

    # ---------- 产物导出（新增） ----------
    def _export_results(self, task_uid: str, step_uid: str) -> None:
        """
        将最后一步的输出目录内容复制到 workspace/<user_uid>/workspace/<task_uid>/results
        - 合并拷贝：已存在同名文件将覆盖；目录合并
        - 逐项拷贝并记录日志；失败项目跳过但不断流程
        """
        import shutil

        try:
            user_uid = self._get_user_uid_by_task(task_uid)
        except Exception as e:
            log_exception("RESULT", f"_export_results(): get user_uid failed task={task_uid}", e)
            return

        src_dir = (self.workspace_root / user_uid / "workspace" / task_uid / step_uid).resolve()
        dst_dir = (self.workspace_root / user_uid / "workspace" / task_uid / "results").resolve()
        try:
            if not src_dir.exists() or not src_dir.is_dir():
                log_warn("RESULT", f"_export_results(): src_dir invalid: {src_dir}")
                return
            dst_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log_exception("RESULT", f"_export_results(): prepare dst failed dst={dst_dir}", e)
            return

        log_info("RESULT", f"export begin: task={task_uid}, step_uid={step_uid}, src={src_dir}, dst={dst_dir}")

        try:
            for item in src_dir.iterdir():
                s = item
                d = dst_dir / item.name
                try:
                    if s.is_dir():
                        # Python 3.8+ dirs_exist_ok
                        shutil.copytree(s, d, dirs_exist_ok=True)
                        log_debug("RESULT", f"copytree OK: {s} -> {d}")
                    elif s.is_file():
                        # 确保父目录
                        d.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(s, d)
                        log_debug("RESULT", f"copy2 OK: {s} -> {d}")
                    else:
                        log_warn("RESULT", f"skip non-file/dir: {s}")
                except Exception as ie:
                    log_exception("RESULT", f"copy item failed: {s} -> {d}", ie)
                    # 不中断整体流程
                    continue
        except Exception as e:
            log_exception("RESULT", "iterate src_dir failed", e)
            return

        # 生成一个简单清单
        try:
            manifest = {
                "task_uid": task_uid,
                "from_step_uid": step_uid,
                "export_time": _now(),
                "src_dir": str(src_dir),
                "dst_dir": str(dst_dir),
            }
            (dst_dir / "_export_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            log_info("RESULT", f"export done: dst={dst_dir}")
        except Exception as e:
            log_exception("RESULT", "write export manifest failed", e)

    def _export_latest_results_for_task(self, task_uid: str) -> None:
        """
        找到该任务状态为 succeeded 的最大步骤号的 step_uid，并进行导出
        """
        try:
            row = self.db.execute(
                "SELECT step_uid FROM steps WHERE task_uid=? AND status='succeeded' "
                "AND step_number=(SELECT MAX(step_number) FROM steps WHERE task_uid=? AND status='succeeded') "
                "ORDER BY rowid DESC LIMIT 1",
                (task_uid, task_uid),
            ).fetchone()
            if not row:
                log_warn("RESULT", f"_export_latest_results_for_task(): no succeeded step found for task={task_uid}")
                return
            step_uid = str(row["step_uid"])
            self._export_results(task_uid, step_uid)
        except Exception as e:
            log_exception("RESULT", f"_export_latest_results_for_task(): query failed task={task_uid}", e)

    # ==================== 启动/恢复 + 主循环 ====================
    def start(self) -> None:
        """恢复数据库状态，构建队列，启动运行线程（主循环）。"""
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
        """请求停止运行线程，不影响 MCPExecutor。"""
        log_info("RUN", "stop(): stop_evt set, waiting thread")
        self._stop_evt.set()
        if self._runner_thread and self._runner_thread.is_alive():
            self._runner_thread.join(timeout=timeout)
        self._runner_thread = None
        log_info("RUN", "stop(): runner thread joined")

    def close(self) -> None:
        """优雅关闭：停止主循环 → 关闭 MCP → 关闭 DB。"""
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
            "SELECT step_uid, task_uid, step_number FROM steps WHERE status = 'running'"
        )
        rows = cur.fetchall()
        log_info("RECOVER", f"steps.running count={len(rows)} -> mark failed")
        for r in rows:
            step_uid = r["step_uid"]
            task_uid = r["task_uid"]
            step_number = r["step_number"]
            self.db.execute(
                "UPDATE steps SET status='failed' WHERE step_uid = ?", (step_uid,)
            )
            self.db.execute(
                "UPDATE tasks SET failed_step_number=?, failed_step_uid=? WHERE task_uid=?",
                (step_number, step_uid, task_uid),
            )

        self.db.execute(
            "UPDATE tasks SET status='queued', current_step_number=NULL, current_step_uid=NULL "
            "WHERE status='running'"
        )
        log_info("RECOVER", "tasks.running -> queued")

        self.db.execute(
            "UPDATE tasks SET last_completed_step = COALESCE((SELECT MAX(step_number) FROM steps "
            "WHERE steps.task_uid = tasks.task_uid AND steps.status = 'succeeded'), 0)"
        )
        log_info("RECOVER", "recalc last_completed_step done")

        self.db.commit()
        log_info("RECOVER", "recover_on_startup(): committed")

    def _load_queued_tasks_into_queue(self) -> None:
        """将所有 queued 任务入内存队列（避免重复）"""
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
                if self.task_running is None:
                    # A) 没有任务在跑：从队列取一个（若空则 5s 后再看）
                    try:
                        task_uid = self.task_queue.get_nowait()
                        log_info("LOOP", f"A-POP: got task_uid={task_uid}")
                    except Empty:
                        log_debug("LOOP", "A-IDLE: queue empty, sleep 5s")
                        time.sleep(5.0)
                        continue

                    task = self._get_task(task_uid)
                    if task is None:
                        log_warn("LOOP", f"A-DROP: task not found in DB, task_uid={task_uid}")
                        continue

                    if task["status"] != "queued":
                        log_info("LOOP", f"A-DROP: status={task['status']} != queued")
                        continue

                    last_done = int(task["last_completed_step"] or 0)
                    total = int(task["total_steps"] or 0)
                    log_info("LOOP", f"A-CHECK: last_done={last_done}, total={total}")

                    if last_done >= total:
                        # 任务已完成但状态未标记，先导出再标记成功
                        self._export_latest_results_for_task(task_uid)
                        self.db.execute(
                            "UPDATE tasks SET status='succeeded', current_step_number=NULL, current_step_uid=NULL "
                            "WHERE task_uid=?",
                            (task_uid,),
                        )
                        self.db.commit()
                        log_info("LOOP", f"A-MARK: already complete -> succeeded, task={task_uid}")
                        continue

                    self.db.execute(
                        "UPDATE tasks SET status='running' WHERE task_uid=?", (task_uid,)
                    )
                    self.db.commit()
                    self.task_running = task_uid
                    log_info("LOOP", f"A-SET: task_running={task_uid}, status=running")
                    continue

                # B) 有任务在跑：确保确实有步骤在执行
                task_uid = self.task_running
                task = self._get_task(task_uid)
                if task is None:
                    log_error("LOOP", f"B-ERR: current task missing in DB, task_running={task_uid}")
                    self.task_running = None
                    continue

                last_done = int(task["last_completed_step"] or 0)
                total = int(task["total_steps"] or 0)
                log_info("LOOP", f"B-STATE: task={task_uid}, last_done={last_done}, total={total}")

                if last_done >= total:
                    # 可能是上一轮已把最后一步标成功，这里补导出并收尾
                    self._export_latest_results_for_task(task_uid)
                    self.db.execute(
                        "UPDATE tasks SET status='succeeded', current_step_number=NULL, current_step_uid=NULL "
                        "WHERE task_uid=?",
                        (task_uid,),
                    )
                    self.db.commit()
                    log_info("LOOP", f"B-MARK: task complete -> succeeded, task={task_uid}")
                    self.task_running = None
                    continue

                step_row = self.db.execute(
                    "SELECT * FROM steps WHERE task_uid=? AND status='running' ORDER BY rowid DESC LIMIT 1",
                    (task_uid,),
                ).fetchone()
                log_info("LOOP", f"B-CHECK-RUNNING: has_running={bool(step_row)}")

                if step_row:
                    run_id = step_row["run_id"]
                    st = self._safe_get_status(run_id)
                    done = bool(st.get("done")) if isinstance(st, dict) else False
                    exit_code = st.get("exit_code") if isinstance(st, dict) else None

                    log_info("LOOP", f"B-POLL: run_id={run_id}, done={done}, exit_code={exit_code}")

                    def _is_zero(x):
                        try:
                            return int(x) == 0
                        except Exception:
                            return False

                    if done and _is_zero(exit_code):
                        # 成功：落盘 steps=Succeeded、tasks.last_completed_step=step_number
                        self.db.execute("UPDATE steps SET status='succeeded' WHERE step_uid=?", (step_row["step_uid"],))
                        self.db.execute(
                            "UPDATE tasks SET last_completed_step=?, current_step_number=NULL, current_step_uid=NULL WHERE task_uid=?",
                            (step_row["step_number"], task_uid),
                        )
                        self.db.commit()
                        log_info("LOOP", f"B-DONE-OK: step_number={step_row['step_number']} succeeded; will create next")

                        # 如果这是最后一个步骤，立即导出产物并标记任务成功
                        if int(step_row["step_number"]) >= total:
                            self._export_results(task_uid, step_row["step_uid"])
                            self.db.execute(
                                "UPDATE tasks SET status='succeeded' WHERE task_uid=?",
                                (task_uid,),
                            )
                            self.db.commit()
                            log_info("RESULT", f"final step succeeded -> exported + task succeeded, task={task_uid}")
                            self.task_running = None
                            time.sleep(0.05)
                            continue

                        time.sleep(0.05)
                        continue

                    elif done and exit_code is not None and not _is_zero(exit_code):
                        # 失败
                        self.db.execute("UPDATE steps SET status='failed' WHERE step_uid=?", (step_row["step_uid"],))
                        self.db.execute(
                            "UPDATE tasks SET status='failed', failed_step_number=?, failed_step_uid=?, "
                            "current_step_number=NULL, current_step_uid=NULL WHERE task_uid=?",
                            (step_row["step_number"], step_row["step_uid"], task_uid),
                        )
                        self.db.commit()
                        log_error("LOOP", f"B-DONE-FAIL: step_number={step_row['step_number']} exit_code={exit_code}")
                        self.task_running = None
                        time.sleep(0.05)
                        continue

                    elif done and exit_code is None:
                        # 边缘竞态：给一次“短暂确认”
                        log_debug("LOOP", "B-POLL: done=True but exit_code=None, short sleep for confirm")
                        time.sleep(0.05)
                        st2 = self._safe_get_status(run_id)
                        ec2 = st2.get("exit_code") if isinstance(st2, dict) else None
                        if _is_zero(ec2):
                            self.db.execute("UPDATE steps SET status='succeeded' WHERE step_uid=?", (step_row["step_uid"],))
                            self.db.execute(
                                "UPDATE tasks SET last_completed_step=?, current_step_number=NULL, current_step_uid=NULL WHERE task_uid=?",
                                (step_row["step_number"], task_uid),
                            )
                            self.db.commit()
                            log_info("LOOP", f"B-DONE-OK2: confirm success step_number={step_row['step_number']}")

                            if int(step_row["step_number"]) >= total:
                                self._export_results(task_uid, step_row["step_uid"])
                                self.db.execute(
                                    "UPDATE tasks SET status='succeeded' WHERE task_uid=?",
                                    (task_uid,),
                                )
                                self.db.commit()
                                log_info("RESULT", f"final step succeeded (confirm) -> exported + task succeeded, task={task_uid}")
                                self.task_running = None
                                time.sleep(0.05)
                                continue

                            time.sleep(0.05)
                            continue
                        elif ec2 is not None and not _is_zero(ec2):
                            self.db.execute("UPDATE steps SET status='failed' WHERE step_uid=?", (step_row["step_uid"],))
                            self.db.execute(
                                "UPDATE tasks SET status='failed', failed_step_number=?, failed_step_uid=?, "
                                "current_step_number=NULL, current_step_uid=NULL WHERE task_uid=?",
                                (step_row["step_number"], step_row["step_uid"], task_uid),
                            )
                            self.db.commit()
                            log_error("LOOP", f"B-DONE-FAIL2: confirm fail step_number={step_row['step_number']} ec2={ec2}")
                            self.task_running = None
                            time.sleep(0.05)
                            continue
                        else:
                            log_debug("LOOP", "B-POLL: still unclear, sleep 0.1s and continue")
                            time.sleep(0.1)
                            continue
                    else:
                        # 未完成
                        time.sleep(0.2)
                        continue

                # 没有运行中的步骤：创建下一步实例
                next_k = (int(task["last_completed_step"] or 0)) + 1
                if next_k > total:
                    # 保险：再判一次完成，做导出并收尾
                    self._export_latest_results_for_task(task_uid)
                    self.db.execute(
                        "UPDATE tasks SET status='succeeded', current_step_number=NULL, current_step_uid=NULL "
                        "WHERE task_uid=?",
                        (task_uid,),
                    )
                    self.db.commit()
                    log_info("LOOP", f"B-MARK-AGAIN: completed on recheck -> exported + succeeded, task={task_uid}")
                    self.task_running = None
                    continue

                step_def = self._get_step_def_from_request(task, next_k)
                log_info("LOOP", f"B-NEXT: next_k={next_k}, step_def_exists={bool(step_def)}")
                if step_def is None:
                    self._fail_task_with_step(task_uid=task_uid, step_number=next_k, step_uid=None)
                    self.task_running = None
                    log_error("LOOP", f"B-ERR: step_def missing, mark task failed, task={task_uid}, next_k={next_k}")
                    continue

                # 解析输入目录
                try:
                    in_dir = self._resolve_input_dir(
                        task_uid=task_uid,
                        source_kind=str(step_def.get("source_kind") or step_def.get("sourceKind")),
                        source=str(step_def.get("source")),
                        relative=step_def.get("relative"),
                    )
                except Exception as e:
                    self._fail_task_with_step(task_uid=task_uid, step_number=next_k, step_uid=None)
                    self.task_running = None
                    log_exception("LOOP", f"B-ERR: resolve input dir failed for next_k={next_k}", e)
                    continue

                step_uid, out_dir = self._alloc_step_uid_and_output_dir(task_uid)

                tool_name = str(step_def.get("tool_name") or step_def.get("toolName"))
                if not tool_name:
                    self._fail_task_with_step(task_uid=task_uid, step_number=next_k, step_uid=step_uid)
                    self.task_running = None
                    log_error("LOOP", f"B-ERR: empty tool_name, task={task_uid}, next_k={next_k}")
                    continue

                additional_params = step_def.get("additional_params") or step_def.get("additionalParams") or {}
                if isinstance(additional_params, str):
                    try:
                        additional_params = json.loads(additional_params)
                    except Exception:
                        additional_params = {}

                args = dict(additional_params or {})
                args.setdefault("in_dir", str(in_dir))
                args.setdefault("out_dir", str(out_dir))

                log_info("LOOP", f"B-CALL: tool={tool_name}, next_k={next_k}, in_dir={in_dir}, out_dir={out_dir}, "
                                  f"add_keys={list((additional_params or {}).keys())}")

                # 提交到 MCP：直到成功（demo 版，简单重试，间隔 0.5s）
                run_id = None
                retries = 0
                while run_id is None and not self._stop_evt.is_set():
                    try:
                        res = self.call_tool(tool_name, args)
                        if isinstance(res, dict) and "run_id" in res:
                            run_id = res["run_id"]
                        elif isinstance(res, dict) and "data" in res and isinstance(res["data"], dict) and "run_id" in res["data"]:
                            run_id = res["data"]["run_id"]
                        else:
                            try:
                                txt = res if isinstance(res, str) else ""
                                parsed = json.loads(txt) if txt else {}
                                if "run_id" in parsed:
                                    run_id = parsed["run_id"]
                            except Exception:
                                pass
                    except Exception as e:
                        log_exception("LOOP", f"B-CALL: call_tool exception (will retry) tool={tool_name}", e)

                    retries += 1
                    if run_id is None:
                        log_warn("LOOP", f"B-CALL: run_id missing (retry #{retries})")
                        time.sleep(0.5)

                    if retries >= 10 and run_id is None:
                        # 限制重试次数，避免无限重试
                        log_error("LOOP", f"B-CALL: run_id still None after {retries} retries, will fail step")
                        break

                if run_id is None:
                    self._fail_task_with_step(task_uid=task_uid, step_number=next_k, step_uid=step_uid)
                    self.task_running = None
                    log_error("LOOP", f"B-FAIL: cannot obtain run_id, task failed, task={task_uid}, step={next_k}")
                    continue

                self.db.execute(
                    "INSERT INTO steps (step_uid, task_uid, step_number, tool_name, source_kind, source, relative, run_id, additional_params, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running')",
                    (
                        step_uid, task_uid, next_k, tool_name,
                        str(step_def.get("source_kind") or step_def.get("sourceKind")),
                        str(step_def.get("source")),
                        step_def.get("relative"),
                        str(run_id),
                        json.dumps(additional_params or {}, ensure_ascii=False),
                    ),
                )
                self.db.execute(
                    "UPDATE tasks SET current_step_number=?, current_step_uid=?, status='running' WHERE task_uid=?",
                    (next_k, step_uid, task_uid),
                )
                self.db.commit()
                log_info("LOOP", f"B-STARTED: step running, task={task_uid}, step={next_k}, step_uid={step_uid}, run_id={run_id}")

                time.sleep(0.1)
                continue

            except Exception as e:
                log_exception("LOOP", "UNCAUGHT in main_loop iteration (sleep 0.3s)", e)
                time.sleep(0.3)
                continue

    # ---------- 工具方法 ----------
    def _get_task(self, task_uid: str) -> Optional[sqlite3.Row]:
        row = self.db.execute("SELECT * FROM tasks WHERE task_uid=?", (task_uid,)).fetchone()
        log_debug("TASK", f"_get_task(): task_uid={task_uid}, exists={bool(row)}")
        return row

    def _fail_task_with_step(self, task_uid: str, step_number: int, step_uid: Optional[str]) -> None:
        """标记任务失败，并填写失败步信息，清空 current_step_*。"""
        if step_uid:
            self.db.execute("UPDATE steps SET status='failed' WHERE step_uid=?", (step_uid,))
        self.db.execute(
            "UPDATE tasks SET status='failed', failed_step_number=?, failed_step_uid=?, "
            "current_step_number=NULL, current_step_uid=NULL WHERE task_uid=?",
            (step_number, step_uid, task_uid),
        )
        self.db.commit()
        log_error("TASK", f"_fail_task_with_step(): task={task_uid}, step_number={step_number}, step_uid={step_uid}")

    def _safe_get_status(self, run_id: str) -> Dict[str, Any]:
        """调用 get_status 工具；支持 dict 和 JSON 字符串；异常时返回空 dict。"""
        try:
            res = self.call_tool("get_status", {"run_id": run_id})

            # 直接是 dict
            if isinstance(res, dict):
                done = res.get("done")
                exit_code = res.get("exit_code")
                log_debug("MCP", f"_safe_get_status(): run_id={run_id}, done={done}, exit_code={exit_code}")
                return res

            # 是 JSON 字符串或 bytes，尝试解析
            if isinstance(res, (str, bytes)):
                txt = res.decode("utf-8", errors="ignore") if isinstance(res, bytes) else res
                txt_stripped = txt.strip()
                # 仅当看起来像 JSON 时再解析，避免误伤纯日志文本
                if txt_stripped.startswith("{") or txt_stripped.startswith("["):
                    try:
                        obj = json.loads(txt_stripped)
                        if isinstance(obj, dict):
                            done = obj.get("done")
                            exit_code = obj.get("exit_code")
                            log_debug("MCP",
                                      f"_safe_get_status(): (parsed str) run_id={run_id}, done={done}, exit_code={exit_code}")
                            return obj
                        else:
                            log_warn("MCP",
                                     f"_safe_get_status(): parsed JSON is not a dict (type={type(obj).__name__})")
                    except Exception as je:
                        log_warn("MCP", f"_safe_get_status(): json parse failed: {je!r}; preview={txt_stripped[:200]}")

            # 其他类型或解析失败
            log_warn("MCP", f"_safe_get_status(): unsupported type={type(res).__name__}; return empty dict")
            return {}
        except Exception as e:
            log_exception("MCP", f"_safe_get_status(): exception for run_id={run_id}", e)
            return {}

    def _get_step_def_from_request(self, task_row: sqlite3.Row, step_number: int) -> Optional[Dict[str, Any]]:
        """从 tasks.request_json 解析并取出指定步骤号的定义。允许两种结构：list 或 dict。"""
        req = task_row["request_json"]
        if not req:
            log_warn("TASK", "_get_step_def_from_request(): empty request_json")
            return None
        try:
            obj = json.loads(req) if isinstance(req, (str, bytes)) else req
        except Exception as e:
            log_exception("TASK", "_get_step_def_from_request(): json loads failed", e)
            return None

        steps = obj.get("steps") if isinstance(obj, dict) else None
        if steps is None:
            log_warn("TASK", "_get_step_def_from_request(): 'steps' missing")
            return None

        if isinstance(steps, list):
            for s in steps:
                try:
                    if int(s.get("step_number") or s.get("stepNumber")) == int(step_number):
                        log_debug("TASK", f"_get_step_def_from_request(): list found step_number={step_number}")
                        return s
                except Exception:
                    continue

        if isinstance(steps, dict):
            s = steps.get(str(step_number)) or steps.get(step_number)
            if isinstance(s, dict):
                s.setdefault("step_number", step_number)
                log_debug("TASK", f"_get_step_def_from_request(): dict found step_number={step_number}")
                return s

        log_warn("TASK", f"_get_step_def_from_request(): step_number={step_number} not found")
        return None


# 兼容：某些环境缺少 os 的情况下（上面日志初始化里用到了）
import os  # 放在文件尾，确保已导入
