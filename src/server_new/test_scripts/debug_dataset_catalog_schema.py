#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
debug_dataset_catalog_schema.py
目的：
1. 确认我们连接到的 SQLite 路径是不是你预期的那一个
2. 打印 dataset_catalog 的列结构（PRAGMA table_info）
3. 手动执行和 overview() 同款的 SELECT，看看会不会报错
"""

import sqlite3
from pathlib import Path

# 根据实际工程 import
from mediagent.modules import dataset_manager

def main():
    db_path = Path(dataset_manager.DATASET_DB_PATH).expanduser().resolve()
    print("=== DB PATH (from dataset_manager.DATASET_DB_PATH) ===")
    print(db_path)
    print()

    if not db_path.exists():
        print("!!! 这个路径下的数据库文件不存在，说明我们脚本和你想的不在同一个库 !!!")
        return

    # 连接
    conn = sqlite3.connect(db_path.as_posix(), check_same_thread=False)
    cur = conn.cursor()

    print("=== PRAGMA table_info(dataset_catalog) ===")
    try:
        cur.execute("PRAGMA table_info(dataset_catalog)")
        rows = cur.fetchall()
        # rows: [ (cid, name, type, notnull, dflt_value, pk), ... ]
        for r in rows:
            print(r)
    except Exception as e:
        print("读取表结构失败：", repr(e))
    print()

    print("=== SAMPLE ROWS (SELECT * FROM dataset_catalog LIMIT 3) ===")
    try:
        cur.execute("SELECT * FROM dataset_catalog LIMIT 3")
        rows = cur.fetchall()
        print("共拿到", len(rows), "行")
        for r in rows:
            print(r)
    except Exception as e:
        print("读取行失败：", repr(e))
    print()

    print("=== TRY overview-style SELECT (with explicit column list) ===")
    try:
        cur.execute(
            """
            SELECT
                id,
                user_id,
                dataset_name,
                case_count,
                clinical_data_desc,
                text_data_desc,
                imaging_data_desc,
                pathology_data_desc,
                genomics_data_desc,
                annotation_desc,
                notes,
                has_data,
                has_description_file,
                data_path,
                description_path
            FROM dataset_catalog
            WHERE user_id = ? OR user_id = -1
            ORDER BY dataset_name ASC
            """,
            (5931999430,)  # 随便给一个user_uid做测试
        )
        rows = cur.fetchall()
        print("查询成功，返回行数:", len(rows))
        for r in rows:
            print(r)
    except Exception as e:
        print("SELECT 报错：", repr(e))
    print()

    conn.close()


if __name__ == "__main__":
    main()
