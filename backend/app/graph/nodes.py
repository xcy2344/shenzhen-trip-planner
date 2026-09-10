import json
from app.core.llm import chat, set_context
from app.graph.state import TripState
from app.core.session import session_store
from app.tools.attractions import search_shenzhen_attractions
from app.tools.food import recommend_shenzhen_food


def safe_number(value, default=0):
    """安全转数字"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            cleaned = value.replace("¥", "").replace("元", "").replace(",", "").strip()
            cleaned = cleaned.split("/")[0].strip()
            if "-" in cleaned:
                cleaned = cleaned.split("-")[0].strip()
            cleaned = "".join(c for c in cleaned if c.isdigit() or c == ".")
            return float(cleaned) if cleaned else default
        except (ValueError, AttributeError):
            return default
    return default


def load_session(state: TripState) -> dict:
    """从会话存储加载历史"""
    session_id = state.get("session_id", "")
    if not session_id:
        return {}
    
    session = session_store.get(session_id)
    if not session:
        return {}
    
    return {
        "prev_plan": session.get("current_plan", []),
        "version": session.get("version", 0),
        "request": session.get("current_request", {}) or state.get("request", {}),
    }


def parse_intent(state: TripState) -> dict:
    """解析用户意图"""
    set_context(state.get("session_id", ""), "parse_intent")
    
    user_input = state["user_input"]
    has_prev = len(state.get("prev_plan", [])) > 0
    
    prompt = f"""你是一个意图识别助手。
判断用户输入属于：plan（规划新行程）、modify（修改已有行程）、chat（闲聊）。

当前有历史行程：{'是' if has_prev else '否'}

用户输入：{user_input}

只返回一个单词。"""
    
    intent = chat(prompt, purpose="parse_intent").strip().lower()
    if intent not in ["plan", "modify", "chat"]:
        if any(k in user_input for k in ["规划", "行程", "旅游"]):
            intent = "plan"
        elif any(k in user_input for k in ["改", "调整", "换", "轻松", "加点"]):
            intent = "modify"
        else:
            intent = "chat"
    
    if intent == "modify" and not has_prev:
        intent = "plan"
    
    return {"intent": intent}


def parse_request(state: TripState) -> dict:
    """解析用户请求参数"""
    set_context(state.get("session_id", ""), "parse_request")
    
    user_input = state["user_input"]
    prompt = f"""提取旅游参数，返回 JSON：
- departure: 出发地
- days: 天数（整数）
- people: 人数（整数）
- budget: 预算（数字）
- transport: 交通方式
- interests: 兴趣标签（数组）
- preferences: 额外偏好

用户输入：{user_input}

只返回 JSON。"""
    result = chat(prompt, purpose="parse_request").strip()
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
    result = result.strip()
    try:
        request_data = json.loads(result)
    except json.JSONDecodeError:
        request_data = {}
    request_data.setdefault("departure", "")
    request_data.setdefault("days", 0)
    request_data.setdefault("people", 0)
    request_data.setdefault("budget", 0)
    request_data.setdefault("transport", "")
    request_data.setdefault("interests", [])
    request_data.setdefault("preferences", "")
    
    request_data["days"] = int(safe_number(request_data["days"], 0))
    request_data["people"] = int(safe_number(request_data["people"], 0))
    request_data["budget"] = safe_number(request_data["budget"], 0)
    
    return {"request": request_data}


def parse_modification(state: TripState) -> dict:
    """解析修改意图"""
    set_context(state.get("session_id", ""), "parse_modification")
    
    user_input = state["user_input"]
    prev_plan = state.get("prev_plan", [])
    
    if not prev_plan:
        return {
            "modify_target": {},
            "errors": ["没有找到之前的行程，无法修改。请先规划一次行程。"]
        }
    
    plan_summary = []
    for day in prev_plan:
        if isinstance(day, dict):
            attractions = day.get("attractions", [])
            names = []
            for a in attractions:
                if isinstance(a, dict):
                    names.append(a.get("name", ""))
                else:
                    names.append(str(a))
            plan_summary.append({
                "day": day.get("day"),
                "theme": day.get("theme"),
                "attractions": names,
                "cost": day.get("estimated_cost")
            })
    
    prompt = f"""你是一个行程修改意图解析助手。

当前行程：
{json.dumps(plan_summary, ensure_ascii=False, indent=2)}

用户输入：{user_input}

请判断：
1. 要改哪一天？（没指定返回 "all"，指定了返回数字）
2. 用户想怎么改？（简短概括）
3. 修改类型：
   - reduce_intensity：减少行程，轻松一些
   - add_attraction：增加景点
   - add_food：增加美食
   - change_hotel：换酒店
   - change_budget：调整预算
   - other：其他

返回 JSON：
{{"day": 1 或 "all", "change": "...", "change_type": "..."}}

只返回 JSON。"""

    result = chat(prompt, purpose="parse_modification").strip()
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
    result = result.strip()
    
    try:
        modify_target = json.loads(result)
    except json.JSONDecodeError:
        modify_target = {
            "day": "all",
            "change": user_input,
            "change_type": "other"
        }
    
    modify_target.setdefault("day", "all")
    modify_target.setdefault("change", user_input)
    modify_target.setdefault("change_type", "other")
    
    return {"modify_target": modify_target}


def search_attractions(state: TripState) -> dict:
    """检索深圳景点（保留备用）"""
    set_context(state.get("session_id", ""), "search_attractions")
    
    request = state.get("request", {})
    interests = request.get("interests", [])
    base_result = search_shenzhen_attractions()
    prompt = f"""根据景点资料和用户兴趣，推荐景点。

资料：{base_result}
兴趣：{interests}

返回 JSON 数组，每个景点含：
name, location, duration, ticket, open_time, score, description

只返回 JSON 数组，至少 8 个景点。"""
    result = chat(prompt, purpose="search_attractions").strip()
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
    result = result.strip()
    try:
        attractions = json.loads(result)
    except json.JSONDecodeError:
        attractions = []
    return {"attractions": attractions}


def search_restaurants(state: TripState) -> dict:
    """检索深圳餐饮（保留备用）"""
    set_context(state.get("session_id", ""), "search_restaurants")
    
    request = state.get("request", {})
    interests = request.get("interests", [])
    base_result = recommend_shenzhen_food()
    prompt = f"""根据美食资料和用户兴趣，推荐餐厅。

资料：{base_result}
兴趣：{interests}

返回 JSON 数组，每个餐厅含：
name, location, avg_price, cuisine, score

只返回 JSON 数组，至少 8 个餐厅，覆盖不同价位。"""
    result = chat(prompt, purpose="search_restaurants").strip()
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
    result = result.strip()
    try:
        restaurants = json.loads(result)
    except json.JSONDecodeError:
        restaurants = []
    return {"restaurants": restaurants}


def search_hotels(state: TripState) -> dict:
    """检索深圳酒店"""
    set_context(state.get("session_id", ""), "search_hotels")
    
    request = state.get("request", {})
    budget = request.get("budget", 0) or 3000
    people = request.get("people", 0) or 2
    prompt = f"""推荐深圳酒店，预算：{budget} 元，人数：{people}。

返回 JSON 数组，每个酒店含：
name, location, price, score, distance

要求：
- 至少 8 个酒店
- 覆盖 50 元到 800 元各个价位
- 包含青旅、快捷、中档、高档

只返回 JSON 数组。"""
    result = chat(prompt, purpose="search_hotels").strip()
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
    result = result.strip()
    try:
        hotels = json.loads(result)
        if isinstance(hotels, dict):
            hotels = hotels.get("hotels", []) or list(hotels.values())[0]
    except (json.JSONDecodeError, IndexError):
        hotels = []
    if not hotels:
        hotels = [
            {"name": "漫心公寓青旅", "location": "罗湖区", "price": 68, "score": 4.3, "distance": "近东门老街"},
            {"name": "7天连锁", "location": "罗湖区", "price": 180, "score": 4.0, "distance": "近地铁"},
            {"name": "全季酒店", "location": "福田区", "price": 350, "score": 4.3, "distance": "近地铁"},
            {"name": "深圳湾万怡", "location": "南山区", "price": 500, "score": 4.5, "distance": "近深圳湾"},
            {"name": "香格里拉", "location": "罗湖区", "price": 800, "score": 4.7, "distance": "市中心"}
        ]
    return {"hotels": hotels}


def rag_retrieve(state: TripState) -> dict:
    """RAG 检索：从知识库检索景点/美食"""
    set_context(state.get("session_id", ""), "rag_retrieve")
    
    from app.rag.retriever import hybrid_search, format_context
    
    request = state.get("request", {})
    interests = request.get("interests", [])
    days = request.get("days", 0) or 3
    people = request.get("people", 0) or 1
    budget = safe_number(request.get("budget", 0), 0)
    
    base_queries = [
        "深圳必去景点推荐",
        "深圳特色美食",
    ]
    for interest in interests:
        base_queries.append(f"深圳{interest}")
    
    top_k = max(5, days * 2)
    
    attraction_results = []
    restaurant_results = []
    photo_results = []
    transport_results = []
    
    for q in base_queries:
        results = hybrid_search(q, top_k=top_k)
        for r in results:
            meta = r.get("metadata", {})
            t = meta.get("type", "")
            if t == "景点" and r not in attraction_results:
                attraction_results.append(r)
            elif t == "美食" and r not in restaurant_results:
                restaurant_results.append(r)
            elif t == "拍照点" and r not in photo_results:
                photo_results.append(r)
            elif t == "交通" and r not in transport_results:
                transport_results.append(r)
    
    prompt = f"""你是深圳旅游专家。基于以下真实资料，整理出适合用户需求的景点和餐厅。

用户需求：
- 天数：{days}
- 人数：{people}
- 预算：{budget} 元
- 兴趣：{interests}

【景点资料】
{format_context(attraction_results[:15])}

【美食资料】
{format_context(restaurant_results[:15])}

请返回 JSON：
{{
  "attractions": [
    {{"name": "", "location": "", "duration": 2, "ticket": 0, "open_time": "", "score": 4.5, "description": ""}}
  ],
  "restaurants": [
    {{"name": "", "location": "", "avg_price": 50, "cuisine": "", "score": 4.5}}
  ]
}}

要求：
1. 景点推荐 8 个，餐厅推荐 8 个
2. 必须严格使用资料中的真实信息，不要编造
3. 只返回 JSON，不要其他内容"""

    result = chat(prompt, purpose="rag_retrieve").strip()
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
    result = result.strip()
    
    try:
        data = json.loads(result)
        attractions = data.get("attractions", [])
        restaurants = data.get("restaurants", [])
    except json.JSONDecodeError:
        attractions = []
        restaurants = []
    
    return {
        "attractions": attractions,
        "restaurants": restaurants,
        "route_info": {
            **state.get("route_info", {}),
            "rag_attraction_count": len(attraction_results),
            "rag_restaurant_count": len(restaurant_results),
        }
    }


def enrich_coordinates(state: TripState) -> dict:
    """给景点和餐厅补充经纬度"""
    from app.tools.map_tool import enrich_attractions_with_coords
    
    attractions = state.get("attractions", [])
    restaurants = state.get("restaurants", [])
    
    enriched_attractions = enrich_attractions_with_coords(attractions)
    enriched_restaurants = enrich_attractions_with_coords(restaurants)
    
    return {
        "attractions": enriched_attractions,
        "restaurants": enriched_restaurants,
    }


def allocate_budget(state: TripState) -> dict:
    """用代码算预算约束"""
    request = state.get("request", {})
    days = request.get("days", 0) or 3
    people = request.get("people", 0) or 2
    budget = safe_number(request.get("budget", 0), 3000) or 3000
    hotels = state.get("hotels", [])
    
    hotel_total = budget * 0.4
    food_total = budget * 0.4
    other_total = budget * 0.2
    
    hotel_per_night = hotel_total / days
    food_per_day = food_total / days
    other_per_day = other_total / days
    daily_budget = budget / days
    
    affordable_hotels = []
    for h in hotels:
        if isinstance(h, dict):
            price = safe_number(h.get("price"), 999999)
            if price <= hotel_per_night:
                h["price"] = price
                affordable_hotels.append(h)
    
    if not affordable_hotels:
        valid = [h for h in hotels if isinstance(h, dict)]
        valid.sort(key=lambda x: safe_number(x.get("price"), 999999))
        affordable_hotels = valid[:3]
    
    return {
        "route_info": {
            "daily_budget": round(daily_budget, 2),
            "hotel_per_night": round(hotel_per_night, 2),
            "food_per_day": round(food_per_day, 2),
            "other_per_day": round(other_per_day, 2),
            "affordable_hotels": affordable_hotels,
        }
    }


def generate_plan(state: TripState) -> dict:
    """生成行程"""
    set_context(state.get("session_id", ""), "generate_plan")
    
    request = state.get("request", {})
    attractions = state.get("attractions", [])
    restaurants = state.get("restaurants", [])
    route_info = state.get("route_info", {})
    affordable_hotels = route_info.get("affordable_hotels", [])
    
    days = request.get("days", 0) or 3
    people = request.get("people", 0) or 2
    budget = safe_number(request.get("budget", 0), 3000) or 3000
    interests = request.get("interests", [])
    
    daily_budget = route_info.get("daily_budget", budget / days)
    hotel_per_night = route_info.get("hotel_per_night", 300)
    food_per_day = route_info.get("food_per_day", 100)
    
    retry_count = state.get("retry_count", 0)
    errors = state.get("errors", [])
    
    error_hint = ""
    if errors:
        error_hint = "\n\n⚠️【上次错误，必须修正】\n" + "\n".join([f"- {e}" for e in errors])
    
    prompt = f"""你是深圳旅游规划专家。生成 {days} 天行程。

用户需求：
- 天数：{days} 天
- 人数：{people} 人
- 总预算：{budget} 元
- 兴趣：{interests}{error_hint}

⭐【硬约束】
- 每天 estimated_cost ≤ {daily_budget} 元
- {days} 天总和 ≤ {budget} 元
- 每晚住宿 ≤ {hotel_per_night} 元
- 每天餐饮 ≤ {food_per_day} 元

【可选景点】
{json.dumps(attractions, ensure_ascii=False, indent=2)}

【可选餐厅】
{json.dumps(restaurants, ensure_ascii=False, indent=2)}

【可选酒店】
{json.dumps(affordable_hotels, ensure_ascii=False, indent=2)}

返回 JSON 数组，每天含：
- day, theme
- attractions（2-3个）
- restaurants（1-2个）
- hotel（1个）
- transport
- total_duration（小时）
- estimated_cost（数字）

要求：
1. 每天景点不重复
2. 每天 estimated_cost = 酒店价 + 餐厅人均×{people} + 门票
3. 总和 ≤ {budget} 元
4. 只返回 JSON 数组"""

    result = chat(prompt, purpose="generate_plan").strip()
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
    result = result.strip()
    try:
        plan = json.loads(result)
    except json.JSONDecodeError:
        plan = []
    return {"plan": plan, "retry_count": retry_count + 1}


def modify_plan(state: TripState) -> dict:
    """局部重规划：只改需要改的那一天"""
    set_context(state.get("session_id", ""), "modify_plan")
    
    prev_plan = state.get("prev_plan", [])
    modify_target = state.get("modify_target", {})
    request = state.get("request", {})
    attractions = state.get("attractions", [])
    restaurants = state.get("restaurants", [])
    route_info = state.get("route_info", {})
    affordable_hotels = route_info.get("affordable_hotels", [])
    retry_count = state.get("retry_count", 0)
    
    if not prev_plan:
        return {"errors": ["没有可修改的行程"], "retry_count": retry_count + 1}
    
    target_day = modify_target.get("day", "all")
    change = modify_target.get("change", "")
    change_type = modify_target.get("change_type", "other")
    
    if target_day == "all" or target_day not in [d.get("day") for d in prev_plan if isinstance(d, dict)]:
        return generate_plan(state)
    
    target_day = int(safe_number(target_day, 1))
    people = int(safe_number(request.get("people", 0), 2)) or 2
    
    old_day = None
    for day in prev_plan:
        if isinstance(day, dict) and day.get("day") == target_day:
            old_day = day
            break
    
    prompt = f"""用户想修改 Day {target_day} 的行程。
修改需求：{change}
修改类型：{change_type}

当前 Day {target_day}：
{json.dumps(old_day, ensure_ascii=False, indent=2)}

【可选景点】
{json.dumps(attractions, ensure_ascii=False, indent=2)}

【可选餐厅】
{json.dumps(restaurants, ensure_ascii=False, indent=2)}

【可选酒店】
{json.dumps(affordable_hotels, ensure_ascii=False, indent=2)}

请生成修改后的 Day {target_day}，只返回这一天的 JSON 对象：
- day, theme
- attractions（2-3个）
- restaurants（1-2个）
- hotel（1个）
- transport
- total_duration
- estimated_cost

修改类型说明：
- reduce_intensity：减少景点到 1-2 个，降低时长
- add_attraction：增加 1 个景点
- add_food：增加餐厅
- change_hotel：换酒店
- change_budget：减少花费

只返回这一天的 JSON 对象，不要数组。"""

    result = chat(prompt, purpose="modify_plan").strip()
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
    result = result.strip()
    
    try:
        new_day = json.loads(result)
    except json.JSONDecodeError:
        return {"errors": [f"Day {target_day} 修改失败"], "retry_count": retry_count + 1}
    
    new_plan = []
    for day in prev_plan:
        if isinstance(day, dict) and day.get("day") == target_day:
            new_plan.append(new_day)
        else:
            new_plan.append(day)
    
    return {"plan": new_plan, "retry_count": retry_count + 1}


def validate_plan(state: TripState) -> dict:
    """校验：用代码算钱"""
    plan = state.get("plan", [])
    request = state.get("request", {})
    
    if not plan:
        return {"errors": ["行程为空"]}
    
    budget = safe_number(request.get("budget", 0), 99999) or 99999
    people = int(safe_number(request.get("people", 0), 2)) or 2
    errors = []
    
    total_cost = 0
    for day in plan:
        if not isinstance(day, dict):
            continue
        
        cost = 0
        hotel = day.get("hotel", {})
        if isinstance(hotel, dict):
            cost += safe_number(hotel.get("price"), 0)
        for r in day.get("restaurants", []):
            if isinstance(r, dict):
                cost += safe_number(r.get("avg_price"), 0) * people
        for a in day.get("attractions", []):
            if isinstance(a, dict):
                cost += safe_number(a.get("ticket"), 0)
        cost += 10
        
        day["estimated_cost"] = round(cost, 2)
        total_cost += cost
    
    if total_cost > budget:
        errors.append(f"代码计算总花费 {round(total_cost, 2)} 元超过预算 {budget} 元")
    
    for day in plan:
        if isinstance(day, dict):
            duration = safe_number(day.get("total_duration"), 0)
            if duration > 14:
                errors.append(f"Day {day.get('day')} 时长 {duration} 小时过长")
    
    all_names = []
    for day in plan:
        if isinstance(day, dict):
            for a in day.get("attractions", []):
                if isinstance(a, dict):
                    all_names.append(a.get("name", ""))
                else:
                    all_names.append(str(a))
    if len(all_names) != len(set(all_names)):
        errors.append("不同天数出现重复景点")
    
    return {
        "plan": plan,
        "errors": errors,
        "route_info": {
            **state.get("route_info", {}),
            "total_cost": round(total_cost, 2),
            "is_valid": len(errors) == 0,
        }
    }


def optimize_route(state: TripState) -> dict:
    """路线优化：每天内部景点就近排序 + 开放时间校验"""
    from app.tools.map_tool import optimize_route_order
    
    plan = state.get("plan", [])
    if not plan:
        return {}
    
    warnings = []
    
    for day in plan:
        if not isinstance(day, dict):
            continue
        
        attractions = day.get("attractions", [])
        if len(attractions) <= 1:
            continue
        
        valid = [a for a in attractions if isinstance(a, dict) and a.get("coord")]
        if len(valid) >= 2:
            ordered = optimize_route_order(valid)
            others = [a for a in attractions if not (isinstance(a, dict) and a.get("coord"))]
            day["attractions"] = ordered + others
        
        for a in day.get("attractions", []):
            if not isinstance(a, dict):
                continue
            open_time = a.get("open_time", "")
            if "周一闭馆" in open_time:
                warnings.append(
                    f"Day {day.get('day')} 的「{a.get('name')}」{open_time}，请确认出行日期"
                )
    
    existing_errors = state.get("errors", [])
    new_errors = existing_errors + warnings
    
    return {
        "plan": plan,
        "errors": new_errors,
    }


def auto_fix_plan(state: TripState) -> dict:
    """兜底：重试多次还超预算，代码强制换便宜的"""
    plan = state.get("plan", [])
    request = state.get("request", {})
    hotels = state.get("hotels", [])
    
    people = int(safe_number(request.get("people", 0), 2)) or 2
    
    valid_hotels = [h for h in hotels if isinstance(h, dict) and h.get("price") is not None]
    if valid_hotels:
        cheapest_hotel = min(valid_hotels, key=lambda x: safe_number(x.get("price"), 999999))
    else:
        cheapest_hotel = {"name": "青旅床位", "location": "罗湖区", "price": 68, "score": 4.0, "distance": "近地铁"}
    
    total = 0
    for day in plan:
        if not isinstance(day, dict):
            continue
        
        day["hotel"] = cheapest_hotel
        cost = safe_number(cheapest_hotel.get("price"), 68)
        
        restaurants = [r for r in day.get("restaurants", []) if isinstance(r, dict)]
        if restaurants:
            cheapest_r = min(restaurants, key=lambda x: safe_number(x.get("avg_price"), 999999))
            day["restaurants"] = [cheapest_r]
            cost += safe_number(cheapest_r.get("avg_price"), 30) * people
        else:
            cost += 30 * people
        
        for a in day.get("attractions", []):
            if isinstance(a, dict):
                cost += safe_number(a.get("ticket"), 0)
        
        cost += 10
        day["estimated_cost"] = round(cost, 2)
        total += cost
    
    return {
        "plan": plan,
        "errors": [],
        "route_info": {
            **state.get("route_info", {}),
            "total_cost": round(total, 2),
            "is_valid": True,
            "auto_fixed": True,
        }
    }


def generate_answer(state: TripState) -> dict:
    """生成最终回答"""
    set_context(state.get("session_id", ""), "generate_answer")
    
    plan = state.get("plan", [])
    request = state.get("request", {})
    route_info = state.get("route_info", {})
    errors = state.get("errors", [])
    intent = state.get("intent", "plan")
    
    if not plan:
        return {"final_answer": "抱歉，行程生成失败，请重试。"}
    
    total_cost = route_info.get("total_cost", 0)
    budget = safe_number(request.get("budget", 0), 0)
    auto_fixed = route_info.get("auto_fixed", False)
    
    fix_note = ""
    if auto_fixed:
        fix_note = "\n【提示】为了控制预算，已自动选择更省钱的住宿和餐饮。"
    
    error_note = ""
    if errors:
        error_note = "\n\n⚠️【需要说明的问题】\n" + "\n".join([f"- {e}" for e in errors])
    
    prompt = f"""你是深圳旅游助手。请把行程数据转成友好的自然语言回答。

⚠️【重要】
- 所有数字必须严格使用下方提供的数据
- 禁止自己编造新的金额
- 总花费必须写：{total_cost} 元

用户需求：
- 天数：{request.get('days')} 天
- 人数：{request.get('people')} 人  
- 预算：{budget} 元

行程数据：
{json.dumps(plan, ensure_ascii=False, indent=2)}

总花费（必须用这个数字）：{total_cost} 元{fix_note}{error_note}

要求：
1. 友好语气
2. 按 Day 1、Day 2 格式
3. 每天写清楚：主题、景点、餐厅、住宿、当天花费
4. 最后总结：总花费 = {total_cost} 元，预算 {budget} 元
5. 如果有问题，友好地说明
6. 不要返回 JSON，直接自然语言"""

    answer = chat(prompt, purpose="generate_answer").strip()
    return {"final_answer": answer}