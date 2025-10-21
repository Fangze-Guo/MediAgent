# mediagent/modules/dataset_manager.py
from __future__ import annotations
"""
dataset_manager.py —— DEMO 版（异步）
- 表：dataset_catalog（9个字段）
- 接口：
    async overview() -> {"ok": bool, "text": str}
    async focus(dataset_name, user_need_text) -> {"ok": bool, "text": str}

特性：
- DB：优先 aiosqlite，缺失则用 asyncio.to_thread + sqlite3
- LLM：优先 AsyncOpenAI，缺失/未配则降级本地摘要
- 文件读取：放在线程池中执行，避免阻塞
"""

import csv
import io
import json
import os
import sqlite3
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from mediagent.paths import in_data

# ===================== 需配置路径 =====================
DATASET_FILES_ROOT: Path = in_data("files","public","dataset_info")
DATASET_DB_PATH: Path = in_data("db","app.sqlite3")

# ===================== LLM（OpenAI 兼容网关） =====================
LLM_MODEL: Optional[str] = "deepseek-chat"
LLM_BASE_URL: Optional[str] = "https://api.deepseek.com/v1"
LLM_API_KEY: Optional[str] = "sk-d0e27c4c590a454e8284309067c03f04"
LLM_TIMEOUT: float = 60.0

# ===================== 读取与大小控制 =====================
MAX_TEXT_BYTES_FOR_LLM: int = 2 * 1024 * 1024  # 保留常量
CSV_ENCODING_CANDIDATES: Tuple[str, ...] = ("utf-8-sig", "utf-8", "gbk", "latin-1")
SAMPLE_HEAD_ROWS: int = 200
LOCAL_SUMMARY_ROWS: int = 50

# 🔹 Map-Reduce 触发与分块策略（不改提示词，仅内部控制）
SINGLEPASS_MAX_BYTES: int = 512 * 1024      # 超过则走分块
CHUNK_TARGET_BYTES: int = 256 * 1024        # 每块目标大小（按行对齐）
CHUNK_HARD_MAX_BYTES: int = 320 * 1024      # 单块硬上限（行太长时兜底）

# ===================== 表结构（说明） =====================
"""
CREATE TABLE IF NOT EXISTS dataset_catalog (
  dataset_name         TEXT PRIMARY KEY,
  case_count           INTEGER,
  clinical_data_desc   TEXT,
  text_data_desc       TEXT,
  imaging_data_desc    TEXT,
  pathology_data_desc  TEXT,
  genomics_data_desc   TEXT,
  annotation_desc      TEXT,
  notes                TEXT
);
"""

# ===================== 数据类 =====================

@dataclass
class CatalogRow:
    dataset_name: str
    case_count: Optional[int]
    clinical_data_desc: Optional[str]
    text_data_desc: Optional[str]
    imaging_data_desc: Optional[str]
    pathology_data_desc: Optional[str]
    genomics_data_desc: Optional[str]
    annotation_desc: Optional[str]
    notes: Optional[str]

# ===================== 对外接口（异步） =====================

async def overview(
    *,
    db_path: Optional[Path] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        rows = await _fetch_catalog_rows_async(db_path or DATASET_DB_PATH, limit=limit)
        if not rows:
            return {"ok": True, "text": "当前数据库中没有可用的数据集条目。"}

        parts: List[str] = [f"共收录数据集 {len(rows)} 个。"]
        for i, r in enumerate(rows, 1):
            cc = f"{r.case_count}例" if isinstance(r.case_count, int) else "例数未知"
            im = _short(r.imaging_data_desc)
            tx = _short(r.text_data_desc)
            pa = _short(r.pathology_data_desc)
            ge = _short(r.genomics_data_desc)
            an = _short(r.annotation_desc)
            parts.append(
                f"{i}. {r.dataset_name}：{cc}；影像[{im}]；文本[{tx}]；病理[{pa}]；基因[{ge}]；标注[{an}]。"
            )
        return {"ok": True, "text": "\n".join(parts)}
    except Exception as e:
        return {"ok": False, "text": f"读取 catalog 失败：{e!r}"}


async def focus(
    dataset_name: str,
    user_need_text: str,
    *,
    db_path: Optional[Path] = None,  # 预留
) -> Dict[str, Any]:
    """
    异步定点查询：
    - 定位并读取 <dataset_name>.csv/.xlsx（优先 CSV）
    - 将“完整表格内容”+ 提示 + 用户需求交给 LLM
    - 当全文过大时，自动 Map-Reduce（不改提示词），确保覆盖全部内容
    - 失败/未配则本地启发式摘要
    """
    try:
        # 1) 定位文件
        path, fmt = await asyncio.to_thread(_locate_file, dataset_name)
        if path is None:
            return {"ok": False, "text": f"未找到数据文件：{dataset_name}.csv/.xlsx"}

        # 2) 读取完整文本
        if fmt == "csv":
            full_text, _trunc, info = await asyncio.to_thread(_read_csv_full_text, path)
        else:
            full_text, _trunc, info = await asyncio.to_thread(_read_xlsx_full_tsv, path)

        # 3) 组织你的“固定提示词”（保持原样）
        system_prompt = (
            "你是医疗数据助手。请根据给定的表格内容与用户需求，输出一段简短总结（100~200字），表格是对应同名数据集的信息表，用户想了解的是数据集的情况，你可以从表格出发进行合理推测。"
            "要求：1) 不要逐行罗列原始数据；2) 提炼列名、关键信息与可用性；3) 若信息不足，说明缺口；"
            "4) 中文输出；5) 不包含表格源码。"
        )

        # 4) 判断是否需要 Map-Reduce
        total_bytes = len(full_text.encode("utf-8"))
        if await _llm_available_async():
            if total_bytes <= SINGLEPASS_MAX_BYTES:
                # 单轮直出（完整文本）
                user_prompt = _build_user_prompt_for_llm(
                    dataset_name=dataset_name,
                    user_need_text=user_need_text,
                    file_text=full_text,
                    truncated=False,
                    file_info={**info, "pipeline": "single-pass", "bytes": total_bytes},
                )
                out = await _call_llm_async(system_prompt, user_prompt)
                if out:
                    return {"ok": True, "text": out.strip()}
            else:
                # 🔹 Map-Reduce 路径（不改提示词）
                merged = await _map_reduce_summarize(
                    system_prompt=system_prompt,
                    dataset_name=dataset_name,
                    user_need_text=user_need_text,
                    full_text=full_text,
                    base_file_info=info,
                )
                if merged:
                    return {"ok": True, "text": merged.strip()}

        # 5) LLM 不可用或失败：本地摘要
        local_text = await asyncio.to_thread(
            _local_summarize, dataset_name, user_need_text, full_text, info, max_rows=LOCAL_SUMMARY_ROWS
        )
        return {"ok": True, "text": local_text}
    except Exception as e:
        return {"ok": False, "text": f"处理失败：{e!r}"}

# ===================== DB 读取（优先 aiosqlite） =====================

async def _fetch_catalog_rows_async(db_path: Path, limit: Optional[int]) -> List[CatalogRow]:
    db_path = Path(db_path).expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"catalog 数据库不存在：{db_path}")

    try:
        import aiosqlite  # type: ignore
    except Exception:
        return await asyncio.to_thread(_fetch_catalog_rows_sync, db_path, limit)

    sql = (
        "SELECT dataset_name, case_count, clinical_data_desc, text_data_desc, "
        "imaging_data_desc, pathology_data_desc, genomics_data_desc, annotation_desc, notes "
        "FROM dataset_catalog "
        "ORDER BY dataset_name ASC"
    )
    rows: List[CatalogRow] = []
    async with aiosqlite.connect(db_path.as_posix()) as conn:
        async with conn.execute(sql) as cur:
            i = 0
            async for dn, cc, cl, tx, im, pa, ge, an, no in cur:
                rows.append(
                    CatalogRow(
                        dataset_name=str(dn),
                        case_count=int(cc) if cc is not None else None,
                        clinical_data_desc=_nz(cl),
                        text_data_desc=_nz(tx),
                        imaging_data_desc=_nz(im),
                        pathology_data_desc=_nz(pa),
                        genomics_data_desc=_nz(ge),
                        annotation_desc=_nz(an),
                        notes=_nz(no),
                    )
                )
                i += 1
                if limit is not None and i >= limit:
                    break
    return rows


def _fetch_catalog_rows_sync(db_path: Path, limit: Optional[int]) -> List[CatalogRow]:
    sql = (
        "SELECT dataset_name, case_count, clinical_data_desc, text_data_desc, "
        "imaging_data_desc, pathology_data_desc, genomics_data_desc, annotation_desc, notes "
        "FROM dataset_catalog "
        "ORDER BY dataset_name ASC"
    )
    rows: List[CatalogRow] = []
    with sqlite3.connect(db_path.as_posix(), check_same_thread=False) as conn:
        cur = conn.execute(sql)
        for i, (dn, cc, cl, tx, im, pa, ge, an, no) in enumerate(cur):
            rows.append(
                CatalogRow(
                    dataset_name=str(dn),
                    case_count=int(cc) if cc is not None else None,
                    clinical_data_desc=_nz(cl),
                    text_data_desc=_nz(tx),
                    imaging_data_desc=_nz(im),
                    pathology_data_desc=_nz(pa),
                    genomics_data_desc=_nz(ge),
                    annotation_desc=_nz(an),
                    notes=_nz(no),
                )
            )
            if limit is not None and i + 1 >= limit:
                break
    return rows

# ===================== 文件定位与读取 =====================

def _locate_file(dataset_name: str) -> Tuple[Optional[Path], Optional[str]]:
    root = DATASET_FILES_ROOT.expanduser().resolve()
    csv_path = root / f"{dataset_name}.csv"
    xlsx_path = root / f"{dataset_name}.xlsx"
    if csv_path.exists():
        return csv_path, "csv"
    if xlsx_path.exists():
        return xlsx_path, "xlsx"
    return None, None


def _detect_csv_encoding(p: Path) -> str:
    for enc in CSV_ENCODING_CANDIDATES:
        try:
            with p.open("r", encoding=enc) as f:
                f.read(1024)
            return enc
        except Exception:
            continue
    return "utf-8"

def _read_csv_full_text(p: Path) -> Tuple[str, bool, Dict[str, Any]]:
    enc = _detect_csv_encoding(p)
    txt = p.read_text(encoding=enc)
    return txt, False, {"format": "csv", "encoding": enc, "size_bytes": p.stat().st_size, "note": "full_text"}

def _read_xlsx_full_tsv(p: Path) -> Tuple[str, bool, Dict[str, Any]]:
    try:
        import openpyxl  # type: ignore
    except Exception:
        msg = f"(提示) 未安装 openpyxl，无法读取 {p.name} 的内容。请安装 openpyxl。"
        return msg, False, {"format": "xlsx", "error": "openpyxl_missing", "size_bytes": p.stat().st_size}

    from openpyxl import load_workbook  # type: ignore
    wb = load_workbook(p.as_posix(), read_only=True, data_only=True)
    sheetnames = wb.sheetnames
    if not sheetnames:
        try:
            wb.close()
        except Exception:
            pass
        return "(空表)", False, {"format": "xlsx", "sheets": 0}
    ws = wb[sheetnames[0]]

    out = io.StringIO()
    for row in ws.iter_rows(values_only=True):
        cells = [("" if v is None else str(v)).replace("\r", " ").replace("\n", " ") for v in row]
        out.write("\t".join(cells) + "\n")
    tsv = out.getvalue()
    try:
        wb.close()
    except Exception:
        pass
    return tsv, False, {"format": "xlsx", "sheet": sheetnames[0], "size_bytes": p.stat().st_size, "note": "full_text"}

# ===================== LLM（异步）与降级摘要 =====================

async def _llm_available_async() -> bool:
    if not LLM_MODEL:
        return False
    try:
        from openai import AsyncOpenAI  # type: ignore
    except Exception:
        return False
    return True

async def _call_llm_async(system_prompt: str, user_prompt: str) -> Optional[str]:
    try:
        from openai import AsyncOpenAI  # type: ignore
        client = AsyncOpenAI(
            api_key=(LLM_API_KEY or "lm-studio"),
            base_url=(LLM_BASE_URL or None),
            timeout=LLM_TIMEOUT,
        )
        resp = await client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        txt = (resp.choices[0].message.content or "").strip()
        return txt or None
    except Exception:
        return None

def _build_user_prompt_for_llm(
    *,
    dataset_name: str,
    user_need_text: str,
    file_text: str,
    truncated: bool,
    file_info: Dict[str, Any],
) -> str:
    info = json.dumps(file_info, ensure_ascii=False)
    tip = "（以下内容可能为采样片段）" if truncated else "（以下为完整内容或较完整片段）"
    return (
        f"【用户需求】\n{user_need_text}\n\n"
        f"【数据集名】\n{dataset_name}\n\n"
        f"【文件信息】\n{info}\n\n"
        f"【表格文本】{tip}\n{file_text}"
    )

def _local_summarize(
    dataset_name: str,
    user_need_text: str,
    file_text: str,
    file_info: Dict[str, Any],
    *,
    max_rows: int = 50,
) -> str:
    lines = [ln for ln in (file_text or "").splitlines() if ln.strip()]
    head = lines[:max_rows]
    delimiter = "\t" if ("\t" in head[0] if head else False) else ","
    cols = head[0].split(delimiter) if head else []
    num_cols = len(cols)
    sample_hint = f"已采样前{len(head)}行" if head else "未能采样"
    info_hint = f"格式 {file_info.get('format')}, 估计大小 {file_info.get('size_bytes','?')} 字节"
    cols_short = ", ".join(cols[:10]) + ("..." if len(cols) > 10 else "")
    return (
        f"数据集 {dataset_name} 的简要摘要（本地估计）:\n"
        f"- {info_hint}；{sample_hint}\n"
        f"- 估计列数：{num_cols}；部分列名：{cols_short if cols else '未知'}\n"
        f"- 你的需求：{user_need_text}\n"
        f"若需更详细摘要，请配置 DATASET_LLM_* 并/或缩小数据范围。"
    )

# 🔹 Map-Reduce 实现（不改你的提示词） =====================

def _split_text_by_bytes_linesafe(text: str, target_bytes: int, hard_max: int) -> List[str]:
    """按字节大小切分，尽量在行边界处断开。"""
    lines = text.splitlines(keepends=True)
    chunks: List[str] = []
    buf: List[str] = []
    buf_bytes = 0
    for ln in lines:
        ln_b = len(ln.encode("utf-8"))
        if buf and (buf_bytes + ln_b > target_bytes):
            # 如果单行超长且缓冲为空，硬切
            if buf_bytes == 0 and ln_b > hard_max:
                chunks.append(ln[:hard_max].encode("utf-8", "ignore").decode("utf-8", "ignore"))
                rest = ln[hard_max:]
                if rest:
                    lines.insert(0, rest)  # 继续处理剩余部分
                continue
            chunks.append("".join(buf))
            buf, buf_bytes = [ln], ln_b
        else:
            buf.append(ln)
            buf_bytes += ln_b
        if buf_bytes >= hard_max:
            chunks.append("".join(buf))
            buf, buf_bytes = [], 0
    if buf:
        chunks.append("".join(buf))
    return chunks

async def _map_reduce_summarize(
    *,
    system_prompt: str,
    dataset_name: str,
    user_need_text: str,
    full_text: str,
    base_file_info: Dict[str, Any],
) -> Optional[str]:
    # 切块
    chunks = _split_text_by_bytes_linesafe(full_text, CHUNK_TARGET_BYTES, CHUNK_HARD_MAX_BYTES)
    if not chunks:
        return None

    # Map 阶段：每块各自调用一次同样的提示词
    part_summaries: List[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        file_info = {
            **base_file_info,
            "pipeline": "map-reduce",
            "stage": "map",
            "chunk_index": idx,
            "chunks_total": len(chunks),
            "bytes": len(chunk.encode("utf-8")),
        }
        user_prompt = _build_user_prompt_for_llm(
            dataset_name=dataset_name,
            user_need_text=user_need_text,
            file_text=chunk,
            truncated=False,
            file_info=file_info,
        )
        out = await _call_llm_async(system_prompt, user_prompt)
        if not out:
            continue
        part_summaries.append(f"[第{idx}/{len(chunks)}块摘要]\n{out.strip()}")

    if not part_summaries:
        return None

    # Reduce 阶段：把所有分块摘要合并为“文件文本”，再次调用同样的提示词生成最终总结
    merged_text = "\n\n".join(part_summaries)
    reduce_info = {
        **base_file_info,
        "pipeline": "map-reduce",
        "stage": "reduce",
        "chunks_total": len(chunks),
        "bytes": len(merged_text.encode("utf-8")),
    }
    final_user_prompt = _build_user_prompt_for_llm(
        dataset_name=dataset_name,
        user_need_text=user_need_text,
        file_text=merged_text,
        truncated=False,
        file_info=reduce_info,
    )
    final = await _call_llm_async(system_prompt, final_user_prompt)
    return final

# ===================== 工具函数 =====================

def _nz(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None

def _short(x: Optional[str], n: int = 120) -> str:
    if not x:
        return "无"
    s = str(x).strip().replace("\n", " ")
    return (s[:n] + "…") if len(s) > n else s

def _safe_cell(v: Any) -> str:
    s = "" if v is None else str(v)
    return s.replace("\r", " ").replace("\n", " ")

# ===================== 命令行（异步） =====================

async def _amain(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="dataset_manager DEMO（overview / focus, async）")
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("overview", help="读取 catalog 并生成总览文本")
    p1.add_argument("--db", type=str, default=str(DATASET_DB_PATH), help="SQLite DB 路径")
    p1.add_argument("--limit", type=int, default=None, help="最多读取的条数")

    p2 = sub.add_parser("focus", help="针对数据集做定点查询并生成短摘要")
    p2.add_argument("--name", required=True, help="数据集名（同名 csv/xlsx）")
    p2.add_argument("--need", required=True, help="用户本次需求（自然语言）")

    args = p.parse_args(argv)
    if args.cmd == "overview":
        res = await overview(db_path=Path(args.db), limit=args.limit)
    else:
        res = await focus(dataset_name=args.name, user_need_text=args.need)

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    asyncio.run(_amain())
