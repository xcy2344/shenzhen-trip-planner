def search_shenzhen_attractions(keyword: str = "") -> str:
    """搜索深圳景点（模拟数据）"""
    attractions = {
        "主题公园": "世界之窗、欢乐谷、锦绣中华",
        "自然风光": "深圳湾公园、梧桐山、大梅沙",
        "文化历史": "南头古城、大鹏所城、赤湾天后宫",
        "购物": "东门老街、万象城、海岸城"
    }
    
    if keyword:
        for category, spots in attractions.items():
            if keyword in category or keyword in spots:
                return f"{category}：{spots}"
        return f"未找到相关景点：{keyword}"
    
    result = "深圳热门景点：\n"
    for category, spots in attractions.items():
        result += f"- {category}：{spots}\n"
    return result