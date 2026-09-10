from app.core.redis_rate_limiter import session_limiter

print("=== 测试 session 限流（限制 5 次/分钟）===\n")

for i in range(8):
    allowed, remaining, retry_after = session_limiter.allow("test_user_001")
    if allowed:
        print(f"第{i+1}次：✅ 通过，剩余 {remaining} 次")
    else:
        print(f"第{i+1}次：❌ 被限流，需等 {retry_after} 秒")