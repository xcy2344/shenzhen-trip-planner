from app.graph.nodes import parse_modification

# 模拟一个已有行程
prev_plan = [
    {
        "day": 1,
        "theme": "城市经典游",
        "attractions": [
            {"name": "世界之窗"},
            {"name": "欢乐谷"},
            {"name": "深圳湾公园"}
        ],
        "estimated_cost": 800
    },
    {
        "day": 2,
        "theme": "自然风光游",
        "attractions": [
            {"name": "梧桐山"},
            {"name": "大梅沙"}
        ],
        "estimated_cost": 500
    }
]

# 测试3种修改意图
test_cases = [
    "第一天太累了，轻松一些",
    "加点美食推荐",
    "全部重新安排一下"
]

for user_input in test_cases:
    state = {
        "user_input": user_input,
        "prev_plan": prev_plan,
        "modify_target": {}
    }
    result = parse_modification(state)
    print(f"用户：{user_input}")
    print(f"  → {result['modify_target']}")
    print()