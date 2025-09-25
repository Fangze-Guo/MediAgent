# agent_a.py —— 面向用户的对话编排器（对话管理器 + 执行器；工具目录来自 task_manager；仅暴露 converse）
from __future__ import annotations

import json
import sqlite3
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List, Protocol, Union

try:
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # 直到真正使用时报错


# ============================ 配置 ============================

@dataclass
class AgentAConfig:
    model: str
    api_key: Optional[str] = None                 # LM Studio/Ollama 等可填占位符
    base_url: Optional[str] = None                # 例如 "http://127.0.0.1:1234/v1"
    request_timeout: float = 60.0
    max_retries: int = 2                          # 每轮 LLM 调用的重试次数
    max_tool_rounds: int = 3                      # 连续“工具/任务”回合上限

    # —— 新增：是否在 system 中注入工具目录（只读，帮助模型写出更贴近工具的描述）——
    include_tool_catalog: bool = True
    tool_catalog_limit: int = 20                  # 最多注入多少条工具
    tool_desc_maxlen: int = 160                   # 每条工具描述的截断长度（字符数）

    # 系统提示（不出现“agentA/agentB”等无信息标签）
    system_prefix: str = (
        """
你负责在一次人机对话中做两类决定：
1) 若应直接回复用户，请调用函数 emit_user_reply，并把要说的话放到 content；
2) 若需要创建或推进一项任务，请调用函数 emit_task_request，并把用于创建/推进任务的自然语言描述放到 description。
禁止输出纯文本，你必须调用以上两个函数之一。对话上下文以系统提供的消息为准。

【严格约束——避免“画蛇添足”】
- 不要臆造或扩展任何工具参数键名、字段名或取值；不要凭空给工具加默认值。
- 如需提到工具，只能使用“工具目录”中出现的名称，不加入任何参数键名；更不要写 JSON 片段或键值对；要严格核对工具提供的参数列表，不要臆造工具不存在的参数。
- 你的任务描述只写**目的/输入/输出/约束**的自然语言，不写具体参数键名（例如 batch_size、epochs、lr、patch_size 等）。
- 如果用户明确给了参数（例如“批大小 64”），原样保留为自然语言描述，不转换为“参数键名: 值”的格式。
- 不确定时，不要猜；要么向用户澄清（emit_user_reply），要么在任务描述里标注“需后端根据工具规范补全参数”。
- 若后端（执行器/任务管理器）已经返回“创建成功”且含 task_uid，你必须立刻 emit_user_reply：
  • 告知“任务已创建”
  • 明确给出 task_uid

【任务描述模板（用于 emit_task_request.description）】
请严格用自然语言的短段落，按照以下要点组织（可以合并为一段话）：
- 目的：用一句话概述要完成的事。
- 输入来源：指出数据/路径/上游结果（如“来自公共数据集 test_set”或“使用上一步的产出”）。

【决策准则】
- 如果信息不足以开始：优先 emit_user_reply 提问澄清，问题要具体、可一次性补齐。
- 如果能开始：emit_task_request，用上面的模板写**自然语言**；不要包含任何键名/JSON/代码样式。
        """.strip()
    )


# ============== 松耦合协议（对话管理器 / 执行器 / 任务管理器） ==============

class ConversationManagerLike(Protocol):
    async def add_message_to_main(self, conversation_uid: str, role: str, content: str) -> Dict[str, Any]: ...
    async def add_message_to_stream(self, conversation_uid: str, target: str, role: str, content: str) -> Dict[str, Any]: ...
    async def get_messages(self, conversation_uid: str, target: str) -> Dict[str, Any]: ...


class ExecutorLike(Protocol):
    """执行器：至少需具备 create_task(user_uid, plan_text)。"""
    async def create_task(self, user_uid: Optional[str], plan_text: str) -> Dict[str, Any]: ...


class TaskManagerAsyncLike(Protocol):
    """你给的 AsyncTaskManager 的最小异步接口，用于拉取工具目录。"""
    async def list_tools(self) -> List[Dict[str, Any]]: ...
    # （如需更多可继续补充，但本文件仅用到 list_tools）


# ============================ 主类 ============================

class DialogueAgentA:
    """
    - 初始化需要：executor（执行器）、cm（对话管理器）、stream_id（内部信息流识别码）、
                 task_manager（用于获取工具目录）、数据库文件 db_path、可选 default_user_uid。
    - 在创建/推进任务时：根据 conversation_uid → 查 SQLite(conversations) → 取 owner_uid 作为 user_uid。
    """

    def __init__(
        self,
        executor: ExecutorLike,
        config: AgentAConfig,
        *,
        cm: ConversationManagerLike,
        stream_id: str,
        task_manager: TaskManagerAsyncLike,
        db_path: Union[str, Path],                 # 新增：SQLite 数据库文件路径
        default_user_uid: Optional[str] = None,   # 查不到时的兜底
    ):
        if AsyncOpenAI is None:
            raise RuntimeError("请安装 openai v1：pip install openai")
        self.cfg = config
        self.executor = executor
        self.cm = cm
        self.stream_id = stream_id
        self.tm = task_manager
        self.default_user_uid = default_user_uid

        self.db_path = Path(db_path).expanduser().resolve()

        self._client = AsyncOpenAI(
            api_key=(self.cfg.api_key or "lm-studio"),
            base_url=(self.cfg.base_url or "http://127.0.0.1:1234/v1"),
            timeout=self.cfg.request_timeout,
        )
        # 工具目录缓存（格式化后的只读文本）
        self._tool_catalog_cache: Optional[str] = None

    # -------------------- 唯一外部接口 --------------------
    async def converse(self, conversation_uid: str, user_input: str) -> str:
        """对外唯一入口：直到产出面向用户的最终回复文本才返回。"""
        # 1) 把用户消息写入 main_chat 与 内部信息流
        await self._append_main(conversation_uid, role="user", text=user_input)
        await self._append_internal(conversation_uid, role="user", text=user_input)

        tool_round = 0
        limit = max(1, self.cfg.max_tool_rounds)

        while True:
            # 2) 组装 LLM 输入（system + 工具目录[可选] + 内部历史）
            messages = await self._build_llm_messages(conversation_uid)
            tools = [self._tool_emit_user_reply(), self._tool_emit_task_request()]

            # 3) 调 LLM（带重试）
            raw_resp, err = await self._call_llm_with_retry(messages, tools)
            if err or raw_resp is None:
                fallback = f"抱歉，本轮解析失败：{err or 'LLM 无返回'}"
                await self._append_internal(conversation_uid, role="assistant", text=fallback)
                await self._append_main(conversation_uid, role="assistant", text=fallback)
                return fallback

            # 4) 记录 LLM 原始输出到内部流
            await self._append_internal(
                conversation_uid, role="assistant",
                text=json.dumps(raw_resp, ensure_ascii=False)
            )

            # 5) 解析意图
            intent, payload, perr = self._parse_llm_decision(raw_resp)
            if perr:
                # 不立刻退出，给模型一个轻提示并进入下一轮（受上限约束）
                nudge = f"请仅调用 emit_user_reply 或 emit_task_request 两个函数之一。错误信息：{perr}"
                await self._append_internal(conversation_uid, role="system", text=nudge)
                tool_round += 1
                if tool_round >= limit:
                    final_text = "本轮已达最大尝试次数，请确认需求或稍后再试。"
                    await self._append_main(conversation_uid, role="assistant", text=final_text)
                    return final_text
                continue

            # 6) 分流执行
            if intent == "user_reply":
                content = (payload.get("content") or "").strip() or "(空)"
                await self._append_main(conversation_uid, role="assistant", text=content)
                return content

            if intent == "task_request":
                description = (payload.get("description") or "").strip()
                if not description:
                    # 任务描述为空，提示并进入下一轮
                    note = "任务描述为空，无法创建或推进。请补全关键信息。"
                    await self._append_internal(conversation_uid, role="assistant", text=note)
                    tool_round += 1
                    if tool_round >= limit:
                        # 达到上限：请求模型输出一句面向用户的总结/下一步说明
                        summary_prompt = (
                            "请用一句中文向用户说明当前进展："
                            "若任务已成功，给出明确结果；"
                            "若仍需信息或发生失败，说明缺失项/原因，并给出下一步建议。"
                            "只输出给用户看的文本。"
                        )
                        await self._append_internal(conversation_uid, role="system", text=summary_prompt)
                        messages2 = await self._build_llm_messages(conversation_uid)
                        raw2, err2 = await self._call_llm_with_retry(messages2, tools)
                        final_text = None
                        if not err2 and raw2:
                            await self._append_internal(
                                conversation_uid, role="assistant",
                                text=json.dumps(raw2, ensure_ascii=False)
                            )
                            fin_intent, fin_payload, _ = self._parse_llm_decision(raw2)
                            if fin_intent == "user_reply":
                                final_text = (fin_payload.get("content") or "").strip()
                        if not final_text:
                            final_text = "本轮已达最大尝试次数，请确认需求或稍后再试。"
                        await self._append_main(conversation_uid, role="assistant", text=final_text)
                        return final_text
                    # 未达上限：继续循环
                    continue

                # ===== 在此处查询 user_uid（owner_uid） =====
                owner_uid = await self._get_owner_uid(conversation_uid)
                if not owner_uid:
                    # 兜底：允许使用 default_user_uid；若也没有则报错并退出
                    if self.default_user_uid:
                        owner_uid = self.default_user_uid
                    else:
                        msg = "无法确定任务归属用户：未在数据库(conversations)中找到该对话的 owner_uid。"
                        await self._append_internal(conversation_uid, role="assistant", text=msg)
                        await self._append_main(conversation_uid, role="assistant", text=msg)
                        return msg

                # 调用执行器
                try:
                    res = await self.executor.create_task(owner_uid, plan_text=description)
                except Exception as e:
                    res = {"ok": False, "error": f"执行器异常: {e!r}"}
                # 执行器回执写入内部流（role=tool）
                await self._append_internal(
                    conversation_uid, role="tool",
                    text=json.dumps(res, ensure_ascii=False)
                )

                tool_round += 1
                if tool_round >= limit:
                    # 达到上限：请求模型输出一句面向用户的总结/下一步说明
                    summary_prompt = (
                        "请用一句中文向用户说明当前进展："
                        "若任务已成功，给出明确结果（含 task_uid，如有）；"
                        "若仍需信息或发生失败，说明缺失项/原因，并给出下一步建议。"
                        "只输出给用户看的文本。"
                    )
                    await self._append_internal(conversation_uid, role="system", text=summary_prompt)
                    messages2 = await self._build_llm_messages(conversation_uid)
                    raw2, err2 = await self._call_llm_with_retry(messages2, tools)
                    final_text = None
                    if not err2 and raw2:
                        await self._append_internal(
                            conversation_uid, role="assistant",
                            text=json.dumps(raw2, ensure_ascii=False)
                        )
                        fin_intent, fin_payload, _ = self._parse_llm_decision(raw2)
                        if fin_intent == "user_reply":
                            final_text = (fin_payload.get("content") or "").strip()
                    if not final_text:
                        final_text = "本轮已达最大尝试次数，请确认需求或稍后再试。"
                    await self._append_main(conversation_uid, role="assistant", text=final_text)
                    return final_text

                # 未达上限：继续把“工具回执”作为上下文喂给模型
                continue

            # 7) 兜底：未知分支（理论上不会到这）。给个轻提示并继续循环
            await self._append_internal(conversation_uid, role="system",
                                        text="请仅使用 emit_user_reply 或 emit_task_request。")
            tool_round += 1
            if tool_round >= limit:
                final_text = "本轮已达最大尝试次数，请确认需求或稍后再试。"
                await self._append_main(conversation_uid, role="assistant", text=final_text)
                return final_text
            # 继续下一轮
            continue

    # -------------------- LLM 调用与解析 --------------------

    async def _call_llm_with_retry(self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]):
        attempts = 0
        errors: List[str] = []
        while attempts < max(1, self.cfg.max_retries):
            attempts += 1
            raw, err = await self._call_llm(messages, tools)
            if not err and raw is not None:
                return raw, None
            errors.append(err or "unknown")
        return None, "; ".join(errors)

    async def _call_llm(self, messages: List[dict], tools: List[dict]) -> Tuple[Optional[dict], Optional[str]]:
        try:
            resp = await self._client.chat.completions.create(
                model=self.cfg.model,
                messages=messages,
                temperature=0.2,
                tools=tools,
                tool_choice="required",
            )
            return json.loads(resp.model_dump_json()), None
        except Exception as e:
            return None, f"chat.completions failed: {repr(e)}"

    def _parse_llm_decision(self, resp: dict) -> Tuple[Optional[str], Dict[str, Any], Optional[str]]:
        """
        返回:
          - intent: "user_reply" | "task_request" | None
          - payload: {"content": "..."} 或 {"description": "..."}
          - error: 解析错误描述（无错误则为 None）
        """
        try:
            choices = resp.get("choices") or []
            msg = (choices[0] or {}).get("message") or {}

            # 1) 新版 tool_calls
            for tc in (msg.get("tool_calls") or []):
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
                    return "user_reply", {"content": (args_obj.get("content") or "")}, None
                if name == "emit_task_request":
                    return "task_request", {"description": (args_obj.get("description") or "")}, None

            # 2) 旧版 function_call
            fc = msg.get("function_call") or {}
            if fc.get("name") in ("emit_user_reply", "emit_task_request"):
                args = fc.get("arguments")
                if isinstance(args, str):
                    try:
                        args_obj = json.loads(args)
                    except Exception:
                        args_obj = {"_raw": args}
                else:
                    args_obj = args or {}
                if fc.get("name") == "emit_user_reply":
                    return "user_reply", {"content": (args_obj.get("content") or "")}, None
                else:
                    return "task_request", {"description": (args_obj.get("description") or "")}, None

            # 3) 内容兜底（部分网关把 JSON 塞在 content）
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
        # 如果整体以代码围栏开头（例如 ``` 或 ```json），去掉首尾围栏行
        if txt.startswith("```"):
            lines: List[str] = []
            for line in txt.splitlines():
                if line.strip().startswith("```"):
                    continue
                lines.append(line)
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
                    "当你认为需要创建或推进任务时调用此函数。把完整的自然语言描述放进 description，"
                    "描述应清楚表达要做什么、关键输入/输出和期望结果。"
                ),
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["description"],
                    "properties": {
                        "description": {
                            "type": "string",
                            "minLength": 4,
                            "description": "创建/推进任务所需的自然语言描述（执行器会把它结构化为严格计划）。"
                        }
                    }
                }
            }
        }

    # -------------------- 构造对 LLM 的 messages --------------------

    async def _build_llm_messages(self, conversation_uid: str) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = [{"role": "system", "content": self.cfg.system_prefix}]

        # —— 注入一次精简工具目录（只读；真实调用仍由执行器完成）——
        if self.cfg.include_tool_catalog:
            if self._tool_catalog_cache is None:
                self._tool_catalog_cache = await self._get_tool_catalog_text()
            if self._tool_catalog_cache:
                msgs.append({
                    "role": "system",
                    "content": (
                        "以下为当前环境的工具能力简介，供你编写更贴近工具能力的任务描述时参考（仅供理解，调用由后端完成）：\n"
                        + self._tool_catalog_cache
                    )
                })

        # —— 拼接内部信息流历史 —— #
        res = await self.cm.get_messages(conversation_uid, target=self.stream_id)
        if res.get("ok"):
            for it in (res.get("messages") or []):
                role = str(it.get("role") or "user")
                text = str(it.get("content") or "")
                if role not in {"system", "user", "assistant", "tool"}:
                    role = "user"
                msgs.append({"role": role, "content": text})
        return msgs

    async def _get_tool_catalog_text(self) -> Optional[str]:
        """
        从 task_manager 读取工具列表并格式化为简洁目录文本；
        task_manager 为异步外观（如 AsyncTaskManager）。
        """
        try:
            tools = await self.tm.list_tools()
        except Exception:
            return None
        if not tools:
            return None

        N = max(1, int(self.cfg.tool_catalog_limit))
        L = max(40, int(self.cfg.tool_desc_maxlen))
        lines: List[str] = []
        for t in tools[:N]:
            name = str(t.get("name", "")).strip()[:80]
            desc = str(t.get("description", "")).strip()
            desc = " ".join(desc.split())
            if len(desc) > L:
                desc = desc[:L].rstrip() + "..."
            if name:
                lines.append(f"- {name}: {desc}" if desc else f"- {name}")
        if not lines:
            return None
        return "\n".join(lines)

    # -------------------- 与 CM 的读写（直接写 role/content） --------------------

    async def _append_main(self, conversation_uid: str, role: str, text: str) -> None:
        await self.cm.add_message_to_main(conversation_uid, role=role, content=text)

    async def _append_internal(self, conversation_uid: str, role: str, text: str) -> None:
        await self.cm.add_message_to_stream(conversation_uid, target=self.stream_id, role=role, content=text)

    # -------------------- DB 查询：根据对话ID拿 owner_uid --------------------

    async def _get_owner_uid(self, conversation_uid: str) -> Optional[str]:
        """
        查询 conversations(conversation_uid, owner_uid)，返回 owner_uid。
        - 使用线程池包装同步 sqlite3，避免阻塞事件循环。
        """
        return await asyncio.to_thread(self._lookup_owner_uid_sync, conversation_uid)

    def _lookup_owner_uid_sync(self, conversation_uid: str) -> Optional[str]:
        try:
            conn = sqlite3.connect(self.db_path.as_posix(), check_same_thread=False)
            try:
                cur = conn.execute(
                    "SELECT owner_uid FROM conversations WHERE conversation_uid = ? LIMIT 1",
                    (conversation_uid,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])
                return None
            finally:
                conn.close()
        except Exception:
            return None
