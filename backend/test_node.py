from app.graph.state import TripState
from app.graph.nodes import (
    parse_intent, parse_request,
    search_attractions, search_restaurants, search_hotels,
    generate_plan
)

state: TripState = {
    "user_input": "帮我规划深圳3日游，从北京出发，2个人，预算3000，喜欢美食和摄影",
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

print("=== 开始规划 ===")

state.update(parse_intent(state))
print("意图：", state["intent"])

state.update(parse_request(state))
print("参数：", state["request"])

state.update(search_attractions(state))
state.update(search_restaurants(state))
state.update(search_hotels(state))
print(f"景点：{len(state['attractions'])} 个")
print(f"餐厅：{len(state['restaurants'])} 个")
print(f"酒店：{len(state['hotels'])} 个")

state.update(generate_plan(state))
print(f"\n=== 行程（{len(state['plan'])} 天）===")


def get_name(item):
    """兼容字符串和字典两种格式"""
    if isinstance(item, dict):
        return item.get("name", "")
    return str(item)


for day in state["plan"]:
    print(f"\nDay {day.get('day')}：{day.get('theme')}")
    attractions = day.get('attractions', [])
    restaurants = day.get('restaurants', [])
    hotel = day.get('hotel', {})
    print(f"  景点：{', '.join([get_name(a) for a in attractions])}")
    print(f"  餐厅：{', '.join([get_name(r) for r in restaurants])}")
    if isinstance(hotel, dict):
        print(f"  住宿：{hotel.get('name', '无')}")
    else:
        print(f"  住宿：{hotel}")
    print(f"  花费：{day.get('estimated_cost', 0)} 元")