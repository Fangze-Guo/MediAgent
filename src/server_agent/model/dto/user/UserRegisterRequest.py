from pydantic import BaseModel


class UserRegisterRequest(BaseModel):
    user_name: str
    password: str
