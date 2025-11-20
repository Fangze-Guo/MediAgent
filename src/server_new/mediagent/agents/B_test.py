# agent_b.py —— “任务计划结构化器/执行器”：两阶段生成严格 steps[*].args(JSON) + $ref
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Set, Literal

# --------------------------- 依赖 ---------------------------
try:
    # OpenAI v1 异步客户端（用于 OpenAI 兼容的 /v1/chat/completions）
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # 直到真正使用时再报错


# --------------------------- 小工具 ---------------------------

def _strip_json_fences(txt: str) -> str:
    """去除常见的 ```json ... ``` 或 ``` ... ``` 围栏。"""
    if not txt:
        return txt
    txt = txt.strip()
    fence = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S | re.I)
    m = fence.match(txt)
    return m.group(1) if m else txt


def _clip(s: str, n: int = 800) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else (s[:n] + " …")


# --------------------------- 配置 ---------------------------

@dataclass
class AgentBConfig:
    model: str
    max_retries: int = 3

    # 工具白名单；若为 None，则以 TaskManager.list_tools() 的返回为准
    allowed_tools: Optional[Set[str]] = None

    # 数据集白名单（可选）；若为 None，dataset_id 的权限交给 TaskManager
    allowed_datasets: Optional[Set[int]] = None

    # OpenAI 连接（必须把 base_url 指到 OpenAI 兼容网关（含 /v1））
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # 例如 "http://127.0.0.1:1234/v1"

    # 提示裁剪：最多在提示里列出多少工具（避免提示过长）
    prompt_tools_limit: int = 20


# --------------------------- 主类 ---------------------------

class TaskCreationAgentB:
    """
    新版 AgentB：两阶段生成 TaskManager 所需 steps JSON：

    1) 阶段一：步骤规划
       - 输入：AgentA 传入的 plan_text + 工具 HUMAN_DESC 摘要
       - 输出：steps_plan = [{"step_number", "tool_name", "purpose"}, ...]

    2) 阶段二：参数规划
       - 对每个 step，根据工具 description 中的 PARAM_SPEC_JSON.params
       - 针对每一个 filled_by == "agent" 的参数，逐个调用 LLM：
            → 产生易填的中间结构 ParamAnswer
            → AgentB 校验 + 解析成字面量 / {"$ref": {...}}
       - 组合为：
            {
              "step_number": k,
              "tool_name": "...",
              "args": { param_name: value_or_$ref, ... }
            }

    3) 调用 AsyncTaskManager.create_task(user_uid, steps)，由 TaskManager 负责执行。
    """

    def __init__(self, task_manager, config: AgentBConfig):
        """
        :param task_manager: AsyncTaskManager 实例（外部生命周期里已 astart）
        :param config: AgentBConfig
        """
        self.tm = task_manager
        self.cfg = config

        if AsyncOpenAI is None:
            raise RuntimeError(
                "openai 库未安装或版本不兼容，请安装 `pip install openai` 并确保为 v1+"
            )

        self._client = AsyncOpenAI(
            api_key=(self.cfg.api_key or "lm-studio"),
            base_url=(self.cfg.base_url or "http://127.0.0.1:1234/v1"),
            timeout=60.0,
        )

        # 工具缓存：
        # name -> {
        #   "human_desc": str,
        #   "param_spec": Optional[dict],  # 来自 PARAM_SPEC_JSON
        #   "raw_description": str
        # }
        self._tool_index: Dict[str, Dict[str, Any]] = {}

    # ==================== 对外主接口 ====================

    async def create_task(self, user_uid: str, plan_text: str) -> Dict[str, Any]:
        """
        外部唯一业务入口。

        输入：
            - user_uid: 当前用户 UID
            - plan_text: AgentA 的自然语言任务描述

        输出：
            成功:
            {
              "ok": true,
              "task_uid": "...",
              "attempts": 1,
              "errors": [],
            }

            失败:
            {
              "ok": false,
              "attempts": 1,
              "errors": [
                {"stage": "network/step_plan/param_plan/manager", "message": "...", "details": ...}
              ],
              "message": "创建任务失败",
            }
        """
        errors: List[Dict[str, Any]] = []
        attempts = 1  # 新流程暂不做整体 retry（参数内部有单独 retry）

        # 0) LLM 连通性冒烟
        try:
            await self._llm_smoke_test()
        except Exception as e:
            return {
                "ok": False,
                "attempts": attempts,
                "errors": [
                    {
                        "stage": "network",
                        "message": f"LLM 连接失败：{e!r}",
                    }
                ],
                "message": "无法连接 LLM 网关，请检查 base_url（必须包含 /v1）与端口",
            }

        # 1) 工具缓存
        try:
            await self._ensure_tool_cache()
        except Exception as e:
            return {
                "ok": False,
                "attempts": attempts,
                "errors": [
                    {
                        "stage": "tools",
                        "message": f"获取工具列表失败：{e!r}",
                    }
                ],
                "message": "无法获取工具目录",
            }

        # 1.1) 构造工具白名单
        if self.cfg.allowed_tools is not None:
            allowed_tools = set(self.cfg.allowed_tools)
        else:
            allowed_tools = set(self._tool_index.keys())

        if not allowed_tools:
            return {
                "ok": False,
                "attempts": attempts,
                "errors": [
                    {
                        "stage": "tools",
                        "message": "没有可用工具（allowed_tools 为空，且 TaskManager.list_tools() 也为空）",
                    }
                ],
                "message": "没有可用工具，无法创建任务",
            }

        # 2) 阶段一：步骤规划
        steps_plan, err = await self._plan_steps_with_llm(
            plan_text=plan_text,
            allowed_tools=allowed_tools,
        )
        if err or not steps_plan:
            errors.append(
                {
                    "stage": "step_plan",
                    "message": "步骤规划失败",
                    "details": err,
                }
            )
            return {
                "ok": False,
                "attempts": attempts,
                "errors": errors,
                "message": "创建任务失败（步骤规划阶段）",
            }

        # 3) 阶段二：参数规划（逐步骤、逐参数）
        try:
            final_steps, param_errors = await self._build_steps_args(
                plan_text=plan_text,
                steps_plan=steps_plan,
                allowed_tools=allowed_tools,
            )
        except Exception as e:
            errors.append(
                {
                    "stage": "param_plan",
                    "message": "参数规划过程中出现异常",
                    "details": repr(e),
                }
            )
            return {
                "ok": False,
                "attempts": attempts,
                "errors": errors,
                "message": "创建任务失败（参数规划异常）",
            }

        if param_errors:
            errors.extend(
                {
                    "stage": "param_plan",
                    "message": "参数规划失败",
                    "details": pe,
                }
                for pe in param_errors
            )
            return {
                "ok": False,
                "attempts": attempts,
                "errors": errors,
                "message": "创建任务失败（参数规划阶段）",
            }

        if not final_steps:
            errors.append(
                {
                    "stage": "param_plan",
                    "message": "未生成任何步骤",
                }
            )
            return {
                "ok": False,
                "attempts": attempts,
                "errors": errors,
                "message": "创建任务失败（没有有效步骤）",
            }

        # 4) 调 TaskManager.create_task
        try:
            created = await self.tm.create_task(
                user_uid=user_uid,
                steps=final_steps,
                check_tools=True,
            )
            task_uid = created.get("task_uid")
            if not task_uid:
                errors.append(
                    {
                        "stage": "manager",
                        "message": "TaskManager 返回结果缺少 task_uid",
                        "details": created,
                    }
                )
                return {
                    "ok": False,
                    "attempts": attempts,
                    "errors": errors,
                    "message": "创建任务时出现未知错误，请重试",
                }

            return {
                "ok": True,
                "task_uid": task_uid,
                "attempts": attempts,
                "errors": [],
            }
        except Exception as e:
            errors.append(
                {
                    "stage": "manager",
                    "message": f"TaskManager 异常：{e!r}",
                }
            )
            return {
                "ok": False,
                "attempts": attempts,
                "errors": errors,
                "message": "创建任务失败（TaskManager 异常）",
            }

    # ==================== LLM 冒烟 ====================

    async def _llm_smoke_test(self) -> None:
        await self._client.chat.completions.create(
            model=self.cfg.model,
            messages=[{"role": "user", "content": "ping"}],
            temperature=0,
            max_tokens=1,
        )

    # ==================== 工具描述解析 ====================

    async def _ensure_tool_cache(self) -> None:
        if self._tool_index:
            return

        tools = await self.tm.list_tools()
        for t in tools:
            name = t.get("name")
            if not name:
                continue
            desc = t.get("description", "") or ""
            # 加一行调试：
            # print(f"\n[AgentB DEBUG] ==== tool={name!r} raw description snippet ====")
            # print(desc)
            # print("=============================================\n")

            human_desc, param_spec = self._parse_tool_description(desc)
            print(f"[AgentB] tool={name!r}, has_param_spec={param_spec is not None}")
            self._tool_index[name] = {
                "human_desc": human_desc,
                "param_spec": param_spec,
                "raw_description": desc,
            }

    @staticmethod
    def _parse_tool_description(desc: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        解析形如：

        【HUMAN_DESC_BEGIN】
        ...
        【HUMAN_DESC_END】

        【PARAM_SPEC_JSON_BEGIN】
        { ... }
        【PARAM_SPEC_JSON_END】
        """
        if not desc:
            return "", None

        text = str(desc)

        def _extract_block(start: str, end: str) -> Optional[str]:
            pattern = re.compile(
                re.escape(start) + r"(.*?)" + re.escape(end),
                re.S,
            )
            m = pattern.search(text)
            if not m:
                return None
            return m.group(1).strip()

        human = _extract_block("【HUMAN_DESC_BEGIN】", "【HUMAN_DESC_END】")
        if not human:
            human = text.strip()

        param_block = _extract_block(
            "【PARAM_SPEC_JSON_BEGIN】", "【PARAM_SPEC_JSON_END】"
        )
        param_spec: Optional[Dict[str, Any]] = None
        if param_block:
            try:
                param_spec = json.loads(param_block)
            except Exception:
                param_spec = None

        return human, param_spec

    def _summarize_tools_for_prompt(self, allowed_tools: Set[str]) -> str:
        """
        将工具的 HUMAN_DESC 摘要化给 LLM，用于指导“步骤规划”。
        只展示：
            - 工具名
            - 简要的 HUMAN_DESC
        不展示 PARAM_SPEC_JSON，避免提示过长。
        """
        lines: List[str] = []
        count = 0

        for name in sorted(self._tool_index.keys()):
            if name not in allowed_tools:
                continue
            if count >= self.cfg.prompt_tools_limit:
                break
            meta = self._tool_index[name]
            desc = _clip(meta.get("human_desc", "") or "(no description)", 600)
            lines.append(f"- {name} :: {desc}")
            count += 1

        extra_rules = (
            "通用规则：\n"
            "• 你只负责规划步骤（step_number, tool_name, purpose），不负责具体参数。\n"
            "• step_number 从 1 开始，按执行顺序递增，不能跳号。\n"
            "• tool_name 只能从下列工具名中选择，不要自己发明新工具名。\n"
        )
        return extra_rules + "\n" + ("\n".join(lines) if lines else "(no tools)")

    # ==================== 阶段一：步骤规划 ====================

    def _emit_step_plan_tool(self, allowed_tools: Set[str]) -> Dict[str, Any]:
        """定义 function-calling 工具：emit_step_plan。"""
        allowed_tools_sorted = sorted(list(allowed_tools))
        return {
            "type": "function",
            "function": {
                "name": "emit_step_plan",
                "description": (
                    "输出本次任务的步骤规划。"
                    "只负责决定每一步使用的工具和用途（purpose），不填写任何具体参数。"
                ),
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["steps"],
                    "properties": {
                        "steps": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 50,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["step_number", "tool_name", "purpose"],
                                "properties": {
                                    "step_number": {
                                        "type": "integer",
                                        "minimum": 1,
                                    },
                                    "tool_name": {
                                        "type": "string",
                                        "enum": allowed_tools_sorted,
                                    },
                                    "purpose": {
                                        "type": "string",
                                        "minLength": 1,
                                        "maxLength": 2000,
                                    },
                                },
                            },
                        }
                    },
                },
            },
        }

    async def _plan_steps_with_llm(
        self,
        plan_text: str,
        allowed_tools: Set[str],
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]]]:
        """
        调 LLM 规划步骤：
            输入：自然语言计划 + 工具 HUMAN_DESC
            输出：steps_plan 数组 或 错误信息
        """
        tools_summary = self._summarize_tools_for_prompt(allowed_tools)

        system_prompt = f"""你是一个严格的“任务规划器”。任务如下：
- 根据用户给出的自然语言需求，结合可用工具列表，规划一个多步骤流水线。
- 每个步骤只需要包含：step_number（整数）、tool_name（工具名）、purpose（该步用途的中文简要说明）。
- 你**不负责**填写参数值（例如路径、$ref 等）。

强制约束：
1) steps[*].step_number 必须从 1 开始、连续递增（1,2,3,...）。
2) steps[*].tool_name 必须从工具列表中选择。
3) purpose 使用简洁自然语言说明该步干什么即可，不要出现 JSON 或参数细节。
4) 你**必须**调用 function: emit_step_plan，并把最终 JSON 作为 emit_step_plan 的 arguments 返回。

可用工具及说明（仅供你理解，不必逐字复制）：
{tools_summary}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "下面是用户的任务需求描述，请据此规划步骤（但不要写参数，只要 step_number/tool_name/purpose）：\n"
                    + _clip(plan_text, 4000)
                ),
            },
        ]

        tool_def = self._emit_step_plan_tool(allowed_tools)

        try:
            resp = await self._client.chat.completions.create(
                model=self.cfg.model,
                messages=messages,
                temperature=0,
                tools=[tool_def],
                tool_choice="required",
            )
        except Exception as e:
            return None, {"error": f"chat.completions failed: {repr(e)}"}

        # 提取 emit_step_plan.arguments
        try:
            choice0 = (resp.choices or [None])[0]
            if not choice0 or not getattr(choice0, "message", None):
                return None, {"error": "no choices/message in response"}

            tool_calls = getattr(choice0.message, "tool_calls", None) or []
            raw_args: Optional[str] = None

            for tc in tool_calls:
                fn = getattr(tc, "function", None)
                if fn and getattr(fn, "name", None) == "emit_step_plan":
                    arguments = getattr(fn, "arguments", None)
                    if isinstance(arguments, str):
                        raw_args = arguments
                    elif isinstance(arguments, dict):
                        raw_args = json.dumps(arguments, ensure_ascii=False)
                    break

            if raw_args is None:
                fc = getattr(choice0.message, "function_call", None)
                if fc and getattr(fc, "name", None) == "emit_step_plan":
                    args = getattr(fc, "arguments", None)
                    if isinstance(args, str):
                        raw_args = args
                    elif isinstance(args, dict):
                        raw_args = json.dumps(args, ensure_ascii=False)

            if raw_args is None:
                content = getattr(choice0.message, "content", None) or ""
                if isinstance(content, str) and content.strip():
                    raw_args = content

            if raw_args is None:
                return None, {"error": "emit_step_plan arguments not found"}

            obj, perr = self._parse_json(raw_args)
            if perr:
                return None, {"error": f"JSON parse failed: {perr}"}

            steps = obj.get("steps")
            if not isinstance(steps, list) or not steps:
                return None, {"error": "steps 缺失或不是非空数组"}

            ok, verr = self._validate_step_plan(steps, allowed_tools)
            if not ok:
                return None, {"error": "step plan validation failed", "details": verr}

            return steps, None
        except Exception as e:
            return None, {"error": f"extract tool_calls failed: {repr(e)}"}

    def _parse_json(self, raw: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        try:
            if not isinstance(raw, str):
                return None, f"输出不是字符串类型：{type(raw).__name__}"
            text = _strip_json_fences(raw)
            obj = json.loads(text)
            if not isinstance(obj, dict):
                return None, "顶层不是 JSON 对象(dict)"
            return obj, None
        except Exception as e:
            return None, f"JSON 解析异常：{e!r}"

    def _validate_step_plan(
        self,
        steps: List[Dict[str, Any]],
        allowed_tools: Set[str],
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        校验步骤规划的基本逻辑：
        - step_number 从 1 连续
        - tool_name 在白名单内
        - purpose 非空字符串
        """
        errors: List[Dict[str, Any]] = []

        nums = []
        for s in steps:
            try:
                n = int(s.get("step_number"))
            except Exception:
                errors.append(
                    {"message": f"step_number 非法：{s.get('step_number')!r}"}
                )
                continue
            nums.append(n)

            tool = s.get("tool_name")
            if not isinstance(tool, str) or not tool:
                errors.append({"message": f"tool_name 缺失或非法：{tool!r}"})
            elif tool not in allowed_tools:
                errors.append(
                    {
                        "message": f"tool_name 不在白名单：{tool}",
                        "step_number": n,
                    }
                )

            purpose = s.get("purpose")
            if not isinstance(purpose, str) or not purpose.strip():
                errors.append(
                    {"message": "purpose 缺失或为空", "step_number": n}
                )

        if nums:
            if sorted(nums) != list(range(1, len(nums) + 1)):
                errors.append(
                    {
                        "message": f"step_number 必须从 1 连续：{nums}",
                    }
                )

        return (len(errors) == 0), {"errors": errors} if errors else {}

    # ==================== 阶段二：参数规划 ====================

    async def _build_steps_args(
        self,
        plan_text: str,
        steps_plan: List[Dict[str, Any]],
        allowed_tools: Set[str],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        根据 steps_plan 逐步构建最终 steps（含 args）。

        返回：
            (final_steps, param_errors)
        """
        final_steps: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        # 简要步骤摘要，提供给参数阶段 LLM 做上下文
        steps_summary_for_prompt = [
            {
                "step_number": int(s["step_number"]),
                "tool_name": str(s["tool_name"]),
                "purpose": str(s.get("purpose") or ""),
            }
            for s in steps_plan
        ]

        for s in steps_plan:
            step_number = int(s["step_number"])
            tool_name = str(s["tool_name"])
            purpose = str(s.get("purpose") or "")

            meta = self._tool_index.get(tool_name) or {}
            param_spec = meta.get("param_spec")

            # 没有 PARAM_SPEC_JSON：认为该工具不需要任何参数（TaskManager 会注入 out_dir）
            if not isinstance(param_spec, dict) or not isinstance(
                param_spec.get("params"), list
            ):
                final_steps.append(
                    {
                        "step_number": step_number,
                        "tool_name": tool_name,
                        "args": {},
                    }
                )
                continue

            params_list: List[Dict[str, Any]] = param_spec["params"]

            # 对该步骤的所有参数进行规划
            args: Dict[str, Any] = {}
            step_param_errors: List[Dict[str, Any]] = []

            for p in params_list:
                try:
                    pname = p.get("name")
                    if not pname or not isinstance(pname, str):
                        continue  # 跳过非法定义的参数

                    filled_by = p.get("filled_by", "agent")
                    if filled_by == "task_manager":
                        # 例如 out_dir 由 TaskManager 自动注入
                        continue

                    # 逐参数调用 LLM（带 retry）
                    value_ok = False
                    last_err: Optional[str] = None
                    for attempt in range(max(1, self.cfg.max_retries)):
                        ans_obj, aerr = await self._ask_param_value_with_llm(
                            plan_text=plan_text,
                            steps_summary=steps_summary_for_prompt,
                            current_step={
                                "step_number": step_number,
                                "tool_name": tool_name,
                                "purpose": purpose,
                            },
                            tool_meta=meta,
                            param_spec=p,
                        )
                        if aerr or ans_obj is None:
                            last_err = f"LLM 返回错误：{aerr}"
                            continue

                        try:
                            resolved = self._interpret_param_answer(
                                param_spec=p,
                                answer_obj=ans_obj,
                                current_step_number=step_number,
                            )
                            # resolved:
                            #   - None: 表示可选参数被省略
                            #   - 其他: 字面量或 {"$ref": {...}} / 列表
                            if resolved is not None:
                                args[pname] = resolved
                            value_ok = True
                            break
                        except Exception as ve:
                            last_err = f"解析/校验参数失败：{ve!r}"
                            continue

                    if not value_ok:
                        # 对于必填参数，整个任务失败；可选参数失败则忽略
                        if bool(p.get("required", False)):
                            step_param_errors.append(
                                {
                                    "step_number": step_number,
                                    "tool_name": tool_name,
                                    "param": pname,
                                    "message": last_err or "未知错误",
                                }
                            )
                except Exception as e:
                    step_param_errors.append(
                        {
                            "step_number": step_number,
                            "tool_name": tool_name,
                            "message": f"处理参数异常：{e!r}",
                        }
                    )

            if step_param_errors:
                errors.extend(step_param_errors)
                # 一旦某个步骤必填参数失败，整体任务就不执行
                return [], errors

            final_steps.append(
                {
                    "step_number": step_number,
                    "tool_name": tool_name,
                    "args": args,
                }
            )

        return final_steps, errors

    # ---------- 参数阶段：LLM 调用 ----------

    def _emit_param_value_tool(
        self,
        ref_kinds: List[str],
    ) -> Dict[str, Any]:
        """
        定义 function-calling 工具：emit_param_value。
        返回的 arguments 即 ParamAnswer 中间结构。
        """
        # 允许的 ref_kinds 列表传给 LLM（由 param_spec.ref_kinds 决定）
        ref_enum = sorted(list(set(ref_kinds))) or [
            "dataset",
            "job_output",
            "filesystem",
        ]

        return {
            "type": "function",
            "function": {
                "name": "emit_param_value",
                "description": (
                    "为当前参数选择取值方案，只输出 JSON，不要自然语言。\n"
                    "支持三种模式：\n"
                    "1) value_mode='literal'：直接给出字面量（见 literal_value）。\n"
                    "2) value_mode='ref'：使用 $ref 语义；ref_kind ∈ ref_kinds；根据类型填写 ref_dataset_id/ref_step/ref_relative。\n"
                    "3) value_mode='omit'：仅当参数非必填时，表示不填写该参数。\n"
                    "对于列表参数，请设置 is_list=true，并在 items 数组中为每一项提供上述字段；items 中不应出现 omit 的项。"
                ),
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["is_list"],
                    "properties": {
                        "is_list": {
                            "type": "boolean",
                            "description": "是否为列表参数（由 param_spec.is_list 决定）。",
                        },
                        "value_mode": {
                            "type": "string",
                            "enum": ["literal", "ref", "omit"],
                            "description": "当 is_list=false 时有效。",
                        },
                        "ref_kind": {
                            "type": ["string", "null"],
                            "enum": ref_enum + [None],
                            "description": "当 value_mode='ref' 且 is_list=false 时，引用类型。",
                        },
                        "ref_dataset_id": {
                            "description": "当 ref_kind='dataset' 时，数据集主键 ID（整数）。",
                        },
                        "ref_step": {
                            "description": "当 ref_kind='job_output' 时，前置步骤号（整数，必须小于当前步骤号）。",
                        },
                        "ref_relative": {
                            "type": ["string", "null"],
                            "description": "相对于 dataset/job_output/filesystem 根的子路径，可为空字符串。",
                        },
                        "literal_value": {
                            "description": "当 value_mode='literal' 时，字面量取值，类型与 param_spec.type 相符。",
                        },
                        "items": {
                            "type": "array",
                            "description": "当 is_list=true 时，包含每一项的取值方案。",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["value_mode"],
                                "properties": {
                                    "value_mode": {
                                        "type": "string",
                                        "enum": ["literal", "ref"],
                                    },
                                    "ref_kind": {
                                        "type": ["string", "null"],
                                        "enum": ref_enum + [None],
                                    },
                                    "ref_dataset_id": {},
                                    "ref_step": {},
                                    "ref_relative": {
                                        "type": ["string", "null"],
                                    },
                                    "literal_value": {},
                                },
                            },
                        },
                    },
                },
            },
        }

    async def _ask_param_value_with_llm(
        self,
        plan_text: str,
        steps_summary: List[Dict[str, Any]],
        current_step: Dict[str, Any],
        tool_meta: Dict[str, Any],
        param_spec: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        针对某一个参数调用 LLM，返回 ParamAnswer 对象。
        """
        human_desc = tool_meta.get("human_desc", "") or ""
        tool_name = current_step["tool_name"]
        step_number = current_step["step_number"]
        purpose = current_step.get("purpose", "")

        # 从 param_spec 中提取关键信息
        pname = param_spec.get("name")
        ptype = param_spec.get("type")
        prequired = bool(param_spec.get("required", False))
        pis_list = bool(param_spec.get("is_list", False))
        allow_ref = bool(param_spec.get("allow_ref", False))
        ref_kinds = param_spec.get("ref_kinds") or []
        if not isinstance(ref_kinds, list):
            ref_kinds = []

        description = param_spec.get("description") or ""
        examples = param_spec.get("examples") or []

        # 将 steps_summary 压缩成简短文本
        steps_text_lines = []
        for s in steps_summary:
            steps_text_lines.append(
                f"步骤 {s['step_number']}: {s['tool_name']} —— {s.get('purpose','')}"
            )
        steps_text = "\n".join(steps_text_lines)

        system_prompt = f"""你是“参数填写助手”，负责为单个参数选择取值方案。

当前场景：
- 用户有一个多步骤流水线任务，每一步调用一个工具。
- 工具的参数规范由 PARAM_SPEC_JSON 提供。
- 你只负责**当前这个参数**的取值，不要为其他参数做决定。

取值模式（单值参数时）：
1) value_mode='literal'
   - 直接给出字面量（literal_value），类型与 param_spec.type 一致。
   - 例如 type='int' → literal_value=1；type='path' → literal_value='/path/to/dir'。

2) value_mode='ref'
   - 使用 $ref 语义，不直接给路径，而是描述引用。
   - ref_kind ∈ {ref_kinds}。
       * 若 ref_kind='dataset'：ref_dataset_id=数据集整数 ID，ref_relative=相对子路径（可为空字符串）。
       * 若 ref_kind='job_output'：ref_step=前置步骤号（< 当前步骤号），ref_relative=相对子路径。
       * 若 ref_kind='filesystem'：通常 literal_value 可以省略，仅用 ref_relative 描述相对路径（如有需要可以在 literal_value 里写基础路径）。
   - literal_value 在 ref 模式下一般留空。

3) value_mode='omit'
   - 仅当参数非必填时，表示在 args 中完全省略该参数。
   - 如果 param_spec.required=true，请不要使用 omit。

对于列表参数（param_spec.is_list=true）：
- 请设置 is_list=true，并在 items 数组中为每一项提供 value_mode/ref/literal_value。
- items 中不应出现 omit；如果需要省略整个参数，请返回一个空 items 数组，并仅在参数非必填时这样做。

你必须调用 function: emit_param_value，并将整个取值方案作为其 arguments。
不要输出自然语言说明。
"""

        user_prompt = (
            "【用户的整体任务需求（节选）】\n"
            + _clip(plan_text, 1200)
            + "\n\n"
            "【整个流水线的步骤概要】\n"
            + steps_text
            + "\n\n"
            f"【当前步骤】\n"
            f"- step_number = {step_number}\n"
            f"- tool_name   = {tool_name}\n"
            f"- purpose     = {purpose}\n\n"
            "【当前工具的简要说明（HUMAN_DESC）】\n"
            + _clip(human_desc, 1200)
            + "\n\n"
            "【当前参数的规范（来自 PARAM_SPEC_JSON.params）】\n"
            + json.dumps(param_spec, ensure_ascii=False, indent=2)
            + "\n\n"
            f"请根据上述信息，为参数 '{pname}' 选择合适的取值方案。"
            f"\n- param_spec.type       = {ptype}"
            f"\n- param_spec.required   = {prequired}"
            f"\n- param_spec.is_list    = {pis_list}"
            f"\n- param_spec.allow_ref  = {allow_ref}"
            f"\n- param_spec.ref_kinds  = {ref_kinds}"
            f"\n如允许使用 $ref，请优先使用 $ref 描述数据集或前置步骤输出，而不是直接写绝对路径。"
        )

        if description:
            user_prompt += "\n\n【参数说明】\n" + description
        if examples:
            user_prompt += "\n\n【参数示例（仅供参考，不要照抄路径）】\n" + "\n".join(
                ["- " + str(x) for x in examples]
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        tool_def = self._emit_param_value_tool(ref_kinds)

        try:
            resp = await self._client.chat.completions.create(
                model=self.cfg.model,
                messages=messages,
                temperature=0,
                tools=[tool_def],
                tool_choice="required",
            )
        except Exception as e:
            return None, {"error": f"chat.completions failed: {repr(e)}"}

        try:
            choice0 = (resp.choices or [None])[0]
            if not choice0 or not getattr(choice0, "message", None):
                return None, {"error": "no choices/message in response"}

            tool_calls = getattr(choice0.message, "tool_calls", None) or []
            raw_args: Optional[str] = None

            for tc in tool_calls:
                fn = getattr(tc, "function", None)
                if fn and getattr(fn, "name", None) == "emit_param_value":
                    arguments = getattr(fn, "arguments", None)
                    if isinstance(arguments, str):
                        raw_args = arguments
                    elif isinstance(arguments, dict):
                        raw_args = json.dumps(arguments, ensure_ascii=False)
                    break

            if raw_args is None:
                fc = getattr(choice0.message, "function_call", None)
                if fc and getattr(fc, "name", None) == "emit_param_value":
                    args = getattr(fc, "arguments", None)
                    if isinstance(args, str):
                        raw_args = args
                    elif isinstance(args, dict):
                        raw_args = json.dumps(args, ensure_ascii=False)

            if raw_args is None:
                content = getattr(choice0.message, "content", None) or ""
                if isinstance(content, str) and content.strip():
                    raw_args = content

            if raw_args is None:
                return None, {"error": "emit_param_value arguments not found"}

            text = _strip_json_fences(raw_args)
            obj = json.loads(text)
            if not isinstance(obj, dict):
                return None, {"error": "arguments 不是 JSON 对象"}

            return obj, None
        except Exception as e:
            return None, {"error": f"extract tool_calls failed: {repr(e)}"}

    # ---------- 参数阶段：解析 ParamAnswer → 最终值/$ref ----------

    def _interpret_param_answer(
        self,
        param_spec: Dict[str, Any],
        answer_obj: Dict[str, Any],
        current_step_number: int,
    ) -> Any:
        """
        将 LLM 返回的 ParamAnswer 解析成：
            - None: 表示省略该参数（仅允许 required=false 时）
            - 字面量：int/float/bool/str/path 等
            - {"$ref": {...}} 或 其列表
        """
        pname = param_spec.get("name")
        ptype = param_spec.get("type") or "string"
        prequired = bool(param_spec.get("required", False))
        pis_list = bool(param_spec.get("is_list", False))
        allow_ref = bool(param_spec.get("allow_ref", False))
        ref_kinds = param_spec.get("ref_kinds") or []
        if not isinstance(ref_kinds, list):
            ref_kinds = []

        if not isinstance(answer_obj, dict):
            raise ValueError(f"参数 {pname} 的回答不是对象")

        is_list_answer = bool(answer_obj.get("is_list", False))

        if pis_list != is_list_answer:
            raise ValueError(
                f"参数 {pname} 的 is_list 与 param_spec 不一致：期望 {pis_list}，实际 {is_list_answer}"
            )

        # ===== 非列表参数 =====
        if not pis_list:
            value_mode = answer_obj.get("value_mode")
            if value_mode not in ("literal", "ref", "omit"):
                raise ValueError(
                    f"参数 {pname} 的 value_mode 非法：{value_mode!r}"
                )

            # omit：仅当非必填时允许
            if value_mode == "omit":
                if prequired:
                    raise ValueError(
                        f"参数 {pname} 是必填参数，不能使用 value_mode='omit'"
                    )
                return None

            # literal
            if value_mode == "literal":
                val = answer_obj.get("literal_value", None)
                return self._cast_literal_value(ptype, val, pname)

            # ref
            if value_mode == "ref":
                if not allow_ref:
                    raise ValueError(
                        f"参数 {pname} 不允许引用（allow_ref=false），但 LLM 选择了 value_mode='ref'"
                    )
                ref_kind = answer_obj.get("ref_kind")
                if ref_kinds and ref_kind not in ref_kinds:
                    raise ValueError(
                        f"参数 {pname} 的 ref_kind={ref_kind!r} 不在允许范围 {ref_kinds}"
                    )

                return self._build_ref_from_answer(
                    pname=pname,
                    ref_kind=ref_kind,
                    answer_obj=answer_obj,
                    current_step_number=current_step_number,
                )

        # ===== 列表参数 =====
        items = answer_obj.get("items", [])
        if items is None:
            items = []
        if not isinstance(items, list):
            raise ValueError(f"参数 {pname} 的 items 必须是数组")

        # 对于必填列表参数，至少要有一个有效元素
        if prequired and not items:
            raise ValueError(f"参数 {pname} 是必填列表，但 items 为空")

        out_list: List[Any] = []
        for i, item in enumerate(items, 1):
            if not isinstance(item, dict):
                raise ValueError(
                    f"参数 {pname} 的 items[{i}] 不是对象：{type(item).__name__}"
                )
            mode = item.get("value_mode")
            if mode not in ("literal", "ref"):
                raise ValueError(
                    f"参数 {pname} 的 items[{i}].value_mode 非法：{mode!r}"
                )
            if mode == "literal":
                val = item.get("literal_value", None)
                out_list.append(
                    self._cast_literal_value(ptype, val, f"{pname}[{i}]")
                )
            else:  # ref
                if not allow_ref:
                    raise ValueError(
                        f"参数 {pname} 不允许引用（allow_ref=false），但 items[{i}] 选择了 ref"
                    )
                ref_kind = item.get("ref_kind")
                if ref_kinds and ref_kind not in ref_kinds:
                    raise ValueError(
                        f"参数 {pname} 的 items[{i}].ref_kind={ref_kind!r} 不在允许范围 {ref_kinds}"
                    )
                out_list.append(
                    self._build_ref_from_answer(
                        pname=f"{pname}[{i}]",
                        ref_kind=ref_kind,
                        answer_obj=item,
                        current_step_number=current_step_number,
                    )
                )

        if prequired and not out_list:
            raise ValueError(f"参数 {pname} 是必填列表，但所有元素无效")
        if not out_list:
            return None
        return out_list

    def _cast_literal_value(
        self,
        ptype: str,
        val: Any,
        pname: str,
    ) -> Any:
        """根据 param_spec.type 将 literal_value 转换为合适类型。"""
        t = (ptype or "string").lower()
        if t in ("int", "integer"):
            try:
                return int(val)
            except Exception:
                raise ValueError(f"参数 {pname} 期望 int，实际 {val!r}")
        if t in ("float", "number", "double"):
            try:
                return float(val)
            except Exception:
                raise ValueError(f"参数 {pname} 期望 float，实际 {val!r}")
        if t in ("bool", "boolean"):
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                v = val.strip().lower()
                if v in ("true", "1", "yes", "y"):
                    return True
                if v in ("false", "0", "no", "n"):
                    return False
            try:
                return bool(int(val))
            except Exception:
                raise ValueError(f"参数 {pname} 期望 bool，实际 {val!r}")
        # string/path/其他：统一转 str
        if val is None:
            return ""
        return str(val)

    def _build_ref_from_answer(
        self,
        pname: str,
        ref_kind: Any,
        answer_obj: Dict[str, Any],
        current_step_number: int,
    ) -> Dict[str, Any]:
        """根据 answer_obj 构建标准 $ref 结构。"""
        rk = ref_kind or ""
        rk = str(rk) if rk is not None else ""
        rk = rk.strip()

        rel = answer_obj.get("ref_relative")
        if rel is None:
            rel_str: Optional[str] = None
        else:
            rel_str = str(rel)

        # dataset
        if rk == "dataset":
            ds = answer_obj.get("ref_dataset_id")
            try:
                ds_id = int(ds)
            except Exception:
                raise ValueError(
                    f"参数 {pname} 引用 dataset，但 ref_dataset_id 非法：{ds!r}"
                )
            # 可选 dataset 白名单
            if self.cfg.allowed_datasets is not None and ds_id not in self.cfg.allowed_datasets:
                raise ValueError(
                    f"参数 {pname} 引用的数据集 {ds_id} 不在 allowed_datasets 白名单中"
                )
            ref: Dict[str, Any] = {
                "kind": "dataset",
                "id": ds_id,
            }
            if rel_str is not None:
                ref["relative"] = rel_str
            return {"$ref": ref}

        # job_output
        if rk == "job_output":
            st = answer_obj.get("ref_step")
            try:
                st_num = int(st)
            except Exception:
                raise ValueError(
                    f"参数 {pname} 引用 job_output，但 ref_step 非法：{st!r}"
                )
            if not (1 <= st_num < current_step_number):
                raise ValueError(
                    f"参数 {pname} 引用 job_output 的 ref_step={st_num} 不在 1..{current_step_number-1}"
                )
            ref = {
                "kind": "job_output",
                "step": st_num,
            }
            if rel_str is not None:
                ref["relative"] = rel_str
            return {"$ref": ref}

        # filesystem
        if rk == "filesystem":
            base_path = answer_obj.get("literal_value")
            if base_path is not None:
                base_str = str(base_path)
            else:
                base_str = ""
            ref = {
                "kind": "filesystem",
                "path": base_str or ".",
            }
            if rel_str is not None:
                ref["relative"] = rel_str
            return {"$ref": ref}

        raise ValueError(f"参数 {pname} 的 ref_kind 未知或未实现：{rk!r}")
