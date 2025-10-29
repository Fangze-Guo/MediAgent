#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_dataset_manager.py
目的：
1. 测 overview() 权限过滤、返回格式
2. 测 focus() 权限过滤、路径解析、摘要回退逻辑

使用前请确认：
- mediagent/modules/dataset_manager.py 已更新为新版本
- SQLite 数据库文件中已存在 dataset_catalog 表，且至少插入了若干条测试数据
  字段包括：
    id, user_id, dataset_name, case_count,
    clinical_data_desc, text_data_desc, imaging_data_desc, pathology_data_desc,
    genomics_data_desc, annotation_desc, notes,
    has_data, has_description_file, data_path, description_path

- dataset_manager.DATASET_DB_PATH 指向的 db 确实存在
- dataset_manager.DATASET_STORAGE_ROOT 指向的根目录下，能找到
  description_path 对应的实际文件（csv/xlsx），至少准备一条，否则 focus 会返回“尚未提供描述文件”
"""

import asyncio
from pathlib import Path

# === 根据你的工程实际路径来写 import ===
# 假设这个脚本位于 server_new/test_scripts/ 下，
# 而 mediagent 是 server_new/mediagent/
# 如果运行报 ModuleNotFoundError，请在运行前:
#   cd server_new
#   python test_scripts/test_dataset_manager.py
from mediagent.modules import dataset_manager


async def run_tests() -> None:
    print("=== 测试配置检查 ===")
    print(f"DB PATH: {dataset_manager.DATASET_DB_PATH}")
    print(f"STORAGE ROOT: {dataset_manager.DATASET_STORAGE_ROOT}")
    print()

    # 你可以根据需要改成你自己的测试用户ID
    # 场景约定：
    #   - 假设数据库里有若干条：
    #       user_id = 5931999430, id = 某些数字
    #     以及一些公共数据集 user_id = -1
    #
    # 如果你现在数据库里还没有这些用户，下面可以手动改成现有的 user_id
    test_user_uid = 5931999430

    print("=== 1) 调用 overview() ===")
    res_overview = await dataset_manager.overview(
        user_uid=test_user_uid,
        db_path=dataset_manager.DATASET_DB_PATH,
        limit=None,  # 也可以传个小数字比如 5
    )
    print("overview() 返回：")
    print(res_overview)
    print()

    if not res_overview.get("ok", False):
        print("overview() 失败，后续 focus() 测试可能无意义。")
        return

    items = res_overview.get("items", [])
    if not items:
        print("overview() 可访问items为空，数据库可能没有可见数据集，无法继续 focus 测试。")
        return

    # 选第一条可见数据集做后续 focus 测试
    first_item = items[0]
    dataset_id = first_item["id"]
    print(f"选择 dataset_id={dataset_id} (name={first_item.get('name')} is_public={first_item.get('is_public')}) 做 focus 测试")
    print()

    # 2) focus: 用户需求可以随便给一段中文
    user_need_text = "请总结一下这个数据集都包含了哪些信息、病例数量、以及主要可用字段。"

    print("=== 2) 调用 focus() ===")
    res_focus = await dataset_manager.focus(
        dataset_id=dataset_id,
        user_need_text=user_need_text,
        user_uid=test_user_uid,
        db_path=dataset_manager.DATASET_DB_PATH,
    )
    print("focus() 返回：")
    print(res_focus)
    print()

    # 额外校验：尝试越权访问
    # 我们模拟另一个用户（不是 -1 且不是 owner）来看看权限拒绝是否正常
    # 注意：如果 first_item 本身是公共数据集 (is_public=True)，这个越权测试应该仍然放行
    fake_other_user = 1111111111
    if fake_other_user != test_user_uid:
        print("=== 3) 调用 focus() 使用一个不同 user_uid，测试权限控制 ===")
        res_focus_other = await dataset_manager.focus(
            dataset_id=dataset_id,
            user_need_text="权限校验测试",
            user_uid=fake_other_user,
            db_path=dataset_manager.DATASET_DB_PATH,
        )
        print(f"focus() (user_uid={fake_other_user}) 返回：")
        print(res_focus_other)
        print()

    # 4) 一些健壮性测试：传不存在的 dataset_id
    print("=== 4) 调用 focus() 使用不存在的 dataset_id ===")
    res_focus_missing = await dataset_manager.focus(
        dataset_id=99999999,  # 大概率不存在
        user_need_text="不存在测试",
        user_uid=test_user_uid,
        db_path=dataset_manager.DATASET_DB_PATH,
    )
    print("focus() (dataset_id=99999999) 返回：")
    print(res_focus_missing)
    print()

    print("=== 测试完成 ===")


if __name__ == "__main__":
    # 为了保险起见，确保当前工作目录是 server_new/ 再跑
    # 例：python test_scripts/test_dataset_manager.py
    asyncio.run(run_tests())
