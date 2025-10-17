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
    max_tool_rounds: int = 3                      # 连续“工具/任务/查询状态”回合上限

    # —— 是否在 system 中注入工具目录（只读，帮助模型写出更贴近工具的描述）——
    include_tool_catalog: bool = True
    tool_catalog_limit: int = 20                  # 最多注入多少条工具
    tool_desc_maxlen: int = 160                   # 每条工具描述的截断长度（字符数）

    # 系统提示
    system_prefix: str = (
        """
你现在是一个医疗工具助手系统中的核心智能体，负责和用户直接对话，然后根据用户的需求执行对应操作（实际执行会交由其他模块完成）。
为了保证你的输出规范可以被固定程序解析，你在产生回复时只能通过调用工具的形式。
你想要进行输出时，根据需求从以下函数中挑选一个
1) 若应直接回复用户，请调用函数 emit_user_reply，并把要说的话放到 content；
2) 若需要创建或推进一项任务，请调用函数 emit_task_request，并把用于创建/推进任务的自然语言描述放到 description；
在你使用这个功能之前，保证你要先回复一次用户，把你想要生成的创建任务的自然语言描述交给用户审核一遍，用户确认无误之后再正式使用该功能创建任务。很多工具的参数是只有输入源的，没有额外参数，不要臆造参数来询问用户，这会对用户造成困扰。
3) 若用户想查询某个任务的运行状态，请调用函数 emit_task_status_query，并把任务的 task_uid 放到 task_uid。

禁止输出纯文本，你必须调用以上三个函数之一。对话上下文以系统提供的消息为准。
有时候用户会想知道你拥有什么功能，不要将上述这几个函数暴露给用户，这些函数只是为了规范输出而设置的。
后续会将实际可用的工具函数列表暴露给你，这些才是用户真的想知道的内容。
同时，在调用函数 emit_task_request来创建任务时，本质上会将你提出的描述提交给一个专门负责创建任务的智能体（后续简称智能体B），由它来生成规范的、可以被解析的输出
之后系统会解析智能体B的输出，来进行具体的操作。为了降低智能体B的负担，我虽然不要求你生成的描述格式上规范，但至少保证信息要清晰。

【严格约束——避免“画蛇添足”】
- 不要臆造或扩展任何工具参数键名、字段名或取值；不要凭空给工具加默认值。
- 如需提到工具，只能使用“工具目录”中出现的名称。
- 你的任务描述可以写**目的/输入/输出/约束**的自然语言，如果能明确，则具体到参数键名（例如 batch_size、epochs、lr、patch_size 等）。
- 如果用户明确给了参数（例如“批大小 64”），尝试转换为“参数键名: 值”的格式。
- 不确定时，不要猜；要么向用户澄清（emit_user_reply），要么在任务描述里标注“需后端根据工具规范补全参数”。
- 若后端已返回“创建成功”且含 task_uid，你必须立刻 emit_user_reply：
  • 告知“任务已创建”
  • 明确给出 task_uid

【任务描述模板（用于 emit_task_request.description）】
请严格用自然语言短段落，包含：
- 目的（一句话概述要做什么，然后可以补充上具体的参数）
- 输入来源（数据/路径/上游结果）

【决策准则】
- 信息不足则先 emit_user_reply 提问澄清（一次性补齐的具体问题）。
- 能开始则 emit_task_request。
- 用户询问进度/状态/日志→ emit_task_status_query，拿到状态后用一句中文汇报。
        """.strip()
    )


# ============== 松耦合协议（对话管理器 / 执行器 / 任务管理器） ==============

class ConversationManagerLike(Protocol):
    async def add_message_to_main(self, conversation_uid: str, role: str, content: str) -> Dict[str, Any]: ...
    async def add_message_to_stream(self, conversation_uid: str, target: str, role: str, content: str) -> Dict[str, Any]: ...
    async def get_messages(self, conversation_uid: str, target: str) -> Dict[str, Any]: ...


class ExecutorLike(Protocol):
    """执行器：至少具备 create_task(user_uid, plan_text)。"""
    async def create_task(self, user_uid: Optional[str], plan_text: str) -> Dict[str, Any]: ...


class TaskManagerAsyncLike(Protocol):
    """
    你提供的 AsyncTaskManager 关键接口（我们只用到 list_tools 与 get_task_status）。
    """
    async def list_tools(self) -> List[Dict[str, Any]]: ...
    async def get_task_status(self, task_uid: str) -> Dict[str, Any]: ...


# ============================ 主类 ============================

class DialogueAgentA:
    """
    - 初始化需要：executor（执行器）、cm（对话管理器）、stream_id（内部信息流识别码）、
                 task_manager（获取工具目录/查询任务状态）、数据库文件 db_path、可选 default_user_uid。
    - 创建/推进任务时：根据 conversation_uid → 查 SQLite(conversations) → 取 owner_uid 作为 user_uid。
    - 新增：emit_task_status_query → 调用 tm.get_task_status(task_uid)。
    """

    def __init__(
        self,
        executor: ExecutorLike,
        config: AgentAConfig,
        *,
        cm: ConversationManagerLike,
        stream_id: str,
        task_manager: TaskManagerAsyncLike,
        db_path: Union[str, Path],
        default_user_uid: Optional[str] = None,
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
        # 1) 记录用户消息
        await self._append_main(conversation_uid, role="user", text=user_input)
        await self._append_internal(conversation_uid, role="user", text=user_input)

        tool_round = 0
        limit = max(1, self.cfg.max_tool_rounds)

        while True:
            # 2) 组装 LLM 输入（system + 工具目录[可选] + 内部历史）
            messages = await self._build_llm_messages(conversation_uid)
            tools = [
                self._tool_emit_user_reply(),
                self._tool_emit_task_request(),
                self._tool_emit_task_status_query(),  # 新增
            ]

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
                nudge = "请仅调用 emit_user_reply / emit_task_request / emit_task_status_query 之一。" + f"错误：{perr}"
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
                    note = "任务描述为空，无法创建或推进。请补全关键信息。"
                    await self._append_internal(conversation_uid, role="assistant", text=note)
                    tool_round += 1
                    if tool_round >= limit:
                        final_text = "本轮已达最大尝试次数，请确认需求或稍后再试。"
                        await self._append_main(conversation_uid, role="assistant", text=final_text)
                        return final_text
                    continue

                # 查询任务归属用户
                owner_uid = await self._get_owner_uid(conversation_uid)
                if not owner_uid:
                    if self.default_user_uid:
                        owner_uid = self.default_user_uid
                    else:
                        msg = "无法确定任务归属用户：未在数据库(conversations)中找到该对话的 owner_uid。"
                        await self._append_internal(conversation_uid, role="assistant", text=msg)
                        await self._append_main(conversation_uid, role="assistant", text=msg)
                        return msg

                # 调用执行器创建任务（保持你的现有架构：创建由 executor 负责）
                try:
                    res = await self.executor.create_task(owner_uid, plan_text=description)
                except Exception as e:
                    res = {"ok": False, "error": f"执行器异常: {e!r}"}

                # 执行器回执写入内部流
                await self._append_internal(
                    conversation_uid, role="tool_result",
                    text=json.dumps(res, ensure_ascii=False)
                )

                tool_round += 1
                if tool_round >= limit:
                    # 请模型向用户做一句话总结（含 task_uid 如有）
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

                continue  # 未达上限，继续作为上下文驱动下一轮

            if intent == "task_status_query":
                task_uid = (payload.get("task_uid") or "").strip()
                if not task_uid:
                    note = "未提供 task_uid，无法查询任务状态。请给出具体 task_uid。"
                    await self._append_internal(conversation_uid, role="assistant", text=note)
                    tool_round += 1
                    if tool_round >= limit:
                        final_text = "没有 task_uid，无法查询任务状态。请提供任务编号后重试。"
                        await self._append_main(conversation_uid, role="assistant", text=final_text)
                        return final_text
                    continue

                # —— 直接调用你提供的异步包装：tm.get_task_status(task_uid) —— #
                try:
                    result = await self.tm.get_task_status(task_uid)
                except Exception as e:
                    result = {"ok": False, "error": f"查询异常: {e!r}", "task_uid": task_uid}

                await self._append_internal(
                    conversation_uid, role="tool_result",
                    text=json.dumps(result, ensure_ascii=False)
                )

                # 让模型基于 tool_result 说一句人话；若失败则用兜底摘要
                tool_round += 1
                if tool_round >= limit:
                    final_text = self._summarize_status_for_user(result)
                    await self._append_main(conversation_uid, role="assistant", text=final_text)
                    return final_text

                summary_prompt = (
                    "请读取上一个工具结果中的任务状态，为用户用一句中文进行简明汇报："
                    "指出任务当前状态（运行中/已完成/失败），若提供了 progress 则给出百分比，"
                    "若有 running_step 则简单点名（不超过一处），并包含 task_uid。只输出给用户看的文本。"
                )
                await self._append_internal(conversation_uid, role="system", text=summary_prompt)
                messages2 = await self._build_llm_messages(conversation_uid)
                raw2, err2 = await self._call_llm_with_retry(messages2, tools)
                if not err2 and raw2:
                    await self._append_internal(
                        conversation_uid, role="assistant",
                        text=json.dumps(raw2, ensure_ascii=False)
                    )
                    fin_intent, fin_payload, _ = self._parse_llm_decision(raw2)
                    if fin_intent == "user_reply":
                        final_text = (fin_payload.get("content") or "").strip() or "已返回任务状态。"
                        await self._append_main(conversation_uid, role="assistant", text=final_text)
                        return final_text

                final_text = self._summarize_status_for_user(result)
                await self._append_main(conversation_uid, role="assistant", text=final_text)
                return final_text

            # 7) 兜底
            await self._append_internal(conversation_uid, role="system",
                                        text="请仅使用 emit_user_reply / emit_task_request / emit_task_status_query。")
            tool_round += 1
            if tool_round >= limit:
                final_text = "本轮已达最大尝试次数，请确认需求或稍后再试。"
                await self._append_main(conversation_uid, role="assistant", text=final_text)
                return final_text
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
          - intent: "user_reply" | "task_request" | "task_status_query" | None
          - payload: {"content": "..."} | {"description": "..."} | {"task_uid": "..."}
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
                if name == "emit_task_status_query":
                    return "task_status_query", {"task_uid": (args_obj.get("task_uid") or "")}, None

            # 2) 旧版 function_call
            fc = msg.get("function_call") or {}
            if fc.get("name") in ("emit_user_reply", "emit_task_request", "emit_task_status_query"):
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
                if fc.get("name") == "emit_task_request":
                    return "task_request", {"description": (args_obj.get("description") or "")}, None
                return "task_status_query", {"task_uid": (args_obj.get("task_uid") or "")}, None

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
                        if obj.get("type") == "task_status_query" and "task_uid" in obj:
                            return "task_status_query", {"task_uid": str(obj["task_uid"])}, None
                except Exception:
                    pass

            return None, {}, "未找到函数调用（tool_calls/function_call/content 解析失败）"
        except Exception as e:
            return None, {}, f"解析异常：{e!r}"

    @staticmethod
    def _strip_json_fences(txt: str) -> str:
        txt = txt.strip()
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

    def _tool_emit_task_status_query(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "emit_task_status_query",
                "description": "当用户想查询某个任务的运行状态时调用此函数，传入任务的 task_uid。",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_uid"],
                    "properties": {
                        "task_uid": {
                            "type": "string",
                            "minLength": 4,
                            "description": "要查询状态的任务唯一编号（task_uid）。"
                        }
                    }
                }
            }
        }

    # -------------------- 构造对 LLM 的 messages --------------------

    async def _build_llm_messages(self, conversation_uid: str) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = [{"role": "system", "content": self.cfg.system_prefix}]

        # 注入一次精简工具目录（只读）
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

        # 拼接内部信息流历史
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

    # -------------------- 与 CM 的读写 --------------------

    async def _append_main(self, conversation_uid: str, role: str, text: str) -> None:
        await self.cm.add_message_to_main(conversation_uid, role=role, content=text)

    async def _append_internal(self, conversation_uid: str, role: str, text: str) -> None:
        await self.cm.add_message_to_stream(conversation_uid, target=self.stream_id, role=role, content=text)

    # -------------------- DB 查询：根据对话ID拿 owner_uid --------------------

    async def _get_owner_uid(self, conversation_uid: str) -> Optional[str]:
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

    # -------------------- 兜底摘要：把 get_task_status 返回压成一句人话 --------------------

    def _summarize_status_for_user(self, result: Dict[str, Any]) -> str:
        """
        适配你提供的 get_task_status 返回结构：
        {
          "ok": True/False,
          "task_uid": "...",
          "status": "running|succeeded|failed|queued|created|...",
          "user_uid": "...",
          "total_steps": int,
          "last_completed_step": int,
          "current_step_number": Optional[int],
          "current_step_uid": Optional[str],
          "failed_step_number": Optional[int],
          "failed_step_uid": Optional[str],
          "running_step": Optional[{
              "step_uid": "...",
              "step_number": int,
              "tool_name": "...",
              "status": "running",
              "run_id": "..."
          }],
          "progress": Optional[float in [0,1]]
        }
        """
        ok = result.get("ok", False)
        task_uid = result.get("task_uid") or "(未知)"
        if not ok:
            return f"查询任务 {task_uid} 状态失败：{result.get('error') or '未知错误'}。"

        status = str(result.get("status") or "").lower()
        progress = result.get("progress")
        prog_txt = ""
        if isinstance(progress, (int, float)):
            try:
                prog_txt = f"（进度 {round(progress * 100)}%）"
            except Exception:
                prog_txt = ""

        running = result.get("running_step") or {}
        running_hint = ""
        if isinstance(running, dict) and running:
            sn = running.get("step_number")
            tn = running.get("tool_name")
            if sn is not None and tn:
                running_hint = f"；当前执行第{sn}步 {tn}"
            elif sn is not None:
                running_hint = f"；当前执行第{sn}步"
            elif tn:
                running_hint = f"；当前执行 {tn}"

        failed_no = result.get("failed_step_number")
        failed_uid = result.get("failed_step_uid")
        failed_hint = ""
        if failed_no is not None or failed_uid:
            if failed_no is not None and failed_uid:
                failed_hint = f"；失败发生在第{failed_no}步（{failed_uid}）"
            elif failed_no is not None:
                failed_hint = f"；失败发生在第{failed_no}步"
            else:
                failed_hint = f"；失败步骤UID：{failed_uid}"

        # 统一的对用户文案
        status_map = {
            "running": "运行中",
            "succeeded": "已完成",
            "success": "已完成",
            "done": "已完成",
            "failed": "失败",
            "error": "失败",
            "queued": "排队中",
            "created": "已创建",
        }
        human = status_map.get(status, status or "未知")

        return f"任务 {task_uid} 当前状态：{human}{prog_txt}{running_hint}{failed_hint}。"
