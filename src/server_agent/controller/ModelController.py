"""
模型管理API控制器
提供模型配置管理的相关接口
"""

from typing import List, Dict, Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel

from src.server_agent.common import BaseResponse
from src.server_agent.common.ResultUtils import ResultUtils
from src.server_agent.service.ModelConfigService import ModelConfigService, ModelConfig
from .base import BaseController


# 请求数据模型
class SetCurrentModelRequest(BaseModel):
    """设置当前模型请求"""
    model_id: str


class CreateModelConfigRequest(BaseModel):
    """创建模型配置请求"""
    id: str
    name: str
    description: str
    provider: str
    base_url: str
    api_key: Optional[str] = None
    status: str = 'online'
    tags: Optional[List[str]] = None


class UpdateModelConfigRequest(BaseModel):
    """更新模型配置请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None


# 响应数据模型
class ModelConfigResponse(BaseModel):
    """模型配置响应"""
    id: str
    name: str
    description: str
    provider: str
    base_url: str
    api_key: Optional[str] = None
    status: str
    tags: Optional[List[str]] = None


class ModelConfigsResponse(BaseModel):
    """所有模型配置响应"""
    current_model_id: str
    models: Dict[str, ModelConfigResponse]


class ModelController(BaseController):
    """模型管理控制器"""

    def __init__(self):
        super().__init__(prefix="/models", tags=["模型管理"])
        self.model_service = ModelConfigService()
        self._register_routes()

    def _register_routes(self):
        """注册路由"""

        @self.router.get("/configs", response_model=BaseResponse[ModelConfigsResponse])
        async def getModelConfigs() -> BaseResponse[ModelConfigsResponse]:
            """获取所有模型配置（每次从文件重新加载）"""
            try:
                # 重新从文件加载配置
                self.model_service.reload_configs()
                
                models = self.model_service.get_all_models()
                current_model_id = self.model_service.current_model_id or ""
                
                models_dict = {}
                for model in models:
                    models_dict[model.id] = ModelConfigResponse(
                        id=model.id,
                        name=model.name,
                        description=model.description,
                        provider=model.provider,
                        base_url=model.base_url,
                        api_key=model.api_key,
                        status=model.status,
                        tags=model.tags
                    )
                
                response = ModelConfigsResponse(
                    current_model_id=current_model_id,
                    models=models_dict
                )
                
                return ResultUtils.success(response)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"获取模型配置失败: {str(e)}")

        @self.router.get("/current", response_model=BaseResponse[ModelConfigResponse])
        async def getCurrentModel() -> BaseResponse[ModelConfigResponse]:
            """获取当前使用的模型"""
            try:
                current_model = self.model_service.get_current_model()
                if current_model:
                    model_response = ModelConfigResponse(
                        id=current_model.id,
                        name=current_model.name,
                        description=current_model.description,
                        provider=current_model.provider,
                        base_url=current_model.base_url,
                        api_key=current_model.api_key,
                        status=current_model.status,
                        tags=current_model.tags
                    )
                    return ResultUtils.success(model_response)
                else:
                    raise HTTPException(status_code=404, detail="未找到当前模型配置")
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"获取当前模型失败: {str(e)}")

        from fastapi import Request as _FastRequest
        @self.router.post("/current", response_model=BaseResponse[bool])
        async def setCurrentModel(req: _FastRequest, request: SetCurrentModelRequest) -> BaseResponse[bool]:
            """设置当前使用的模型"""
            try:
                # 通过 app.state 的 provider 与 registry 完成原子切换
                provider = req.app.state.config_provider
                registry = req.app.state.runtime_registry
                success = provider.set_current_model(request.model_id)
                if success:
                    snapshot = provider.get_snapshot()
                    print(f"🔄 模型切换成功: {request.model_id}")
                    print(f"🔄 快照信息: model={snapshot.current_model_id}, base_url={snapshot.base_url}")
                    registry.refresh_runtime(snapshot)
                    return ResultUtils.success(True)
                else:
                    raise HTTPException(status_code=400, detail=f"模型 {request.model_id} 不存在或状态异常")
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"设置当前模型失败: {str(e)}")

        @self.router.post("/configs", response_model=BaseResponse[ModelConfigResponse])
        async def createModelConfig(request: CreateModelConfigRequest) -> BaseResponse[ModelConfigResponse]:
            """创建模型配置"""
            try:
                # 创建新的模型配置
                new_model = ModelConfig(
                    id=request.id,
                    name=request.name,
                    description=request.description,
                    provider=request.provider,
                    base_url=request.base_url,
                    api_key=request.api_key,
                    status=request.status,
                    tags=request.tags
                )
                
                # 验证配置
                is_valid, error_msg = self.model_service.validate_model_config(new_model)
                if not is_valid:
                    raise HTTPException(status_code=400, detail=error_msg)
                
                # 添加到服务中
                success = self.model_service.add_model(new_model)
                if not success:
                    raise HTTPException(status_code=500, detail="添加模型配置失败")
                
                response = ModelConfigResponse(
                    id=new_model.id,
                    name=new_model.name,
                    description=new_model.description,
                    provider=new_model.provider,
                    base_url=new_model.base_url,
                    api_key=new_model.api_key,
                    status=new_model.status,
                    tags=new_model.tags
                )
                
                return ResultUtils.success(response)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"创建模型配置失败: {str(e)}")

        @self.router.put("/configs/{model_id}", response_model=BaseResponse[ModelConfigResponse])
        async def updateModelConfig(model_id: str, request: UpdateModelConfigRequest) -> BaseResponse[ModelConfigResponse]:
            """更新模型配置"""
            try:
                if model_id not in self.model_service.model_configs:
                    raise HTTPException(status_code=404, detail=f"模型 {model_id} 不存在")
                
                # 准备更新数据
                update_data = {}
                if request.name is not None:
                    update_data['name'] = request.name
                if request.description is not None:
                    update_data['description'] = request.description
                if request.provider is not None:
                    update_data['provider'] = request.provider
                if request.base_url is not None:
                    update_data['base_url'] = request.base_url
                if request.api_key is not None:
                    update_data['api_key'] = request.api_key
                if request.status is not None:
                    update_data['status'] = request.status
                if request.tags is not None:
                    update_data['tags'] = request.tags
                
                # 使用服务方法更新
                success = self.model_service.update_model(model_id, **update_data)
                if not success:
                    raise HTTPException(status_code=500, detail="更新模型配置失败")
                
                # 获取更新后的模型
                model = self.model_service.get_model_by_id(model_id)
                if not model:
                    raise HTTPException(status_code=404, detail="模型不存在")
                
                response = ModelConfigResponse(
                    id=model.id,
                    name=model.name,
                    description=model.description,
                    provider=model.provider,
                    base_url=model.base_url,
                    api_key=model.api_key,
                    status=model.status,
                    tags=model.tags
                )
                
                return ResultUtils.success(response)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"更新模型配置失败: {str(e)}")

        @self.router.delete("/configs/{model_id}", response_model=BaseResponse[bool])
        async def deleteModelConfig(model_id: str) -> BaseResponse[bool]:
            """删除模型配置"""
            try:
                success = self.model_service.remove_model(model_id)
                if not success:
                    raise HTTPException(status_code=404, detail=f"模型 {model_id} 不存在或删除失败")
                
                return ResultUtils.success(True)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"删除模型配置失败: {str(e)}")

