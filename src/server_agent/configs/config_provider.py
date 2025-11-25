import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class ModelSnapshot:
    """模型快照，用来驱动运行态"原子重建" """
    current_model_id: str
    api_key: Optional[str]
    base_url: Optional[str]


class ConfigProvider:
    """
    唯一可信的数据源，负责从磁盘读取/写入 model_configs.json，
    并生成"只读快照"供运行态重建使用
    
    新架构：
    - user_config.json: {"current_model_id": "xxx", "models": ["id1", "id2"]}
    - main_model_config.json: 包含所有模型的详细信息
    """

    def __init__(self, config_path: str = "src/server_agent/configs/model_configs.json") -> None:
        self._path = Path(config_path)
        self._main_config_path = self._path.parent / "main_model_config.json"
        self._lock = threading.RLock()
        # 内存缓存
        self._data: Dict[str, Any] = {}
        self._main_data: Dict[str, Any] = {}
        self.reload_from_disk()

    def reload_from_disk(self) -> None:
        """从磁盘加载配置"""
        with self._lock:
            # 加载用户配置
            if self._path.exists():
                self._data = json.loads(self._path.read_text("utf-8"))
            else:
                self._data = {"current_model_id": "", "models": []}
            
            # 加载主配置
            if self._main_config_path.exists():
                self._main_data = json.loads(self._main_config_path.read_text("utf-8"))
            else:
                self._main_data = {"models": {}}

    def _write_to_disk(self) -> None:
        """写入配置到磁盘"""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), "utf-8")

    def set_current_model(self, model_id: str) -> bool:
        """设置当前模型"""
        with self._lock:
            # 重新从磁盘加载最新配置
            self.reload_from_disk()
            
            # 检查模型是否在用户选择列表中
            user_models = self._data.get("models", [])
            if model_id not in user_models:
                return False
            
            # 检查模型是否在主配置中存在
            main_models = self._main_data.get("models", {})
            if model_id not in main_models:
                return False
            
            self._data["current_model_id"] = model_id
            self._write_to_disk()
            return True

    def get_snapshot(self) -> ModelSnapshot:
        """生成快照，用于只读"""
        with self._lock:
            # 重新从磁盘加载最新配置
            self.reload_from_disk()
            
            current_model_id = self._data.get("current_model_id", "")
            
            # 从主配置获取当前模型的详细信息
            api_key = None
            base_url = None
            
            if current_model_id:
                main_models = self._main_data.get("models", {})
                current_model = main_models.get(current_model_id, {})
                config = current_model.get("config", {})
                api_key = config.get("api_key")
                base_url = config.get("base_url")
            
            return ModelSnapshot(
                current_model_id=current_model_id,
                api_key=api_key,
                base_url=base_url,
            )

    def add_user_model(self, model_id: str) -> bool:
        """添加模型到用户配置"""
        with self._lock:
            self.reload_from_disk()
            
            # 检查模型是否在主配置中存在
            main_models = self._main_data.get("models", {})
            if model_id not in main_models:
                return False
            
            # 添加到用户配置
            user_models = self._data.get("models", [])
            if model_id not in user_models:
                user_models.append(model_id)
                self._data["models"] = user_models
                self._write_to_disk()
            
            return True

    def remove_user_model(self, model_id: str) -> bool:
        """从用户配置中移除模型"""
        with self._lock:
            self.reload_from_disk()
            
            user_models = self._data.get("models", [])
            current_model_id = self._data.get("current_model_id")
            
            # 不能删除当前使用的模型
            if current_model_id == model_id:
                return False
            
            if model_id in user_models:
                user_models.remove(model_id)
                self._data["models"] = user_models
                self._write_to_disk()
                return True
            
            return False

    def get_user_models(self) -> list:
        """获取用户选择的模型ID列表"""
        with self._lock:
            self.reload_from_disk()
            return self._data.get("models", [])

    def get_current_model_id(self) -> str:
        """获取当前模型ID"""
        with self._lock:
            self.reload_from_disk()
            return self._data.get("current_model_id", "")
