"""
LangGraph ReAct conversation agent for MediAgent.

LLM 自主决策是否需要调用工具查询知识库，而非每次都强制 RAG。
"""
from __future__ import annotations

import json
import logging
import mimetypes
import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field
from src.server_agent.agent.medical_report_agent import MedicalImageReportAgent
from src.server_agent.mapper.paths import in_data
from src.server_agent.service.EmbeddingService import EmbeddingService

_embedding_service = EmbeddingService()

logger = logging.getLogger(__name__)

TOOL_META: dict[str, dict] = {
    "search_knowledge_base": {"display_name": "Knowledge Search", "icon": "📚"},
    "web_search": {"display_name": "Web Search", "icon": "🌐"},
    "read_local_file": {"display_name": "Read Local File", "icon": "📄"},
    "get_datetime": {"display_name": "Date Time", "icon": "🕐"},
    "list_dataset_files": {"display_name": "Dataset Browser", "icon": "📁"},
    "read_dataset_text_file": {"display_name": "Read Dataset File", "icon": "📄"},
    "get_dataset_file_metadata": {"display_name": "Dataset Metadata", "icon": "ℹ️"},
    "generate_medical_report": {"display_name": "Medical Report Generation", "icon": "📝"},
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
NIFTI_EXTENSIONS = {".nii", ".nii.gz"}
MAX_IMAGE_INPUT_SIZE = 10 * 1024 * 1024
MAX_NIFTI_INPUT_SIZE = 1024 * 1024 * 1024


class MedicalReportInput(BaseModel):
    image_paths: List[str] = Field(
        ...,
        description="用户选择的数据集影像相对路径，支持图片和 NIfTI（.nii/.nii.gz），例如 private/4243200690/dataset/case001/ct.nii.gz",
    )
    report_type: str = Field(
        "ct_image_summary",
        description="报告类型，例如 ct_image_summary、medical_image_summary、ct_lung_nodule、custom",
    )
    dataset_owner: Optional[str] = Field(
        None,
        description="数据集所属用户 ID。普通用户只能填写自己；管理员可以填写其他用户。",
    )
    language: str = Field("zh-CN", description="报告语言，zh-CN 或 en-US")


class DateTimeInput(BaseModel):
    target: Optional[str] = Field(
        None,
        description=(
            "要查询的目标日期或时间。支持 ISO 格式如 2026-05-29、2026-05-29 14:30:00，"
            "也支持 now/today/tomorrow/yesterday。为空表示当前时间。"
        ),
    )
    timezone: str = Field(
        "Asia/Shanghai",
        description="IANA 时区名，例如 Asia/Shanghai、UTC、America/New_York、Europe/London。",
    )
    offset_days: int = Field(
        0,
        description="在 target 基础上偏移的天数。查询明天可传 1，昨天可传 -1。",
    )


async def _web_search(query: str) -> str:
    """网络搜索工具：使用 Tavily API（免费 1000 次/月，注册：https://tavily.com）。"""
    from tavily import AsyncTavilyClient
    client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    try:
        resp = await client.search(query, max_results=6, search_depth="basic")
        lines: list[str] = []
        for r in resp.get("results", []):
            title = r.get("title", "")
            content = r.get("content", "")[:300]
            url = r.get("url", "")
            lines.append(f"• {title}\n  {content}\n  {url}")
        return "\n\n".join(lines) if lines else "（Tavily 未返回结果）"
    except Exception as exc:
        logger.warning("Tavily search failed: %s", exc)
        return f"Tavily 搜索失败: {exc}"


async def _read_local_file(path: str) -> str:
    """读取本地文件内容。传入完整文件路径，返回文件文本（限 100 KB 以内）。"""
    import pathlib
    safe_dir = pathlib.Path(os.getenv("SAFE_READ_DIR", os.path.expanduser("~/mediagent"))).resolve()
    try:
        target = pathlib.Path(path).resolve()
        target.relative_to(safe_dir)
        if not target.is_file():
            return f"文件不存在或不是普通文件: {path}"
        size = target.stat().st_size
        if size > 100 * 1024:
            return f"文件过大（{size // 1024} KB），仅支持 100 KB 以内的文件"
        return target.read_text(encoding="utf-8", errors="replace")
    except ValueError:
        return f"安全限制：只能读取 {safe_dir} 目录下的文件"
    except Exception as exc:
        return f"读取文件失败: {exc}"


def _get_datetime(
    target: Optional[str] = None,
    timezone: str = "Asia/Shanghai",
    offset_days: int = 0,
) -> str:
    """获取当前或指定日期时间信息。"""
    from datetime import datetime, time, timedelta
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(timezone or "Asia/Shanghai")
    except Exception:
        tz = ZoneInfo("Asia/Shanghai")
        timezone = "Asia/Shanghai"

    now = datetime.now(tz)
    raw_target = (target or "now").strip()
    normalized = raw_target.lower()

    if normalized in {"", "now", "current", "当前", "现在"}:
        dt = now
    elif normalized in {"today", "今天"}:
        dt = datetime.combine(now.date(), time.min, tzinfo=tz)
    elif normalized in {"tomorrow", "明天"}:
        dt = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=tz)
    elif normalized in {"yesterday", "昨天"}:
        dt = datetime.combine(now.date() - timedelta(days=1), time.min, tzinfo=tz)
    else:
        try:
            iso_text = raw_target.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            else:
                dt = dt.astimezone(tz)
        except Exception:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"无法解析目标时间：{target}",
                    "supported_examples": ["now", "today", "tomorrow", "yesterday", "2026-05-29", "2026-05-29 14:30:00"],
                    "timezone": timezone,
                },
                ensure_ascii=False,
            )

    if offset_days:
        dt = dt + timedelta(days=offset_days)

    weekdays_zh = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    result = {
        "status": "success",
        "target": raw_target,
        "timezone": timezone,
        "iso": dt.isoformat(),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "weekday": weekdays_zh[dt.weekday()],
        "year": dt.year,
        "month": dt.month,
        "day": dt.day,
        "utc_offset": dt.strftime("%z"),
        "summary": f"{dt.strftime('%Y年%m月%d日 %H:%M:%S')}（{timezone}，{weekdays_zh[dt.weekday()]}）",
    }
    return json.dumps(result, ensure_ascii=False)


SYSTEM_PROMPT = """\
你是一个医疗工具助手，负责与用户直接对话，提供专业的医学信息与智能分析支持。

当用户询问专业医学问题（如疾病诊断、用药方案、手术指征、检验指标解读、医学文献等）时，\
请主动调用 search_knowledge_base 工具查询知识库获取循证依据。
当用户需要查询网络上的最新资讯、新闻、实时数据时，调用 web_search 工具。
当用户询问日期、时间、星期、今天几号、现在几点、今年、今天、本周、本月、某一天是星期几、跨时区时间、相对日期等与时间相关的问题时，必须调用 get_datetime 工具，不得凭记忆猜测。
当用户需要读取本地文件内容时，调用 read_local_file 工具。
当用户通过 @ 选择了数据集文件，并要求查看、读取、总结文件时，优先调用 dataset 专用工具，不要使用 read_local_file。
当用户要求基于 private/{用户ID}/dataset 下的图片或 NIfTI 生成医学报告、影像报告、CT 报告、数据集报告时，调用 generate_medical_report 工具。
对于日常问候、简单对话等无需工具的场景，直接回答即可。

【语言规则】
- 若用户使用中文，全程中文回复。
- 若用户使用英文，全程英文回复。
- 不混用语言。

【医学报告安全规则】
- 报告结论必须说明“AI 辅助分析结果，需医生复核”。
- 不得编造患者身份、检查日期、病理结果、真实诊断或测量值。
- 如果工具结果提示图像分析不足，应明确建议医生复核或补充结构化测量数据。"""


@dataclass
class AgentConfig:
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.2
    request_timeout: float = 60.0
    max_retries: int = 2


class ReActAgent:
    """
    LangGraph ReAct agent。

    LLM 自主决策：直接回答 or 调用工具 → 查 KB → 综合回答。
    KB mapper 在每次 stream() 时传入，不在实例上持有（request-scoped）。
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._build_llm()

    def _build_llm(self) -> None:
        self._llm = ChatOpenAI(
            model=self.config.model,
            api_key=self.config.api_key or "lm-studio",
            base_url=self.config.base_url or "http://127.0.0.1:1234/v1",
            temperature=self.config.temperature,
            timeout=self.config.request_timeout,
            max_retries=self.config.max_retries,
        )

    def update_config(
        self,
        model: str,
        api_key: Optional[str],
        base_url: Optional[str],
    ) -> None:
        """Hot-reload LLM settings."""
        self.config.model = model
        self.config.api_key = api_key
        self.config.base_url = base_url
        self._build_llm()
        logger.info("ReActAgent: LLM config reloaded — model=%s", model)

    def _build_messages(
        self,
        user_input: str,
        history: List[Dict[str, str]],
        images: Optional[List[str]] = None,
    ) -> List[BaseMessage]:
        messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        if images:
            content_parts: List[dict] = [{"type": "text", "text": user_input}]
            for img_url in images:
                content_parts.append({"type": "image_url", "image_url": {"url": img_url}})
            messages.append(HumanMessage(content=content_parts))
        else:
            messages.append(HumanMessage(content=user_input))
        return messages

    async def stream(
        self,
        user_input: str,
        history: List[Dict[str, str]],
        kb_mapper=None,
        images: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        user_role: str = "user",
        selected_files_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        流式执行 ReAct 循环。

        Yields（与旧管道兼容的 SSE 前缀事件）:
            [SEARCH_START]{...}   — KB 搜索开始
            [SEARCH_RESULT]{...}  — KB 搜索结束
            [SOURCES]{...}        — 知识库引用列表（搜索后汇总一次）
            [TOOL_CALLS]{...}     — 完整工具调用链路（用于持久化）
            <text tokens>         — LLM 逐 token 输出
        """
        collected_sources: List[dict] = []
        collected_tool_calls: List[dict] = []
        _sources_before: List[int] = [0]  # 可变容器，供闭包跨事件共享
        _ws_results: List[dict] = []     # 最近一次 web_search 的结构化结果
        current_user_id = str(user_id) if user_id is not None else ""
        current_user_role = user_role or "user"

        def _validate_dataset_path(path: str, *, must_be_file: bool = False, must_be_dir: bool = False):
            from pathlib import Path

            if not current_user_id:
                return None, "无法识别当前用户身份。"
            rel_text = str(path or "").strip().lstrip("/")
            rel_path = Path(rel_text)
            if not rel_text or rel_path.is_absolute() or ".." in rel_path.parts:
                return None, f"路径不合法：{path}"
            parts = rel_path.parts
            if len(parts) < 3 or parts[0] != "private":
                return None, f"只能访问 private/{{用户ID}}/dataset 下的文件：{path}"
            owner_id = parts[1]
            if current_user_role != "admin" and owner_id != current_user_id:
                return None, f"普通用户只能访问 private/{current_user_id}/dataset 下的文件。"
            if len(parts) < 4 or parts[2] != "dataset":
                return None, f"只能访问 dataset 目录下的文件：{path}"
            files_root = in_data("files")
            abs_path = (files_root / rel_path).resolve()
            try:
                abs_path.relative_to(files_root.resolve())
            except ValueError:
                return None, f"路径越界：{path}"
            if must_be_file and not abs_path.is_file():
                return None, f"文件不存在：{path}"
            if must_be_dir and not abs_path.is_dir():
                return None, f"目录不存在：{path}"
            return abs_path, ""

        async def _search_kb(query: str) -> str:
            """搜索医疗知识库，获取相关医学文献、指南、诊疗规范。当需要专业医学信息时调用。"""
            if kb_mapper is None:
                return "（知识库未配置）"

            kbs = await kb_mapper.get_all_kbs()
            if not kbs:
                return "（当前没有可用的知识库）"

            all_results: List[dict] = []
            for kb in kbs:
                try:
                    results = await _embedding_service.search(kb.id, query, top_k=3)
                    for r in results:
                        r["kb_name"] = kb.name
                    scores = [round(r["score"], 4) for r in results]
                    logger.info("KB %d scores for query '%s': %s", kb.id, query[:60], scores)
                    relevant = [r for r in results if r["score"] < 1.5]
                    all_results.extend(relevant)
                except Exception as e:
                    logger.warning("KB %d 检索失败: %s", kb.id, e)

            if not all_results:
                return "（未在知识库中找到相关内容）"

            all_results.sort(key=lambda x: x["score"])
            top = all_results[:5]

            doc_names: dict[int, str] = {}
            for r in top:
                doc_id = r.get("doc_id")
                if doc_id and doc_id not in doc_names:
                    try:
                        doc = await kb_mapper.get_document_by_id(doc_id)
                        doc_names[doc_id] = doc.file_name if doc else f"doc_{doc_id}"
                    except Exception:
                        doc_names[doc_id] = f"doc_{doc_id}"

            for r in top:
                collected_sources.append({
                    "kb_name": r["kb_name"],
                    "file_name": doc_names.get(r.get("doc_id"), ""),
                    "content": r["content"][:300],
                    "score": round(r["score"], 4),
                    "doc_id": r.get("doc_id"),
                })

            lines = ["以下是知识库检索结果：", ""]
            for i, r in enumerate(top, 1):
                lines.append(f"[{i}] 知识库：{r['kb_name']}")
                lines.append(r["content"])
                lines.append("")

            logger.info(
                "ReActAgent: KB search found %d chunks for query: %s",
                len(top), query[:80],
            )
            return "\n".join(lines)

        search_tool = StructuredTool.from_function(
            coroutine=_search_kb,
            name="search_knowledge_base",
            description="搜索医疗知识库，获取相关医学文献、指南、诊疗规范。当需要专业医学信息时调用。",
        )
        async def _web_search_cached(query: str) -> str:
            """搜索互联网获取最新资讯、新闻、实时数据、百科知识。当用户需要网络上的最新信息时调用。"""
            from tavily import AsyncTavilyClient
            logger.info("[web_search] starting query: %s", query[:80])
            client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            try:
                resp = await client.search(query, max_results=6, search_depth="basic")
                logger.info("[web_search] raw resp type=%s keys=%s", type(resp).__name__, list(resp.keys()) if isinstance(resp, dict) else "N/A")
                _ws_results.clear()
                lines: list[str] = []
                for r in resp.get("results", []):
                    title = r.get("title", "")
                    content = r.get("content", "")[:300]
                    url = r.get("url", "")
                    lines.append(f"• {title}\n  {content}\n  {url}")
                    _ws_results.append({"title": title, "content": content, "url": url})
                logger.info("[web_search] parsed %d results, _ws_results len=%d", len(lines), len(_ws_results))
                return "\n\n".join(lines) if lines else "（Tavily 未返回结果）"
            except Exception as exc:
                logger.warning("[web_search] Tavily search failed: %s", exc)
                return f"Tavily 搜索失败: {exc}"

        web_search_tool = StructuredTool.from_function(
            coroutine=_web_search_cached,
            name="web_search",
            description="搜索互联网获取最新资讯、新闻、实时数据、百科知识。当用户需要网络上的最新信息时调用。",
        )
        read_file_tool = StructuredTool.from_function(
            coroutine=_read_local_file,
            name="read_local_file",
            description="读取本地文件内容。传入完整文件路径，返回文件的文本内容。",
        )
        datetime_tool = StructuredTool.from_function(
            func=_get_datetime,
            name="get_datetime",
            description=(
                "获取当前或指定日期时间信息。支持 now/today/tomorrow/yesterday、ISO 日期或日期时间、"
                "IANA 时区和天数偏移；可用于回答现在几点、某天星期几、跨时区时间、明天/昨天/本周等时间问题。"
                "禁止凭训练数据推测时间。"
            ),
            args_schema=DateTimeInput,
        )

        async def _list_dataset_files(path: Optional[str] = None) -> str:
            """列出用户 dataset 目录下的文件。path 为空时列出 private/{当前用户}/dataset。"""
            import mimetypes
            from pathlib import Path

            rel_path = path or f"private/{current_user_id}/dataset"
            abs_path, error = _validate_dataset_path(rel_path, must_be_dir=True)
            if error:
                return error

            items = []
            for child in sorted(abs_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:80]:
                rel_child = child.relative_to(in_data("files")).as_posix()
                mime_type = mimetypes.guess_type(str(child))[0] or ("inode/directory" if child.is_dir() else "application/octet-stream")
                items.append({
                    "name": child.name,
                    "path": rel_child,
                    "type": "directory" if child.is_dir() else "file",
                    "mime_type": mime_type,
                    "size": child.stat().st_size if child.is_file() else 0,
                })
            return json.dumps({"path": rel_path, "items": items}, ensure_ascii=False, indent=2)

        async def _read_dataset_text_file(path: str) -> str:
            """读取 dataset 下的文本文件内容，限制 200KB。"""
            abs_path, error = _validate_dataset_path(path, must_be_file=True)
            if error:
                return error
            mime_type = mimetypes.guess_type(str(abs_path))[0] or "application/octet-stream"
            text_ext = {".txt", ".md", ".csv", ".json", ".tsv", ".log", ".xml", ".html"}
            if not (mime_type.startswith("text/") or abs_path.suffix.lower() in text_ext):
                return f"该文件不是文本文件，不能直接读取：{path}（{mime_type}）"
            size = abs_path.stat().st_size
            if size > 200 * 1024:
                return f"文件过大（{size // 1024}KB），仅支持读取 200KB 以内的文本文件。"
            try:
                return abs_path.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return f"读取失败：{exc}"

        async def _get_dataset_file_metadata(path: str) -> str:
            """获取 dataset 文件或目录的元数据。"""
            abs_path, error = _validate_dataset_path(path)
            if error:
                return error
            if not abs_path.exists():
                return f"路径不存在：{path}"
            stat = abs_path.stat()
            if abs_path.name.lower().endswith((".nii", ".nii.gz")):
                mime_type = "application/nifti"
            else:
                mime_type = mimetypes.guess_type(str(abs_path))[0] or ("inode/directory" if abs_path.is_dir() else "application/octet-stream")
            result = {
                "path": path,
                "name": abs_path.name,
                "type": "directory" if abs_path.is_dir() else "file",
                "mime_type": mime_type,
                "size": stat.st_size,
                "modified_at": stat.st_mtime,
            }
            if abs_path.is_file() and mime_type == "application/nifti":
                try:
                    import SimpleITK as sitk
                    image = sitk.ReadImage(str(abs_path))
                    result["nifti"] = {
                        "size_xyz": list(image.GetSize()),
                        "spacing_xyz": [round(float(v), 4) for v in image.GetSpacing()],
                        "origin_xyz": [round(float(v), 4) for v in image.GetOrigin()],
                    }
                except Exception as exc:
                    result["nifti_error"] = str(exc)
            return json.dumps(result, ensure_ascii=False, indent=2)

        list_dataset_tool = StructuredTool.from_function(
            coroutine=_list_dataset_files,
            name="list_dataset_files",
            description="列出当前用户 dataset 目录中的文件和子目录。path 为空时列出 private/{当前用户ID}/dataset。",
        )
        read_dataset_text_tool = StructuredTool.from_function(
            coroutine=_read_dataset_text_file,
            name="read_dataset_text_file",
            description="读取 private/{用户ID}/dataset 下的文本文件内容。仅支持 txt、md、csv、json 等小文本文件。",
        )
        dataset_metadata_tool = StructuredTool.from_function(
            coroutine=_get_dataset_file_metadata,
            name="get_dataset_file_metadata",
            description="获取 private/{用户ID}/dataset 下文件或目录的元数据，包括类型、大小和 MIME。",
        )

        async def _generate_medical_report(
            image_paths: List[str],
            report_type: str = "ct_image_summary",
            dataset_owner: Optional[str] = None,
            language: str = "zh-CN",
        ) -> str:
            """
            基于用户从 private/{user_id}/dataset 中选择的医学图像生成固定格式报告。
            工具会校验路径权限，输出 report.json 和 report.html。
            """
            import base64
            import html
            import mimetypes
            from datetime import datetime
            from pathlib import Path

            if not current_user_id:
                return "生成失败：无法识别当前用户身份。"
            if not image_paths:
                return "生成失败：请至少选择一张数据集图片。"

            owner = str(dataset_owner or current_user_id)
            if current_user_role != "admin" and owner != current_user_id:
                return f"生成失败：普通用户只能基于 private/{current_user_id}/dataset 下的数据生成报告。"

            files_root = in_data("files")
            dataset_prefix = Path("private") / owner / "dataset"
            validated: List[dict] = []

            def _medical_ext(path: Path) -> str:
                name = path.name.lower()
                if name.endswith(".nii.gz"):
                    return ".nii.gz"
                return path.suffix.lower()

            def _is_nifti(path: Path) -> bool:
                return _medical_ext(path) in NIFTI_EXTENSIONS

            def _normalize_slice(slice_2d):
                import numpy as np
                from PIL import Image

                arr = np.asarray(slice_2d, dtype=np.float32)
                arr = np.nan_to_num(arr)
                lo, hi = np.percentile(arr, [1, 99])
                if hi <= lo:
                    lo, hi = float(arr.min()), float(arr.max())
                if hi <= lo:
                    arr = np.zeros_like(arr, dtype=np.uint8)
                else:
                    arr = np.clip((arr - lo) / (hi - lo), 0, 1)
                    arr = (arr * 255).astype(np.uint8)
                return Image.fromarray(arr).convert("L")

            def _make_nifti_preview(nifti_path: Path, output_dir: Path) -> dict:
                import numpy as np
                from PIL import Image, ImageDraw
                import SimpleITK as sitk

                image = sitk.ReadImage(str(nifti_path))
                volume = sitk.GetArrayFromImage(image)  # z, y, x
                if volume.ndim == 4:
                    volume = volume[0]
                if volume.ndim != 3:
                    raise ValueError(f"NIfTI volume must be 3D, got shape={volume.shape}")

                z, y, x = volume.shape
                slices = [
                    ("Axial", volume[z // 2, :, :]),
                    ("Coronal", volume[:, y // 2, :]),
                    ("Sagittal", volume[:, :, x // 2]),
                ]
                panels = []
                for label, arr in slices:
                    img = _normalize_slice(arr)
                    img = img.resize((256, 256))
                    canvas = Image.new("RGB", (256, 284), "white")
                    canvas.paste(img.convert("RGB"), (0, 0))
                    draw = ImageDraw.Draw(canvas)
                    draw.text((8, 263), label, fill=(32, 33, 36))
                    panels.append(canvas)

                combined = Image.new("RGB", (256 * 3 + 24, 284), "white")
                for i, panel in enumerate(panels):
                    combined.paste(panel, (i * (256 + 12), 0))

                assets_dir = output_dir / "assets"
                assets_dir.mkdir(parents=True, exist_ok=True)
                preview_name = f"{nifti_path.name.replace('.', '-')}-preview.png"
                preview_path = assets_dir / preview_name
                combined.save(preview_path)

                spacing = image.GetSpacing()
                size = image.GetSize()
                stats = {
                    "shape_zyx": list(volume.shape),
                    "size_xyz": list(size),
                    "spacing_xyz": [round(float(v), 4) for v in spacing],
                    "intensity_min": round(float(np.nanmin(volume)), 4),
                    "intensity_max": round(float(np.nanmax(volume)), 4),
                    "intensity_mean": round(float(np.nanmean(volume)), 4),
                }
                return {"preview_path": preview_path, "stats": stats}

            for raw_path in image_paths[:12]:
                rel_text = str(raw_path).strip().lstrip("/")
                rel_path = Path(rel_text)
                if rel_path.is_absolute() or ".." in rel_path.parts:
                    return f"生成失败：路径不合法：{raw_path}"
                if len(rel_path.parts) < 4 or rel_path.parts[:3] != dataset_prefix.parts:
                    return f"生成失败：图片必须位于 private/{owner}/dataset 目录下：{raw_path}"
                ext = _medical_ext(rel_path)
                if ext not in IMAGE_EXTENSIONS and ext not in NIFTI_EXTENSIONS:
                    return f"生成失败：仅支持图片文件或 NIfTI 文件（.nii/.nii.gz）：{raw_path}"

                abs_path = (files_root / rel_path).resolve()
                try:
                    abs_path.relative_to(files_root.resolve())
                except ValueError:
                    return f"生成失败：路径越界：{raw_path}"
                if not abs_path.is_file():
                    return f"生成失败：文件不存在：{raw_path}"
                size = abs_path.stat().st_size
                if ext in NIFTI_EXTENSIONS:
                    if size > MAX_NIFTI_INPUT_SIZE:
                        return f"生成失败：单个 NIfTI 文件不能超过 1GB：{raw_path}"
                elif size > MAX_IMAGE_INPUT_SIZE:
                    return f"生成失败：单张图片不能超过 10MB：{raw_path}"

                mime_type = mimetypes.guess_type(str(abs_path))[0] or "image/png"
                validated.append({
                    "relative_path": rel_path.as_posix(),
                    "absolute_path": abs_path,
                    "serve_url": "/files/serve/" + "/".join(rel_path.parts),
                    "mime_type": mime_type,
                    "name": abs_path.name,
                    "kind": "nifti" if _is_nifti(abs_path) else "image",
                })

            date_tag = datetime.now().strftime("%Y%m%d")
            output_root = files_root / "private" / owner
            base_name = f"medical-report-{date_tag}"
            output_dir = output_root / base_name
            version = 2
            while output_dir.exists():
                output_dir = output_root / f"{base_name}-v{version}"
                version += 1
            output_dir.mkdir(parents=True, exist_ok=False)

            visual_inputs: List[dict] = []
            for item in validated:
                if item["kind"] == "nifti":
                    try:
                        preview = _make_nifti_preview(item["absolute_path"], output_dir)
                        preview_rel = preview["preview_path"].relative_to(files_root).as_posix()
                        item["preview_url"] = f"/files/serve/{preview_rel}"
                        item["preview_path"] = preview["preview_path"]
                        item["nifti_stats"] = preview["stats"]
                        visual_inputs.append({
                            "name": f"{item['name']} preview",
                            "absolute_path": preview["preview_path"],
                            "mime_type": "image/png",
                            "source": item,
                        })
                    except Exception as exc:
                        logger.warning("NIfTI preview generation failed for %s: %s", item["relative_path"], exc)
                        item["preview_error"] = str(exc)
                else:
                    item["preview_url"] = item["serve_url"]
                    item["preview_path"] = item["absolute_path"]
                    visual_inputs.append({
                        "name": item["name"],
                        "absolute_path": item["absolute_path"],
                        "mime_type": item["mime_type"],
                        "source": item,
                    })

            visual_content_parts: List[dict[str, Any]] = []
            for visual in visual_inputs[:12]:
                data = base64.b64encode(visual["absolute_path"].read_bytes()).decode("ascii")
                visual_content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{visual['mime_type']};base64,{data}"},
                })

            input_metadata = [
                {k: v for k, v in item.items() if k in ("name", "kind", "relative_path", "nifti_stats", "preview_error")}
                for item in validated
            ]

            fallback_report = {
                "title": "CT影像总结报告" if language.startswith("zh") else "CT Imaging Summary Report",
                "summary": "已根据用户选择的数据集图片生成固定格式报告。图像结论需医生复核。" if language.startswith("zh") else "A fixed-format report was generated from selected dataset images. Findings require clinician review.",
                "image_findings": [
                    {
                        "image_index": i + 1,
                        "image_name": item["name"],
                        "finding": "影像已纳入报告，具体医学发现需医生复核。" if language.startswith("zh") else "Image included in the report; clinical findings require clinician review.",
                        "caption": f"{item['name']} ({'NIfTI preview' if item['kind'] == 'nifti' else 'image'})",
                    }
                    for i, item in enumerate(validated)
                ],
                "measurement_table": [],
                "impression": ["AI 辅助分析结果，需医生复核。"] if language.startswith("zh") else ["AI-assisted result; clinician review required."],
                "recommendation": ["建议结合原始影像、临床资料和医生阅片结果综合判断。"] if language.startswith("zh") else ["Correlate with original imaging, clinical context, and radiologist review."],
            }

            medical_agent = MedicalImageReportAgent(self._llm)
            report = await medical_agent.generate_report(
                visual_content_parts=visual_content_parts,
                input_metadata=input_metadata,
                report_type=report_type,
                language=language,
                fallback_report=fallback_report,
            )

            report["report_type"] = report_type
            report["dataset_owner"] = owner
            report["images"] = [
                {
                    "name": item["name"],
                    "relative_path": item["relative_path"],
                    "serve_url": item["serve_url"],
                    "preview_url": item.get("preview_url"),
                    "kind": item["kind"],
                    "nifti_stats": item.get("nifti_stats"),
                }
                for item in validated
            ]
            report["disclaimer"] = "AI 辅助分析结果，仅供医生复核参考。" if language.startswith("zh") else "AI-assisted analysis for clinician review only."
            report["created_at"] = datetime.now().isoformat(timespec="seconds")

            report_json_path = output_dir / "report.json"
            report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

            def esc(value: Any) -> str:
                return html.escape(str(value or ""))

            def asset_url(value: Any) -> str:
                raw = str(value or "")
                if raw.startswith("/files/serve/"):
                    return f"/api{raw}"
                return raw

            findings = report.get("image_findings") or []
            rows = report.get("measurement_table") or []
            impressions = report.get("impression") or []
            recommendations = report.get("recommendation") or []
            if not rows:
                rows = []
                for item in report.get("images") or []:
                    stats = item.get("nifti_stats") or {}
                    if not stats:
                        continue
                    rows.extend([
                        {
                            "item": f"{item.get('name')} 体数据尺寸",
                            "value": " × ".join(str(v) for v in (stats.get("shape_zyx") or [])),
                            "unit": "voxel",
                            "note": "z/y/x",
                        },
                        {
                            "item": f"{item.get('name')} 体素间距",
                            "value": " × ".join(str(v) for v in (stats.get("spacing_xyz") or [])),
                            "unit": "mm",
                            "note": "x/y/z",
                        },
                        {
                            "item": f"{item.get('name')} 强度范围",
                            "value": f"{stats.get('intensity_min')} ~ {stats.get('intensity_max')}",
                            "unit": "HU/原始强度",
                            "note": f"mean {stats.get('intensity_mean')}",
                        },
                    ])
            image_cards = []
            for i, item in enumerate(report["images"]):
                finding = findings[i].get("finding", "") if i < len(findings) and isinstance(findings[i], dict) else ""
                caption = findings[i].get("caption", item["name"]) if i < len(findings) and isinstance(findings[i], dict) else item["name"]
                image_url = item.get("preview_url") or item.get("serve_url")
                stats = item.get("nifti_stats")
                stats_html = ""
                if stats:
                    stats_html = (
                        "<div class='metric-strip'>"
                        f"<span>Shape z/y/x <b>{esc(stats.get('shape_zyx'))}</b></span>"
                        f"<span>Spacing x/y/z <b>{esc(stats.get('spacing_xyz'))}</b></span>"
                        f"<span>Mean <b>{esc(stats.get('intensity_mean'))}</b></span>"
                        "</div>"
                    )
                image_cards.append(
                    "<figure class='analysis-card'>"
                    f"<div class='scan-frame'><img src='{esc(asset_url(image_url))}' alt='{esc(item['name'])}' /></div>"
                    f"<figcaption>{esc(caption)}</figcaption>"
                    f"<p class='finding-text'>{esc(finding)}</p>"
                    f"{stats_html}"
                    "</figure>"
                )
            measurement_rows = "".join(
                "<tr>"
                f"<td>{esc(row.get('item'))}</td><td>{esc(row.get('value'))}</td>"
                f"<td>{esc(row.get('unit'))}</td><td>{esc(row.get('note'))}</td>"
                "</tr>"
                for row in rows if isinstance(row, dict)
            ) or "<tr><td colspan='4'>暂无结构化测量数据，需医生复核。</td></tr>"
            primary_image = report["images"][0] if report.get("images") else {}
            primary_image_url = asset_url(primary_image.get("preview_url") or primary_image.get("serve_url"))
            modality_label = "NIfTI CT" if primary_image.get("kind") == "nifti" else "Medical Image"
            html_doc = f"""<!doctype html>
<html lang="{esc(language)}">
<head>
  <meta charset="utf-8" />
  <title>{esc(report.get("title"))}</title>
  <style>
    :root {{ --ink:#111827; --muted:#5b667a; --line:#d7dde8; --soft:#f5f7fb; --accent:#2457c5; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #eef1f6; color: var(--ink); font-family: Arial, "Microsoft YaHei", sans-serif; }}
    .report {{ width: 960px; margin: 24px auto 40px; }}
    .sheet {{ min-height: 1280px; background: #fff; margin-bottom: 22px; padding: 46px 54px; box-shadow: 0 3px 14px rgba(15, 23, 42, .18); }}
    .cover {{ display: flex; flex-direction: column; }}
    .title-row {{ display:flex; align-items:flex-end; justify-content:space-between; gap: 20px; border-bottom: 3px solid var(--ink); padding-bottom: 14px; }}
    h1 {{ font-size: 28px; margin:0; letter-spacing: 0; }}
    .doc-meta {{ color: var(--muted); font-size: 12px; text-align:right; line-height:1.5; }}
    .summary {{ margin: 20px 0 24px; font-size: 15px; line-height: 1.9; }}
    .hero-scan {{ display:grid; grid-template-columns: 1.15fr .85fr; gap: 28px; align-items:center; margin-top: 22px; }}
    .hero-image {{ min-height: 520px; display:flex; align-items:center; justify-content:center; border: 1px solid var(--line); background: #050505; }}
    .hero-image img {{ width:100%; max-height: 560px; object-fit: contain; display:block; }}
    .hero-copy h2 {{ font-size: 20px; margin: 0 0 14px; border:0; padding:0; }}
    .hero-copy p {{ color: var(--muted); line-height: 1.8; font-size: 14px; margin: 0; }}
    .section-title {{ margin: 0 0 14px; padding-bottom: 10px; border-bottom: 1px solid var(--line); font-size: 18px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    .analysis-card {{ margin: 0; border: 1px solid var(--line); background: #fff; break-inside: avoid; }}
    .scan-frame {{ height: 320px; display:flex; align-items:center; justify-content:center; background:#050505; border-bottom:1px solid var(--line); }}
    .scan-frame img {{ max-width: 100%; max-height: 100%; object-fit: contain; display:block; }}
    figcaption {{ padding: 10px 12px 0; font-weight: 700; font-size: 13px; }}
    .finding-text {{ padding: 6px 12px 10px; color: #2f3a4c; font-size: 13px; line-height: 1.65; margin:0; }}
    .metric-strip {{ display:grid; grid-template-columns: 1fr; gap:5px; padding: 8px 12px 12px; border-top:1px solid var(--line); background: var(--soft); color: var(--muted); font-size: 11px; }}
    .metric-strip b {{ color: var(--ink); font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; background:#fff; }}
    th, td {{ border: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; font-weight: 700; }}
    .two-col {{ display:grid; grid-template-columns: 1fr 1fr; gap: 22px; }}
    .box {{ border: 1px solid var(--line); padding: 16px 18px; min-height: 220px; }}
    .box h3 {{ margin:0 0 10px; font-size: 16px; }}
    ul {{ padding-left: 20px; margin: 0; line-height: 1.8; }}
    .notice {{ margin-top: auto; padding-top: 22px; color: var(--muted); font-size: 12px; border-top: 1px solid var(--line); }}
    @media print {{ body {{ background:#fff; }} .report {{ width:auto; margin:0; }} .sheet {{ box-shadow:none; margin:0; page-break-after: always; }} }}
  </style>
</head>
<body>
  <main class="report">
    <section class="sheet cover">
      <div class="title-row">
        <h1>{esc(report.get("title") or ("CT影像总结报告" if language.startswith("zh") else "CT Imaging Summary Report"))}</h1>
        <div class="doc-meta">{esc(modality_label)}<br />{esc(report.get("created_at"))}</div>
      </div>
      <p class="summary">{esc(report.get("summary"))}</p>
      <div class="hero-scan">
        <div class="hero-image"><img src="{esc(primary_image_url)}" alt="{esc(primary_image.get("name"))}" /></div>
        <div class="hero-copy">
          <h2>AI Analysis of CT Images</h2>
          <p>Three-plane center-slice visualization is generated from the selected CT volume. The body region is not assumed from file format alone. Findings are intended to support review and must be confirmed on the complete image series by a qualified clinician.</p>
        </div>
      </div>
      <p class="notice">{esc(report.get("disclaimer"))}</p>
    </section>
    <section class="sheet">
    <h2 class="section-title">Image Analysis</h2>
    <div class="grid">{''.join(image_cards)}</div>
    </section>
    <section class="sheet">
    <h2 class="section-title">Measurements</h2>
    <table><thead><tr><th>Item</th><th>Value</th><th>Unit</th><th>Note</th></tr></thead><tbody>{measurement_rows}</tbody></table>
    <div class="two-col" style="margin-top:28px">
      <div class="box"><h3>Impression</h3><ul>{''.join(f"<li>{esc(x)}</li>" for x in impressions)}</ul></div>
      <div class="box"><h3>Recommendation</h3><ul>{''.join(f"<li>{esc(x)}</li>" for x in recommendations)}</ul></div>
    </div>
    <p class="notice">{esc(report.get("disclaimer"))}</p>
    </section>
  </main>
</body>
</html>"""
            report_html_path = output_dir / "report.html"
            report_html_path.write_text(html_doc, encoding="utf-8")

            rel_output = output_dir.relative_to(files_root).as_posix()
            result = {
                "status": "success",
                "title": report.get("title"),
                "summary": report.get("summary"),
                "image_count": len(validated),
                "output_dir": rel_output,
                "report_json": f"{rel_output}/report.json",
                "report_html": f"{rel_output}/report.html",
                "preview_url": f"/files/serve/{rel_output}/report.html",
                "disclaimer": report.get("disclaimer"),
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        medical_report_tool = StructuredTool.from_function(
            coroutine=_generate_medical_report,
            name="generate_medical_report",
            description=(
                "基于用户从 private/{用户ID}/dataset 中选择的医学影像生成固定格式医学报告。"
                "支持普通图片和 CT/MRI NIfTI 文件（.nii/.nii.gz）；NIfTI 会先生成中心三平面预览。"
                "输入 image_paths 为数据集影像相对路径列表，可选 dataset_owner/report_type/language。"
            ),
            args_schema=MedicalReportInput,
        )

        agent_graph = create_react_agent(
            model=self._llm,
            tools=[
                search_tool,
                web_search_tool,
                read_file_tool,
                datetime_tool,
                list_dataset_tool,
                read_dataset_text_tool,
                dataset_metadata_tool,
                medical_report_tool,
            ],
        )

        messages = self._build_messages(user_input, history, images)
        if selected_files_context:
            messages.insert(1, SystemMessage(content=selected_files_context))

        try:
            async for event in agent_graph.astream_events(
                {"messages": messages},
                version="v2",
            ):
                kind = event["event"]
                name = event.get("name", "")

                if kind == "on_tool_start":
                    tool_input = event.get("data", {}).get("input", {})
                    meta = TOOL_META.get(name, {"display_name": name, "icon": "🔧"})
                    if isinstance(tool_input, dict):
                        input_summary = str(
                            tool_input.get("query") or
                            tool_input.get("path") or
                            next(iter(tool_input.values()), "")
                        )[:120]
                    else:
                        input_summary = str(tool_input)[:120]

                    collected_tool_calls.append({
                        "name": name,
                        "display_name": meta["display_name"],
                        "icon": meta["icon"],
                        "query": input_summary,
                        "status": "running",
                    })
                    yield f"[TOOL_START]{json.dumps({'name': name, 'display_name': meta['display_name'], 'icon': meta['icon'], 'input_summary': input_summary}, ensure_ascii=False)}"

                    if name == "search_knowledge_base":
                        _sources_before[0] = len(collected_sources)
                        yield f"[SEARCH_START]{json.dumps({'kb': '知识库', 'kb_id': 0, 'query': input_summary}, ensure_ascii=False)}"

                elif kind == "on_tool_end":
                    meta = TOOL_META.get(name, {"display_name": name, "icon": "🔧"})
                    raw_output = event.get("data", {}).get("output", "")
                    raw_str = raw_output.content if hasattr(raw_output, "content") else str(raw_output)
                    output_summary = raw_str[:120] if raw_str else ""
                    extra: dict = {}
                    logger.info("[on_tool_end] name=%s raw_output type=%s raw_str[:80]=%s _ws_results=%d",
                                name, type(raw_output).__name__, raw_str[:80], len(_ws_results))

                    for tc in reversed(collected_tool_calls):
                        if tc.get("name") == name and tc.get("status") == "running":
                            tc["status"] = "done"
                            tc["output_summary"] = output_summary
                            break

                    if name == "search_knowledge_base":
                        found = len(collected_sources) - _sources_before[0]
                        for tc in reversed(collected_tool_calls):
                            if tc.get("name") == name:
                                tc["found"] = found
                                break
                        yield f"[SEARCH_RESULT]{json.dumps({'kb': '知识库', 'kb_id': 0, 'found': found}, ensure_ascii=False)}"
                        output_summary = f"找到 {found} 个相关片段"

                    elif name == "get_datetime":
                        try:
                            datetime_result = json.loads(raw_str)
                            if isinstance(datetime_result, dict):
                                output_summary = datetime_result.get("summary") or datetime_result.get("message") or output_summary
                        except Exception:
                            pass

                    elif name == "web_search" and _ws_results:
                        output_summary = f"找到 {len(_ws_results)} 条结果"
                        extra["search_results"] = list(_ws_results)
                        for tc in reversed(collected_tool_calls):
                            if tc.get("name") == name:
                                tc["search_results"] = list(_ws_results)
                                break

                    elif name == "generate_medical_report":
                        try:
                            report_result = json.loads(raw_str)
                        except Exception:
                            report_result = None
                        if isinstance(report_result, dict) and report_result.get("status") == "success":
                            output_summary = f"已生成报告：{report_result.get('title') or '医学报告'}"
                            extra["report_result"] = report_result
                            child_calls = [
                                {
                                    "name": "MedicalImageReportAgent",
                                    "display_name": "Medical Image Report Agent",
                                    "icon": "🧠",
                                    "status": "done",
                                    "input_summary": "分析医学影像预览与元数据",
                                    "output_summary": "生成结构化报告 JSON",
                                },
                                {
                                    "name": "render_medical_report",
                                    "display_name": "Report Renderer",
                                    "icon": "📄",
                                    "status": "done",
                                    "input_summary": "report JSON + 影像预览",
                                    "output_summary": "生成 HTML 报告与 JSON 文件",
                                },
                            ]
                            extra["child_calls"] = child_calls
                            for tc in reversed(collected_tool_calls):
                                if tc.get("name") == name:
                                    tc["report_result"] = report_result
                                    tc["child_calls"] = child_calls
                                    break

                    for tc in reversed(collected_tool_calls):
                        if tc.get("name") == name:
                            tc["output_summary"] = output_summary
                            break

                    yield f"[TOOL_END]{json.dumps({'name': name, 'display_name': meta['display_name'], 'icon': meta['icon'], 'success': True, 'output_summary': output_summary, **extra}, ensure_ascii=False)}"

                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content"):
                        token = chunk.content
                        if isinstance(token, str) and token:
                            yield token

            if collected_sources:
                yield f"[SOURCES]{json.dumps(collected_sources, ensure_ascii=False)}"
            if collected_tool_calls:
                yield f"[TOOL_CALLS]{json.dumps(collected_tool_calls, ensure_ascii=False)}"

        except Exception as exc:
            logger.error("ReActAgent stream failed: %s", exc, exc_info=True)
            yield f"\n\n抱歉，与语言模型通信失败：{exc}"
