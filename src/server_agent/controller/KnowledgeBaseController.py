"""
知识库管理 API 控制器
- 查看：所有登录用户
- 创建/修改/删除/上传：仅 admin
"""
from typing import List

from fastapi import UploadFile, File, Header, Depends

from src.server_agent.common import BaseResponse
from src.server_agent.common.ResultUtils import ResultUtils
from src.server_agent.exceptions import AuthenticationError, ValidationError
from src.server_agent.model.dto.knowledge_base import CreateKnowledgeBaseRequest, UpdateKnowledgeBaseRequest
from src.server_agent.model.vo.KnowledgeBaseVO import KnowledgeBaseVO, KbDocumentVO
from src.server_agent.model.vo.UserVO import UserVO
from src.server_agent.service.KnowledgeBaseService import KnowledgeBaseService
from src.server_agent.dependencies.services import get_user_service
from .base import BaseController


class KnowledgeBaseController(BaseController):
    """知识库控制器"""

    def __init__(self):
        super().__init__(prefix="/knowledge-base", tags=["知识库管理"])
        self.kb_service = KnowledgeBaseService()
        self.user_service = get_user_service()
        self._register_routes()

    def _register_routes(self):

        # ==================== 所有登录用户可访问 ====================

        @self.router.get("")
        async def list_knowledge_bases(
            userVO: UserVO = Depends(self._get_current_user),
        ) -> BaseResponse[List[KnowledgeBaseVO]]:
            """获取知识库列表"""
            try:
                kbs = await self.kb_service.get_kb_list()
                return ResultUtils.success(kbs)
            except Exception as e:
                return ResultUtils.error(400, f"获取知识库列表失败: {self._msg(e)}")

        @self.router.get("/{kb_id}")
        async def get_knowledge_base(
            kb_id: int,
            userVO: UserVO = Depends(self._get_current_user),
        ) -> BaseResponse[KnowledgeBaseVO]:
            """获取知识库详情（含文档列表）"""
            try:
                kb = await self.kb_service.get_kb_by_id(kb_id)
                return ResultUtils.success(kb)
            except Exception as e:
                return ResultUtils.error(400, f"获取知识库失败: {self._msg(e)}")

        @self.router.post("/{kb_id}/search")
        async def search_knowledge_base(
            kb_id: int,
            body: dict,
            userVO: UserVO = Depends(self._get_current_user),
        ) -> BaseResponse[list]:
            """语义检索知识库，body: {query: str, top_k?: int}"""
            try:
                query = body.get("query", "").strip()
                if not query:
                    return ResultUtils.error(400, "query 不能为空")
                top_k = int(body.get("top_k", 5))
                results = await self.kb_service.search_kb(kb_id, query, top_k)
                return ResultUtils.success(results)
            except Exception as e:
                return ResultUtils.error(400, f"检索失败: {self._msg(e)}")

        @self.router.get("/{kb_id}/documents/{doc_id}/preview")
        async def preview_document(
            kb_id: int,
            doc_id: int,
            userVO: UserVO = Depends(self._get_current_user),
        ) -> BaseResponse[dict]:
            """预览文档内容（PDF/Word/Excel/TXT）"""
            try:
                result = await self.kb_service.get_document_preview(kb_id, doc_id)
                return ResultUtils.success(result)
            except Exception as e:
                return ResultUtils.error(400, f"预览文档失败: {self._msg(e)}")

        # ==================== 仅 admin 可访问 ====================

        @self.router.post("")
        async def create_knowledge_base(
            request: CreateKnowledgeBaseRequest,
            userVO: UserVO = Depends(self._get_admin_user),
        ) -> BaseResponse[KnowledgeBaseVO]:
            """创建知识库（仅 admin）"""
            try:
                kb = await self.kb_service.create_kb(
                    name=request.name,
                    description=request.description,
                    created_by=userVO.uid,
                )
                return ResultUtils.success(kb)
            except Exception as e:
                return ResultUtils.error(400, f"创建知识库失败: {self._msg(e)}")

        @self.router.put("/{kb_id}")
        async def update_knowledge_base(
            kb_id: int,
            request: UpdateKnowledgeBaseRequest,
            userVO: UserVO = Depends(self._get_admin_user),
        ) -> BaseResponse[KnowledgeBaseVO]:
            """更新知识库信息（仅 admin）"""
            try:
                kb = await self.kb_service.update_kb(
                    kb_id=kb_id,
                    name=request.name,
                    description=request.description,
                )
                return ResultUtils.success(kb)
            except Exception as e:
                return ResultUtils.error(400, f"更新知识库失败: {self._msg(e)}")

        @self.router.delete("/{kb_id}")
        async def delete_knowledge_base(
            kb_id: int,
            userVO: UserVO = Depends(self._get_admin_user),
        ) -> BaseResponse[None]:
            """删除知识库（仅 admin）"""
            try:
                await self.kb_service.delete_kb(kb_id)
                return ResultUtils.success(None)
            except Exception as e:
                return ResultUtils.error(400, f"删除知识库失败: {self._msg(e)}")

        @self.router.post("/{kb_id}/documents/upload")
        async def upload_documents(
            kb_id: int,
            files: List[UploadFile] = File(...),
            userVO: UserVO = Depends(self._get_admin_user),
        ) -> BaseResponse[List[KbDocumentVO]]:
            """上传文档到知识库（仅 admin）"""
            try:
                docs = await self.kb_service.upload_documents(kb_id, files)
                return ResultUtils.success(docs)
            except Exception as e:
                return ResultUtils.error(400, f"上传文档失败: {self._msg(e)}")

        @self.router.post("/{kb_id}/documents/{doc_id}/analyze")
        async def analyze_document(
            kb_id: int,
            doc_id: int,
            body: dict = None,
            userVO: UserVO = Depends(self._get_admin_user),
        ) -> BaseResponse[KbDocumentVO]:
            """手动触发文档 embedding（仅 admin）。body 可选: {chunk_size, chunk_overlap}"""
            try:
                body = body or {}
                chunk_size = body.get("chunk_size")
                chunk_overlap = body.get("chunk_overlap")
                doc = await self.kb_service.analyze_document(kb_id, doc_id, chunk_size, chunk_overlap)
                return ResultUtils.success(doc)
            except Exception as e:
                return ResultUtils.error(400, f"分析文档失败: {self._msg(e)}")

        @self.router.delete("/{kb_id}/documents/{doc_id}")
        async def delete_document(
            kb_id: int,
            doc_id: int,
            userVO: UserVO = Depends(self._get_admin_user),
        ) -> BaseResponse[None]:
            """删除文档（仅 admin）"""
            try:
                await self.kb_service.delete_document(kb_id, doc_id)
                return ResultUtils.success(None)
            except Exception as e:
                return ResultUtils.error(400, f"删除文档失败: {self._msg(e)}")

    # ==================== 工具方法 ====================

    @staticmethod
    def _msg(e: Exception) -> str:
        return e.detail if hasattr(e, "detail") else str(e)

    async def _get_current_user(self, authorization: str = Header(None)) -> UserVO:
        """任意登录用户"""
        if not authorization:
            raise AuthenticationError(detail="Missing authorization header", context={})
        token = authorization[7:] if authorization.startswith("Bearer ") else authorization
        userVO: UserVO = await self.user_service.get_user_by_token(token)
        if not userVO:
            raise AuthenticationError(detail="Invalid token", context={})
        return userVO

    async def _get_admin_user(self, authorization: str = Header(None)) -> UserVO:
        """仅 admin 用户"""
        userVO = await self._get_current_user(authorization)
        if userVO.role != "admin":
            raise ValidationError(detail="仅管理员可执行此操作", context={"role": userVO.role})
        return userVO
