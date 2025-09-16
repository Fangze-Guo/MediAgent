# src/server_new/mediagent/controller/user_controller.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# 调用你写的注册逻辑（异步 aiosqlite 版）
from ..modules.register import register_user
from ..modules.login import login_user

router = APIRouter(prefix="/user", tags=["user"])

class RegisterIn(BaseModel):
    user_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)

class RegisterOut(BaseModel):
    uid: int
    message: str = "registered successfully"

@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn):
    """
    POST /user/register
    body: { "user_name": "...", "password": "..." }
    """
    res = await register_user(payload.user_name, payload.password)

    if not res["ok"]:
        if res["code"] == "USERNAME_EXISTS":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")
        if res["code"] == "INVALID_INPUT":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid input")
        # 其他错误
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="unknown error")

    return {"uid": res["uid"], "message": "registered successfully"}


class LoginIn(BaseModel):
    user_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)

class LoginOut(BaseModel):
    token: str
    message: str = "login successful"

@router.post("/login", response_model=LoginOut)
async def login(payload: LoginIn):
    res = await login_user(payload.user_name, payload.password)

    if not res["ok"]:
        if res["code"] == "USERNAME_NOT_FOUND":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="username not found")
        if res["code"] == "BAD_PASSWORD":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="incorrect password")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="unknown error")

    return {"token": res["token"], "message": "login successful"}