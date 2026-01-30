from datetime import datetime, timedelta
from typing import Any, Optional, TYPE_CHECKING

# 延迟导入 jose，避免在不需要 JWT 功能的模块中触发导入错误
# 这样 schema_agent 等模块导入 crud 时不会因为 jose 缺失而失败
if TYPE_CHECKING:
    from jose import jwt, JWTError

from app.core.config import settings

# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return _pwd_context.hash(password)


def create_access_token(
    subject: Any, 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token.
    
    Args:
        subject: The subject to encode (typically user id)
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    from jose import jwt  # 延迟导入，仅在需要时加载
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[str]:
    """
    Verify JWT token and extract subject.
    
    Args:
        token: JWT token string
        
    Returns:
        Subject (user id) if valid, None otherwise
    """
    from jose import jwt, JWTError  # 延迟导入，仅在需要时加载
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        subject: str = payload.get("sub")
        if subject is None:
            return None
        return subject
    except JWTError:
        return None
