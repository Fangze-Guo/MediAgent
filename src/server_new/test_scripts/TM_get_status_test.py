# tm_status_test.py
# 说明：
# - 仅用于测试 TaskManager.get_task_status() 功能
# - 不会启动 MCP，不会触发 list_tools，不会跑主循环
# - 只读取数据库中的 tasks/steps 状态

from __future__ import annotations
import sqlite3
import json
import time
import types
from pathlib import Path
from mediagent.paths import in_data

# === 手动填写 ===
DATABASE_FILE = in_data("db","app.sqlite3")  # 你的 SQLite 文件
TASK_UID      = "f7286750a3a749e3b946da2eb4f9fdea"                    # 要查询的任务ID
WATCH_MODE    = False                                       # True=每2秒刷新查看一次

# === 导入你的 TaskManager 和日志函数 ===
from mediagent.modules.task_manager import TaskManager, log_info, log_warn, log_error  # noqa: E402

def _bind_minimal_db_instance(db_path: str | Path) -> TaskManager:
    """构造一个最小可用的 TaskManager 实例：仅包含 db 与 _get_task。"""
    tm = TaskManager.__new__(TaskManager)  # 跳过 __init__
    tm.db = sqlite3.connect(str(db_path), check_same_thread=False)
    tm.db.row_factory = sqlite3.Row

    # 绑定一个最小版的 _get_task（与原类方法等价）
    def _get_task(self, task_uid: str):
        row = self.db.execute("SELECT * FROM tasks WHERE task_uid=?", (task_uid,)).fetchone()
        return row
    tm._get_task = types.MethodType(_get_task, tm)

    # 如果你的 get_task_status 用到了 log_*，这里已从模块导入，无需额外处理
    return tm

def main():
    db_path = Path(DATABASE_FILE).expanduser().resolve()
    if not db_path.exists():
        print(f"[ERR] DB 文件不存在: {db_path}")
        return

    tm = _bind_minimal_db_instance(db_path)

    def run_once():
        try:
            res = tm.get_task_status(TASK_UID)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"[ERR] get_task_status 调用失败: {e!r}")

    if not WATCH_MODE:
        run_once()
        return

    # 简易 watch 模式：每2秒刷新一次
    try:
        while True:
            print("=" * 80)
            print(time.strftime("%Y-%m-%d %H:%M:%S"))
            run_once()
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("\n[INFO] 停止 watch。")

if __name__ == "__main__":
    main()
