"""
LangGraph ReAct conversation agent for MediAgent.

LLM 自主决策是否需要调用工具查询知识库，而非每次都强制 RAG。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是一个医疗工具助手，负责与用户直接对话，提供专业的医学信息与智能分析支持。

当用户询问专业医学问题（如疾病诊断、用药方案、手术指征、检验指标解读、医学文献等）时，\
请主动调用 search_knowledge_base 工具查询知识库获取循证依据。
对于日常问候、简单对话、非医学问题，直接回答即可，无需调用工具。

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

        async def _search_kb(query: str) -> str:
            """搜索医疗知识库，获取相关医学文献、指南、诊疗规范。当需要专业医学信息时调用。"""
            from src.server_agent.service.EmbeddingService import EmbeddingService

            if kb_mapper is None:
                return "（知识库未配置）"

            kbs = await kb_mapper.get_all_kbs()
            if not kbs:
                return "（当前没有可用的知识库）"

            embedding = EmbeddingService()
            all_results: List[dict] = []
            for kb in kbs:
                try:
                    results = await embedding.search(kb.id, query, top_k=3)
                    for r in results:
                        r["kb_name"] = kb.name
                    relevant = [r for r in results if r["score"] < 0.6]
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

        agent_graph = create_react_agent(
            model=self._llm,
            tools=[search_tool],
        )

        messages = self._build_messages(user_input, history, images)

        try:
            async for event in agent_graph.astream_events(
                {"messages": messages},
                version="v2",
            ):
                kind = event["event"]
                name = event.get("name", "")

                if kind == "on_tool_start" and name == "search_knowledge_base":
                    tool_input = event.get("data", {}).get("input", {})
                    query = (
                        tool_input.get("query", "")
                        if isinstance(tool_input, dict)
                        else str(tool_input)
                    )
                    _sources_before[0] = len(collected_sources)
                    collected_tool_calls.append({"name": "search_knowledge_base", "query": query, "status": "running"})
                    yield (
                        f"[SEARCH_START]"
                        + json.dumps(
                            {"kb": "知识库", "kb_id": 0, "query": query},
                            ensure_ascii=False,
                        )
                    )

                elif kind == "on_tool_end" and name == "search_knowledge_base":
                    found = len(collected_sources) - _sources_before[0]
                    if collected_tool_calls:
                        collected_tool_calls[-1]["status"] = "done"
                        collected_tool_calls[-1]["found"] = found
                    yield (
                        f"[SEARCH_RESULT]"
                        + json.dumps(
                            {"kb": "知识库", "kb_id": 0, "found": found},
                            ensure_ascii=False,
                        )
                    )

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
