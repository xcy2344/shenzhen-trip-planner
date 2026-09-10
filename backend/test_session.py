from app.core.session import session_store

# 存
session_store.append_message("user_001", "user", "帮我规划深圳3日游")
session_store.append_message("user_001", "assistant", "好的，我来帮你规划")
session_store.update("user_001", current_plan=[{"day": 1, "theme": "测试"}], version=1)

# 取
print("对话历史：", session_store.get_messages("user_001"))
print("当前行程：", session_store.get_plan("user_001"))
print("版本号：", session_store.get_version("user_001"))