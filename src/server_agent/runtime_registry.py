import logging
from typing import Optional

from mediagent.agents.chat_plan_agent import AgentAConfig
from mediagent.agents.task_create_agent import AgentBConfig, TaskCreationAgentB
from src.server_agent.configs.config_provider import ModelSnapshot


class RuntimeRegistry:
    """管理当前运行态实例：cfg_a/cfg_b/executor/agent。"""

    def __init__(self, *, task_manager, conversation_manager, database_path: str, stream_id: str) -> None:
        self._tm = task_manager
        self._cm = conversation_manager
        self._database_path = database_path
        self._stream_id = stream_id

        self.cfg_a: Optional[AgentAConfig] = None
        self.cfg_b: Optional[AgentBConfig] = None
        self.executor: Optional[TaskCreationAgentB] = None
        self.agent = None

    def refresh_runtime(self, snapshot: ModelSnapshot) -> None:
        """根据快照原子重建运行实例。"""
        if snapshot is None:
            return
        if (self.cfg_a and getattr(self.cfg_a, "model", None) == snapshot.current_model_id
                and getattr(self.cfg_a, "base_url", None) == snapshot.base_url):
            return

        new_cfg_b = AgentBConfig(
            model=snapshot.current_model_id,
            api_key=snapshot.api_key,
            base_url=snapshot.base_url,
            max_retries=3,
            allowed_tools=None,
            allowed_datasets=None,
            extra_param_rules=None,
            prompt_tools_limit=20,
        )
        new_executor = TaskCreationAgentB(task_manager=self._tm, config=new_cfg_b)

        new_cfg_a = AgentAConfig(
            model=snapshot.current_model_id,
            api_key=snapshot.api_key,
            base_url=snapshot.base_url,
            request_timeout=60.0,
        )

        # 延迟导入，避免循环
        from src.server_new.mediagent.agents.chat_plan_agent import DialogueAgentA
        new_agent = DialogueAgentA(
            new_executor, new_cfg_a,
            cm=self._cm,
            stream_id=self._stream_id,
            task_manager=self._tm,
            db_path=self._database_path,
            default_user_uid="6127016735"
        )

        old_model = getattr(self.cfg_a, "model", None) if self.cfg_a else None
        old_base = getattr(self.cfg_a, "base_url", None) if self.cfg_a else None

        self.cfg_a = new_cfg_a
        self.cfg_b = new_cfg_b
        self.executor = new_executor
        self.agent = new_agent

        logging.getLogger(__name__).info(
            "模式配置刷新 | current=%s | model %s -> %s | base_url %s -> %s",
            snapshot.current_model_id, old_model, snapshot.current_model_id, str(old_base), str(snapshot.base_url)
        )

    def get_agent(self):
        return self.agent

    def get_executor(self):
        return self.executor
