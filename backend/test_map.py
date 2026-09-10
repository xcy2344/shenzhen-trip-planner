from app.tools.map_tool import geocode, enrich_attractions_with_coords, optimize_route_order

# 1. 测试地理编码
print("=== 测试地理编码 ===")
result = geocode("深圳湾公园")
print("深圳湾公园：", result)

# 2. 测试给景点列表补坐标
print("\n=== 测试批量补坐标 ===")
attractions = [
    {"name": "深圳湾公园", "location": "南山区"},
    {"name": "世界之窗", "location": "南山区"},
    {"name": "梧桐山", "location": "罗湖区"},
    {"name": "南头古城", "location": "南山区"},
]

enriched = enrich_attractions_with_coords(attractions)
for a in enriched:
    print(f"{a['name']}: {a.get('coord', '无坐标')} ({a.get('district', '')})")

# 3. 测试路线优化
print("\n=== 测试路线优化 ===")
ordered = optimize_route_order(enriched)
print("优化前：", [a["name"] for a in enriched])
print("优化后：", [a["name"] for a in ordered])