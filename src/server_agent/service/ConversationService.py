from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from src.server_agent.agent.conversation_agent import ConversationAgent
from src.server_agent.exceptions import NotFoundError, AuthorizationError, handle_service_exception
from src.server_agent.mapper.ConversationMapper import ConversationMapper
from src.server_agent.service.EmbeddingService import EmbeddingService
from src.server_agent.service.OssService import OssService

logger = logging.getLogger(__name__)


class ConversationService:
    """会话服务类（PostgreSQL 版本，无本地文件 I/O）"""

    def __init__(self) -> None:
        pass

    # ---------------------- 私有：从 app.state 获取依赖 ----------------------

    def _get_mapper(self, request) -> ConversationMapper:
        return request.app.state.conv_mapper

    def _get_agent(self, request) -> ConversationAgent:
        return request.app.state.runtime_registry.get_agent()

    def _get_kb_mapper(self, request):
        return getattr(request.app.state, "kb_mapper", None)

    async def _fetch_rag_context(self, request, user_msg: str) -> Tuple[str, List[dict]]:
        """并行检索所有知识库，返回 (rag_context_string, sources_list)。"""
        try:
            kb_mapper = self._get_kb_mapper(request)
            if kb_mapper is None:
                return "", []

            kbs = await kb_mapper.get_all_kbs()
            if not kbs:
                return "", []

            embedding = EmbeddingService()
            all_results: List[dict] = []
            for kb in kbs:
                try:
                    results = await embedding.search(kb.id, user_msg, top_k=3)
                    for r in results:
                        r["kb_name"] = kb.name
                    relevant = [r for r in results if r["score"] < 0.6]
                    all_results.extend(relevant)
                except Exception as e:
                    logger.warning("KB %d 检索失败: %s", kb.id, e)

            if not all_results:
                return "", []

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

            lines = [
                "<参考资料>",
                "以下内容来自知识库，请结合参考回答用户问题，并在回答末尾注明参考来源编号：",
                "",
            ]
            for i, r in enumerate(top, 1):
                lines.append(f"[{i}] 知识库：{r['kb_name']}")
                lines.append(r["content"])
                lines.append("")
            lines.append("</参考资料>")

            sources = [
                {
                    "kb_name": r["kb_name"],
                    "file_name": doc_names.get(r.get("doc_id"), ""),
                    "content": r["content"][:300],
                    "score": round(r["score"], 4),
                    "doc_id": r.get("doc_id"),
                }
                for r in top
            ]
            logger.info("RAG: found %d relevant chunks for query", len(top))
            return "\n".join(lines), sources

        except Exception as exc:
            logger.warning("RAG 检索失败，降级到普通对话: %s", exc)
            return "", []

    async def _stream_rag_context(
        self, request, user_msg: str
    ) -> AsyncGenerator[str, None]:
        """逐知识库检索，边搜索边 yield 进度事件；最终 yield [SOURCES] 和 [RAG_CONTEXT] 事件。"""
        import json

        kb_mapper = self._get_kb_mapper(request)
        if kb_mapper is None:
            return

        try:
            kbs = await kb_mapper.get_all_kbs()
        except Exception as exc:
            logger.warning("获取知识库列表失败: %s", exc)
            return

        if not kbs:
            return

        embedding = EmbeddingService()
        all_results: List[dict] = []

        for kb in kbs:
            yield f"[SEARCH_START]{json.dumps({'kb': kb.name, 'kb_id': kb.id}, ensure_ascii=False)}"
            try:
                results = await embedding.search(kb.id, user_msg, top_k=3)
                for r in results:
                    r["kb_name"] = kb.name
                relevant = [r for r in results if r["score"] < 0.6]
                all_results.extend(relevant)
                yield f"[SEARCH_RESULT]{json.dumps({'kb': kb.name, 'kb_id': kb.id, 'found': len(relevant)}, ensure_ascii=False)}"
            except Exception as e:
                logger.warning("KB %d 检索失败: %s", kb.id, e)
                yield f"[SEARCH_RESULT]{json.dumps({'kb': kb.name, 'kb_id': kb.id, 'found': 0}, ensure_ascii=False)}"

        if not all_results:
            return

        all_results.sort(key=lambda x: x["score"])
        top = all_results[:5]

        # 批量查文件名
        doc_names: dict[int, str] = {}
        for r in top:
            doc_id = r.get("doc_id")
            if doc_id and doc_id not in doc_names:
                try:
                    doc = await kb_mapper.get_document_by_id(doc_id)
                    doc_names[doc_id] = doc.file_name if doc else f"doc_{doc_id}"
                except Exception:
                    doc_names[doc_id] = f"doc_{doc_id}"

        lines = [
            "<参考资料>",
            "以下内容来自知识库，请结合参考回答用户问题，并在回答末尾注明参考来源编号：",
            "",
        ]
        for i, r in enumerate(top, 1):
            lines.append(f"[{i}] 知识库：{r['kb_name']}")
            lines.append(r["content"])
            lines.append("")
        lines.append("</参考资料>")

        sources = [
            {
                "kb_name": r["kb_name"],
                "file_name": doc_names.get(r.get("doc_id"), ""),
                "content": r["content"][:300],
                "score": round(r["score"], 4),
                "doc_id": r.get("doc_id"),
            }
            for r in top
        ]
        logger.info("RAG: found %d relevant chunks for query", len(top))
        yield f"[SOURCES]{json.dumps(sources, ensure_ascii=False)}"
        rag_context = json.dumps({"context": "\n".join(lines)}, ensure_ascii=False)
        yield f"[RAG_CONTEXT]{rag_context}"

    # ---------------------- 对话管理 ----------------------

    @handle_service_exception
    async def create_conversation(self, request, owner_uid: str) -> str:
        """创建新对话，返回 uid"""
        mapper = self._get_mapper(request)
        uid = await mapper.create_conversation(owner_uid)
        logger.info("对话创建成功: %s", uid)
        return uid

    @handle_service_exception
    async def get_messages(
        self,
        request,
        conversation_uid: str,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取对话全量消息；可选校验所有权"""
        mapper = self._get_mapper(request)

        if not await mapper.conversation_exists(conversation_uid):
            raise NotFoundError(
                resource_type="conversation",
                resource_id=conversation_uid,
                detail="该对话不存在",
            )

        if user_id and not await mapper.user_owns_conversation(conversation_uid, user_id):
            raise AuthorizationError(
                detail="无权访问该会话",
                context={"conversation_uid": conversation_uid, "user_id": user_id},
            )

        return await mapper.get_messages(conversation_uid)

    @handle_service_exception
    async def get_user_conversation_uids(self, request, user_id: str) -> List[str]:
        """获取用户所有对话 uid 列表"""
        mapper = self._get_mapper(request)
        return await mapper.get_conversations_by_owner(user_id)

    @handle_service_exception
    async def delete_conversation(self, request, conversation_uid: str) -> bool:
        """删除对话（消息随 ON DELETE CASCADE 一并删除，同步清理 OSS 图片）"""
        mapper = self._get_mapper(request)

        if not await mapper.conversation_exists(conversation_uid):
            raise NotFoundError(
                resource_type="conversation",
                resource_id=conversation_uid,
                detail="该会话不存在",
            )

        # 删库前先收集所有图片 URL，提取 object_key
        oss_service = OssService()
        messages = await mapper.get_messages(conversation_uid)
        object_keys = [
            key
            for m in messages
            for a in m.get("attachments", [])
            if a.get("type") == "image" and a.get("url")
            for key in [oss_service.extract_object_key(a["url"])]
            if key
        ]

        deleted = await mapper.delete_conversation(conversation_uid)
        logger.info("会话删除成功: %s", conversation_uid)

        # 异步清理 OSS（不阻塞响应）
        if deleted and object_keys:
            logger.info("异步清理 OSS 对象 %d 个: %s", len(object_keys), conversation_uid)
            asyncio.get_event_loop().run_in_executor(None, oss_service.delete_objects, object_keys)

        return deleted

    # ---------------------- 消息发送 ----------------------

    @handle_service_exception
    async def send_message(
        self, request, conversation_uid: str, content: str,
        images: Optional[List[str]] = None,
        attachments: Optional[List[dict]] = None,
    ) -> dict:
        """同步发送：等待完整回复后返回 {reply, sources}"""
        mapper = self._get_mapper(request)
        agent = self._get_agent(request)

        rag_context, sources = await self._fetch_rag_context(request, content)
        history = await mapper.get_messages(conversation_uid)
        reply = await agent.converse(content, history, rag_context=rag_context, images=images)

        await mapper.add_message(conversation_uid, "user", content, attachments)
        await mapper.add_message(conversation_uid, "assistant", reply, sources=sources)

        return {"reply": reply, "sources": sources}

    async def stream_message(
        self, request, conversation_uid: str, content: str,
        images: Optional[List[str]] = None,
        attachments: Optional[List[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """流式发送：先逐 KB yield 检索进度，再逐 token yield，完成后持久化"""
        mapper = self._get_mapper(request)
        agent = self._get_agent(request)
        import json

        rag_context = ""
        sources_data: list = []
        async for event in self._stream_rag_context(request, content):
            if event.startswith("[RAG_CONTEXT]"):
                try:
                    rag_context = json.loads(event[13:])["context"]
                except Exception:
                    pass
            elif event.startswith("[SOURCES]"):
                try:
                    sources_data = json.loads(event[9:])
                except Exception:
                    pass
                yield event
            else:
                yield event

        history = await mapper.get_messages(conversation_uid)
        await mapper.add_message(conversation_uid, "user", content, attachments)

        full_reply: List[str] = []
        try:
            async for token in agent.stream(content, history, rag_context=rag_context, images=images):
                full_reply.append(token)
                yield token
        finally:
            await mapper.add_message(conversation_uid, "assistant", "".join(full_reply), sources=sources_data)