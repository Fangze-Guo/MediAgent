from pydantic import BaseModel


class UserInfo(BaseModel):
    uid: int
    user_name: str
    password: str
    token: str
