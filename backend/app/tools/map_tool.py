"""
高德地图工具
封装地理编码、距离计算、路线规划
"""
import requests
from app.core.config import config


AMAP_BASE_URL = "https://restapi.amap.com/v3"


def geocode(address: str, city: str = "深圳") -> dict:
    """地址 → 经纬度
    返回：{"location": "114.025,22.608", "formatted_address": "..."}
    失败返回：{}
    """
    if not config.AMAP_API_KEY or not address:
        return {}
    
    url = f"{AMAP_BASE_URL}/geocode/geo"
    params = {
        "key": config.AMAP_API_KEY,
        "address": address,
        "city": city,
        "citylimit": "true",
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
    except Exception:
        return {}
    
    if data.get("status") != "1":
        return {}
    
    geocodes = data.get("geocodes", [])
    if not geocodes:
        return {}
    
    item = geocodes[0]
    return {
        "location": item.get("location", ""),
        "formatted_address": item.get("formatted_address", ""),
        "city": item.get("city", ""),
        "district": item.get("district", ""),
    }


def get_distance_matrix(origins: list, destination: str = "深圳") -> list:
    """计算多个地点到目标地点的距离
    origins: [{"name": "深圳湾公园", "location": "114.0,22.5"}, ...]
    返回：[{"name": "...", "distance": 1234, "duration": 300}, ...]
    """
    if not config.AMAP_API_KEY or not origins:
        return []
    
    locations_str = "|".join([o["location"] for o in origins if o.get("location")])
    if not locations_str:
        return []
    
    url = f"{AMAP_BASE_URL}/distance"
    params = {
        "key": config.AMAP_API_KEY,
        "origins": locations_str,
        "destination": destination,
        "type": "1",
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
    except Exception:
        return []
    
    if data.get("status") != "1":
        return []
    
    results = data.get("results", [])
    output = []
    for i, r in enumerate(results):
        output.append({
            "name": origins[i].get("name", ""),
            "distance": int(r.get("distance", 0)),
            "duration": int(r.get("duration", 0)),
        })
    return output


def get_route_plan(waypoints: list, mode: str = "driving") -> dict:
    """路线规划
    waypoints: [{"name": "A", "location": "114.0,22.5"}, ...]
    mode: driving / walking / transit
    返回：{"distance": 总距离(米), "duration": 总耗时(秒), "steps": [...]}
    """
    if not config.AMAP_API_KEY or len(waypoints) < 2:
        return {}
    
    origin = waypoints[0]["location"]
    destination = waypoints[-1]["location"]
    middle = "|".join([w["location"] for w in waypoints[1:-1]]) if len(waypoints) > 2 else ""
    
    url = f"{AMAP_BASE_URL}/direction/{mode}"
    params = {
        "key": config.AMAP_API_KEY,
        "origin": origin,
        "destination": destination,
        "output": "json",
    }
    if middle:
        params["waypoints"] = middle
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
    except Exception:
        return {}
    
    if data.get("status") != "1":
        return {}
    
    route = data.get("route", {})
    paths = route.get("paths", [])
    if not paths:
        return {}
    
    path = paths[0]
    return {
        "distance": int(path.get("distance", 0)),
        "duration": int(path.get("duration", 0)),
        "tolls": int(path.get("tolls", 0)),
    }


def enrich_attractions_with_coords(attractions: list) -> list:
    """给景点列表补充经纬度
    策略：
    1. 先用「景点名」查（最准）
    2. 失败再用「详细地址」查
    """
    enriched = []
    for a in attractions:
        if not isinstance(a, dict):
            continue
        name = a.get("name", "")
        location_text = a.get("location", "")
        
        # 策略1：用名字查
        geo = {}
        if name:
            geo = geocode(name)
        
        # 策略2：名字失败，用详细地址查
        if not geo and location_text and len(location_text) > 4:
            geo = geocode(location_text)
        
        enriched.append({
            **a,
            "location": geo.get("formatted_address", location_text or name),
            "coord": geo.get("location", ""),
            "district": geo.get("district", ""),
        })
    return enriched


def optimize_route_order(attractions: list) -> list:
    """就近排序：用贪心算法
    从第一个景点开始，每次选最近的未访问景点
    """
    if len(attractions) <= 2:
        return attractions
    
    valid = [a for a in attractions if a.get("coord")]
    if len(valid) <= 1:
        return attractions
    
    def parse_coord(coord_str):
        try:
            parts = coord_str.split(",")
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            return 0.0, 0.0
    
    ordered = [valid[0]]
    remaining = valid[1:]
    
    while remaining:
        last = ordered[-1]
        last_lng, last_lat = parse_coord(last["coord"])
        
        def dist_sq(a):
            lng, lat = parse_coord(a["coord"])
            return (lng - last_lng) ** 2 + (lat - last_lat) ** 2
        
        nearest = min(remaining, key=dist_sq)
        ordered.append(nearest)
        remaining.remove(nearest)
    
    return ordered