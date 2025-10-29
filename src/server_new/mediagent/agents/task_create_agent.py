# agent_b.py —— “任务计划结构化器/执行器”：将不规范计划→严格 JSON → 校验/裁剪 → 调度
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

try:
    import jsonschema
    from jsonschema import validate as jsonschema_validate
    HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover
    HAS_JSONSCHEMA = False
    jsonschema_validate = None  # type: ignore


# --------------------------- 常量与基础工具 ---------------------------

SOURCE_KINDS: Set[str] = {"dataset", "step", "direct"}
# 运行时由 TaskManager 注入；禁止出现在 additional_params 中
RUNTIME_PARAMS_FORBID: Set[str] = {"in_dir", "out_dir"}

# 顶层 JSON Schema（结构层约束：字段、类型、最小值、枚举）
PLAN_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["steps"],
    "additionalProperties": False,
    "properties": {
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 50,
            "items": {
                "type": "object",
                "required": ["step_number", "tool_name", "source_kind", "source", "additional_params"],
                "additionalProperties": False,
                "properties": {
                    "step_number": {"type": "integer", "minimum": 1},
                    "tool_name": {"type": "string", "minLength": 1, "maxLength": 128},
                    "source_kind": {"type": "string", "enum": sorted(list(SOURCE_KINDS))},
                    "source": {
                        # 语义：
                        # - 当 source_kind == "dataset": 该数据集的【整数编号 id】（dataset_catalog.id）
                        # - 当 source_kind == "step":    前置步骤号（小于本步骤号的正整数）
                        # - 当 source_kind == "direct":  直接的输入目录路径或 URI scheme
                        "oneOf": [
                            {"type": "string", "minLength": 1, "maxLength": 1024},
                            {"type": "integer", "minimum": 1}
                        ]
                    },
                    "relative": {"type": ["string", "null"], "maxLength": 1024},
                    "additional_params": {
                        "type": "object",
                        "maxProperties": 50,
                    },
                },
            },
        }
    },
}


def _strip_json_fences(txt: str) -> str:
    """去除常见的 ```json ... ``` 或 ``` ... ``` 围栏。"""
    if not txt:
        return txt
    txt = txt.strip()
    fence = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S | re.I)
    m = fence.match(txt)
    return m.group(1) if m else txt


# --------------------------- 配置 ---------------------------

@dataclass
class AgentBConfig:
    model: str
    max_retries: int = 3
    # 可选：白名单工具；若为空则以 TaskManager.list_tools() 为准
    allowed_tools: Optional[Set[str]] = None
    # 可选：公共数据集编号白名单（如需）
    # 现在 source_kind == "dataset" 的 source 是数据集主键 id（整数或数字字符串）
    # 如果想完全放权给 TaskManager 校验权限，可以传 None
    allowed_datasets: Optional[Set[str]] = None
    # OpenAI 连接（必须把 base_url 指到 OpenAI 兼容网关（含 /v1））
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # 例如 "http://127.0.0.1:1234/v1"
    # 额外的参数规则（当你仍希望对某些工具施加互斥/依赖/范围时）
    extra_param_rules: Optional[Dict[str, Dict[str, Any]]] = None
    # LLM 提示裁剪：最多在提示里列出多少工具（避免提示过长）
    prompt_tools_limit: int = 20

    # ====== 新增：参数白名单与策略（核心防多余参数） ======
    # 每个工具允许的 additional_params 键名白名单；不配置即默认不允许任何业务参数（会被清空）
    allowed_param_whitelist: Optional[Dict[str, Set[str]]] = None
    # 策略：drop=自动删除白名单外参数；error=出现白名单外参数则报错；allow=不启用白名单
    param_policy: Literal["drop", "error", "allow"] = "drop"


# --------------------------- Agent B 主类 ---------------------------

class TaskCreationAgentB:
    """
    - 接收 A 的“不规范自然语言计划”
    - 通过 LLM 产出“严格 JSON”
    - 进行三层控制：
        1) JSON Schema（结构）
        2) 逻辑校验（步号、依赖、工具白名单、数据集白名单*可选*）
        3) 参数控制（运行时键禁止 + 业务参数白名单策略）
    - 通过后调用 TaskManager.create_task()

    ⚠ dataset 模式的关键点：
      steps[*].source_kind == "dataset" 时，
      steps[*].source 必须是一个数据集主键 ID（dataset_catalog.id，整数）。
      我们不再接受路径或“数据集名称”。
      TaskManager 会在运行阶段根据该 ID 去 DB 做权限校验并解析实际路径。
    """

    def __init__(self, task_manager, config: AgentBConfig):
        """
        :param task_manager: AsyncTaskManager 实例（已在外部生命周期里启动）
        :param config: AgentBConfig
        """
        self.tm = task_manager
        self.cfg = config

        if AsyncOpenAI is None:
            raise RuntimeError("openai 库未安装或版本不兼容，请安装 `pip install openai` 并确保为 v1+")
        self._client = AsyncOpenAI(
            api_key=(self.cfg.api_key or "lm-studio"),
            base_url=(self.cfg.base_url or "http://127.0.0.1:1234/v1"),
            timeout=30.0,
        )

        # 工具缓存：name -> {"description": "..."}（这里只保存 name/description）
        self._tool_index: Dict[str, Dict[str, Any]] = {}

    # -------------------- 外部接口 --------------------

    async def create_task(self, user_uid: str, plan_text: str) -> Dict[str, Any]:
        """
        返回形如：
        {
          "ok": true/false,
          "task_uid": "...",          # ok 时
          "attempts": int,
          "errors": [ {stage, attempt, message, details?}, ... ],
          "sanitized_report": [{step, tool, removed: [...]}]  # 当 policy='drop' 且有删除时
        }
        """
        errors: List[Dict[str, Any]] = []
        attempts = 0
        sanitized_report: List[Dict[str, Any]] = []

        # LLM 连通性冒烟
        try:
            await self._llm_smoke_test()
        except Exception as e:
            return {
                "ok": False,
                "attempts": 1,
                "errors": [{"stage": "network", "attempt": 1, "message": f"LLM 连接失败：{e!r}"}],
                "message": "无法连接 LLM 网关，请检查 base_url（必须包含 /v1）与端口",
            }

        await self._ensure_tool_cache()

        # 构建工具白名单
        if self.cfg.allowed_tools is not None:
            allowed_tools = set(self.cfg.allowed_tools)
        else:
            allowed_tools = set(self._tool_index.keys())

        plan_obj: Optional[Dict[str, Any]] = None
        while attempts < max(1, self.cfg.max_retries):
            attempts += 1

            # === 1) 调 LLM 产出 JSON（强制 function 调用 emit_plan） ===
            raw, fc_err = await self._call_llm_via_function(plan_text, allowed_tools=allowed_tools)
            if fc_err:
                errors.append({"stage": "json_schema", "attempt": attempts, "message": "LLM 返回错误", "details": fc_err})
                continue

            plan_obj, parse_err = self._parse_json(raw)
            if parse_err:
                errors.append({"stage": "json_schema", "attempt": attempts, "message": "JSON 解析失败", "details": parse_err})
                continue

            # === 2) 顶层 JSON Schema ===
            schema_ok, schema_errs = self._validate_json_schema(plan_obj)
            if not schema_ok:
                errors.append({"stage": "json_schema", "attempt": attempts, "message": "顶层 JSON Schema 校验失败", "details": schema_errs})
                continue

            # === 3) 逻辑校验 ===
            logic_ok, logic_errs = self._validate_logic(plan_obj, allowed_tools)
            if not logic_ok:
                errors.append({"stage": "logic", "attempt": attempts, "message": "任务逻辑校验失败", "details": logic_errs})
                continue

            # === 4) 运行时参数禁止 + 业务参数白名单策略 ===
            param_ok, param_errs, sanitized_report = self._enforce_param_policy(plan_obj)
            if not param_ok:
                errors.append({"stage": "param", "attempt": attempts, "message": "参数校验失败", "details": param_errs})
                continue

            # 通过
            break

        # 失败
        if plan_obj is None or (errors and attempts >= self.cfg.max_retries):
            return {
                "ok": False,
                "attempts": attempts,
                "errors": errors,
                "message": "创建任务失败",
            }

        # === 5) 调 TaskManager 创建任务 ===
        try:
            steps = plan_obj["steps"]
            created = await self.tm.create_task(user_uid=user_uid, steps=steps, check_tools=True)
            task_uid = created.get("task_uid")
            if task_uid:
                out: Dict[str, Any] = {"ok": True, "task_uid": task_uid, "attempts": attempts, "errors": []}
                if sanitized_report:
                    out["sanitized_report"] = sanitized_report
                return out
            else:
                errors.append({"stage": "manager", "attempt": attempts, "message": "TaskManager 返回异常", "details": created})
                return {"ok": False, "attempts": attempts, "errors": errors, "message": "创建任务时出现未知错误，请重试"}
        except Exception as e:
            errors.append({"stage": "manager", "attempt": attempts, "message": f"TaskManager 异常：{e!r}"})
            return {"ok": False, "attempts": attempts, "errors": errors, "message": "创建任务时出现未知错误，请重试"}

    # -------------------- LLM 交互（function calling） --------------------

    def _emit_plan_tool(self, allowed_tools: Set[str]) -> Dict[str, Any]:
        """
        返回 OpenAI function-calling 工具定义（用 JSON Schema 限制 arguments）。
        这里我们在 description 里也明确 dataset/source 的语义，减少模型乱填路径的概率。
        """
        allowed_tools_sorted = sorted(list(allowed_tools))
        return {
            "type": "function",
            "function": {
                "name": "emit_plan",
                "description": (
                    "输出最终的计划 JSON。严格遵守参数 schema；严禁在 additional_params 中包含 in_dir、out_dir。"
                    "如果不确定，请将 additional_params 置为 {}（不要编造键名）。"
                    "注意：当 source_kind == 'dataset' 时，source 必须是数据集的整数编号（dataset_id），"
                    "不是名称、不是路径。"
                    "当 source_kind == 'step' 时，source 是前置步骤号（必须小于当前步骤号的正整数）。"
                    "当 source_kind == 'direct' 时，source 可以是一个已有目录的路径/URI。"
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
                                "required": [
                                    "step_number",
                                    "tool_name",
                                    "source_kind",
                                    "source",
                                    "additional_params"
                                ],
                                "properties": {
                                    "step_number": {"type": "integer", "minimum": 1},
                                    "tool_name": {
                                        "type": "string",
                                        "enum": allowed_tools_sorted
                                    },
                                    "source_kind": {
                                        "type": "string",
                                        "enum": sorted(list(SOURCE_KINDS))
                                    },
                                    "source": {
                                        "oneOf": [
                                            {
                                                "type": "string",
                                                "minLength": 1,
                                                "maxLength": 1024
                                            },
                                            {
                                                "type": "integer",
                                                "minimum": 1
                                            }
                                        ]
                                    },
                                    "relative": {
                                        "type": ["string", "null"],
                                        "maxLength": 1024
                                    },
                                    "additional_params": {"type": "object"},
                                },
                            },
                        }
                    },
                },
            },
        }

    async def _call_llm_via_function(
        self,
        plan_text: str,
        allowed_tools: Set[str]
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        通过 /v1/chat/completions + function calling，强制模型调用 emit_plan 并返回其 arguments(JSON 字符串)。
        system_prompt 里我们强化 dataset/source 的定义。
        """
        tools_summary = self._summarize_tools_for_prompt(allowed_tools)

        system_prompt = f"""你是一个严格的“任务计划结构化器”。请将用户给出的不规范任务计划转换为**严格 JSON**。
不要输出自然语言，也不要给出任何解释。你**必须**调用 function: emit_plan，并把最终 JSON 作为 emit_plan 的 arguments 返回。

强制约束（重要）：
1) steps[*].step_number 必须从 1 开始、连续（1,2,3,...）。
2) steps[*].source_kind ∈ {sorted(list(SOURCE_KINDS))}。
3) 若 source_kind == "step"，则 steps[*].source 必须是小于当前步骤号的正整数（引用前置步骤的结果目录）。
4) 若 source_kind == "dataset"，则 steps[*].source 必须是该数据集的整数编号 dataset_id（即数据库主键 id），
   不能是数据集名称、别名、描述、路径或相对路径。
   例如：source_kind="dataset" 时，source=42 这样的数字是允许的；"customer_logs_may" 之类字符串不允许。
5) 若 source_kind == "direct"，steps[*].source 可以是一个现有输入目录路径或自定义 URI。
6) tool_name 必须在白名单内（见下方列表）。
7) steps[*].additional_params：若工具描述未要求业务参数，使用 {{}}；
   **禁止**包含 in_dir/out_dir（运行时注入）。不得发明键名。
8) relative 字段是可选子路径（相对于输入目录）；如果用户没有特别指定子目录/子文件夹，请用 null 或不要加这个字段。

可用工具及说明（仅供你理解，不必逐字复制，也不要据此发明参数键名）：
{tools_summary}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": plan_text},
        ]

        emit_plan_tool = self._emit_plan_tool(allowed_tools)

        try:
            resp = await self._client.chat.completions.create(
                model=self.cfg.model,
                messages=messages,
                temperature=0,
                tools=[emit_plan_tool],
                tool_choice="required",
            )
        except Exception as e:
            return None, {"error": f"chat.completions failed: {repr(e)}"}

        # 从返回中提取 emit_plan 的 arguments
        try:
            choice0 = (resp.choices or [None])[0]
            if not choice0 or not getattr(choice0, "message", None):
                return None, {"error": "no choices/message in response"}

            # 1) 新版字段：message.tool_calls[*].function.arguments
            tool_calls = getattr(choice0.message, "tool_calls", None) or []
            for tc in tool_calls:
                fn = getattr(tc, "function", None)
                if fn and getattr(fn, "name", None) == "emit_plan":
                    arguments = getattr(fn, "arguments", None)
                    if isinstance(arguments, str):
                        return arguments, None
                    if isinstance(arguments, dict):
                        return json.dumps(arguments, ensure_ascii=False), None

            # 2) 旧版字段：message.function_call
            fc = getattr(choice0.message, "function_call", None)
            if fc and getattr(fc, "name", None) == "emit_plan":
                args = getattr(fc, "arguments", None)
                if isinstance(args, str):
                    return args, None
                if isinstance(args, dict):
                    return json.dumps(args, ensure_ascii=False), None

            # 3) 兜底：content
            content = getattr(choice0.message, "content", None) or ""
            if isinstance(content, str) and content.strip():
                return content, None

            return None, {"error": "emit_plan arguments not found"}
        except Exception as e:
            return None, {"error": f"extract tool_calls failed: {repr(e)}"}

    # -------------------- 工具能力缓存与提示构建 --------------------

    async def _ensure_tool_cache(self) -> None:
        if self._tool_index:
            return
        tools = await self.tm.list_tools()
        for t in tools:
            name = t.get("name")
            if not name:
                continue
            self._tool_index[name] = {
                "description": t.get("description", "") or "",
            }

    def _summarize_tools_for_prompt(self, allowed_tools: Set[str]) -> str:
        """
        将工具的描述摘要化给 LLM，用于指导 steps[*] 的生成。
        - 不展示参数 schema
        - 强调 additional_params 默认 {}，且禁止 in_dir/out_dir，禁止发明键名
        - 我们不告诉 LLM任何关于运行时 out_dir/in_dir 注入细节，避免它尝试自己生成这些字段
        """
        def _clip(s: str, n: int = 600) -> str:
            s = (s or "").strip()
            return s if len(s) <= n else (s[:n] + " …")

        lines: List[str] = []
        count = 0
        for name in sorted(self._tool_index.keys()):
            if name not in allowed_tools:
                continue
            if count >= self.cfg.prompt_tools_limit:
                break
            desc = _clip(self._tool_index[name].get("description", "")) or "(no description)"
            lines.append(f"- {name} :: {desc}")
            count += 1

        extra_rules = (
            "通用规则：\n"
            "• 每个步骤必须含 step_number / tool_name / source_kind / source / additional_params；relative 可选。\n"
            "• tool_name 只能取上述工具列表中的名称；不要凭描述‘猜’参数键名。\n"
            "• 若 source_kind=='step'，source=小于当前步骤号的整数（引用前置步骤）。\n"
            "• 若 source_kind=='dataset'，source=该数据集的整数编号 dataset_id（不能是名称、路径）。\n"
            "• additional_params：除非业务上确有必要，否则使用空对象 {}；严禁包含 in_dir/out_dir。\n"
        )
        return extra_rules + "\n" + ("\n".join(lines) if lines else "(no tools)")

    # -------------------- JSON 解析与校验 --------------------

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

    def _validate_json_schema(self, plan_obj: Dict[str, Any]) -> Tuple[bool, Any]:
        if HAS_JSONSCHEMA and jsonschema_validate:
            try:
                jsonschema_validate(instance=plan_obj, schema=PLAN_JSON_SCHEMA)
                return True, None
            except Exception as ve:  # jsonschema.ValidationError 也在这里处理
                try:
                    path = list(getattr(ve, "path", []))
                    message = getattr(ve, "message", str(ve))
                    validator = getattr(ve, "validator", None)
                    return False, {"path": path, "message": message, "validator": validator}
                except Exception:
                    return False, {"message": f"JsonSchema 校验失败：{ve!r}"}
        else:
            # 轻量兜底
            if (
                not isinstance(plan_obj, dict)
                or "steps" not in plan_obj
                or not isinstance(plan_obj["steps"], list)
                or not plan_obj["steps"]
            ):
                return False, {"message": "缺少 steps 或 steps 不是非空数组"}
            for i, s in enumerate(plan_obj["steps"], 1):
                for key in ("step_number", "tool_name", "source_kind", "source", "additional_params"):
                    if key not in s:
                        return False, {"message": f"steps[{i}] 缺少字段：{key}"}
            return True, None

    def _validate_logic(
        self,
        plan_obj: Dict[str, Any],
        allowed_tools: Set[str]
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        steps: List[Dict[str, Any]] = plan_obj["steps"]
        errors: List[Dict[str, Any]] = []

        # 1) 步号从 1 连续
        numbers = [int(s.get("step_number", -1)) for s in steps]
        if sorted(numbers) != list(range(1, len(numbers) + 1)):
            errors.append({
                "type": "step_number",
                "message": f"step_number 必须从 1 连续：{numbers}"
            })

        # 2) 工具白名单、source_kind 枚举
        for s in steps:
            k = int(s["step_number"])
            tool = str(s["tool_name"])
            if tool not in allowed_tools:
                errors.append({
                    "type": "tool_name",
                    "step": k,
                    "message": f"不在白名单：{tool}"
                })

            sk = str(s["source_kind"])
            if sk not in SOURCE_KINDS:
                errors.append({
                    "type": "source_kind",
                    "step": k,
                    "message": f"非法 source_kind：{sk}"
                })

            # 3) 依赖合法：source_kind=step → source 必须是 < k 的整数
            if sk == "step":
                src = s["source"]
                try:
                    src_num = int(src)
                except Exception:
                    errors.append({
                        "type": "source",
                        "step": k,
                        "message": f"step 模式下 source 必须是整数：{src!r}"
                    })
                    continue
                if not (1 <= src_num < k):
                    errors.append({
                        "type": "source",
                        "step": k,
                        "message": f"非法前置引用：{src_num}（必须在 1..{k-1}）"
                    })

            # 4) dataset 白名单（可选）
            #    注意：现在 dataset 模式下 source 是数据集主键 ID（整数）。
            #    如果 cfg.allowed_datasets=None，就等 TaskManager 去判权限/存在性。
            if sk == "dataset" and self.cfg.allowed_datasets is not None:
                ds = str(s["source"])
                if ds not in self.cfg.allowed_datasets:
                    errors.append({
                        "type": "dataset",
                        "step": k,
                        "message": f"数据集不在白名单：{ds}"
                    })

        return (len(errors) == 0), errors

    # -------------------- 参数策略（核心） --------------------

    def _enforce_param_policy(
        self,
        plan_obj: Dict[str, Any]
    ) -> Tuple[bool, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        应用运行时参数禁止 + 业务参数白名单策略。
        返回 (ok, errors, sanitized_report)
        """
        policy = self.cfg.param_policy
        whitelist = self.cfg.allowed_param_whitelist or {}

        errors: List[Dict[str, Any]] = []
        sanitized_report: List[Dict[str, Any]] = []

        for s in plan_obj["steps"]:
            step_no = int(s["step_number"])
            tool = str(s["tool_name"])
            add = s.get("additional_params")
            if add is None or not isinstance(add, dict):
                s["additional_params"] = {}
                continue

            # 1) 运行时参数一律禁止
            rt_hit = set(add.keys()) & RUNTIME_PARAMS_FORBID
            if rt_hit:
                # 统一删除（比直接报错更稳健），并记录
                for k in list(rt_hit):
                    add.pop(k, None)
                sanitized_report.append({
                    "step": step_no,
                    "tool": tool,
                    "removed": sorted(list(rt_hit)),
                    "reason": "runtime_forbidden"
                })

            # 2) 白名单策略
            if policy == "allow":
                continue  # 不做白名单限制

            allowed_keys = whitelist.get(tool, set())
            if not allowed_keys:
                # 未配置白名单 → 默认不允许任何业务参数
                extra_keys = list(add.keys())
            else:
                extra_keys = [k for k in add.keys() if k not in allowed_keys]

            if not extra_keys:
                continue

            if policy == "error":
                errors.append({
                    "type": "param_whitelist",
                    "step": step_no,
                    "tool": tool,
                    "message": (
                        f"出现白名单外参数：{sorted(extra_keys)}；允许的参数："
                        f"{sorted(list(allowed_keys)) if allowed_keys else []}"
                    )
                })
            else:
                # drop（默认）：删除多余参数
                for k in extra_keys:
                    add.pop(k, None)
                sanitized_report.append({
                    "step": step_no,
                    "tool": tool,
                    "removed": sorted(extra_keys),
                    "reason": (
                        "whitelist_drop" if allowed_keys
                        else "default_drop_no_whitelist"
                    )
                })

        ok = len(errors) == 0
        return ok, errors, sanitized_report

    # -------------------- 冒烟测试 --------------------

    async def _llm_smoke_test(self) -> None:
        await self._client.chat.completions.create(
            model=self.cfg.model,
            messages=[{"role": "user", "content": "ping"}],
            temperature=0,
            max_tokens=1,
        )
