"""
JSONL 消息解析器 - 从 CodeAgentController._parse_jsonl_messages 提取

将原始 JSONL 记录转换成 MessageResponse 列表，供 Controller 和 Service 共用，
确保前端聊天界面与导出功能使用完全一致的解析逻辑。
"""
import json
from typing import Any, Dict, List, Optional

from src.server_agent.model.entity.MessageResponse import MessageResponse


def _extract_text_and_thinking(message_content: Any) -> tuple:
    """
    从 JSONL 的 message.content 中提取可见文本与 thinking。
    支持 Claude 风格内容分块：text / thinking。
    """
    text_parts: List[str] = []
    thinking_parts: List[str] = []

    if isinstance(message_content, str):
        if message_content.strip():
            text_parts.append(message_content.strip())
    elif isinstance(message_content, list):
        for part in message_content:
            if isinstance(part, str):
                if part.strip():
                    text_parts.append(part.strip())
                continue

            if not isinstance(part, dict):
                continue

            part_type = part.get("type")
            if part_type in ("text", "input_text", "output_text"):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
            elif part_type == "thinking":
                thinking = part.get("thinking") or part.get("text")
                if isinstance(thinking, str) and thinking.strip():
                    thinking_parts.append(thinking.strip())

    text = "\n".join(text_parts).strip()
    thinking = "\n".join(thinking_parts).strip() if thinking_parts else None
    return text, thinking


def parse_jsonl_messages(
    jsonl_messages: List[Dict[str, Any]],
    conversation_id: str,
) -> List[MessageResponse]:
    """
    将原始 JSONL 记录转换成前端可渲染消息。

    与 CodeAgentController._parse_jsonl_messages 逻辑完全一致：
    - Skill call 组：toolUseResult.commandName 条目 + 后续连续的 isMeta/attachment 条目
    - TodoWrite 事件：从 tool_use 类型中提取 name==TodoWrite 的 todo 列表
    - 跳过控制类记录（queue-operation / last-prompt / attachment）
    - 仅保留 user/assistant 消息
    - 对同一个 message.id 的 assistant thinking/text 片段做合并
    """
    sorted_entries = sorted(jsonl_messages, key=lambda x: x.get("timestamp", ""))
    messages_response: List[MessageResponse] = []
    assistant_index_by_message_id: Dict[str, int] = {}

    # 预扫描：建立 tool_use_id → agentId 映射表（用于子智能体文件定位）
    # toolUseResult.agentId 在 user type 的工具结果条目里，指向对应的 agent-{agentId}.jsonl
    tool_use_to_agent_id: Dict[str, str] = {}
    for _entry in sorted_entries:
        _tur = _entry.get("toolUseResult")
        if not isinstance(_tur, dict):
            continue
        _agent_id = _tur.get("agentId")
        if not _agent_id:
            continue
        _msg = _entry.get("message", {})
        if isinstance(_msg, dict):
            for _part in (_msg.get("content") or []):
                if isinstance(_part, dict) and _part.get("type") == "tool_result":
                    _tuid = _part.get("tool_use_id")
                    if _tuid:
                        tool_use_to_agent_id[_tuid] = _agent_id

    # Skill call 分组收集：跳过 isMeta/attachment 条目
    skill_call_skipped_indices: set = set()

    for i, entry in enumerate(sorted_entries):
        entry_type = entry.get("type", "")
        is_meta = entry.get("isMeta", False)
        raw_message = entry.get("message", {})
        entry_role = raw_message.get("role") if isinstance(raw_message, dict) else None

        # 跳过 type=user 且 isMeta=true 的条目（这些是 skill 内部的用户输入，不对外展示）
        if entry_role == "user" and is_meta:
            continue

        # 跳过 Monitor 工具注入的 task-notification 消息（进度通知，不是用户说的话）
        origin = entry.get("origin", {})
        if isinstance(origin, dict) and origin.get("kind") == "task-notification":
            continue

        # 跳过已被 skill call 收集的条目
        if i in skill_call_skipped_indices:
            continue

        # 跳过控制类记录（但不在 skill call 组中的）
        if entry_type in ("queue-operation", "last-prompt"):
            continue

        # ======== tool_use block 检测（TodoWrite / Task / 其他）========
        raw_message = entry.get("message", {})
        raw_content = raw_message.get("content", []) if isinstance(raw_message, dict) else None

        todo_handled = False
        if isinstance(raw_content, list):
            for part in raw_content:
                if not isinstance(part, dict) or part.get("type") != "tool_use":
                    continue

                tool_name = part.get("name", "")
                tool_id = part.get("id", "")
                tool_input = part.get("input") or {}

                if tool_name == "TodoWrite":
                    todos = tool_input.get("todos", [])
                    messages_response.append(MessageResponse(
                        message_id=entry.get("uuid") or f"todo_{i}",
                        conversation_id=conversation_id,
                        role=None,
                        content=None,
                        thinking=None,
                        created_at=entry.get("timestamp"),
                        event_type="todo",
                        skill_name="TodoWrite",
                        todo_list=todos
                    ))
                    todo_handled = True
                    break  # 一条消息只取第一个 TodoWrite

                elif tool_name in ("Agent", "Task"):
                    # 子智能体调用：从 input 中提取任务描述
                    prompt = (
                        tool_input.get("prompt")
                        or tool_input.get("description")
                        or json.dumps(tool_input, ensure_ascii=False)
                    )
                    # 优先使用预扫描的 agentId（用于定位 agent-{agentId}.jsonl），回退到 tool_use block id
                    resolved_agent_id = tool_use_to_agent_id.get(tool_id, tool_id)
                    messages_response.append(MessageResponse(
                        message_id=f"subagent_{entry.get('uuid', i)}_{tool_id}",
                        conversation_id=conversation_id,
                        role=None,
                        content=prompt,
                        thinking=None,
                        created_at=entry.get("timestamp"),
                        event_type="sub_agent_call",
                        skill_name="Agent",
                        tool_use_id=resolved_agent_id,
                    ))
                    # 不设 todo_handled，继续处理同条消息中可能的文本内容

        if todo_handled:
            continue

        # ======== Skill Call 检测（toolUseResult.commandName） ========
        # 检查是否是 skill call 触发条目
        tool_use_result = entry.get("toolUseResult", {})
        command_name = tool_use_result.get("commandName") if isinstance(tool_use_result, dict) else None

        if command_name:
            # Skill call 组：收集后续连续的 isMeta/attachment 条目
            group_indices = {i}
            arguments = None

            for j in range(i + 1, len(sorted_entries)):
                next_entry = sorted_entries[j]
                next_type = next_entry.get("type", "")
                next_is_meta = next_entry.get("isMeta", False)

                if next_is_meta or next_type == "attachment":
                    group_indices.add(j)
                    # 从 isMeta 条目提取 arguments（message.content 末尾的 ARGUMENTS: 行）
                    if next_is_meta:
                        msg_content = next_entry.get("message", {}).get("content", "")
                        if isinstance(msg_content, str):
                            # 查找末尾的 ARGUMENTS: 行
                            for line in reversed(msg_content.strip().split('\n')):
                                if line.startswith("ARGUMENTS:"):
                                    arguments = line[len("ARGUMENTS:"):].strip()
                                    break
                                elif line.strip():
                                    # 遇到非空的非 ARGUMENTS 行则停止查找
                                    break
                else:
                    break

            skill_call_skipped_indices.update(group_indices)

            # 创建 skill_call 事件
            skill_call_event = MessageResponse(
                message_id=entry.get("uuid") or f"skill_{i}",
                conversation_id=conversation_id,
                role=None,
                content=None,
                thinking=None,
                created_at=entry.get("timestamp"),
                event_type="skill_call",
                skill_name=command_name,
                skill_arguments=arguments,
            )
            messages_response.append(skill_call_event)
            continue

        # 跳过 attachment 类型（已被 skill call 收集或独立存在）
        if entry_type == "attachment":
            continue

        if not isinstance(raw_message, dict):
            continue

        role = raw_message.get("role")
        if role not in ("user", "assistant"):
            continue

        content, thinking = _extract_text_and_thinking(raw_message.get("content", ""))
        if not content and not thinking:
            continue

        message_id = entry.get("uuid") or f"msg_{i}"
        assistant_message_id = raw_message.get("id")

        if role == "assistant" and assistant_message_id and assistant_message_id in assistant_index_by_message_id:
            idx = assistant_index_by_message_id[assistant_message_id]
            existing = messages_response[idx]

            if content:
                existing.content = f"{existing.content}\n{content}".strip() if existing.content else content
            if thinking:
                existing.thinking = f"{existing.thinking}\n{thinking}".strip() if existing.thinking else thinking
            continue

        parsed_message = MessageResponse(
            message_id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            thinking=thinking,
            created_at=entry.get("timestamp"),
        )
        messages_response.append(parsed_message)

        if role == "assistant" and assistant_message_id:
            assistant_index_by_message_id[assistant_message_id] = len(messages_response) - 1

    return messages_response
