from app.graph.builder import app_graph

initial_state = {
    "user_input": "帮我规划深圳3日游，从北京出发，2个人，预算3000，喜欢美食",
    "request": {},
    "intent": "",
    "attractions": [],
    "restaurants": [],
    "hotels": [],
    "weather": "",
    "route_info": {},
    "plan": [],
    "final_answer": "",
    "version": 0,
    "errors": [],
    "messages": []
}

print("=== LangGraph 开始运行 ===\n")

result = app_graph.invoke(initial_state)

print("=" * 60)
print("📝 最终回答：")
print("=" * 60)
print(result["final_answer"])