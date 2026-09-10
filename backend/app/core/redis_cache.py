"""
Redis 缓存模块
用于缓存 AI 生成结果，避免重复调用
"""
import json
import hashlib
from typing import Optional, Any
from app.core.redis_client import redis_client
from app.core.logging import logger


class RedisCache:
    """Redis 缓存"""
    
    def __init__(self, prefix: str = "cache", default_ttl: int = 86400):
        """
        prefix: key 前缀
        default_ttl: 默认过期时间（秒），86400 = 24小时
        """
        self.prefix = prefix
        self.default_ttl = default_ttl
    
    def _make_key(self, raw: str) -> str:
        """生成缓存 key"""
        h = hashlib.md5(raw.encode("utf-8")).hexdigest()
        return f"{self.prefix}:{h}"
    
    def get(self, raw_key: str) -> Optional[Any]:
        """读取缓存"""
        if not redis_client:
            return None
        try:
            key = self._make_key(raw_key)
            data = redis_client.get(key)
            if data:
                logger.info(f"✅ 缓存命中：{raw_key[:50]}")
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"缓存读取失败：{e}")
            return None
    
    def set(self, raw_key: str, value: Any, ttl: Optional[int] = None):
        """写入缓存"""
        if not redis_client:
            return
        try:
            key = self._make_key(raw_key)
            redis_client.setex(
                key,
                ttl or self.default_ttl,
                json.dumps(value, ensure_ascii=False)
            )
            logger.info(f"💾 缓存写入：{raw_key[:50]}")
        except Exception as e:
            logger.warning(f"缓存写入失败：{e}")
    
    def delete(self, raw_key: str):
        """删除缓存"""
        if not redis_client:
            return
        try:
            key = self._make_key(raw_key)
            redis_client.delete(key)
        except Exception as e:
            logger.warning(f"缓存删除失败：{e}")
    
    def clear_all(self):
        """清空所有缓存"""
        if not redis_client:
            return
        try:
            keys = redis_client.keys(f"{self.prefix}:*")
            if keys:
                redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"缓存清理失败：{e}")


# 行程规划缓存（TTL 24 小时）
plan_cache = RedisCache(prefix="plan", default_ttl=86400)