# Mapper 层 - 数据访问层

## 📁 文件结构

```
mapper/
├── __init__.py          # 包入口，导出所有接口
├── user_mapper.py       # 用户数据访问层
├── base_mapper.py       # 基础 Mapper 类
├── config.py            # 数据库配置管理
├── migrations.py        # 数据库迁移工具
└── paths.py             # 路径工具
```

## 🎯 设计原则

### 数据访问封装
- **Mapper**: 只负责数据库操作，不包含业务逻辑
- **Service**: 调用 Mapper 进行数据操作
- **BaseMapper**: 提供通用的数据库操作功能

### 连接管理
- 智能连接池管理
- 自动连接创建和回收
- 支持并发访问

## 🚀 使用示例

### 基础 Mapper
```python
class BaseMapper(ABC):
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection_pool = asyncio.Queue(maxsize=10)
    
    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = await self._get_connection()
        try:
            yield conn
        finally:
            await self._return_connection(conn)
    
    async def execute_query(self, query: str, params: tuple = (), 
                           fetch_one: bool = False, fetch_all: bool = False):
        """统一的查询执行接口"""
        async with self.get_connection() as db:
            async with db.execute(query, params) as cursor:
                if fetch_one:
                    return await cursor.fetchone()
                elif fetch_all:
                    return await cursor.fetchall()
```

### 用户 Mapper
```python
class UserMapper(BaseMapper):
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = in_data("db", "app.sqlite3")
        super().__init__(db_path)
    
    async def find_user_by_name(self, user_name: str) -> Optional[User]:
        """按用户名查找用户"""
        query = """
            SELECT uid, user_name, password, token, created_at, updated_at, last_login 
            FROM users 
            WHERE user_name = ? COLLATE NOCASE 
            LIMIT 1
        """
        result = await self.execute_query(query, (user_name,), fetch_one=True)
        
        if result:
            return User(
                uid=result[0],
                user_name=result[1],
                password_hash=result[2],
                token=result[3],
                created_at=datetime.fromisoformat(result[4]) if result[4] else None,
                updated_at=datetime.fromisoformat(result[5]) if result[5] else None,
                last_login=datetime.fromisoformat(result[6]) if result[6] else None
            )
        return None
```

## 📋 主要功能

### 用户数据访问 (`user_mapper.py`)
- `find_user_by_name()` - 按用户名查找
- `find_user_by_token()` - 按 token 查找
- `create_user()` - 创建用户
- `update_user_info()` - 更新用户信息
- `verify_password()` - 验证密码

### 基础功能 (`base_mapper.py`)
- `execute_query()` - 执行查询
- `execute_transaction()` - 执行事务
- `execute_batch()` - 批量操作
- 连接池管理

### 配置管理 (`config.py`)
- 数据库连接配置
- SQLite 优化参数
- 环境变量支持

### 数据库迁移 (`migrations.py`)
- 版本管理
- 自动表创建
- 向前/向后迁移

## 🔧 开发指南

### 添加新 Mapper
1. 继承 `BaseMapper`
2. 实现数据访问方法
3. 使用 `@handle_mapper_exception` 装饰器
4. 返回强类型数据模型

### 数据模型
```python
@dataclass
class User:
    """用户数据模型"""
    uid: int
    user_name: str
    password_hash: str
    token: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
```

### 异常处理
```python
from ..exceptions import DatabaseError, handle_mapper_exception

@handle_mapper_exception
async def database_operation(self, param: str) -> Optional[User]:
    """数据库操作"""
    try:
        # 数据库操作
        result = await self.execute_query("SELECT * FROM users WHERE name = ?", (param,), fetch_one=True)
        return User.from_result(result) if result else None
    except Exception as e:
        raise DatabaseError(
            detail="Database operation failed",
            operation="find_user",
            context={"param": param, "error": str(e)}
        )
```

### 事务处理
```python
async def create_user_with_profile(self, user_data: dict, profile_data: dict) -> bool:
    """创建用户和配置文件"""
    operations = [
        {
            'query': "INSERT INTO users (name, email) VALUES (?, ?)",
            'params': (user_data['name'], user_data['email'])
        },
        {
            'query': "INSERT INTO profiles (user_id, bio) VALUES (?, ?)",
            'params': (profile_data['user_id'], profile_data['bio'])
        }
    ]
    
    return await self.execute_transaction(operations)
```

## 🚀 性能优化

### 连接池
- 智能连接管理
- 减少连接创建开销
- 支持并发访问

### SQLite 优化
```python
pragma_settings = {
    "foreign_keys": "ON",
    "journal_mode": "WAL",
    "synchronous": "NORMAL",
    "busy_timeout": 30000,
    "cache_size": 10000,
    "temp_store": "MEMORY"
}
```

### 索引优化
```sql
CREATE INDEX idx_users_username ON users(user_name);
CREATE INDEX idx_users_token ON users(token);
CREATE INDEX idx_users_created_at ON users(created_at);
```
