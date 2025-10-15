"""
用户信息更新请求模型
"""
from pydantic import BaseModel, Field
from typing import Optional


class UpdateUserProfileRequest(BaseModel):
    """用户信息更新请求"""
    
    user_name: str = Field(..., min_length=2, max_length=20, description="用户名")
    avatar: Optional[str] = Field(None, description="用户头像（Base64格式）")
