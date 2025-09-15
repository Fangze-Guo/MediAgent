# src/server_new/utils/init_db.py
from pathlib import Path
import sqlite3

def main():
    # 找到 server_new/data/db 路径
    root = Path(__file__).resolve().parents[1]   # 定位到 server_new/
    db_dir = root / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)

    db_path = db_dir / "app.sqlite3"

    # 连接数据库（如果不存在会自动创建），这里不建表
    with sqlite3.connect(db_path):
        pass

    print(f"空数据库已创建: {db_path}")

if __name__ == "__main__":
    main()
