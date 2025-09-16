# Tools 层 - 工具模块

## 📁 文件结构

```
tools/
├── __init__.py          # 工具模块导出
├── base_tool.py         # 基础工具类
├── data_tools.py        # 数据处理工具
└── image_tools.py       # 图像处理工具
```

## 🎯 设计原则

### 工具抽象
- **BaseTool**: 所有工具的基类
- **统一接口**: 标准化的工具调用接口
- **类型安全**: 强类型的参数和返回值

### 工具分类
- **数据处理**: CSV 文件处理、数据转换
- **图像处理**: 图像缩放、格式转换
- **系统工具**: 文件操作、系统信息

## 🚀 使用示例

### 基础工具类
```python
class BaseTool:
    """基础工具类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具操作"""
        raise NotImplementedError("子类必须实现 execute 方法")
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具参数模式"""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
```

### 具体工具实现
```python
class ResizeImageTool(BaseTool):
    """图像缩放工具"""
    
    def __init__(self):
        super().__init__(
            name="resize_image",
            description="调整图像大小"
        )
    
    async def execute(self, input_path: str, output_path: str, 
                     width: int, height: int, **kwargs) -> Dict[str, Any]:
        """执行图像缩放"""
        try:
            from PIL import Image
            
            with Image.open(input_path) as img:
                resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
                resized_img.save(output_path)
            
            return {
                "success": True,
                "message": f"图像已缩放为 {width}x{height}",
                "output_path": output_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_schema(self) -> Dict[str, Any]:
        """获取参数模式"""
        return {
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": "输入图像路径"
                },
                "output_path": {
                    "type": "string",
                    "description": "输出图像路径"
                },
                "width": {
                    "type": "integer",
                    "description": "目标宽度"
                },
                "height": {
                    "type": "integer",
                    "description": "目标高度"
                }
            },
            "required": ["input_path", "output_path", "width", "height"]
        }
```

## 📋 工具功能

### 数据处理工具 (`data_tools.py`)
- `CSVProcessorTool` - CSV 文件处理
- `DataConverterTool` - 数据格式转换
- `DataAnalyzerTool` - 数据分析

### 图像处理工具 (`image_tools.py`)
- `ResizeImageTool` - 图像缩放
- `FormatConverterTool` - 图像格式转换
- `ImageFilterTool` - 图像滤镜

### 系统工具
- `FileOperationTool` - 文件操作
- `SystemInfoTool` - 系统信息获取
- `ProcessManagerTool` - 进程管理

## 🔧 开发指南

### 添加新工具
1. 继承 `BaseTool` 类
2. 实现 `execute` 方法
3. 定义 `get_schema` 方法
4. 在 `__init__.py` 中注册

### 工具注册
```python
# tools/__init__.py
from .image_tools import ResizeImageTool
from .data_tools import CSVProcessorTool

# 工具注册表
TOOLS = {
    "resize_image": ResizeImageTool(),
    "csv_processor": CSVProcessorTool(),
}

def get_tool(name: str) -> Optional[BaseTool]:
    """获取工具实例"""
    return TOOLS.get(name)

def list_tools() -> List[Dict[str, Any]]:
    """获取所有工具列表"""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "schema": tool.get_schema()
        }
        for tool in TOOLS.values()
    ]
```

### 工具调用
```python
from tools import get_tool

# 获取工具实例
tool = get_tool("resize_image")
if tool:
    # 调用工具
    result = await tool.execute(
        input_path="input.jpg",
        output_path="output.jpg",
        width=800,
        height=600
    )
    print(result)
```

### 错误处理
```python
class BaseTool:
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具操作"""
        try:
            # 工具逻辑
            return {"success": True, "data": result}
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
```

## 🚀 工具集成

### 与 AI Agent 集成
```python
# agent.py
class MCPAgent:
    def __init__(self):
        self.tools = {}
        self._load_tools()
    
    def _load_tools(self):
        """加载工具"""
        from tools import TOOLS
        self.tools = TOOLS
    
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"工具不存在: {tool_name}")
        
        return await tool.execute(**args)
```

### 工具服务器
```python
# tools_server.py
from fastapi import FastAPI
from tools import list_tools, get_tool

app = FastAPI(title="Tools Server")

@app.get("/tools")
async def get_tools():
    """获取工具列表"""
    return {"tools": list_tools()}

@app.post("/tools/{tool_name}/call")
async def call_tool(tool_name: str, args: Dict[str, Any]):
    """调用工具"""
    tool = get_tool(tool_name)
    if not tool:
        raise HTTPException(404, f"工具不存在: {tool_name}")
    
    result = await tool.execute(**args)
    return result
```

## 📊 工具管理

### 工具发现
- 自动扫描工具目录
- 动态加载工具类
- 工具元数据管理

### 工具验证
- 参数类型验证
- 参数范围检查
- 依赖检查

### 工具监控
- 工具执行统计
- 性能监控
- 错误日志记录
