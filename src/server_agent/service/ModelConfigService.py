"""
模型配置管理服务
提供统一的模型配置管理和切换功能
"""

import json
import logging
import pathlib
from dataclasses import dataclass
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """模型配置数据类"""
    id: str
    name: str
    description: str
    provider: str
    base_url: str
    api_key: Optional[str] = None
    status: str = 'online'
    tags: Optional[List[str]] = None


class ModelConfigService:
    """模型配置管理服务类"""

    def __init__(self, config_file: str = "src/server_agent/configs/model_configs.json"):
        self.config_file = pathlib.Path(config_file)
        self.current_model_id: Optional[str] = None
        self.model_configs: Dict[str, ModelConfig] = {}
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        self._load_configs_from_file()


    def _load_configs_from_file(self):
        """从文件加载配置"""
        try:
            if not self.config_file.exists():
                logger.info(f"配置文件 {self.config_file} 不存在，模型列表为空")
                return

            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 加载当前模型ID
            if 'current_model_id' in data:
                self.current_model_id = data['current_model_id']

            # 加载模型配置 - 新结构中models是数组，需要从主配置获取详情
            if 'models' in data:
                user_model_ids = data['models']
                if isinstance(user_model_ids, list):
                    # 新结构：models是数组，从主配置获取详情
                    main_config_path = self.config_file.parent / "main_model_config.json"
                    if main_config_path.exists():
                        with open(main_config_path, 'r', encoding='utf-8') as f:
                            main_config = json.load(f)
                        
                        for model_id in user_model_ids:
                            main_model = main_config.get("models", {}).get(model_id)
                            if main_model:
                                config = ModelConfig(
                                    id=main_model['id'],
                                    name=main_model['name'],
                                    description=main_model['description'],
                                    provider=main_model['provider'],
                                    base_url=main_model.get('config', {}).get('base_url', ''),
                                    api_key=main_model.get('config', {}).get('api_key'),
                                    status='online' if main_model.get('enabled', True) else 'offline',
                                    tags=main_model.get('capabilities', [])
                                )
                                self.model_configs[model_id] = config
                else:
                    # 旧结构：models是字典（向后兼容）
                    for model_id, config_dict in data['models'].items():
                        config = ModelConfig(
                            id=config_dict['id'],
                            name=config_dict['name'],
                            description=config_dict['description'],
                            provider=config_dict['provider'],
                            base_url=config_dict['base_url'],
                            api_key=config_dict.get('api_key'),
                            status=config_dict.get('status', 'online'),
                            tags=config_dict.get('tags')
                        )
                        self.model_configs[model_id] = config

            logger.info(f"已从 {self.config_file} 加载模型配置")

        except Exception as e:
            logger.error(f"加载模型配置失败: {e}")

    def _save_configs_to_file(self):
        """保存配置到文件（新结构：只保存模型ID数组）"""
        try:
            data = {
                'current_model_id': self.current_model_id,
                'models': list(self.model_configs.keys())  # 只保存模型ID数组
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"已保存模型配置到 {self.config_file}")

        except Exception as e:
            logger.error(f"保存模型配置失败: {e}")

    def get_current_model(self) -> Optional[ModelConfig]:
        """获取当前模型配置"""
        return self.model_configs.get(self.current_model_id) if self.current_model_id else None

    def set_current_model(self, model_id: str) -> bool:
        """设置当前模型"""
        if model_id not in self.model_configs:
            logger.warning(f"模型 {model_id} 不存在")
            return False

        self.current_model_id = model_id
        self._save_configs_to_file()
        logger.info(f"已切换到模型: {self.model_configs[model_id].name}")
        return True

    def reload_configs(self):
        """重新从文件加载配置"""
        self.model_configs.clear()
        self.current_model_id = None
        self._load_configs_from_file()
        logger.info("已重新加载模型配置")

    def get_all_models(self) -> List[ModelConfig]:
        """获取所有模型配置"""
        return list(self.model_configs.values())

    def get_model_by_id(self, model_id: str) -> Optional[ModelConfig]:
        """根据ID获取模型配置"""
        return self.model_configs.get(model_id)

    def add_model(self, model: ModelConfig) -> bool:
        """添加模型配置"""
        try:
            if model.id in self.model_configs:
                logger.warning(f"模型 {model.id} 已存在，将覆盖")
            
            self.model_configs[model.id] = model
            self._save_configs_to_file()
            logger.info(f"已添加模型: {model.name} ({model.id})")
            return True
        except Exception as e:
            logger.error(f"添加模型失败: {e}")
            return False

    def remove_model(self, model_id: str) -> bool:
        """删除模型配置"""
        try:
            if model_id not in self.model_configs:
                logger.warning(f"模型 {model_id} 不存在")
                return False
            
            # 如果是当前模型，先清除当前模型设置
            if self.current_model_id == model_id:
                self.current_model_id = None
            
            del self.model_configs[model_id]
            self._save_configs_to_file()
            logger.info(f"已删除模型: {model_id}")
            return True
        except Exception as e:
            logger.error(f"删除模型失败: {e}")
            return False

    def update_model(self, model_id: str, **kwargs) -> bool:
        """更新模型配置"""
        try:
            if model_id not in self.model_configs:
                logger.warning(f"模型 {model_id} 不存在")
                return False
            
            model = self.model_configs[model_id]
            
            # 更新字段
            for key, value in kwargs.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            
            self._save_configs_to_file()
            logger.info(f"已更新模型: {model.name} ({model_id})")
            return True
        except Exception as e:
            logger.error(f"更新模型失败: {e}")
            return False

    def get_models_by_provider(self, provider: str) -> List[ModelConfig]:
        """根据提供商获取模型列表"""
        return [model for model in self.model_configs.values() if model.provider == provider]

    def get_online_models(self) -> List[ModelConfig]:
        """获取在线状态的模型列表"""
        return [model for model in self.model_configs.values() if model.status == 'online']

    def validate_model_config(self, model: ModelConfig) -> tuple[bool, str]:
        """验证模型配置"""
        try:
            # 检查必填字段
            if not model.id:
                return False, "模型ID不能为空"
            if not model.name:
                return False, "模型名称不能为空"
            if not model.provider:
                return False, "提供商不能为空"
            if not model.base_url:
                return False, "API端点不能为空"
            
            # 检查状态值
            if model.status not in ['online', 'maintenance', 'offline']:
                return False, f"无效的状态值: {model.status}"
            
            return True, "配置有效"
        except Exception as e:
            return False, f"验证失败: {e}"

