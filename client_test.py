# client_chat.py
import requests
import json
import uuid

SERVER = "http://127.0.0.1:8000/chat"   # 如果端口或主机不同，改这里
CONV_ID = f"c-{uuid.uuid4().hex[:8]}"   # 也可改成固定字符串
history: list[dict] = []

def ask(text: str) -> dict:
    payload = {
        "conversation_id": CONV_ID,
        "message": text,
        "history": history
    }
    r = requests.post(SERVER, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()

def main():
    print(f"📨 会话已创建: {CONV_ID}")
    print("输入你的问题，输入 /exit 退出。")
    while True:
        try:
            user = input("\n你> ").strip()
            if not user:
                continue
            if user.lower() in ("/exit", "exit", "quit"):
                print("再见！")
                break

            # 发送
            resp = ask(user)

            # 打印答案
            answer = resp.get("answer", "")
            print("\n助理> " + answer)

            # 如需查看工具调用详情，取消注释下一行
            # print(json.dumps(resp.get("tool_calls", []), ensure_ascii=False, indent=2))

            # 维护历史（与后端 model 对齐的最简格式）
            history.append({"role": "user", "content": user})
            history.append({"role": "assistant", "content": answer})

        except KeyboardInterrupt:
            print("\n(已中断) 再见！")
            break
        except requests.HTTPError as e:
            print("HTTP 错误：", e, "\n响应：", e.response.text if e.response else "")
        except Exception as e:
            print("异常：", repr(e))

if __name__ == "__main__":
    main()
