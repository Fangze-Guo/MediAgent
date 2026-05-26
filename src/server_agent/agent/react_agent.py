"""
LangGraph ReAct conversation agent for MediAgent.

LLM 自主决策是否需要调用工具查询知识库，而非每次都强制 RAG。
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from src.server_agent.service.EmbeddingService import EmbeddingService

_embedding_service = EmbeddingService()

logger = logging.getLogger(__name__)

TOOL_META: dict[str, dict] = {
    "search_knowledge_base": {"display_name": "知识库检索", "icon": "📚"},
    "web_search":            {"display_name": "网络搜索",   "icon": "🌐"},
    "read_local_file":       {"display_name": "读取文件",   "icon": "📄"},
    "get_datetime":          {"display_name": "Got current time", "icon": "🕐"},
}


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


def _get_datetime() -> str:
    """获取当前日期和时间（北京时间）。"""
    from datetime import datetime
    try:
        import pytz
        now = datetime.now(pytz.timezone("Asia/Shanghai"))
    except Exception:
        from datetime import timezone, timedelta
        now = datetime.now(timezone(timedelta(hours=8)))
    return now.strftime("%Y年%m月%d日 %H:%M:%S（北京时间）")


SYSTEM_PROMPT = """\
你是一个医疗工具助手，负责与用户直接对话，提供专业的医学信息与智能分析支持。

当用户询问专业医学问题（如疾病诊断、用药方案、手术指征、检验指标解读、医学文献等）时，\
请主动调用 search_knowledge_base 工具查询知识库获取循证依据。
当用户需要查询网络上的最新资讯、新闻、实时数据时，调用 web_search 工具。
当用户询问当前日期、时间、星期、今天几号、现在几点、今年、今天、本周、本月等与当前时间相关的问题时，必须调用 get_datetime 工具，不得凭记忆猜测。
当用户需要读取本地文件内容时，调用 read_local_file 工具。
对于日常问候、简单对话等无需工具的场景，直接回答即可。

【语言规则】
- 若用户使用中文，全程中文回复。
- 若用户使用英文，全程英文回复。
- 不混用语言。"""


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
            description="获取当前真实日期和时间（北京时间）。只要用户提到：今天、现在、当前、几号、几点、星期几、本周、本月、今年、最近日期等任何与时间相关的表达，都必须调用此工具。禁止凭训练数据推测当前时间。",
        )

        agent_graph = create_react_agent(
            model=self._llm,
            tools=[search_tool, web_search_tool, read_file_tool, datetime_tool],
        )

        messages = self._build_messages(user_input, history, images)

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

                    elif name == "web_search" and _ws_results:
                        output_summary = f"找到 {len(_ws_results)} 条结果"
                        extra["search_results"] = list(_ws_results)
                        for tc in reversed(collected_tool_calls):
                            if tc.get("name") == name:
                                tc["search_results"] = list(_ws_results)
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
