import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """用户名即为邮箱地址。"""

    username: str = Field(..., description="登录用户名（邮箱）")
    password: str = Field(..., min_length=1, description="密码")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="有效期（秒），自签发时起算")


class RegisterRequest(BaseModel):
    """注册：用户名即为邮箱。"""

    username: EmailStr = Field(..., description="用户名（邮箱）")
    password: str = Field(..., description="密码（长度等规则后续再加）")


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="当前密码")
    new_password: str = Field(..., min_length=6, max_length=256, description="新密码（至少 6 位）")


class MessageResponse(BaseModel):
    message: str
