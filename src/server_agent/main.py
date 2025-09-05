# main.py
import asyncio, os, uuid
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
from agent import MCPAgent
from fastapi.middleware.cors import CORSMiddleware
import pathlib
import shutil
from datetime import datetime

app = FastAPI(title="MediAgent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = MCPAgent()
_init_lock = asyncio.Lock()
_initialized = False

class FileInfo(BaseModel):
    id: str
    originalName: str
    size: int
    type: str
    path: str
    uploadTime: str

class ChatReq(BaseModel):
    conversation_id: str
    message: str
    history: list[dict] = []
    files: list[FileInfo] = []

class ChatResp(BaseModel):
    conversation_id: str
    answer: str
    tool_calls: list = []

class ToolReq(BaseModel):
    name: str
    args: dict

class FileInfo(BaseModel):
    id: str
    originalName: str
    size: int
    type: str
    path: str
    uploadTime: str

class FileUploadResp(BaseModel):
    success: bool
    file: FileInfo
    error: str = None

class FileListResp(BaseModel):
    files: list[FileInfo]

# 文件上传配置
UPLOAD_DIR = pathlib.Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.csv'}

#各项功能以及内部需要等待IO的调用等都要写成协程，防止阻塞整个服务器
@app.on_event("startup")
async def startup():
    global _initialized
    async with _init_lock:#进入一个 异步锁（_init_lock = asyncio.Lock() 通常在模块顶层创建）。作用：避免竞态——如果有多个并发路径可能触发初始化（例如你在路由里也做了“懒加载兜底”），只有第一个协程能进入临界区，其它协程会等待；等初始化完成再放行。
        if not _initialized:#双保险。即使多个并发都到达这里，只有第一个会执行真正的初始化；后面进来的看到标记已置位，就直接跳过
            await agent.init_tools()
            _initialized = True

@app.get("/tools")
async def list_tools():
    if not _initialized:
        await startup()
    return {"tools": agent.tools}

@app.post("/refresh-tools")
async def refresh_tools():
    await agent.init_tools()
    return {"ok": True, "count": len(agent.tools)}

@app.post("/chat", response_model=ChatResp)
async def chat(req: ChatReq):
    try:
        if not _initialized:
            await startup()
        msgs = [{"role": "system", "content": "你可以在需要时调用可用工具来完成任务，工具返回JSON，请先解析后用中文总结关键结果。"}]
        msgs += req.history
        msgs += [{"role": "user", "content": req.message}]
        result = await agent.chat(msgs)
        return ChatResp(conversation_id=req.conversation_id, answer=result["content"], tool_calls=result["tool_calls"])
    except Exception as e:
        print(f"/chat 调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"聊天服务错误: {str(e)}")

@app.post("/chat/stream")
async def chat_stream(req: ChatReq):
    """流式聊天接口，支持实时输出"""
    try:
        if not _initialized:
            await startup()
        
        # 构建系统消息，包含文件信息
        system_content = "你是一个智能助手，可以调用工具来帮助用户完成任务。\n\n重要规则：\n1. 当需要调用工具时，请直接调用，不要输出<think>标签或思考过程\n2. 工具返回JSON格式，请解析后用中文总结关键结果\n3. 回复要简洁明了，避免冗余的思考过程"
        
        # 如果有文件，添加文件信息到系统消息
        if req.files:
            system_content += f"\n\n可用文件："
            for file in req.files:
                if file.type.startswith('image/'):
                    system_content += f"\n- {file.originalName} → {file.path}"
                elif 'csv' in file.type:
                    system_content += f"\n- {file.originalName} → {file.path}"
                else:
                    system_content += f"\n- {file.originalName} → {file.path}"
            
            system_content += f"\n\n注意：调用工具时使用完整路径，不要使用原始文件名。"
        
        msgs = [{"role": "system", "content": system_content}]
        msgs += req.history
        msgs += [{"role": "user", "content": req.message}]
        
        async def generate():
            try:
                # 发送开始信号
                yield f"data: {json.dumps({'type': 'start', 'conversation_id': req.conversation_id}, ensure_ascii=False)}\n\n"
                
                # 流式获取AI回复
                async for chunk in agent.chat_stream(msgs):
                    if chunk['type'] == 'content':
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif chunk['type'] == 'tool_call':
                        yield f"data: {json.dumps({'type': 'tool_call', 'tool': chunk['tool']}, ensure_ascii=False)}\n\n"
                    elif chunk['type'] == 'complete':
                        yield f"data: {json.dumps({'type': 'complete', 'tool_calls': chunk.get('tool_calls', [])}, ensure_ascii=False)}\n\n"
                        break
                
            except Exception as e:
                print(f"流式聊天错误: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",  # ← 改成 SSE 正确类型
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # ← 反向代理(如Nginx)禁缓冲，避免卡流
            },
        )


    except Exception as e:
        print(f"/chat/stream 调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"流式聊天服务错误: {str(e)}")

# === 直连工具：绕过 LLM，快速排障 ===
@app.post("/call-tool")
async def call_tool(req: ToolReq):
    if not _initialized:
        await startup()
    names = [t["function"]["name"] for t in agent.tools if "function" in t]
    if req.name not in names:
        raise HTTPException(404, f"tool not found: {req.name}")
    # 内部方法，直接调用 MCP 工具
    result = await agent._call_tool(req.name, req.args)
    return {"ok": True, "result": result}

# === 健康检查 ===
@app.get("/healthz")
async def healthz():
    base_url = os.getenv("BASE_URL", "http://localhost:1234/v1")
    model = os.getenv("MODEL", "unknown")
    mcp_py = "unknown"
    try:
        # 从 tools_server 日志里已经能看到 sys.executable；这里简单带回当前进程信息
        import sys
        mcp_py = sys.executable
    except Exception:
        pass
    if not _initialized:
        await startup()
    return {
        "status": "ok",
        "model": model,
        "lm_server": base_url,
        "tools_count": len(agent.tools),
        "python": mcp_py,
    }

# === 文件上传和管理 ===
@app.post("/upload", response_model=FileUploadResp)
async def upload_file(file: UploadFile = File(...)):
    """上传文件接口"""
    try:
        # 检查文件大小
        if file.size > MAX_FILE_SIZE:
            return FileUploadResp(
                success=False,
                file=None,
                error=f"文件大小超过限制 ({MAX_FILE_SIZE // (1024*1024)}MB)"
            )
        
        # 检查文件扩展名
        file_ext = pathlib.Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return FileUploadResp(
                success=False,
                file=None,
                error=f"不支持的文件类型: {file_ext}"
            )
        
        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        file_name = f"{file_id}{file_ext}"
        file_path = UPLOAD_DIR / file_name
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建文件信息
        file_info = FileInfo(
            id=file_id,
            originalName=file.filename,
            size=file.size,
            type=file.content_type,
            path=str(file_path.resolve()),
            uploadTime=datetime.now().isoformat()
        )
        
        return FileUploadResp(success=True, file=file_info)
        
    except Exception as e:
        print(f"文件上传失败: {e}")
        return FileUploadResp(
            success=False,
            file=None,
            error=f"文件上传失败: {str(e)}"
        )

@app.post("/files", response_model=FileListResp)
async def list_files():
    """获取已上传文件列表"""
    try:
        files = []
        for file_path in UPLOAD_DIR.iterdir():
            if file_path.is_file():
                # 从文件名提取ID
                file_id = file_path.stem
                file_ext = file_path.suffix
                
                # 获取文件信息
                stat = file_path.stat()
                file_info = FileInfo(
                    id=file_id,
                    originalName=f"{file_id}{file_ext}",  # 简化显示
                    size=stat.st_size,
                    type=get_content_type(file_ext),
                    path=str(file_path.resolve()),
                    uploadTime=datetime.fromtimestamp(stat.st_mtime).isoformat()
                )
                files.append(file_info)
        
        return FileListResp(files=files)
        
    except Exception as e:
        print(f"获取文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")

def get_content_type(ext: str) -> str:
    """根据文件扩展名获取内容类型"""
    content_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.csv': 'text/csv'
    }
    return content_types.get(ext.lower(), 'application/octet-stream')

# === 自测：生成、缩放、校验（本地磁盘） ===
@app.get("/selftest")
async def selftest():
    import pathlib
    from PIL import Image
    root = pathlib.Path("../..")
    inp = root / "selftest_in.jpg"
    outp = root / "selftest_out.jpg"
    Image.new("RGB", (320, 200), (180, 200, 240)).save(inp)
    # 直连工具调用
    res = await agent._call_tool("resize_image", {
        "input_path": str(inp.resolve()),
        "output_path": str(outp.resolve()),
        "width": 128,
        "height": 128,
        "timeout": 30
    })
    return {"ok": True, "result": res}
