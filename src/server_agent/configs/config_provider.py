import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class ModelSnapshot:
    """模型快照，用来驱动运行态"原子重建" """
    current_model_id: str
    model: str
    api_key: Optional[str]
    base_url: Optional[str]
    temperature: float = 0.2


class ConfigProvider:
    """
    全局模型目录的数据源，负责读取系统默认项和主模型配置，
    并为单次请求生成不可变的模型快照。
    
    新架构：
    - model_configs.json: {"current_model_id": "xxx"}（仅作为系统默认值）
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
                self._data = {"current_model_id": ""}
            
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

            # 检查模型是否在主配置中存在
            main_models = self._main_data.get("models", {})
            target_model = main_models.get(model_id)
            if not target_model:
                return False

            if not target_model.get("enabled", True):
                return False
            
            self._data["current_model_id"] = model_id
            self._write_to_disk()
            return True

    def get_model_snapshot(self, model_id: str) -> Optional[ModelSnapshot]:
        """按配置 ID 获取一个不可变、可用于单次请求的模型快照。"""
        with self._lock:
            self.reload_from_disk()
            current_model = self._main_data.get("models", {}).get(model_id)
            if not current_model or not current_model.get("enabled", True):
                return None

            config = current_model.get("config", {})
            return ModelSnapshot(
                current_model_id=model_id,
                model=config.get("model") or model_id,
                api_key=config.get("api_key"),
                base_url=config.get("base_url"),
                temperature=float(config.get("temperature", 0.2)),
            )

    def get_default_model_id(self) -> str:
        """返回有效的系统默认模型；默认项失效时回退到第一个启用模型。"""
        with self._lock:
            self.reload_from_disk()
            models = self._main_data.get("models", {})
            current_model_id = self._data.get("current_model_id", "")
            current_model = models.get(current_model_id)
            if current_model and current_model.get("enabled", True):
                return current_model_id
            return next(
                (model_id for model_id, model in models.items() if model.get("enabled", True)),
                "",
            )

    def get_snapshot(self) -> Optional[ModelSnapshot]:
        """生成系统默认模型快照（兼容旧调用）。"""
        model_id = self.get_default_model_id()
        return self.get_model_snapshot(model_id) if model_id else None

    def get_current_model_id(self) -> str:
        """获取当前模型ID"""
        with self._lock:
            self.reload_from_disk()
            return self._data.get("current_model_id", "")
