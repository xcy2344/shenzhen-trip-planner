"""
Redis 滑动窗口限流器
用 ZSET + Lua 脚本保证原子性
"""
import time
from app.core.redis_client import redis_client
from app.core.logging import logger


LUA_SLIDING_WINDOW = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

local count = redis.call('ZCARD', key)

if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = math.ceil(oldest[2] + window - now)
    return {0, retry_after}
end

redis.call('ZADD', key, now, now .. '-' .. math.random(1000000))
redis.call('EXPIRE', key, window)

return {1, limit - count - 1}
"""


class RedisRateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60, name: str = "default"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self._script = None
        
        if redis_client:
            try:
                self._script = redis_client.register_script(LUA_SLIDING_WINDOW)
            except Exception as e:
                logger.warning(f"限流脚本注册失败：{e}")
    
    def allow(self, key: str) -> tuple:
        """返回 (allowed, remaining, retry_after)"""
        if not self._script:
            return True, 999, 0
        
        now = time.time()
        full_key = f"rate_limit:{self.name}:{key}"
        
        try:
            result = self._script(
                keys=[full_key],
                args=[self.max_requests, self.window_seconds, now]
            )
            allowed = result[0] == 1
            if allowed:
                return True, int(result[1]), 0
            else:
                return False, 0, int(result[1])
        except Exception as e:
            logger.warning(f"限流检查失败：{e}，降级放行")
            return True, 999, 0
    
    def reset(self, key: str):
        if not redis_client:
            return
        try:
            redis_client.delete(f"rate_limit:{self.name}:{key}")
        except Exception:
            pass


# 每 IP 每分钟 10 次
ip_limiter = RedisRateLimiter(max_requests=10, window_seconds=60, name="ip")

# 每会话每分钟 5 次
session_limiter = RedisRateLimiter(max_requests=5, window_seconds=60, name="session")