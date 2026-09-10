"""
Redis 客户端
"""
import redis
from app.core.logging import logger


def create_client():
    """创建 Redis 连接"""
    try:
        client = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        client.ping()
        logger.info("✅ Redis 连接成功")
        return client
    except Exception as e:
        logger.warning(f"❌ Redis 连接失败：{e}，限流将降级为放行模式")
        return None


redis_client = create_client()