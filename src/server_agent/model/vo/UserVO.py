from pydantic import BaseModel


class UserVO(BaseModel):
    uid: int
    user_name: str
    token: str
    role: str = 'user'  # 用户角色：user, admin
