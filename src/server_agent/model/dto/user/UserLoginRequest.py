from pydantic import BaseModel


class UserLoginRequest(BaseModel):
    user_name: str
    password: str
