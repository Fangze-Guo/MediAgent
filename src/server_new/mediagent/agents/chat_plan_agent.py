# agent_a.py —— “Agent A”：面向用户对话的编排器（对话 / 任务创建 分流）
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # 直到真正使用时报错


# ============================ 配置 ============================

@dataclass
class AgentAConfig:
    model: str
    api_key: Optional[str] = None                # LM Studio/Ollama 等可填占位符
    base_url: Optional[str] = None               # 例如 "http://127.0.0.1:1234/v1"
    request_timeout: float = 60.0
    max_retries: int = 2                         # LLM 重试次数
    # 系统提示（会拼接到每轮对话前）
    system_prefix: str = (
        "你是一个对话编排代理（Agent A）。你只做两类事："
        "1) 若应该直接回复用户，请调用函数 emit_user_reply，并把要说的话放到 content。"
        "2) 若应该创建任务，请调用函数 emit_task_request，并把用于创建任务的自然语言描述放到 description。"
        "禁止输出纯文本回答；你必须调用上面两个函数之一。"
    )


# ============================ Agent A 主类 ============================

class DialogueAgentA:
    """
    Agent A：
    - 接收用户输入（以及可选的对话历史）
    - 向 LLM 注入系统提示（system_prefix + 你的额外系统提示）
    - 限制 LLM 必须调用 function（二选一）
    - 解析意图：
        • emit_user_reply → 直接把 content 返回给前端
        • emit_task_request → 调用 Agent B 的 create_task()，返回创建结果
    """

    def __init__(self, agent_b, config: AgentAConfig):
        """
        :param agent_b: TaskCreationAgentB 实例（你提供的 Agent B）
        :param config: AgentAConfig
        """
        if AsyncOpenAI is None:
            raise RuntimeError("请安装 openai v1：pip install openai")
        self.cfg = config
        self.agent_b = agent_b
        self._client = AsyncOpenAI(
            api_key=(self.cfg.api_key or "lm-studio"),
            base_url=(self.cfg.base_url or "http://127.0.0.1:1234/v1"),
            timeout=self.cfg.request_timeout,
        )

    # -------------------- 外部接口 --------------------

    async def handle_user_message(
        self,
        user_uid: str,
        user_input: str,
        *,
        extra_system_hint: Optional[str] = None,
        chat_history: Optional[list[dict]] = None,
    ) -> Dict[str, Any]:
        """
        统一入口：
        - user_uid: 当前用户 UID（用于任务创建时传给 Agent B）
        - user_input: 本轮用户发言
        - extra_system_hint:（可选）你想在本轮拼到系统提示里的额外提示词
        - chat_history:（可选）前情（格式为 openai chat messages 的同构结构）
        返回：
        {
          "ok": true/false,
          "type": "user_reply" | "task_created" | "task_failed" | "llm_error",
          "content"?: str,           # 当 type == user_reply
          "task_uid"?: str,          # 当 type == task_created
          "attempts": int,
          "errors": [ ... ]          # 可选
        }
        """
        attempts = 0
        errors = []

        # 1) 准备消息
        system_prompt = self._build_system_prompt(extra_system_hint)
        messages = [{"role": "system", "content": system_prompt}]
        if chat_history:
            messages.extend(chat_history)
        messages.append({"role": "user", "content": user_input})

        # 2) 函数定义（强制二选一）
        tools = [
            self._tool_emit_user_reply(),
            self._tool_emit_task_request(),
        ]

        # 3) 调 LLM（重试容错）
        raw = None
        while attempts < max(1, self.cfg.max_retries):
            attempts += 1
            raw, err = await self._call_llm(messages, tools)
            if err:
                errors.append({"stage": "llm", "attempt": attempts, "message": err})
                continue

            # 4) 解析为（意图, 负载）
            intent, payload, perr = self._parse_llm_decision(raw)
            if perr:
                errors.append({"stage": "parse", "attempt": attempts, "message": perr, "raw": raw})
                continue

            # 5) 按意图执行
            if intent == "user_reply":
                return {
                    "ok": True,
                    "type": "user_reply",
                    "content": payload.get("content", "").strip(),
                    "attempts": attempts,
                }

            if intent == "task_request":
                description = payload.get("description", "").strip()
                if not description:
                    errors.append({"stage": "parse", "attempt": attempts, "message": "任务描述为空"})
                    continue

                # 调用 Agent B 创建任务
                try:
                    b_res = await self.agent_b.create_task(user_uid=user_uid, plan_text=description)
                except Exception as e:
                    errors.append({"stage": "agent_b", "attempt": attempts, "message": f"AgentB 异常：{e!r}"})
                    continue

                if b_res.get("ok"):
                    return {
                        "ok": True,
                        "type": "task_created",
                        "task_uid": b_res.get("task_uid"),
                        "attempts": attempts,
                    }
                else:
                    # 把 B 的错误透传出来（供前端提示/告警）
                    return {
                        "ok": False,
                        "type": "task_failed",
                        "attempts": attempts,
                        "errors": [{"stage": "agent_b", "message": b_res}],
                    }

            # 若不是两个函数之一，继续重试
            errors.append({"stage": "parse", "attempt": attempts, "message": "未识别的意图"})
            # loop 重试

        # 走到这里代表 LLM 或解析多次失败
        return {
            "ok": False,
            "type": "llm_error",
            "attempts": attempts,
            "errors": errors,
        }

    # -------------------- LLM 交互 --------------------

    async def _call_llm(self, messages: list[dict], tools: list[dict]) -> Tuple[Optional[dict], Optional[str]]:
        """
        统一封装对 chat.completions 的调用。
        我们提供两个函数，并设置 tool_choice="required"，强制 LLM 选择其中之一。
        返回 (resp_dict, error_msg)
        """
        try:
            resp = await self._client.chat.completions.create(
                model=self.cfg.model,
                messages=messages,
                temperature=0.2,
                tools=tools,
                tool_choice="required",
            )
            # 转普通 dict 便于后续处理
            return json.loads(resp.model_dump_json()), None
        except Exception as e:
            return None, f"chat.completions failed: {repr(e)}"

    # -------------------- 意图解析 --------------------

    def _parse_llm_decision(self, resp: dict) -> Tuple[Optional[str], Dict[str, Any], Optional[str]]:
        """
        从返回里摘出：
          - intent: "user_reply" | "task_request"
          - payload: {"content": "..."} | {"description": "..."}
        兼容多种字段：tool_calls / function_call / content 兜底。
        """
        try:
            choices = resp.get("choices") or []
            choice0 = (choices[0] or {})
            msg = choice0.get("message") or {}

            # 1) 新版 tool_calls
            tcs = msg.get("tool_calls") or []
            for tc in tcs:
                fn = (tc.get("function") or {})
                name = fn.get("name")
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args_obj = json.loads(args)
                    except Exception:
                        args_obj = {"_raw": args}
                elif isinstance(args, dict):
                    args_obj = args
                else:
                    args_obj = {}

                if name == "emit_user_reply":
                    content = (args_obj.get("content") or "").strip()
                    return "user_reply", {"content": content}, None
                if name == "emit_task_request":
                    desc = (args_obj.get("description") or "").strip()
                    return "task_request", {"description": desc}, None

            # 2) 旧版 function_call
            fc = msg.get("function_call") or {}
            name = fc.get("name")
            if name in ("emit_user_reply", "emit_task_request"):
                args = fc.get("arguments")
                if isinstance(args, str):
                    try:
                        args_obj = json.loads(args)
                    except Exception:
                        args_obj = {"_raw": args}
                else:
                    args_obj = args or {}
                if name == "emit_user_reply":
                    return "user_reply", {"content": (args_obj.get("content") or "").strip()}, None
                else:
                    return "task_request", {"description": (args_obj.get("description") or "").strip()}, None

            # 3) 某些网关把 JSON 塞 content，尝试兜底解析
            content = (msg.get("content") or "").strip()
            if content:
                try:
                    obj = json.loads(self._strip_json_fences(content))
                    if isinstance(obj, dict):
                        if obj.get("type") == "user_reply" and "content" in obj:
                            return "user_reply", {"content": str(obj["content"])}, None
                        if obj.get("type") == "task_request" and "description" in obj:
                            return "task_request", {"description": str(obj["description"])}, None
                except Exception:
                    pass

            return None, {}, "未找到函数调用（tool_calls/function_call/content 解析失败）"
        except Exception as e:
            return None, {}, f"解析异常：{e!r}"

    @staticmethod
    def _strip_json_fences(txt: str) -> str:
        txt = txt.strip()
        if txt.startswith("```"):
            # 简单去围栏
            lines = [line for line in txt.splitlines() if not line.strip().startswith("```")]
            return "\n".join(lines).strip()
        return txt

    # -------------------- 工具/函数定义（给 LLM） --------------------

    def _tool_emit_user_reply(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "emit_user_reply",
                "description": "当你决定直接回答用户时，调用此函数。只需返回要说的话。",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["content"],
                    "properties": {
                        "content": {
                            "type": "string",
                            "minLength": 1,
                            "description": "对用户的自然语言回答（可包含 Markdown）。"
                        }
                    }
                }
            }
        }

    def _tool_emit_task_request(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "emit_task_request",
                "description": (
                    "当你认为需要创建一个多步骤任务（由 Agent B/TaskManager 执行）时调用此函数。"
                    "把用于创建任务的**自然语言描述**放进 description，描述应清楚表达要做什么、输入/输出的来源与期望。"
                ),
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["description"],
                    "properties": {
                        "description": {
                            "type": "string",
                            "minLength": 4,
                            "description": "创建任务所需的自然语言描述（Agent B 会把它结构化为严格 JSON 计划）。"
                        }
                    }
                }
            }
        }

    # -------------------- 系统提示拼接 --------------------

    def _build_system_prompt(self, extra: Optional[str]) -> str:
        if extra and extra.strip():
            return f"{self.cfg.system_prefix}\n\n附加约束：{extra.strip()}"
        return self.cfg.system_prefix


# ============================ 最小可跑示例 ============================

# 下面这个示例假定你已经在别处构造了 Agent B 对象：TaskCreationAgentB(tm, cfg_b)
# from agent_b import TaskCreationAgentB, AgentBConfig
#
# async def demo():
#     agent_b = TaskCreationAgentB(task_manager=tm, config=AgentBConfig(model="your_model", base_url="http://127.0.0.1:1234/v1"))
#     agent_a = DialogueAgentA(agent_b, AgentAConfig(model="your_model", base_url="http://127.0.0.1:1234/v1"))
#
#     # 1) 用户只是闲聊/问答
#     r1 = await agent_a.handle_user_message(user_uid="u_001", user_input="帮我解释下Dice系数")
#     print(r1)  # => {"ok":True,"type":"user_reply","content":"..."}
#
#     # 2) 用户提出一个需要创建任务的诉求
#     r2 = await agent_a.handle_user_message(
#         user_uid="u_001",
#         user_input="请把 dataset 里的 DCE 全流程跑一下，然后给我导出 summary 表格",
#         extra_system_hint="偏向自动化：如需创建任务，请优先 emit_task_request。",
#     )
#     print(r2)  # => {"ok":True,"type":"task_created","task_uid":"..."} 或 {"ok":False,"type":"task_failed",...}
#
# if __name__ == "__main__":
#     asyncio.run(demo())
