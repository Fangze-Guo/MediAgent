#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_dataset_manager_simple.py —— 最小异步测试脚本
直接调用 mediagent.modules.dataset_manager 的 overview() 与 focus()
使用 dataset_manager.py 内已配置的默认路径与数据库。

运行方式：
    在 PyCharm 里直接点击 “Run 当前文件” 即可。
"""

import asyncio
import json
from mediagent.modules import dataset_manager as dm


# ======== 在这里改测试参数 ========
DATASET_NAME = "big_test"   # 你数据库中已有的条目名
USER_NEED_TEXT = "该数据集是否存在数据缺失"
# ===============================


async def main():
    print("=== 测试 overview() ===")
    overview_res = await dm.overview()
    print(json.dumps(overview_res, ensure_ascii=False, indent=2))

    print("\n=== 测试 focus() ===")
    focus_res = await dm.focus(dataset_name=DATASET_NAME, user_need_text=USER_NEED_TEXT)
    print(json.dumps(focus_res, ensure_ascii=False, indent=2))

    print("\n=== 测试结束 ===")


if __name__ == "__main__":
    asyncio.run(main())
