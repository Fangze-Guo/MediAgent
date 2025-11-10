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

# 数据集管理器
try:
    from src.server_new.mediagent.modules import dataset_manager as dsman
except Exception:
    dsman = None  # type: ignore


# ============================ 配置 ============================

@dataclass
class AgentAConfig:
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    request_timeout: float = 60.0
    max_retries: int = 2
    max_tool_rounds: int = 3

    include_tool_catalog: bool = True
    tool_catalog_limit: int = 20
    tool_desc_maxlen: int = 160

    system_prefix: str = (
        """
你现在是一个医疗工具助手系统中的核心智能体，负责与用户直接对话，然后根据用户的需求执行对应操作（实际执行会交由其他模块完成）。

==============================【语言行为规则——严格遵循】==============================
1. 用户可能使用中文或英文与你对话。
   - 若用户使用中文，你必须全程使用中文回复（除非是必要的专有名词或工具名）。
   - 若用户使用英文，你必须全程使用英文回复。
2. 你的回复语言完全由用户最近一次输入语言决定，而不是由上下文其他部分决定。
3. 工具的返回结果或内部控制信息可能包含中英文混杂内容，这些仅供参考，绝不能影响你回复的语言选择。
4. 内部控制、路径、参数、标识符、日志等信息（通常为英文）仅用于系统执行，不影响输出语言。
5. 绝不要在一句话中混合中英文语句，也不要因为系统消息是英文就切换语言。
6. 若不确定用户语言，应优先根据用户上一条消息判断；若上一条消息为中英混杂，则默认使用中文。

==============================【输出方式规范】==============================
为了保证输出可被固定程序解析，你在产生回复时只能通过调用以下函数之一：

1. emit_user_reply：若要直接回复用户，把要说的话放在 content 字段中。
2. emit_task_request：若需要创建或推进任务，把用于创建/推进任务的自然语言描述放到 description 字段中。
   - 在使用此功能前，必须先用 emit_user_reply 与用户确认你准备创建的任务描述。
   - 用户确认无误后，再正式使用该功能创建任务。
   - 很多工具仅有输入源参数，无需额外参数，不要臆造或随意询问。
   - 任何处理或分析的数据必须用“数据集ID（整数）”标识，而非名称或路径。
     若用户未提供数据集ID，必须先 emit_user_reply 询问确认。
     例如：不要说“用乳腺MRI数据集”，应确认成“用数据集ID=42”。
3. emit_task_status_query：若用户想查询任务运行状态，放入 task_uid。
4. emit_dataset_info_query：若用户想查看数据集信息：
   - mode="overview"：查看用户可访问的数据集整体情况（无需其它参数）。
   - mode="focus"：需同时提供 dataset_id 与 user_need_text（自然语言问题描述）。
     * overview 返回所有可访问数据集摘要。
     * focus 返回该数据集的详细总结（100–200字左右）。
   - 你拿到结果后，应根据用户问题整理重点反馈。

禁止输出纯文本。任何输出都必须通过上述四个函数之一完成。
不要向用户暴露函数名或系统机制——这些仅为结构化输出规范。

创建任务时（emit_task_request）会交由后端的“智能体B”进行结构化计划。
任务描述可为自然语言，不要求固定格式，但须清晰表达意图、输入来源、关键参数。

==============================【严格约束——避免“画蛇添足”】==============================
- 不要臆造工具参数、字段名或默认值。
- 若需提到工具，只能使用“工具目录”中出现的名称。
- 任务描述可包含目的 / 输入 / 输出 / 约束，并应融入用户提供的具体参数（如 batch_size=64）。
- 所有数据集引用必须采用格式：“使用数据集ID=42进行推理”。
  绝不允许用模糊描述（如“乳腺MRI数据集”）直接创建任务，先询问ID。
- 信息不足时，不要猜测。
  - 若需用户补充 → emit_user_reply。
  - 若后端可推断 → 在任务描述中写明“需后端补全此参数”。

==============================【数据集查询使用准则】==============================
- 用户问“我有哪些数据集 / 这些数据集大概是什么内容？” → emit_dataset_info_query，mode="overview"。
- 用户针对某个具体数据集提问（如“这个数据集是否包含肿瘤分割标注？”） → emit_dataset_info_query，mode="focus"，并给出 dataset_id 和 user_need_text。
- 用户模糊提问（如“帮我看看乳腺MRI数据集”）但未给 dataset_id → emit_user_reply 询问“请提供数据集ID数字及你想了解的内容”。

==============================【决策准则】==============================
- 若信息不足（尤其缺 dataset_id、task_uid、目标说明），请先 emit_user_reply 一次性问清。
- 信息充分时，按需调用：
  - emit_dataset_info_query
  - emit_task_request
  - emit_task_status_query
  - emit_user_reply

==============================【语言一致性示例】==============================
- 用户：“你好，请帮我查看数据集” → 回复全中文。
- 用户：“Please run nnUNet on dataset ID=42” → 回复全英文。
- 工具返回中有中英文混杂时，只取内容要点，用用户语言重新组织表述。
        """.strip()
    )


# ============== 协议接口 ==============

class ConversationManagerLike(Protocol):
    async def add_message_to_main(self, conversation_uid: str, role: str, content: str) -> Dict[str, Any]: ...
    async def add_message_to_stream(self, conversation_uid: str, target: str, role: str, content: str) -> Dict[str, Any]: ...
    async def get_messages(self, conversation_uid: str, target: str) -> Dict[str, Any]: ...


class ExecutorLike(Protocol):
    async def create_task(self, user_uid: Optional[str], plan_text: str) -> Dict[str, Any]: ...


class TaskManagerAsyncLike(Protocol):
    async def list_tools(self) -> List[Dict[str, Any]]: ...
    async def get_task_status(self, task_uid: str) -> Dict[str, Any]: ...


# ============================ 主类 ============================

class DialogueAgentA:
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

        self._tool_catalog_cache: Optional[str] = None

    # -------------------- 对外主入口 --------------------
    async def converse(self, conversation_uid: str, user_input: str) -> str:
        await self._append_main(conversation_uid, role="user", text=user_input)
        await self._append_internal(conversation_uid, role="user", text=user_input)

        tool_round = 0
        limit = max(1, self.cfg.max_tool_rounds)

        while True:
            messages = await self._build_llm_messages(conversation_uid)
            tools = [
                self._tool_emit_user_reply(),
                self._tool_emit_task_request(),
                self._tool_emit_task_status_query(),
                self._tool_emit_dataset_info_query(),
            ]

            raw_resp, err = await self._call_llm_with_retry(messages, tools)
            if err or raw_resp is None:
                fallback = f"抱歉，本轮解析失败：{err or 'LLM 无返回'}"
                await self._append_internal(conversation_uid, role="assistant", text=fallback)
                await self._append_main(conversation_uid, role="assistant", text=fallback)
                return fallback

            await self._append_internal(
                conversation_uid, role="assistant",
                text=json.dumps(raw_resp, ensure_ascii=False)
            )

            intent, payload, perr = self._parse_llm_decision(raw_resp)
            if perr:
                nudge = (
                    "请仅调用 emit_user_reply / emit_task_request / "
                    "emit_task_status_query / emit_dataset_info_query 之一。"
                    f"错误：{perr}"
                )
                await self._append_internal(conversation_uid, role="system", text=nudge)
                tool_round += 1
                if tool_round >= limit:
                    final_text = "本轮已达最大尝试次数，请确认需求或稍后再试。"
                    await self._append_main(conversation_uid, role="assistant", text=final_text)
                    return final_text
                continue

            # ---------- 普通回复 ----------
            if intent == "user_reply":
                content = (payload.get("content") or "").strip() or "(空)"
                await self._append_main(conversation_uid, role="assistant", text=content)
                return content

            # ---------- 创建/推进任务 ----------
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

                owner_uid = await self._get_owner_uid(conversation_uid)
                if not owner_uid:
                    owner_uid = self.default_user_uid
                if not owner_uid:
                    msg = "无法确定任务归属用户：未找到 owner_uid。"
                    await self._append_internal(conversation_uid, role="assistant", text=msg)
                    await self._append_main(conversation_uid, role="assistant", text=msg)
                    return msg

                try:
                    res = await self.executor.create_task(owner_uid, plan_text=description)
                except Exception as e:
                    res = {"ok": False, "error": f"执行器异常: {e!r}"}

                await self._append_internal(
                    conversation_uid, role="tool_result",
                    text=json.dumps(res, ensure_ascii=False)
                )

                tool_round += 1
                if tool_round >= limit:
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

                continue

            # ---------- 查询任务状态 ----------
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

                try:
                    result = await self.tm.get_task_status(task_uid)
                except Exception as e:
                    result = {"ok": False, "error": f"查询异常: {e!r}", "task_uid": task_uid}

                await self._append_internal(
                    conversation_uid, role="tool_result",
                    text=json.dumps(result, ensure_ascii=False)
                )

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

            # ---------- 数据集信息查询 ----------
            if intent == "dataset_info_query":
                mode = str(payload.get("mode") or "").strip().lower()
                if mode not in {"overview", "focus"}:
                    msg = "数据集查询失败：mode 仅支持 overview 或 focus。"
                    await self._append_main(conversation_uid, role="assistant", text=msg)
                    return msg

                if dsman is None:
                    msg = "数据集查询失败：dataset_manager 模块未就绪。"
                    await self._append_main(conversation_uid, role="assistant", text=msg)
                    return msg

                # 统一拿 user_uid
                owner_uid_str = await self._get_owner_uid(conversation_uid)
                if not owner_uid_str:
                    owner_uid_str = self.default_user_uid
                if not owner_uid_str:
                    msg = "数据集查询失败：无法确定当前用户身份（owner_uid）。"
                    await self._append_main(conversation_uid, role="assistant", text=msg)
                    return msg

                # dataset_manager 目前期望 user_uid 是 int
                try:
                    owner_uid_int = int(owner_uid_str)
                except Exception:
                    msg = f"数据集查询失败：无法解析用户ID {owner_uid_str!r} 为整数。"
                    await self._append_main(conversation_uid, role="assistant", text=msg)
                    return msg

                try:
                    if mode == "overview":
                        # 1) 调 dataset_manager.overview
                        res = await dsman.overview(
                            user_uid=owner_uid_int,
                            db_path=dsman.DATASET_DB_PATH,
                            limit=None,
                        )

                        # 2) 记录内部流
                        await self._append_internal(
                            conversation_uid, role="tool_result",
                            text=json.dumps({
                                "source": "dataset_manager",
                                "mode": "overview",
                                "result": res
                            }, ensure_ascii=False)
                        )

                        ok = bool(res.get("ok"))
                        text = (res.get("text") or "（无返回）")

                        # 3) 让 LLM 生成最终对用户回复
                        post_prompt = (
                            "请基于上一个工具结果(result.text)，结合当前对话上下文，"
                            "向用户输出最终回答："
                            "• 模式=overview：对该用户可访问的全部数据集做全局归纳/对比，"
                            "  特别强调每个数据集大概包含什么（病例数量/影像/文本/病理/基因/标注），"
                            "  如果有公共数据集(公共=所有人都可看)，也请提一下。"
                            "• 禁止臆造；不要贴回原始表格源码；"
                            "• 只调用 emit_user_reply。"
                        )
                        await self._append_internal(conversation_uid, role="system", text=post_prompt)

                        messages2 = await self._build_llm_messages(conversation_uid)
                        raw2, err2 = await self._call_llm_with_retry(messages2, tools)
                        if not err2 and raw2:
                            await self._append_internal(
                                conversation_uid, role="assistant",
                                text=json.dumps(raw2, ensure_ascii=False)
                            )
                            fin_intent, fin_payload, _ = self._parse_llm_decision(raw2)
                            if fin_intent == "user_reply":
                                final = (fin_payload.get("content") or "").strip()
                                if final:
                                    await self._append_main(conversation_uid, role="assistant", text=final)
                                    return final

                        # fallback
                        msg = text if ok else f"读取数据集总览失败：{text}"
                        await self._append_main(conversation_uid, role="assistant", text=msg)
                        return msg

                    # mode == "focus"
                    dataset_id_raw = (payload.get("dataset_id") or "").strip()
                    need = (payload.get("user_need_text") or "").strip()

                    if not dataset_id_raw or not need:
                        msg = "请提供完整参数：dataset_id（数字）和 user_need_text（本次具体想了解什么）。"
                        await self._append_main(conversation_uid, role="assistant", text=msg)
                        return msg

                    try:
                        dataset_id_int = int(dataset_id_raw)
                    except Exception:
                        msg = f"dataset_id 必须是整数，当前是 {dataset_id_raw!r}"
                        await self._append_main(conversation_uid, role="assistant", text=msg)
                        return msg

                    # 1) 调 dataset_manager.focus
                    res = await dsman.focus(
                        dataset_id=dataset_id_int,
                        user_need_text=need,
                        user_uid=owner_uid_int,
                        db_path=dsman.DATASET_DB_PATH,
                    )

                    # 2) 内部流记录
                    await self._append_internal(
                        conversation_uid, role="tool_result",
                        text=json.dumps({
                            "source": "dataset_manager",
                            "mode": "focus",
                            "dataset_id": dataset_id_int,
                            "user_need_text": need,
                            "result": res
                        }, ensure_ascii=False)
                    )

                    ok = bool(res.get("ok"))
                    text = (res.get("text") or "（无返回）")

                    # 3) 让 LLM 生成最终回答
                    post_prompt = (
                        "请基于上一个工具结果(result.text)，结合用户本轮的具体问题(user_need_text)，"
                        "向用户输出最终回答："
                        "• 模式=focus：只围绕这个特定数据集和用户的问题，提炼关键结论。"
                        "• 若信息不足，请明确指出缺失信息，并给出最小的下一步建议（例如“需要上传临床字段字典”）。"
                        "• 禁止臆造；不要贴回原始表格源码；"
                        "• 只调用 emit_user_reply。"
                    )
                    await self._append_internal(conversation_uid, role="system", text=post_prompt)

                    messages2 = await self._build_llm_messages(conversation_uid)
                    raw2, err2 = await self._call_llm_with_retry(messages2, tools)
                    if not err2 and raw2:
                        await self._append_internal(
                            conversation_uid, role="assistant",
                            text=json.dumps(raw2, ensure_ascii=False)
                        )
                        fin_intent, fin_payload, _ = self._parse_llm_decision(raw2)
                        if fin_intent == "user_reply":
                            final = (fin_payload.get("content") or "").strip()
                            if final:
                                await self._append_main(conversation_uid, role="assistant", text=final)
                                return final

                    # fallback
                    msg = text if ok else f"读取数据集 {dataset_id_int} 失败：{text}"
                    await self._append_main(conversation_uid, role="assistant", text=msg)
                    return msg

                except Exception as e:
                    msg = f"数据集查询异常：{e!r}"
                    await self._append_main(conversation_uid, role="assistant", text=msg)
                    return msg

            # ---------- 兜底 ----------
            await self._append_internal(
                conversation_uid, role="system",
                text=(
                    "请仅使用 emit_user_reply / emit_task_request / "
                    "emit_task_status_query / emit_dataset_info_query。"
                )
            )
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
          intent:
            - "user_reply"
            - "task_request"
            - "task_status_query"
            - "dataset_info_query"
            - None

          payload:
            - user_reply: {"content": "..."}
            - task_request: {"description": "..."}
            - task_status_query: {"task_uid": "..."}
            - dataset_info_query: {"mode": "...", "dataset_id": "...", "user_need_text": "..."}

          error: 解析错误字符串
        """
        try:
            choices = resp.get("choices") or []
            msg = (choices[0] or {}).get("message") or {}

            # 1) tool_calls
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
                if name == "emit_dataset_info_query":
                    return "dataset_info_query", {
                        "mode": (args_obj.get("mode") or ""),
                        "dataset_id": (args_obj.get("dataset_id") or ""),
                        "user_need_text": (args_obj.get("user_need_text") or ""),
                    }, None

            # 2) function_call (旧格式)
            fc = msg.get("function_call") or {}
            if fc.get("name") in (
                "emit_user_reply",
                "emit_task_request",
                "emit_task_status_query",
                "emit_dataset_info_query",
            ):
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
                if fc.get("name") == "emit_task_status_query":
                    return "task_status_query", {"task_uid": (args_obj.get("task_uid") or "")}, None
                return "dataset_info_query", {
                    "mode": (args_obj.get("mode") or ""),
                    "dataset_id": (args_obj.get("dataset_id") or ""),
                    "user_need_text": (args_obj.get("user_need_text") or ""),
                }, None

            # 3) 兜底：content 里塞了 JSON
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
                        if obj.get("type") == "dataset_info_query" and "mode" in obj:
                            return "dataset_info_query", {
                                "mode": str(obj.get("mode") or ""),
                                "dataset_id": str(obj.get("dataset_id") or ""),
                                "user_need_text": str(obj.get("user_need_text") or ""),
                            }, None
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

    # -------------------- 工具定义（给 LLM） --------------------

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
                    "当你认为需要创建或推进任务时调用此函数。"
                    "把完整的自然语言描述放进 description，描述里要清楚表达要做什么、关键输入/输出和期望结果。"
                    "如果涉及到数据集，必须在描述里点名具体的数据集ID(整数)，例如“请基于数据集ID=42进行训练”。"
                    "如果用户还没告诉你数据集ID，不要创建任务，先用 emit_user_reply 问清楚。"
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

    def _tool_emit_dataset_info_query(self) -> Dict[str, Any]:
        """
        - mode = "overview": 只需要 mode
        - mode = "focus":    需要 dataset_id (整数ID，可作为字符串传) 和 user_need_text
        """
        return {
            "type": "function",
            "function": {
                "name": "emit_dataset_info_query",
                "description": (
                    "当用户想查看数据集信息时调用：\n"
                    "mode='overview' → 返回该用户可访问的全部数据集总体情况（不需要额外参数）。\n"
                    "mode='focus' → 针对某个特定数据集，必须提供 dataset_id(整数) 和 user_need_text(本次想了解的问题)。"
                ),
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["mode"],
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["overview", "focus"],
                            "description": "查询模式：overview 或 focus"
                        },
                        "dataset_id": {
                            "type": "string",
                            "minLength": 1,
                            "description": "当 mode='focus' 时必须：要查看的数据集唯一ID（整数，字符串形式也可以）"
                        },
                        "user_need_text": {
                            "type": "string",
                            "minLength": 1,
                            "description": "当 mode='focus' 时必须：用户此次具体想问什么（自然语言）"
                        }
                    }
                }
            }
        }

    # -------------------- 构造 LLM messages --------------------

    async def _build_llm_messages(self, conversation_uid: str) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = [{"role": "system", "content": self.cfg.system_prefix}]

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

    # -------------------- log / db helpers --------------------

    async def _append_main(self, conversation_uid: str, role: str, text: str) -> None:
        await self.cm.add_message_to_main(conversation_uid, role=role, content=text)

    async def _append_internal(self, conversation_uid: str, role: str, text: str) -> None:
        await self.cm.add_message_to_stream(conversation_uid, target=self.stream_id, role=role, content=text)

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

    # -------------------- 状态查询兜底文案 --------------------

    def _summarize_status_for_user(self, result: Dict[str, Any]) -> str:
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
