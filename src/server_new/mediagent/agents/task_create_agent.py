# agent_b.py —— “Agent B”：将不规范计划→严格 JSON → 校验 → 调用任务管理器
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Set

try:
    # OpenAI v1+ 异步客户端
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # 允许导入失败，直到真正调用时再报错

try:
    import jsonschema
    from jsonschema import validate as jsonschema_validate, Draft202012Validator
    HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover
    HAS_JSONSCHEMA = False
    Draft202012Validator = None  # type: ignore


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
                        # dataset: 数据集编号（string）
                        # step: 前置步骤号（string 或 integer；后续逻辑再校验取整）
                        # direct: 路径/自定义 scheme（string）
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
    # ```json\n...\n``` 或 ```\n...\n```
    fence = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S | re.I)
    m = fence.match(txt)
    return m.group(1) if m else txt


def _py_type_ok(value: Any, type_decl: Any) -> bool:
    """
    朴素类型检查：将 JSON Schema 的 type 映射为 Python 类型集合进行 isinstance 校验。
    支持 union（list of types）。
    """
    def _one_ok(v: Any, t: str) -> bool:
        if t == "string":
            return isinstance(v, str)
        if t == "integer":
            return isinstance(v, int) and not isinstance(v, bool)
        if t == "number":
            return (isinstance(v, int) or isinstance(v, float)) and not isinstance(v, bool)
        if t == "boolean":
            return isinstance(v, bool)
        if t == "array":
            return isinstance(v, list)
        if t == "object":
            return isinstance(v, dict)
        if t == "null":
            return v is None
        return True  # 未知类型放行
    if isinstance(type_decl, list):
        return any(_one_ok(value, t) for t in type_decl)
    if isinstance(type_decl, str):
        return _one_ok(value, type_decl)
    return True


@dataclass
class AgentBConfig:
    model: str
    max_retries: int = 3
    # 可选：白名单工具；若为空则以 TaskManager.list_tools() 为准
    allowed_tools: Optional[Set[str]] = None
    # 可选：公共数据集编号白名单（如需）
    allowed_datasets: Optional[Set[str]] = None
    # OpenAI 连接
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    # 额外的参数规则（当你仍希望对某些工具施加互斥/依赖/范围时）
    extra_param_rules: Optional[Dict[str, Dict[str, Any]]] = None
    # LLM 提示裁剪：最多在提示里列出多少工具（避免提示过长）
    prompt_tools_limit: int = 20


# --------------------------- Agent B 主类 ---------------------------

class TaskCreationAgentB:
    """
    Agent B：
    - 接收 A 的“不规范自然语言计划”
    - 通过 LLM 产出“严格 JSON”
    - 进行两层校验（JSON Schema + 逻辑/参数（宽松））
    - 成功后调用 TaskManager.create_task()
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
        self._client = AsyncOpenAI(api_key=self.cfg.api_key, base_url=self.cfg.base_url)

        # 工具缓存：name -> {"description": "..."}（不再保存 inputSchema）
        self._tool_index: Dict[str, Dict[str, Any]] = {}
        # 兼容：若仍使用 extra_param_rules，这里只在 _validate_params 中使用
        self._tool_param_rules_cache: Dict[str, Dict[str, Any]] = {}

    # -------------------- 外部接口 --------------------

    async def create_task(self, user_uid: str, plan_text: str) -> Dict[str, Any]:
        """
        入口：单一方法。
        返回形如：
        {
          "ok": true/false,
          "task_uid": "...",          # ok 时
          "attempts": int,
          "errors": [ {stage, attempt, message, details?}, ... ],
        }
        """
        errors: List[Dict[str, Any]] = []
        attempts = 0

        await self._ensure_tool_cache()

        # 构建工具白名单：优先用传入；否则用 tm 返回的列表
        if self.cfg.allowed_tools is not None:
            allowed_tools = set(self.cfg.allowed_tools)
        else:
            allowed_tools = set(self._tool_index.keys())

        # 自纠循环
        plan_obj: Optional[Dict[str, Any]] = None
        while attempts < max(1, self.cfg.max_retries):
            attempts += 1

            # === 1) 调 LLM 严格产出 JSON ===
            raw = await self._call_llm(plan_text, errors_so_far=errors, allowed_tools=allowed_tools)
            plan_obj, parse_err = self._parse_json(raw)
            if parse_err:
                errors.append({"stage": "json_schema", "attempt": attempts, "message": "JSON 解析失败", "details": parse_err})
                continue

            # === 2) 顶层 JSON Schema 校验 ===
            schema_ok, schema_errs = self._validate_json_schema(plan_obj)
            if not schema_ok:
                errors.append({"stage": "json_schema", "attempt": attempts, "message": "顶层 JSON Schema 校验失败", "details": schema_errs})
                continue

            # === 3) 逻辑校验（步号连续、依赖、source_kind 等） ===
            logic_ok, logic_errs = self._validate_logic(plan_obj, allowed_tools)
            if not logic_ok:
                errors.append({"stage": "logic", "attempt": attempts, "message": "任务逻辑校验失败", "details": logic_errs})
                continue

            # === 4) 参数校验（宽松 + 黑名单） ===
            param_ok, param_errs = self._validate_params(plan_obj)
            if not param_ok:
                errors.append({"stage": "param", "attempt": attempts, "message": "参数校验失败", "details": param_errs})
                continue

            # 通过
            break

        # 失败
        if plan_obj is None or (errors and errors[-1]["stage"] in {"json_schema", "logic", "param"} and attempts >= self.cfg.max_retries):
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
                return {"ok": True, "task_uid": task_uid, "attempts": attempts, "errors": []}
            else:
                # 未返回 task_uid 视为未知错误
                errors.append({"stage": "manager", "attempt": attempts, "message": "TaskManager 返回异常", "details": created})
                return {"ok": False, "attempts": attempts, "errors": errors, "message": "创建任务时出现未知错误，请重试"}
        except Exception as e:
            errors.append({"stage": "manager", "attempt": attempts, "message": f"TaskManager 异常：{e!r}"})
            return {"ok": False, "attempts": attempts, "errors": errors, "message": "创建任务时出现未知错误，请重试"}

    # -------------------- 工具能力缓存与提示构建 --------------------

    async def _ensure_tool_cache(self) -> None:
        if self._tool_index:
            return
        tools = await self.tm.list_tools()
        # 统一成 name -> dict（仅保留 description，不再期望 inputSchema）
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
        说明：
        - 不再展示参数 schema
        - 强调 additional_params 默认 {}，且禁止 in_dir/out_dir
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
            desc = _clip(self._tool_index[name].get("description", ""))
            if not desc:
                desc = "(no description)"
            lines.append(f"- {name} :: {desc}")
            count += 1

        extra_rules = (
            "通用规则：\n"
            "• 每个步骤对象必须包含 step_number / tool_name / source_kind / source / additional_params；relative 可选。\n"
            "• tool_name 必须在上面列出的工具名中。\n"
            "• 若 source_kind=='step'，source=小于当前步骤号的整数（引用前置步骤）。\n"
            "• additional_params：除工具描述中特别说明的业务参数外，默认填为空对象 {}。\n"
            "• 绝对禁止在 additional_params 中包含 in_dir/out_dir（这些由运行时注入）。\n"
        )
        return extra_rules + "\n" + ("\n".join(lines) if lines else "(no tools)")

    # -------------------- LLM 交互 --------------------

    async def _call_llm(self, plan_text: str, errors_so_far: List[Dict[str, Any]], allowed_tools: Set[str]) -> str:
        """
        给 LLM 的提示：system 里放硬性约束；如果前几轮有错误，将错误摘要附上要求仅修复。
        """
        tools_summary = self._summarize_tools_for_prompt(allowed_tools)

        system_prompt = f"""你是一个严格的“任务计划结构化器”。请将用户给出的不规范任务计划转换为**严格 JSON**，且只返回 JSON，不要任何额外文本或 Markdown。

JSON 结构如下（仅这些字段，禁止新增）：
{json.dumps(PLAN_JSON_SCHEMA, ensure_ascii=False, indent=2)}

强制约束：
1) steps[*].step_number 必须从 1 开始、连续（1,2,3,...）。
2) steps[*].source_kind ∈ {sorted(list(SOURCE_KINDS))}。
3) 若 source_kind == "step"，则 steps[*].source 必须是小于当前步骤号的整数（引用前置步骤）。
4) tool_name 必须在白名单内；若该工具描述未要求特定业务参数，则 steps[*].additional_params 使用 {{}}。
   禁止在 additional_params 中出现 in_dir / out_dir（运行时由系统注入）。
5) 只输出 JSON 对象（不能有 ```json 围栏、注释、说明文字）。

可用工具与描述（节选）：
{tools_summary}
"""

        # 将错误摘要（若有）拼到“developer”消息，要求只修复
        dev_msg = None
        if errors_so_far:
            last = errors_so_far[-1]
            dev_msg = f"你上一次的输出存在以下问题（仅修复这些问题并重新输出完整 JSON）：\n{json.dumps(last, ensure_ascii=False, indent=2)}"

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if dev_msg:
            messages.append({"role": "developer", "content": dev_msg})
        messages.append({"role": "user", "content": plan_text})

        resp = await self._client.chat.completions.create(
            model=self.cfg.model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},  # OpenAI v1+ 强制 JSON
        )
        content = resp.choices[0].message.content or ""
        return content

    def _parse_json(self, raw: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        try:
            text = _strip_json_fences(raw)
            obj = json.loads(text)
            if not isinstance(obj, dict):
                return None, "顶层不是 JSON 对象"
            return obj, None
        except Exception as e:
            return None, f"JSON 解析异常：{e!r}"

    # -------------------- 校验：JSON Schema / 逻辑 / 参数（宽松） --------------------

    def _validate_json_schema(self, plan_obj: Dict[str, Any]) -> Tuple[bool, Any]:
        if HAS_JSONSCHEMA:
            try:
                jsonschema_validate(instance=plan_obj, schema=PLAN_JSON_SCHEMA)
                return True, None
            except jsonschema.ValidationError as ve:  # type: ignore
                err = {
                    "path": list(ve.path),
                    "message": ve.message,
                    "validator": ve.validator,
                }
                return False, err
            except Exception as e:
                return False, {"message": f"JsonSchema 校验异常：{e!r}"}
        else:
            # 轻量兜底：只做最基本形状检查
            if not isinstance(plan_obj, dict) or "steps" not in plan_obj or not isinstance(plan_obj["steps"], list) or not plan_obj["steps"]:
                return False, {"message": "缺少 steps 或 steps 不是非空数组"}
            for i, s in enumerate(plan_obj["steps"], 1):
                for key in ("step_number", "tool_name", "source_kind", "source", "additional_params"):
                    if key not in s:
                        return False, {"message": f"steps[{i}] 缺少字段：{key}"}
            return True, None

    def _validate_logic(self, plan_obj: Dict[str, Any], allowed_tools: Set[str]) -> Tuple[bool, List[Dict[str, Any]]]:
        steps: List[Dict[str, Any]] = plan_obj["steps"]
        errors: List[Dict[str, Any]] = []

        # 1) 步号从 1 连续
        numbers = [int(s.get("step_number", -1)) for s in steps]
        if sorted(numbers) != list(range(1, len(numbers) + 1)):
            errors.append({"type": "step_number", "message": f"step_number 必须从 1 连续：{numbers}"})

        # 2) 工具白名单、source_kind 枚举（顶层 schema 已做，但再兜一层）
        for s in steps:
            k = int(s["step_number"])
            tool = str(s["tool_name"])
            if tool not in allowed_tools:
                errors.append({"type": "tool_name", "step": k, "message": f"不在白名单：{tool}"})

            sk = str(s["source_kind"])
            if sk not in SOURCE_KINDS:
                errors.append({"type": "source_kind", "step": k, "message": f"非法 source_kind：{sk}"})

            # 3) 依赖合法：source_kind=step → source 必须是 < k 的整数
            if sk == "step":
                src = s["source"]
                try:
                    src_num = int(src)
                except Exception:
                    errors.append({"type": "source", "step": k, "message": f"step 模式下 source 必须是整数：{src!r}"})
                    continue
                if not (1 <= src_num < k):
                    errors.append({"type": "source", "step": k, "message": f"非法前置引用：{src_num}（必须在 1..{k-1}）"})

            # 4) dataset 白名单（可选）
            if sk == "dataset" and self.cfg.allowed_datasets is not None:
                ds = str(s["source"])
                if ds not in self.cfg.allowed_datasets:
                    errors.append({"type": "dataset", "step": k, "message": f"数据集不在白名单：{ds}"})

        return (len(errors) == 0), errors

    def _validate_params(self, plan_obj: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        宽松参数校验：不再依赖 inputSchema。
        仅做：
          - additional_params 必须是对象（或缺省视为 {}）
          - 禁止包含运行时键 in_dir/out_dir
          - 可选：应用 self.cfg.extra_param_rules（若你仍希望对个别工具做互斥/依赖）
        """
        errors: List[Dict[str, Any]] = []
        steps: List[Dict[str, Any]] = plan_obj["steps"]

        for s in steps:
            step_no = int(s["step_number"])
            tool = str(s["tool_name"])
            add = s.get("additional_params")
            if add is None:
                add = {}
            if not isinstance(add, dict):
                errors.append({"type": "params", "step": step_no, "message": "additional_params 必须是对象或省略"})
                continue

            # 禁止运行时键
            rt_hit = set(add.keys()) & RUNTIME_PARAMS_FORBID
            if rt_hit:
                errors.append({
                    "type": "runtime_param_forbidden",
                    "step": step_no,
                    "tool": tool,
                    "message": f"禁止传入运行时参数：{sorted(list(rt_hit))}"
                })

            # 可选：额外复杂规则（若在 cfg.extra_param_rules 中配置了）
            if self.cfg.extra_param_rules and tool in self.cfg.extra_param_rules:
                err = self._apply_extra_rules(tool, add, self.cfg.extra_param_rules[tool])
                if err:
                    errors.append({"type": "extra_rules", "step": step_no, "tool": tool, "message": err})

        return (len(errors) == 0), errors

    def _apply_extra_rules(self, tool: str, add: Dict[str, Any], rules: Dict[str, Any]) -> Optional[str]:
        """
        可选：对某些工具施加手工规则（如互斥、范围、依赖等）。
        规则格式示意：
        {
          "xor": [["a","b"]],        # a 与 b 互斥
          "requires": {"a": ["b"]}   # 有 a 必须有 b
        }
        """
        # 互斥
        for group in rules.get("xor", []):
            hit = [k for k in group if k in add]
            if len(hit) > 1:
                return f"参数互斥：{hit}"
        # 依赖
        reqs = rules.get("requires", {})
        for k, deps in reqs.items():
            if k in add:
                miss = [d for d in deps if d not in add]
                if miss:
                    return f"参数依赖：存在 {k} 时必须包含 {miss}"
        return None


# --------------------------- 辅助：提示中的类型摘要（保留以兼容旧代码） ---------------------------

def _schema_type_repr(s: Any) -> str:
    """将 JSON Schema 的 type/enum 信息简短展示（现已不使用，仅保留以兼容）。"""
    if not isinstance(s, dict):
        return "any"
    typ = s.get("type")
    enum = s.get("enum")
    if enum and isinstance(enum, list):
        return f"enum{tuple(enum[:5]) + (('…',) if len(enum) > 5 else tuple())}"
    if isinstance(typ, list):
        return "|".join(typ)
    if isinstance(typ, str):
        return typ
    return "any"
