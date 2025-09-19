# test_conversation_manager_vars.py
import asyncio
import json
import sys
import random
import string
from pathlib import Path
from typing import Any, Dict, List
from mediagent.paths import in_data

# ====================== 你只需要改这里 ======================
DB_PATH      = in_data("db","app.sqlite3")    # 你的 SQLite 数据库文件（已存在）
CONV_ROOT    = in_data("conversations")   # 对话根目录（需存在且可写）
TEST_UID     = "6127016735"               # 用于测试的用户 UID
ENSURE_UID   = True                          # 若 users 表存在且没有该 uid，则插入一条记录
USE_SUBDIR   = True                          # 是否在根目录下新建隔离子目录（推荐 True）
# ===========================================================

# ---------------- import ConversationManager (兼容多路径) ----------------
CM = None
_import_errors: List[str] = []
try:
    from mediagent.modules.conervsation_manager import ConversationManager  # 你给的导入路径（含拼写）
    CM = ConversationManager
except Exception as e:
    _import_errors.append(f"mediagent.modules.conervsation_manager: {e!r}")
    try:
        from mediagent.modules.conversation_manager import ConversationManager  # 可能是修正后的路径
        CM = ConversationManager
    except Exception as e2:
        _import_errors.append(f"mediagent.modules.conversation_manager: {e2!r}")
        try:
            from conversation_manager import ConversationManager  # 退回本地同目录
            CM = ConversationManager
        except Exception as e3:
            _import_errors.append(f"local conversation_manager: {e3!r}")

if CM is None:
    raise ImportError("无法导入 ConversationManager：\n" + "\n".join(" - " + s for s in _import_errors))

def pretty(title: str, obj: Dict[str, Any]):
    print(f"\n=== {title} ===")
    print(json.dumps(obj, ensure_ascii=False, indent=2))

async def ensure_uid_if_needed(db_path: Path, uid: str) -> None:
    """在 ENSURE_UID=True 时调用：若 users(uid) 不存在则插入；不创建表/不改 schema。"""
    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        # 确认 users 表存在（若不存在则抛错，按你的库结构为准）
        async with db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
        ) as cur:
            ok = await cur.fetchone()
        if not ok:
            raise RuntimeError("数据库中不存在 users 表，脚本不会创建 schema。")

        async with db.execute("SELECT 1 FROM users WHERE uid=? LIMIT 1", (uid,)) as cur:
            exists = (await cur.fetchone()) is not None
        if not exists:
            await db.execute("INSERT INTO users(uid) VALUES(?)", (uid,))
            await db.commit()

async def dump_conv_dir(conv_dir: Path):
    print(f"\n--- Dump conversation dir: {conv_dir} ---")
    if not conv_dir.exists():
        print("目录不存在。")
        return
    for p in sorted(conv_dir.glob("*.json")):
        try:
            print(f"[{p.name}]")
            print(p.read_text("utf-8"))
        except Exception as e:
            print(f"[{p.name}] 读取失败: {e!r}")

def rand_tag(n=6):
    alpha = string.ascii_lowercase + string.digits
    return "".join(random.choice(alpha) for _ in range(n))

async def run_tests():
    db_path = Path(DB_PATH).expanduser().resolve()
    root = Path(CONV_ROOT).expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在：{db_path}")
    if not root.exists():
        raise FileNotFoundError(f"对话根目录不存在：{root}")

    # 可选：确保 uid 存在（不建表）
    if ENSURE_UID:
        await ensure_uid_if_needed(db_path, TEST_UID)

    # 在给定 root 下新建隔离子目录（或直接使用 root）
    test_root = root / f"cm_test_{rand_tag()}" if USE_SUBDIR else root
    if USE_SUBDIR:
        test_root.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] 使用对话根目录: {test_root}")

    # 实例化
    cm = CM(database_path=str(db_path), conversation_root=str(test_root))

    # 1) 创建对话
    r_create = await cm.create_conversation(owner_uid=TEST_UID)
    pretty("创建对话", r_create)
    assert r_create.get("ok"), r_create
    conv_uid = r_create["conversation_uid"]

    # 2) 主流写入 + 查询
    assert (await cm.add_message_to_main(conv_uid, "hello main 1"))["ok"]
    assert (await cm.add_message_to_main(conv_uid, "hello main 2"))["ok"]
    r_get_main = await cm.get_messages(conv_uid, "main_chat")
    pretty("查询主流消息", r_get_main)
    assert r_get_main["ok"] and len(r_get_main["messages"]) == 2

    # 3) 子流写入（不存在即创建）
    assert (await cm.add_message_to_stream(conv_uid, "toolA", "A-1"))["ok"]
    assert (await cm.add_message_to_stream(conv_uid, "toolA", "A-2"))["ok"]
    assert (await cm.add_message_to_stream(conv_uid, "toolB", "B-1"))["ok"]
    pretty("查询 toolA", await cm.get_messages(conv_uid, "toolA"))
    pretty("查询 toolB", await cm.get_messages(conv_uid, "toolB"))

    # 4) 查询不存在目标流
    r_ghost = await cm.get_messages(conv_uid, "ghost")
    pretty("查询 ghost（应失败）", r_ghost)
    assert not r_ghost["ok"]

    # 5) 并发写入主流（验证锁）
    async def add_main(i: int):
        return await cm.add_message_to_main(conv_uid, f"main-concurrent-{i}")

    results = await asyncio.gather(*[asyncio.create_task(add_main(i)) for i in range(10)])
    ok_count = sum(1 for r in results if r.get("ok"))
    pretty("并发写入主流结果", {"ok_count": ok_count})
    assert ok_count == 10

    # 6) 并发后再查
    r_get_main2 = await cm.get_messages(conv_uid, "main_chat")
    pretty("并发后主流消息数", {"count": len(r_get_main2.get("messages", []))})
    assert len(r_get_main2.get("messages", [])) == 12  # 初始2 + 并发10

    # 7) 非法会话ID写入
    r_bad = await cm.add_message_to_main("NotExistConv", "bad")
    pretty("非法会话写入（应失败）", r_bad)
    assert not r_bad["ok"]

    # 8) dump 产物
    await dump_conv_dir(test_root / conv_uid)
    print("\n[✅] 测试完成。产物已写入：", test_root)

def main():
    # Windows 事件循环策略
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore
        except Exception:
            pass
    asyncio.run(run_tests())

if __name__ == "__main__":
    main()
