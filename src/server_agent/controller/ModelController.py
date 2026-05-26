"""
模型管理API控制器
提供模型配置管理的相关接口
"""

from typing import List, Dict, Optional

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

        def load_user_config():
            """加载用户模型选择配置"""
            import json
            from pathlib import Path

            current_dir = Path(__file__).parent.parent
            user_config_path = current_dir / "configs" / "model_configs.json"

            try:
                with open(user_config_path, 'r', encoding='utf-8') as f:
                    return json.load(f), user_config_path
            except FileNotFoundError:
                return {"current_model_id": ""}, user_config_path

        def save_user_config(config, config_path):
            """保存用户模型选择配置"""
            import json

            temp_path = config_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            temp_path.replace(config_path)

        @self.router.get("/configs", response_model=BaseResponse[ModelConfigsResponse])
        async def getModelConfigs() -> BaseResponse[ModelConfigsResponse]:
            """获取所有已启用的模型配置"""
            try:
                main_config, _ = load_main_config()
                user_config, user_config_path = load_user_config()
                models_dict = {}
                enabled_model_ids = []

                for model_id, main_model in main_config.get("models", {}).items():
                    if not main_model.get("enabled", True):
                        continue

                    enabled_model_ids.append(model_id)
                    models_dict[model_id] = ModelConfigResponse(
                        id=main_model["id"],
                        name=main_model["name"],
                        description=main_model["description"],
                        provider=main_model["provider"],
                        base_url=main_model.get("config", {}).get("base_url", ""),
                        api_key=main_model.get("config", {}).get("api_key", ""),
                        status="online",
                        tags=main_model.get("capabilities", [])
                    )

                current_model_id = user_config.get("current_model_id", "")
                if current_model_id not in models_dict:
                    current_model_id = enabled_model_ids[0] if enabled_model_ids else ""
                    if user_config.get("current_model_id") != current_model_id:
                        user_config["current_model_id"] = current_model_id
                        save_user_config(user_config, user_config_path)
                
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
                print(f"🔄 尝试切换模型: {request.model_id}")
                success = provider.set_current_model(request.model_id)
                print(f"🔄 ConfigProvider.set_current_model 返回: {success}")
                
                if success:
                    snapshot = provider.get_snapshot()
                    print(f"🔄 模型切换成功: {request.model_id}")
                    print(f"🔄 快照信息: model={snapshot.current_model_id}, base_url={snapshot.base_url}")
                    registry.refresh_runtime(snapshot)
                    print(f"🔄 RuntimeRegistry 已刷新")
                    return ResultUtils.success(True)
                else:
                    print(f"❌ 模型切换失败: {request.model_id}")
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
            """删除用户模型配置"""
            try:
                # 加载用户配置
                import json
                from pathlib import Path
                
                current_dir = Path(__file__).parent.parent
                user_config_path = current_dir / "configs" / "model_configs.json"
                
                # 读取用户配置
                try:
                    with open(user_config_path, 'r', encoding='utf-8') as f:
                        user_config = json.load(f)
                except FileNotFoundError:
                    raise HTTPException(status_code=404, detail="用户配置文件不存在")
                
                user_models = user_config.get("models", [])
                current_model_id = user_config.get("current_model_id")
                
                # 检查模型是否存在
                if model_id not in user_models:
                    raise HTTPException(status_code=404, detail=f"模型 {model_id} 不存在于用户配置中")
                
                # 检查是否是当前使用的模型
                if current_model_id == model_id:
                    raise HTTPException(status_code=400, detail="无法删除当前正在使用的模型，请先切换到其他模型")
                
                # 从用户配置中移除模型
                user_models.remove(model_id)
                user_config["models"] = user_models
                
                # 保存用户配置
                temp_path = user_config_path.with_suffix('.tmp')
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(user_config, f, ensure_ascii=False, indent=2)
                temp_path.replace(user_config_path)
                
                return ResultUtils.success(True)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"删除模型配置失败: {str(e)}")

        # ==================== 管理员API辅助函数 ====================
        
        def load_main_config():
            """加载主模型配置文件"""
            import json
            from pathlib import Path
            
            # 使用绝对路径
            current_dir = Path(__file__).parent.parent
            main_config_path = current_dir / "configs" / "main_model_config.json"
            
            if not main_config_path.exists():
                raise HTTPException(status_code=404, detail="Main model config file not found")
            
            with open(main_config_path, 'r', encoding='utf-8') as f:
                return json.load(f), main_config_path
        
        def save_main_config(config, config_path):
            """保存主模型配置文件"""
            import json
            
            try:
                # 使用临时文件进行原子性写入
                temp_path = config_path.with_suffix('.tmp')
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                
                # 原子性替换文件
                temp_path.replace(config_path)
                
            except PermissionError as e:
                raise HTTPException(status_code=500, detail=f"无法写入主配置文件，请检查文件权限: {str(e)}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"保存主配置文件失败: {str(e)}")
        
        # ==================== 管理员API ====================
        
        @self.router.get("/admin/models", response_model=BaseResponse[dict])
        async def get_all_admin_models():
            """获取所有模型配置（管理员）"""
            try:
                # TODO: 添加管理员权限检查
                # if not check_admin_permission():
                #     raise HTTPException(status_code=403, detail="Admin permission required")
                
                config, _ = load_main_config()
                return ResultUtils.success(config)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"获取模型配置失败: {str(e)}")

        @self.router.post("/admin/models", response_model=BaseResponse[dict])
        async def create_admin_model(model_data: dict):
            """创建新模型（管理员）"""
            try:
                # TODO: 添加管理员权限检查
                # if not check_admin_permission():
                #     raise HTTPException(status_code=403, detail="Admin permission required")
                
                # 验证必需字段
                required_fields = ["id", "name", "description", "provider", "category"]
                for field in required_fields:
                    if field not in model_data:
                        raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
                config, config_path = load_main_config()
                
                # 检查模型是否已存在
                if model_data["id"] in config.get("models", {}):
                    raise HTTPException(status_code=400, detail="Model already exists")
                
                # 添加新模型
                new_model = {
                    "id": model_data["id"],
                    "name": model_data["name"],
                    "provider": model_data["provider"],
                    "description": model_data["description"],
                    "category": model_data["category"],
                    "capabilities": model_data.get("capabilities", []),
                    "max_tokens": model_data.get("max_tokens", 4096),
                    "input_cost_per_1k": model_data.get("input_cost_per_1k", 0.001),
                    "output_cost_per_1k": model_data.get("output_cost_per_1k", 0.002),
                    "enabled": model_data.get("enabled", True),
                    "config": {
                        "api_key": model_data.get("api_key", ""),
                        "base_url": model_data.get("base_url", ""),
                        "model": model_data.get("model", model_data["id"]),
                        "temperature": model_data.get("temperature", 0.7),
                        "max_tokens": model_data.get("max_tokens", 4096)
                    },
                    "requirements": {
                        "api_key_required": True,
                        "base_url_configurable": True
                    }
                }
                
                config["models"][model_data["id"]] = new_model
                
                # 保存文件
                save_main_config(config, config_path)
                
                return ResultUtils.success({"success": True, "message": "Model created successfully"})
                    
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"创建模型失败: {str(e)}")

        @self.router.put("/admin/models/{model_id}", response_model=BaseResponse[dict])
        async def update_admin_model(model_id: str, model_data: dict):
            """更新模型配置（管理员）"""
            try:
                # TODO: 添加管理员权限检查
                # if not check_admin_permission():
                #     raise HTTPException(status_code=403, detail="Admin permission required")
                
                config, config_path = load_main_config()
                
                if model_id not in config.get("models", {}):
                    raise HTTPException(status_code=404, detail="Model not found")
                
                # 更新模型配置
                model = config["models"][model_id]
                for key, value in model_data.items():
                    if key in ["name", "description", "provider", "category", "capabilities", 
                              "max_tokens", "input_cost_per_1k", "output_cost_per_1k", "enabled"]:
                        model[key] = value
                    elif key in ["api_key", "base_url", "model", "temperature"]:
                        model["config"][key] = value
                
                save_main_config(config, config_path)
                return ResultUtils.success({"success": True, "message": "Model updated successfully"})
                    
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"更新模型失败: {str(e)}")

        @self.router.delete("/admin/models/{model_id}", response_model=BaseResponse[dict])
        async def delete_admin_model(model_id: str):
            """删除模型（管理员）"""
            try:
                # TODO: 添加管理员权限检查
                # if not check_admin_permission():
                #     raise HTTPException(status_code=403, detail="Admin permission required")
                
                config, config_path = load_main_config()
                
                if model_id not in config.get("models", {}):
                    raise HTTPException(status_code=404, detail="Model not found")
                
                del config["models"][model_id]
                save_main_config(config, config_path)
                
                return ResultUtils.success({"success": True, "message": "Model deleted successfully"})
                    
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"删除模型失败: {str(e)}")

        @self.router.put("/admin/models/{model_id}/toggle", response_model=BaseResponse[dict])
        async def toggle_admin_model_status(model_id: str):
            """切换模型启用状态（管理员）"""
            try:
                # TODO: 添加管理员权限检查
                # if not check_admin_permission():
                #     raise HTTPException(status_code=403, detail="Admin permission required")
                
                config, config_path = load_main_config()
                
                if model_id not in config.get("models", {}):
                    raise HTTPException(status_code=404, detail="Model not found")
                
                # 切换启用状态
                current_enabled = config["models"][model_id].get("enabled", True)
                config["models"][model_id]["enabled"] = not current_enabled
                
                save_main_config(config, config_path)
                
                status_text = "enabled" if not current_enabled else "disabled"
                return ResultUtils.success({"success": True, "message": f"Model {status_text} successfully"})
                    
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"切换模型状态失败: {str(e)}")

        # ==================== 用户API ====================
        
        @self.router.get("/user/current-selection", response_model=BaseResponse[dict])
        async def get_user_current_selection():
            """获取用户当前的模型选择"""
            try:
                # 加载用户配置和主配置
                import json
                from pathlib import Path
                
                current_dir = Path(__file__).parent.parent
                user_config_path = current_dir / "configs" / "model_configs.json"
                main_config_path = current_dir / "configs" / "main_model_config.json"
                
                # 读取用户配置
                try:
                    with open(user_config_path, 'r', encoding='utf-8') as f:
                        user_config = json.load(f)
                except FileNotFoundError:
                    user_config = {"current_model_id": ""}
                
                current_model_id = user_config.get("current_model_id", "")
                current_model_config = None
                model_status = "unknown"
                status_message = ""
                
                if current_model_id:
                    # 从主配置获取当前模型详情
                    with open(main_config_path, 'r', encoding='utf-8') as f:
                        main_config = json.load(f)
                    
                    main_model = main_config.get("models", {}).get(current_model_id)
                    if main_model:
                        is_enabled = main_model.get("enabled", True)
                        model_status = "online" if is_enabled else "offline"
                        
                        if not is_enabled:
                            status_message = f"当前模型 '{main_model.get('name', current_model_id)}' 已离线，不可用。请选择其他在线模型。"
                        
                        current_model_config = {
                            "id": main_model["id"],
                            "name": main_model["name"],
                            "provider": main_model["provider"],
                            "description": main_model["description"],
                            "enabled": is_enabled,
                            "status": model_status
                        }
                
                response_data = {
                    "current_model_id": current_model_id,
                    "current_model": current_model_config,
                    "model_status": model_status,
                    "status_message": status_message,
                    "user_config": {}
                }
                
                return ResultUtils.success(response_data)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"获取当前选择失败: {str(e)}")

        @self.router.get("/user/model-status/{model_id}", response_model=BaseResponse[dict])
        async def check_model_status(model_id: str):
            """检查指定模型的状态"""
            try:
                # 加载主配置
                import json
                from pathlib import Path
                
                current_dir = Path(__file__).parent.parent
                main_config_path = current_dir / "configs" / "main_model_config.json"
                
                with open(main_config_path, 'r', encoding='utf-8') as f:
                    main_config = json.load(f)
                
                main_model = main_config.get("models", {}).get(model_id)
                if not main_model:
                    return ResultUtils.error(
                        code=404,
                        message=f"模型 '{model_id}' 不存在"
                    )
                
                is_enabled = main_model.get("enabled", True)
                model_status = "online" if is_enabled else "offline"
                
                status_info = {
                    "model_id": model_id,
                    "model_name": main_model.get("name", model_id),
                    "status": model_status,
                    "enabled": is_enabled,
                    "message": "" if is_enabled else f"模型 '{main_model.get('name', model_id)}' 当前处于离线状态，不可用。请选择其他在线模型。"
                }
                
                return ResultUtils.success(status_info)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"检查模型状态失败: {str(e)}")

        @self.router.get("/providers", response_model=BaseResponse[dict])
        async def get_providers():
            """获取所有提供商信息"""
            try:
                main_config, _ = load_main_config()
                providers = main_config.get("providers", {})
                return ResultUtils.success(providers)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"获取提供商信息失败: {str(e)}")

        @self.router.get("/categories", response_model=BaseResponse[dict])
        async def get_categories():
            """获取所有分类信息"""
            try:
                main_config, _ = load_main_config()
                categories = main_config.get("categories", {})
                return ResultUtils.success(categories)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"获取分类信息失败: {str(e)}")

        @self.router.post("/user/select-model", response_model=BaseResponse[dict])
        async def select_user_model(req: _FastRequest, selection_data: dict):
            """用户选择模型"""
            try:
                model_id = selection_data.get("current_model_id")
                if not model_id:
                    raise HTTPException(status_code=400, detail="Missing current_model_id")
                
                # 加载配置文件
                import json
                from pathlib import Path
                
                current_dir = Path(__file__).parent.parent
                user_config_path = current_dir / "configs" / "model_configs.json"
                main_config_path = current_dir / "configs" / "main_model_config.json"
                
                # 读取主配置，检查模型是否存在
                with open(main_config_path, 'r', encoding='utf-8') as f:
                    main_config = json.load(f)
                
                if model_id not in main_config.get("models", {}):
                    available_models = list(main_config.get("models", {}).keys())
                    raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found in main config. Available: {available_models}")
                
                main_model = main_config["models"][model_id]
                
                # 检查模型是否启用
                if not main_model.get("enabled", True):
                    return ResultUtils.error(
                        code=400,
                        message=f"模型 '{main_model.get('name', model_id)}' 当前处于离线状态，无法选择。请联系管理员启用该模型或选择其他在线模型。"
                    )
                
                # 读取用户配置
                user_config, user_config_path = load_user_config()
                
                # 设置为当前模型
                user_config["current_model_id"] = model_id
                
                # 保存用户配置
                save_user_config(user_config, user_config_path)
                
                # 🔄 刷新 RuntimeRegistry
                print(f"🔄 用户选择模型: {model_id}")
                provider = req.app.state.config_provider
                registry = req.app.state.runtime_registry
                
                # 重新加载配置并刷新运行时
                provider.reload_from_disk()
                snapshot = provider.get_snapshot()
                print(f"🔄 新快照: model={snapshot.current_model_id}, base_url={snapshot.base_url}")
                registry.refresh_runtime(snapshot)
                print(f"🔄 RuntimeRegistry 已刷新")
                
                return ResultUtils.success({"success": True, "message": f"Model {model_id} selected successfully"})
                    
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"选择模型失败: {str(e)}")
