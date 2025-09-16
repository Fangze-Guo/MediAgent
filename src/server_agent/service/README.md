# Service 层 - 业务逻辑层

## 📁 文件结构

```
service/
├── __init__.py          # 服务层导出
├── user_service.py      # 用户业务逻辑
├── chat_service.py      # 聊天业务逻辑
├── tool_service.py      # 工具业务逻辑
├── system_service.py    # 系统业务逻辑
└── file_service.py     # 文件业务逻辑
```

## 🎯 设计原则

### 业务逻辑封装
- **Service**: 处理业务逻辑，数据验证，业务规则
- **Controller**: 只负责接口暴露
- **Mapper**: 只负责数据访问

### 异常处理
- 使用 `@handle_service_exception` 装饰器
- 统一的异常处理机制
- 详细的错误上下文

## 🚀 使用示例

### 基础服务结构
```python
class UserService:
    def __init__(self):
        self.user_mapper = user_mapper  # 注入数据访问层
    
    @handle_service_exception
    async def register_user(self, user_name: str, password: str) -> Dict[str, Any]:
        """用户注册业务逻辑"""
        # 1. 参数验证
        if not user_name or not password:
            raise ValidationError("用户名和密码不能为空")
        
        # 2. 业务规则检查
        if await self.user_mapper.check_username_exists(user_name):
            raise ConflictError("用户名已存在")
        
        # 3. 执行业务操作
        uid = await self.user_mapper.generate_unique_uid()
        success = await self.user_mapper.create_user(uid, user_name, password)
        
        if not success:
            raise ServiceError("用户创建失败")
        
        return {"ok": True, "uid": uid}
```

## 📋 服务功能

### 用户服务 (`user_service.py`)
- `register_user()` - 用户注册
- `login_user()` - 用户登录
- `get_user_by_token()` - 根据 token 获取用户
- `update_user_info()` - 更新用户信息

### 聊天服务 (`chat_service.py`)
- `chat()` - 普通聊天处理
- `chat_stream()` - 流式聊天处理
- `_build_system_content()` - 构建系统消息

### 工具服务 (`tool_service.py`)
- `get_tools_list()` - 获取工具列表
- `refresh_tools()` - 刷新工具
- `call_tool()` - 调用工具

### 系统服务 (`system_service.py`)
- `health_check()` - 健康检查
- `self_test()` - 系统自测

### 文件服务 (`file_service.py`)
- `upload_file()` - 文件上传
- `get_files_list()` - 获取文件列表
- `delete_file()` - 删除文件
- `serve_file()` - 文件下载

## 🔧 开发指南

### 添加新服务
1. 创建服务类
2. 注入 Mapper 依赖
3. 使用 `@handle_service_exception` 装饰器
4. 实现业务逻辑方法
5. 在 `__init__.py` 中导出

### 异常处理
```python
from ..exceptions import ValidationError, ConflictError, ServiceError

@handle_service_exception
async def business_method(self, param: str) -> Dict[str, Any]:
    # 业务逻辑
    if not param:
        raise ValidationError("参数不能为空")
    
    # 业务规则检查
    if await self.mapper.check_exists(param):
        raise ConflictError("资源已存在")
    
    # 执行业务操作
    result = await self.mapper.perform_operation(param)
    if not result:
        raise ServiceError("操作失败")
    
    return {"ok": True, "data": result}
```

### 数据验证
- 在 Service 层进行业务数据验证
- 使用自定义异常提供详细错误信息
- 保持 Controller 层简洁

### 业务规则
- 在 Service 层实现业务规则
- 确保数据一致性
- 处理业务异常情况
