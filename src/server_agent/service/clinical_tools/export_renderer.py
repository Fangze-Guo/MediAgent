"""
会话导出渲染器 - 支持 Markdown / JSON / HTML 三种格式

ExportMessage 字段与后端 MessageResponse（前端实际渲染的数据模型）完全对齐，
确保用户导出看到的内容与前端聊天界面一致。
"""
import html as html_lib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional


# ─── 数据模型（对齐 MessageResponse） ────────────────────────────────────────

class ExportMessage:
    """导出用的统一消息结构，与 MessageResponse 字段一一对应

    前端 CodeAgentView.vue 渲染的消息就是这个结构：
    - role=user/assistant/null → 用户消息/助手消息/事件消息
    - event_type=skill_call → 技能调用气泡（🔧 + skill_name + skill_arguments）
    - event_type=todo → 任务列表气泡（📋 + todo_list）
    - event_type=skill_submitted → 不渲染（跳过）
    - thinking → 助手思考过程（折叠显示）
    - content → 消息正文
    """
    def __init__(
        self,
        message_id: str,
        conversation_id: Optional[str] = None,
        role: Optional[str] = None,
        content: Optional[str] = None,
        thinking: Optional[str] = None,
        created_at: Optional[str] = None,
        # event_type: skill_call | skill_submitted | todo | None
        event_type: Optional[str] = None,
        # skill_call 字段
        skill_name: Optional[str] = None,
        skill_arguments: Optional[str] = None,
        # skill_submitted 字段
        skill_task_id: Optional[str] = None,
        skill_status: Optional[str] = None,
        skill_progress: Optional[int] = None,
        skill_started_at: Optional[str] = None,
        skill_finished_at: Optional[str] = None,
        skill_elapsed_seconds: Optional[float] = None,
        skill_error: Optional[str] = None,
        # todo 字段
        todo_list: Optional[List[dict]] = None,
    ):
        self.message_id = message_id
        self.conversation_id = conversation_id
        self.role = role
        self.content = content
        self.thinking = thinking
        self.created_at = created_at
        self.event_type = event_type
        self.skill_name = skill_name
        self.skill_arguments = skill_arguments
        self.skill_task_id = skill_task_id
        self.skill_status = skill_status
        self.skill_progress = skill_progress
        self.skill_started_at = skill_started_at
        self.skill_finished_at = skill_finished_at
        self.skill_elapsed_seconds = skill_elapsed_seconds
        self.skill_error = skill_error
        self.todo_list = todo_list

    @classmethod
    def from_message_response(cls, msg) -> "ExportMessage":
        """从 MessageResponse (Pydantic model) 转换"""
        return cls(
            message_id=msg.message_id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            thinking=msg.thinking,
            created_at=msg.created_at,
            event_type=msg.event_type,
            skill_name=msg.skill_name,
            skill_arguments=msg.skill_arguments,
            skill_task_id=getattr(msg, "skill_task_id", None),
            skill_status=getattr(msg, "skill_status", None),
            skill_progress=getattr(msg, "skill_progress", None),
            skill_started_at=getattr(msg, "skill_started_at", None),
            skill_finished_at=getattr(msg, "skill_finished_at", None),
            skill_elapsed_seconds=getattr(msg, "skill_elapsed_seconds", None),
            skill_error=getattr(msg, "skill_error", None),
            todo_list=msg.todo_list,
        )


class ExportConversation:
    """导出用的会话元数据"""
    def __init__(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        project_id: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.conversation_id = conversation_id
        self.title = title
        self.project_id = project_id
        self.created_at = created_at
        self.updated_at = updated_at


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def _format_timestamp(ts) -> str:
    """将 timestamp 转为可读字符串"""
    if not ts:
        return ""
    try:
        if isinstance(ts, (int, float)):
            # JSONL 中 timestamp 是毫秒
            dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
        elif isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            return str(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def _escape_html(text: str) -> str:
    return html_lib.escape(text, quote=True)


def _escape_markdown(text: str) -> str:
    """转义 Markdown 特殊字符（仅用于行首）"""
    if text.startswith("#"):
        return "\\" + text
    return text


# ─── Markdown 渲染器 ──────────────────────────────────────────────────────────

def render_markdown(conv: ExportConversation, messages: List[ExportMessage]) -> str:
    lines: list[str] = []

    # 头部
    title = conv.title or "未命名会话"
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- **会话ID**: {conv.conversation_id}")
    if conv.project_id:
        lines.append(f"- **项目**: {conv.project_id}")
    if conv.created_at:
        lines.append(f"- **创建时间**: {_format_timestamp(conv.created_at)}")
    if conv.updated_at:
        lines.append(f"- **更新时间**: {_format_timestamp(conv.updated_at)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in messages:
        ts = _format_timestamp(msg.created_at)

        # skill_submitted 事件：与前端一致，不渲染
        if msg.event_type == "skill_submitted":
            continue

        # Skill call 事件：与前端一致，橙色气泡 🔧 + skill_name + skill_arguments
        if msg.event_type == "skill_call":
            lines.append(f"### 🔧 技能调用: {msg.skill_name or 'unknown'}")
            if ts:
                lines.append(f"> 时间: {ts}")
            if msg.skill_arguments:
                lines.append(f"> 参数: `{msg.skill_arguments}`")
            # skill 后台任务状态（如有）
            if msg.skill_status:
                status_icon = "✅" if msg.skill_status == "success" else "❌" if msg.skill_status == "failed" else "🔄"
                lines.append(f"> 状态: {status_icon} {msg.skill_status}")
            if msg.skill_error:
                lines.append(f"> 错误: {msg.skill_error}")
            if msg.skill_elapsed_seconds is not None:
                lines.append(f"> 耗时: {msg.skill_elapsed_seconds:.1f}s")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        # Todo 事件：与前端一致，📋 任务列表 + todo_list
        if msg.event_type == "todo":
            lines.append("### 📋 任务列表 (Update Todos)")
            if ts:
                lines.append(f"> 时间: {ts}")
            if msg.todo_list:
                for todo in msg.todo_list:
                    status = todo.get("status", "")
                    # 前端用 activeForm 优先，fallback content
                    text = todo.get("activeForm") or todo.get("content", "")
                    icon = "✅" if status == "completed" else "⬜" if status == "in_progress" else "⬚"
                    lines.append(f"- {icon} {text}")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        # 普通消息
        if msg.role == "user":
            lines.append(f"## 👤 用户")
            if ts:
                lines.append(f"*{ts}*")
            lines.append("")
            if msg.content:
                lines.append(_escape_markdown(msg.content))
            lines.append("")
        elif msg.role == "assistant":
            lines.append(f"## 🤖 助手")
            if ts:
                lines.append(f"*{ts}*")
            lines.append("")
            # 思考过程：与前端一致，折叠显示
            if msg.thinking:
                lines.append("> 💡 **思考过程**")
                lines.append(">")
                for thought_line in msg.thinking.split("\n"):
                    lines.append(f"> {thought_line}")
                lines.append("")
            if msg.content:
                lines.append(msg.content)
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ─── JSON 渲染器 ──────────────────────────────────────────────────────────────

def render_json(conv: ExportConversation, messages: List[ExportMessage]) -> str:
    data = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "conversation": {
            "conversation_id": conv.conversation_id,
            "title": conv.title,
            "project_id": conv.project_id,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
        },
        "messages": [],
    }

    for msg in messages:
        entry: dict = {
            "id": msg.message_id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "timestamp": msg.created_at,
        }
        if msg.content:
            entry["content"] = msg.content
        if msg.thinking:
            entry["thinking"] = msg.thinking
        if msg.event_type:
            entry["event_type"] = msg.event_type
        # skill_call 字段
        if msg.skill_name:
            entry["skill_name"] = msg.skill_name
        if msg.skill_arguments:
            entry["skill_arguments"] = msg.skill_arguments
        # skill_submitted 字段
        if msg.skill_task_id:
            entry["skill_task_id"] = msg.skill_task_id
        if msg.skill_status:
            entry["skill_status"] = msg.skill_status
        if msg.skill_progress is not None:
            entry["skill_progress"] = msg.skill_progress
        if msg.skill_started_at:
            entry["skill_started_at"] = msg.skill_started_at
        if msg.skill_finished_at:
            entry["skill_finished_at"] = msg.skill_finished_at
        if msg.skill_elapsed_seconds is not None:
            entry["skill_elapsed_seconds"] = msg.skill_elapsed_seconds
        if msg.skill_error:
            entry["skill_error"] = msg.skill_error
        # todo 字段
        if msg.todo_list:
            entry["todo_list"] = msg.todo_list
        data["messages"].append(entry)

    return json.dumps(data, ensure_ascii=False, indent=2)


# ─── HTML 渲染器 ──────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - 会话导出</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #f5f5f5; color: #333; line-height: 1.6; padding: 24px; max-width: 900px; margin: 0 auto; }}
  .header {{ background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
  .header h1 {{ font-size: 1.5em; margin-bottom: 8px; }}
  .header .meta {{ color: #888; font-size: .9em; }}
  .header .meta span {{ margin-right: 16px; }}
  .message {{ background: #fff; border-radius: 12px; padding: 16px 20px; margin-bottom: 12px;
             box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
  .message.user {{ border-left: 4px solid #1677ff; }}
  .message.assistant {{ border-left: 4px solid #52c41a; }}
  .message.event {{ border-left: 4px solid #faad14; background: #fffbe6; }}
  .role-label {{ font-weight: 600; font-size: .9em; margin-bottom: 6px; }}
  .role-label.user-label {{ color: #1677ff; }}
  .role-label.assistant-label {{ color: #52c41a; }}
  .role-label.event-label {{ color: #d48806; }}
  .timestamp {{ color: #aaa; font-size: .8em; margin-bottom: 8px; }}
  .content {{ white-space: pre-wrap; word-break: break-word; }}
  .thinking {{ background: #f9f0ff; border: 1px solid #d3adf7; border-radius: 8px;
               padding: 12px; margin: 8px 0; font-size: .9em; color: #722ed1; cursor: pointer; }}
  .thinking.collapsed .thinking-body {{ display: none; }}
  .thinking-header {{ font-weight: 600; margin-bottom: 4px; }}
  .skill-call {{ font-size: .9em; }}
  .skill-call .skill-name {{ font-weight: 600; color: #d48806; }}
  .skill-call .skill-args {{ background: #fff7e6; padding: 8px; border-radius: 4px;
                             font-family: monospace; font-size: .85em; margin-top: 4px; }}
  .skill-status {{ margin-top: 6px; font-size: .85em; color: #888; }}
  .skill-status.success {{ color: #52c41a; }}
  .skill-status.failed {{ color: #ff4d4f; }}
  .skill-status.running {{ color: #1677ff; }}
  .todo-list {{ list-style: none; padding: 0; }}
  .todo-list li {{ padding: 4px 0; }}
  .todo-list li.completed {{ text-decoration: line-through; color: #999; }}
  .divider {{ border: none; border-top: 1px solid #eee; margin: 16px 0; }}
</style>
</head>
<body>
{body}
<script>
document.querySelectorAll('.thinking').forEach(el => {{
  el.addEventListener('click', () => el.classList.toggle('collapsed'));
}});
</script>
</body>
</html>"""


def render_html(conv: ExportConversation, messages: List[ExportMessage]) -> str:
    title = _escape_html(conv.title or "未命名会话")
    body_parts: list[str] = []

    # 头部
    meta_parts = [f'<span>会话ID: {_escape_html(conv.conversation_id)}</span>']
    if conv.project_id:
        meta_parts.append(f'<span>项目: {_escape_html(conv.project_id)}</span>')
    if conv.created_at:
        meta_parts.append(f'<span>创建: {_escape_html(_format_timestamp(conv.created_at))}</span>')

    body_parts.append(f'<div class="header">')
    body_parts.append(f'<h1>{title}</h1>')
    body_parts.append(f'<div class="meta">{"&nbsp;".join(meta_parts)}</div>')
    body_parts.append('</div>')

    for msg in messages:
        ts = _format_timestamp(msg.created_at)

        # skill_submitted 事件：与前端一致，不渲染
        if msg.event_type == "skill_submitted":
            continue

        # Skill call：与前端一致，橙色气泡 🔧 + skill_name + skill_arguments
        if msg.event_type == "skill_call":
            body_parts.append('<div class="message event">')
            body_parts.append(f'<div class="role-label event-label">🔧 技能调用</div>')
            if ts:
                body_parts.append(f'<div class="timestamp">{_escape_html(ts)}</div>')
            body_parts.append(f'<div class="skill-call"><span class="skill-name">{_escape_html(msg.skill_name or "unknown")}</span>')
            if msg.skill_arguments:
                body_parts.append(f'<div class="skill-args">{_escape_html(msg.skill_arguments)}</div>')
            # skill 后台任务状态
            if msg.skill_status:
                status_cls = msg.skill_status
                status_icon = "✅" if msg.skill_status == "success" else "❌" if msg.skill_status == "failed" else "🔄"
                body_parts.append(f'<div class="skill-status {status_cls}">{status_icon} {msg.skill_status}</div>')
            if msg.skill_error:
                body_parts.append(f'<div class="skill-status failed">错误: {_escape_html(msg.skill_error)}</div>')
            if msg.skill_elapsed_seconds is not None:
                body_parts.append(f'<div class="skill-status">耗时: {msg.skill_elapsed_seconds:.1f}s</div>')
            body_parts.append('</div></div>')
            continue

        # Todo：与前端一致，📋 Update Todos + todo_list（activeForm 优先）
        if msg.event_type == "todo":
            body_parts.append('<div class="message event">')
            body_parts.append('<div class="role-label event-label">📋 Update Todos</div>')
            if ts:
                body_parts.append(f'<div class="timestamp">{_escape_html(ts)}</div>')
            if msg.todo_list:
                body_parts.append('<ul class="todo-list">')
                for todo in msg.todo_list:
                    status = todo.get("status", "")
                    # 前端用 activeForm 优先，fallback content
                    text = _escape_html(todo.get("activeForm") or todo.get("content", ""))
                    cls = "completed" if status == "completed" else ""
                    icon = "✓" if status == "completed" else ""
                    body_parts.append(f'<li class="{cls}"><span class="todo-checkbox">{icon}</span> <span class="todo-text">{text}</span></li>')
                body_parts.append('</ul>')
            body_parts.append('</div>')
            continue

        # 普通消息
        role_class = msg.role or "assistant"
        label_class = f"{role_class}-label"
        if msg.role == "user":
            label = "👤 用户"
        else:
            label = "🤖 助手"

        body_parts.append(f'<div class="message {role_class}">')
        body_parts.append(f'<div class="role-label {label_class}">{label}</div>')
        if ts:
            body_parts.append(f'<div class="timestamp">{_escape_html(ts)}</div>')

        # 思考过程：与前端一致，折叠显示
        if msg.thinking:
            body_parts.append('<div class="thinking">')
            body_parts.append('<div class="thinking-header">💡 思考过程（点击折叠）</div>')
            body_parts.append(f'<div class="thinking-body">{_escape_html(msg.thinking)}</div>')
            body_parts.append('</div>')

        if msg.content:
            body_parts.append(f'<div class="content">{_escape_html(msg.content)}</div>')

        body_parts.append('</div>')

    body = "\n".join(body_parts)
    return _HTML_TEMPLATE.format(title=title, body=body)


# ─── 调度入口 ─────────────────────────────────────────────────────────────────

def render_conversation(
    conv: ExportConversation,
    messages: List[ExportMessage],
    fmt: str = "markdown",
) -> str:
    """根据格式渲染会话内容

    Args:
        conv: 会话元数据
        messages: 消息列表
        fmt: "markdown" | "json" | "html"

    Returns:
        渲染后的字符串
    """
    renderers = {
        "markdown": render_markdown,
        "json": render_json,
        "html": render_html,
    }
    renderer = renderers.get(fmt)
    if not renderer:
        raise ValueError(f"Unsupported export format: {fmt}, supported: {list(renderers.keys())}")
    return renderer(conv, messages)


def get_mime_type(fmt: str) -> str:
    """获取导出格式的 MIME 类型"""
    return {"markdown": "text/markdown", "json": "application/json", "html": "text/html"}.get(fmt, "application/octet-stream")


def get_file_extension(fmt: str) -> str:
    """获取导出格式的文件扩展名"""
    return {"markdown": ".md", "json": ".json", "html": ".html"}.get(fmt, ".txt")
