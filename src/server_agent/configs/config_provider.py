import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class ModelSnapshot:
    """模型快照，用来驱动运行态“原子重建”"""
    current_model_id: str
    api_key: Optional[str]
    base_url: Optional[str]


class ConfigProvider:
    """
    唯一可信的数据源，负责从磁盘读取/写入 model_configs.json，并生成“只读快照”供运行态重建使用
    """

    def __init__(self, config_path: str = "src/server_agent/configs/model_configs.json") -> None:
        self._path = Path(config_path)
        self._lock = threading.RLock()
        # 内存缓存
        self._data: Dict[str, Any] = {}
        self.reload_from_disk()

    def reload_from_disk(self) -> None:
        """从磁盘加载配置"""
        with self._lock:
            if self._path.exists():
                self._data = json.loads(self._path.read_text("utf-8"))
            else:
                self._data = {"current_model_id": "", "models": {}}

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
            models = (self._data.get("models") or {})
            if model_id not in models:
                return False
            self._data["current_model_id"] = model_id
            self._write_to_disk()
            return True

    def get_snapshot(self) -> ModelSnapshot:
        """生成快照，用于只读"""
        with self._lock:
            # 重新从磁盘加载最新配置
            self.reload_from_disk()
            current_model_id = self._data.get("current_model_id") or ""
            models = (self._data.get("models") or {})
            m = models.get(current_model_id) or {}
            return ModelSnapshot(
                current_model_id=current_model_id,
                api_key=m.get("api_key"),
                base_url=m.get("base_url"),
            )
