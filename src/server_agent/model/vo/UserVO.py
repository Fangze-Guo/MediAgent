from pydantic import BaseModel


class UserVO(BaseModel):
    uid: int
    user_name: str
    token: str
