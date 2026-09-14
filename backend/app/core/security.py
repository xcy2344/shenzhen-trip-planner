"""
JWT 鉴权工具
"""
import datetime as dt

import jwt

from app.core.config import config
from app.core.logging import logger


ALGORITHM = config.JWT_ALGORITHM


def create_access_token(user_id: str) -> str:
    """生成访问 token，有效期 24 小时"""
    if not config.JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY 未配置，请在 .env 中设置")
    
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + dt.timedelta(hours=config.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str | None:
    """校验 token，成功返回 user_id，失败（无效/过期/签名错误）返回 None"""
    if not token or not config.JWT_SECRET_KEY:
        return None
    
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as e:
        logger.warning(f"JWT 校验失败：{e}")
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    return str(user_id)
