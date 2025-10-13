from pydantic import BaseModel


class UserInfo(BaseModel):
    uid: int
    user_name: str
    password: str
    token: str
    role: str = 'user'  # 用户角色：user, admin
