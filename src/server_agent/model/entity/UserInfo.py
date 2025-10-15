from pydantic import BaseModel
from typing import Optional


class UserInfo(BaseModel):
    uid: int
    user_name: str
    password: str
    token: str
    role: str = 'user'  # 用户角色：user, admin
    avatar: Optional[str] = None  # 用户头像（Base64格式）
