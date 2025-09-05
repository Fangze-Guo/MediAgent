# client_stream_test.py
import requests
import json
import uuid
import sys
from typing import List, Dict

# === 基本配置 ===
BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = f"{BASE_URL}/chat/stream"     # 你的流式接口
TIMEOUT = (5, 600)  # (连接超时, 读取超时) 读取设长一点以便持续流

# 可固定会话，或每次随机新会话
CONV_ID = f"c-{uuid.uuid4().hex[:8]}"

# 维护与后端对齐的最简消息格式
history: List[Dict[str, str]] = []

def sse_events(resp: requests.Response):
    """
    简易 SSE 解析器：
    - 以空行(\n\n)为事件边界
    - 同一事件内可能有多行 'data: '，需要合并
    - 忽略以 ':' 开头的注释/心跳行
    """
    buffer_lines: List[str] = []

    # iter_lines 会按 \n 分割，这里逐行累积，遇到空行处理一个事件
    for raw in resp.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        line = raw.strip("\r")

        if line == "":
            # 一个事件结束
            if buffer_lines:
                # 合并同一事件内的多行 data:
                data_lines = [l[6:] for l in buffer_lines if l.startswith("data: ")]
                payload = "\n".join(data_lines)
                yield payload
                buffer_lines.clear()
            continue

        if line.startswith(":"):
            # 注释 / 心跳
            continue

        buffer_lines.append(line)

    # 结束前处理尾巴
    if buffer_lines:
        data_lines = [l[6:] for l in buffer_lines if l.startswith("data: ")]
        payload = "\n".join(data_lines)
        if payload:
            yield payload

def ask_stream(text: str):
    """
    发送一条用户消息，流式打印模型回复。
    返回：最终聚合后的 assistant 文本（用于追加到 history）
    """
    payload = {
        "conversation_id": CONV_ID,
        "message": text,
        "history": history,  # 注意：不要把“空的 assistant 占位”带进去
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",  # 不是必须，但语义化
    }

    with requests.post(
        ENDPOINT,
        json=payload,
        headers=headers,
        stream=True,
        timeout=TIMEOUT,
        proxies={'http': None, 'https': None},
    ) as resp:
        resp.raise_for_status()

        ctype = resp.headers.get("content-type", "")
        if "text/event-stream" not in ctype:
            print(f"[!] 警告：返回的 Content-Type 不是 text/event-stream: {ctype}", file=sys.stderr)

        final_answer_chunks: List[str] = []

        for ev in sse_events(resp):
            # 每个 ev 是一段 data: 合并后的 JSON 字符串
            try:
                obj = json.loads(ev)
            except Exception as e:
                print(f"[SSE解析失败] {e} | 原始: {ev}", file=sys.stderr)
                continue

            etype = obj.get("type")
            if etype == "start":
                cid = obj.get("conversation_id", "")
                print(f"—— 开始流式对话 (conversation_id={cid}) ——")
            elif etype == "content":
                chunk = obj.get("content", "")
                final_answer_chunks.append(chunk)
                # 直接打印，不换行缓存（可按需更改）
                sys.stdout.write(chunk)
                sys.stdout.flush()
            elif etype == "tool_call":
                tool = obj.get("tool", "")
                print(f"\n[工具调用] {tool}")
            elif etype == "complete":
                tool_calls = obj.get("tool_calls", [])
                if tool_calls:
                    print(f"\n—— 对话完成（工具调用 {len(tool_calls)} 次）——")
                else:
                    print("\n—— 对话完成 ——")
                break
            elif etype == "error":
                err = obj.get("error", "未知错误")
                print(f"\n[错误] {err}", file=sys.stderr)
                break
            else:
                print(f"\n[未知事件] {obj}")

        # 返回聚合后的文本
        return "".join(final_answer_chunks)

def main():
    try:
        # 尽量保证控制台能打印中文
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # Py3.7+
        except Exception:
            pass

        print(f"📨 会话已创建: {CONV_ID}")
        print("输入你的问题，输入 /exit 退出。")

        while True:
            user = input("\n你> ").strip()
            if not user:
                continue
            if user.lower() in ("/exit", "exit", "quit"):
                print("再见！")
                break

            print("助理> ", end="", flush=True)
            try:
                answer = ask_stream(user) or ""
            except requests.HTTPError as e:
                print(f"\nHTTP 错误：{e}")
                print("响应：", e.response.text if e.response is not None else "")
                continue
            except requests.ReadTimeout:
                print("\n[读取超时] 可能网络或后端未持续推送。")
                continue
            except KeyboardInterrupt:
                print("\n(已中断)")
                break
            except Exception as e:
                print(f"\n异常：{repr(e)}")
                continue

            # 维护本地 history
            history.append({"role": "user", "content": user})
            history.append({"role": "assistant", "content": answer})

    except KeyboardInterrupt:
        print("\n(已中断) 再见！")

if __name__ == "__main__":
    main()
