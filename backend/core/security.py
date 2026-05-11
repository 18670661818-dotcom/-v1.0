"""
安全模块
JWT认证、密码加密等安全相关功能
"""
from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .config import settings

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 密码Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码

    Returns:
        bool: 密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    获取密码哈希

    Args:
        password: 明文密码

    Returns:
        str: 哈希后的密码
    """
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建访问令牌

    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量

    Returns:
        str: JWT令牌
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码访问令牌

    Args:
        token: JWT令牌

    Returns:
        Optional[dict]: 解码后的数据，失败返回None
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建刷新令牌

    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量

    Returns:
        str: JWT刷新令牌
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # 刷新令牌默认7天过期
        expire = datetime.utcnow() + timedelta(days=7)

    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    获取当前用户（依赖注入）

    Args:
        token: JWT令牌

    Returns:
        当前用户对象

    Raises:
        HTTPException: 认证失败
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 这里应该从数据库获取用户
    # from models.database import get_user_by_username
    # user = get_user_by_username(username)
    # if user is None:
    #     raise credentials_exception
    # return user

    return {"username": username}


async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
):
    """
    获取当前活跃用户

    Args:
        current_user: 当前用户

    Returns:
        当前活跃用户对象

    Raises:
        HTTPException: 用户已禁用
    """
    # if current_user.disabled:
    #     raise HTTPException(status_code=400, detail="用户已禁用")
    return current_user


def verify_token(token: str) -> bool:
    """
    验证令牌是否有效

    Args:
        token: JWT令牌

    Returns:
        bool: 令牌是否有效
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload is not None
    except JWTError:
        return False


def generate_api_key() -> str:
    """
    生成API密钥

    Returns:
        str: API密钥
    """
    import secrets
    return secrets.token_urlsafe(32)


class RateLimiter:
    """简单的速率限制器"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # ip -> list of timestamps

    def is_allowed(self, client_ip: str) -> bool:
        """
        检查请求是否被允许

        Args:
            client_ip: 客户端IP

        Returns:
            bool: 是否允许请求
        """
        import time
        current_time = time.time()

        if client_ip not in self.requests:
            self.requests[client_ip] = []

        # 清理过期的请求记录
        self.requests[client_ip] = [
            t for t in self.requests[client_ip]
            if current_time - t < self.window_seconds
        ]

        # 检查是否超过限制
        if len(self.requests[client_ip]) >= self.max_requests:
            return False

        # 记录本次请求
        self.requests[client_ip].append(current_time)
        return True


# 全局速率限制器实例
rate_limiter = RateLimiter()
